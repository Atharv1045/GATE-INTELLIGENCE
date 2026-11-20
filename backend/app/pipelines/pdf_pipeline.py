"""
16-Stage GATE PDF Ingestion, Multi-Signal OCR, Cross-Page Segmentation & Validation Pipeline.

Fixes all confirmed production bugs:
1. Scanned / Hybrid PDF Detection & Multi-Tier OCR:
   - Evaluates per-page text quality using printable character density, word count, image coverage,
     and question/option marker presence (not just a naive `< 30` char threshold, which fails when
     a scanned page has a digital watermark or running header).
   - Auto-discovers Windows Tesseract binary (`C:\\Program Files\\Tesseract-OCR\\tesseract.exe`, etc.),
     supports `rapidocr_onnxruntime` / `pytesseract`, and provides an automatic **Gemini Vision OCR**
     fallback (`google-genai`) when local OCR binaries are absent on Windows.
2. Booklet Cover Page, Header/Footer & Range Instruction Filtering:
   - Strips repeated running headers/footers across pages.
   - Detects and filters examination booklet instructions (`Do not open the seal of the Question Booklet...`,
     `Take out the Optical Response Sheet (ORS)...`, `Read the following instructions carefully`, etc.).
   - Parses mark-range banners (`Q. 1 - Q. 25 carry one mark each`, `Q. 26 to Q. 55 carry two marks each`,
     `Questions Q. 56 - Q. 60 carry 1 mark each`) to update the active section mark rules WITHOUT
     extracting `Q. 25 carry one mark each` as a question!
3. Context-Aware Original Question Numbering vs. Internal Sub-Items:
   - Distinguishes genuine top-level question anchors (`Q.1`, `Q. 24`, `Question 15`, or top-level
     sequential `1.`, `24.`) from internal numbered statements inside a question stem
     (such as `1) Does a given program ever produce an output? 2) If L is a context-free language...`
     inside GATE CS 2012 Q.24, or `I1:`, `I2:`, `S1:`, `S2:`).
   - Preserves `source_question_label` (`Q.24`, `Q.1`, or `UNKNOWN`) and never resets valid questions to `Q.1`.
4. Cross-Page Question & Option Continuity:
   - Concatenates cleaned pages into a unified document stream with `<<PAGE_BREAK:N>>` markers before
     question segmentation so questions or options spanning 2+ pages remain a single complete record
     with accurate `source_page_start` and `source_page_end`.
5. Deterministic Question Validation & Intra-Paper Deduplication:
   - Validates stem completeness, option sets (`(A)`..`(D)` or `(E)`), marks, negative marks, and
     assigns `extraction_status` (`valid`, `uncertain`, `rejected`) and `extraction_warnings`.
   - Deduplicates identical or overlapping extractions within the same paper while never merging
     distinct questions (including linked/common-data question pairs like Q.48 & Q.49).
"""
from __future__ import annotations

import io
import os
import re
import shutil
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import settings
from app.core.security import sanitize_untrusted_pdf_text

try:
    import fitz as _pymupdf
except ImportError:
    _pymupdf = None

try:
    import pdfplumber as _pdfplumber
except ImportError:
    _pdfplumber = None

try:
    from pypdf import PdfReader as _PdfReader
except ImportError:
    _PdfReader = None

try:
    import pypdfium2 as _pdfium
except ImportError:
    _pdfium = None

try:
    import pytesseract as _pytesseract
except ImportError:
    _pytesseract = None

try:
    from rapidocr_onnxruntime import RapidOCR as _RapidOCR
    _rapid_ocr_engine = _RapidOCR()
except Exception:
    _rapid_ocr_engine = None


# Auto-configure Windows Tesseract path if installed in standard Windows directories
if _pytesseract is not None and os.name == "nt":
    if not shutil.which("tesseract"):
        for win_candidate in [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
            os.path.expandvars(r"%LOCALAPPDATA%\Tesseract-OCR\tesseract.exe"),
        ]:
            if os.path.exists(win_candidate):
                _pytesseract.pytesseract.tesseract_cmd = win_candidate
                break


YEAR_REGEX = re.compile(r"\b(199[0-9]|20[0-2][0-9]|2030)\b")
PAPER_CODE_REGEX = re.compile(
    r"\b(AE|AG|AR|BM|BT|CE|CH|CS|CY|DA|EC|EE|ES|EY|GE|GG|IN|MA|ME|MN|MT|NM|PE|PH|PI|ST|TF|XE|XH|XL)\b"
)

# Range banner pattern, e.g. "Q. 1 – Q. 25 carry one mark each" or "Questions Q. 56 - Q. 60 carry 1 mark each"
MARK_RANGE_BANNER_REGEX = re.compile(
    r"(?:Questions?\s+)?(?:Q\.?\s*|Question\s*)?(\d{1,2})\s*(?:[-–—]|to)\s*(?:Q\.?\s*|Question\s*)?(\d{1,2})\s*"
    r"(?:of\s+Part-[A-Z0-9]+\s+.*?)?carry\s+(one|two|1|2)\s+mark(?:s)?\s+each\.?",
    re.IGNORECASE,
)

# Non-question examination booklet instructions (must NEVER be extracted as questions)
BOOKLET_INSTRUCTION_PATTERNS = [
    re.compile(r"do\s+not\s+open\s+the\s+seal\s+of\s+the\s+question\s+booklet", re.I),
    re.compile(r"until\s+you\s+are\s+asked\s+to\s+do\s+so\s+by\s+the\s+invigilator", re.I),
    re.compile(r"take\s+out\s+the\s+optical\s+response\s+sheet\s*\(?ors\)?", re.I),
    re.compile(r"read\s+the\s+following\s+instructions\s+carefully", re.I),
    re.compile(r"darken\s+the\s+bubble\s+corresponding\s+to\s+your\s+test\s+paper", re.I),
    re.compile(r"question\s+booklet\s+contains\s+\d+\s+pages\s+including\s+blank\s+pages", re.I),
    re.compile(r"there\s+are\s+a\s+total\s+of\s+65\s+questions\s+carrying\s+100\s+marks", re.I),
    re.compile(r"questions\s+must\s+be\s+answered\s+on\s+the\s+left\s+hand\s+side\s+of\s+the\s+ors", re.I),
    re.compile(r"using\s+only\s+a\s+black\s+ink\s+ball\s*point\s+pen", re.I),
    re.compile(r"unattempted\s+questions\s+will\s+result\s+in\s+zero\s+mark", re.I),
    re.compile(r"calculator\s+is\s+allowed\s+whereas\s+charts,\s+graph\s+sheets", re.I),
    re.compile(r"rough\s+work\s+can\s+be\s+done\s+on\s+the\s+question\s+(?:paper|booklet)\s+itself", re.I),
    re.compile(r"before\s+the\s+start\s+of\s+the\s+examination,\s+write\s+your\s+name", re.I),
    re.compile(r"questions?\s+q\.?\s*\d+\s*(?:[-–—]|to)\s*q\.?\s*\d+\s+belong\s+to\s+general\s+aptitude", re.I),
    re.compile(r"^(?:q\.?\s*\d+\s*)?carry\s+(?:one|two|1|2)\s+marks?\s+each\.?$", re.I),
    re.compile(r"space\s+for\s+rough\s+work", re.I),
]

# Explicit Q-prefixed question start: "Q.1", "Q. 12", "Q12.", "Question 5:"
EXPLICIT_Q_START_REGEX = re.compile(
    r"(?:^|\n)\s*(?:Q\.?\s*|Question\s*(?:No\.?\s*)?)(\d{1,3})\s*(?:[\)\.:]\s*|\s+)(?=[A-Z0-9\"'\(\[\$])",
    re.MULTILINE,
)

# Bare numbered start: "1. ", "24. " at start of line (used ONLY when paper uses bare numbering instead of Q.1)
BARE_DOT_START_REGEX = re.compile(
    r"(?:^|\n)\s*(\d{1,2})\.\s+(?=[A-Z\"'\(\[\$])",
    re.MULTILINE,
)


# Option regex supporting inline and multiline options.
# Captures continuation lines until the next option marker or end of question block.
# DOTALL allows option text to span multiple lines while preserving nested parentheses.
OPTION_REGEX = re.compile(
    r"(?:^|\n|\s)(?:\(([A-E])\)|\[([A-E])\])\s*(.*?)(?=\s+(?:\([A-E]\)|\[[A-E]\])\s*|$)",
    re.DOTALL,
)

MARKS_REGEX = re.compile(r"\[?\s*(1|2)\s*Mark(?:s)?\s*\]?", re.IGNORECASE)
MSQ_HINT_REGEX = re.compile(
    r"(one or more than one|multiple select|msq|which of the following.*are correct|more than one option)",
    re.IGNORECASE,
)
NAT_HINT_REGEX = re.compile(
    r"(rounded off to|up to \d+ decimal|in integer|numerical answer|nat|fill in the blank|___+)",
    re.IGNORECASE,
)
MATH_EXPR_REGEX = re.compile(
    r"(\$[^\$]+\$|\b[A-Za-z]\([A-Za-z0-9,\s]+\)\s*=\s*[^\n\.]+|\bO\([^\)]+\)|\b\d+\^\d+|\b(?:lim|log|sin|cos|tan|det|rank|Pr|∀|∃|⊆|⊂|∪|∩|→|⇒|⇔|¬|∧|∨|⊕|∑|∏|∫)\b[^\n\.]{0,40})"
)
DIAGRAM_TABLE_REGEX = re.compile(
    r"\b(figure|fig\.|diagram|circuit|table|graph shown|below shows|transition table|truth table)\b",
    re.IGNORECASE,
)
CODE_BLOCK_REGEX = re.compile(
    r"\b(int\s+main\s*\(|void\s+\w+\s*\(|printf\s*\(|scanf\s*\(|fork\s*\(\)|struct\s+\w+|#include\s*<|return\s+0\s*;)\b"
)

PAGE_MARKER_REGEX = re.compile(r"<<PAGE_BREAK:(\d+)>>")


class PdfIngestionPipeline:
    """
    16-Stage GATE PDF Ingestion Pipeline supporting digital, scanned, and hybrid PDFs
    across all 30 GATE disciplines with cross-page continuity and strict validation.
    """

    @staticmethod
    def evaluate_page_text_quality(text: str, image_count: int = 0) -> Tuple[bool, float, str]:
        """
        Stage 4: Evaluate per-page digital text quality beyond a simple character count.
        Returns (needs_ocr, quality_score, reason).
        """
        stripped = (text or "").strip()
        if not stripped:
            return True, 0.0, "empty_digital_text"

        char_len = len(stripped)
        words = re.findall(r"[A-Za-z]{2,}", stripped)
        word_count = len(words)
        alnum_chars = sum(1 for c in stripped if c.isalnum() or c in " .,;?!()-+=*/<>[]{}:")
        printable_ratio = alnum_chars / max(char_len, 1)

        has_q_or_opt = bool(
            re.search(r"(?:Q\.?\s*\d+|\([A-D]\)|carry\s+(?:one|two)\s+mark|instructions)", stripped, re.I)
        )

        if printable_ratio < 0.55:
            return True, round(printable_ratio, 2), "garbled_font_encoding"

        if char_len < 60 and word_count < 10:
            return True, 0.15, "insufficient_digital_tokens"

        if image_count > 0 and word_count < 35 and not has_q_or_opt:
            return True, 0.25, "watermark_only_on_scanned_page"

        if word_count < 18 and not has_q_or_opt:
            return True, 0.30, "sparse_non_question_text"

        return False, round(min(1.0, printable_ratio), 2), "digital_text_ok"

    def _ocr_single_page_image(
        self, pil_img: Any, page_number: int, extraction_errors: List[str]
    ) -> Tuple[str, str]:
        """
        Stage 5: Multi-Tier CPU & Gemini Vision OCR Fallback.
        """
        if _rapid_ocr_engine is not None:
            try:
                import numpy as np

                img_arr = np.asarray(pil_img)
                result, _ = _rapid_ocr_engine(img_arr)
                if result:
                    lines = [item[1] for item in result if len(item) >= 2 and item[1]]
                    joined = "\n".join(lines).strip()
                    if joined:
                        return joined, "rapidocr_cpu"
            except Exception as e:
                extraction_errors.append(f"Page {page_number} RapidOCR warning: {str(e)}")

        if _pytesseract is not None:
            try:
                ocr_text = _pytesseract.image_to_string(pil_img) or ""
                if ocr_text.strip():
                    return ocr_text.strip(), "tesseract_cpu"
            except Exception as tess_err:
                extraction_errors.append(f"Page {page_number} Tesseract warning: {str(tess_err)}")

        if settings.GEMINI_API_KEY:
            try:
                from google import genai

                client = genai.Client(api_key=settings.GEMINI_API_KEY)
                prompt = (
                    "Perform exact, verbatim OCR transcription of this GATE examination question paper page. "
                    "Preserve all original question numbers (such as Q.1, Q.25, Q.65), section headers, "
                    "options (A), (B), (C), (D), mathematical symbols, equations, C code blocks, and tables. "
                    "Do not summarize, solve, or invent any text."
                )
                resp = client.models.generate_content(
                    model=settings.GEMINI_MODEL,
                    contents=[pil_img, prompt],
                )
                if resp and getattr(resp, "text", None) and resp.text.strip():
                    return resp.text.strip(), f"gemini_vision_ocr:{settings.GEMINI_MODEL}"
            except Exception as gem_err:
                extraction_errors.append(f"Page {page_number} Gemini Vision OCR warning: {str(gem_err)}")

        return "", "none"

    def _render_pdf_page_to_pil(self, pdf_bytes: bytes, page_index: int) -> Optional[Any]:
        if _pdfium is not None:
            try:
                pdf_doc = _pdfium.PdfDocument(pdf_bytes)
                page_obj = pdf_doc[page_index]
                return page_obj.render(scale=2.0).to_pil()
            except Exception:
                pass
        if _pymupdf is not None:
            try:
                from PIL import Image

                doc = _pymupdf.open(stream=pdf_bytes, filetype="pdf")
                page = doc[page_index]
                pix = page.get_pixmap(dpi=180)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                doc.close()
                return img
            except Exception:
                pass
        return None

    def extract_pages_from_pdf(
        self, pdf_bytes: bytes, filename: str = "paper.pdf"
    ) -> Dict[str, Any]:
        pages_info: List[Dict[str, Any]] = []
        extraction_errors: List[str] = []

        if _pymupdf is not None:
            try:
                doc = _pymupdf.open(stream=pdf_bytes, filetype="pdf")
                for idx, page in enumerate(doc):
                    clip_rect = _pymupdf.INFINITE_RECT() if hasattr(_pymupdf, "INFINITE_RECT") else None
                    raw_text = (page.get_text("text", clip=clip_rect) if clip_rect is not None else page.get_text("text")) or ""
                    img_list = page.get_images(full=True) or []
                    pages_info.append(
                        {
                            "page_number": idx + 1,
                            "text": raw_text.strip(),
                            "image_count": len(img_list),
                            "ocr_used": False,
                            "ocr_engine": None,
                            "has_tables": False,
                        }
                    )
                doc.close()
            except Exception as e:
                extraction_errors.append(f"PyMuPDF error: {str(e)}")

        if not pages_info and _pdfplumber is not None:
            try:
                with _pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                    for idx, page in enumerate(pdf.pages):
                        raw_text = page.extract_text(layout=False) or ""
                        tables = page.extract_tables() or []
                        imgs = getattr(page, "images", []) or []
                        pages_info.append(
                            {
                                "page_number": idx + 1,
                                "text": raw_text.strip(),
                                "image_count": len(imgs),
                                "ocr_used": False,
                                "ocr_engine": None,
                                "has_tables": len(tables) > 0,
                            }
                        )
            except Exception as e:
                extraction_errors.append(f"pdfplumber error: {str(e)}")

        if not pages_info and _PdfReader is not None:
            try:
                reader = _PdfReader(io.BytesIO(pdf_bytes))
                for idx, page in enumerate(reader.pages):
                    raw_text = page.extract_text() or ""
                    imgs = getattr(page, "images", []) or []
                    pages_info.append(
                        {
                            "page_number": idx + 1,
                            "text": raw_text.strip(),
                            "image_count": len(imgs),
                            "ocr_used": False,
                            "ocr_engine": None,
                            "has_tables": False,
                        }
                    )
            except Exception as e:
                extraction_errors.append(f"pypdf error: {str(e)}")

        scanned_pages_count = 0
        ocr_recovered_pages = 0

        for p in pages_info:
            needs_ocr, quality_score, reason = self.evaluate_page_text_quality(
                p["text"], p.get("image_count", 0)
            )
            p["text_quality_score"] = quality_score
            p["quality_reason"] = reason

            if needs_ocr:
                scanned_pages_count += 1
                if settings.ENABLE_OCR_FALLBACK:
                    pil_img = self._render_pdf_page_to_pil(pdf_bytes, p["page_number"] - 1)
                    if pil_img is not None:
                        ocr_text, engine_name = self._ocr_single_page_image(
                            pil_img, p["page_number"], extraction_errors
                        )
                        if ocr_text:
                            p["text"] = ocr_text
                            p["ocr_used"] = True
                            p["ocr_engine"] = engine_name
                            ocr_recovered_pages += 1
                        else:
                            extraction_errors.append(
                                f"Page {p['page_number']} requires OCR ({reason}), but no OCR engine succeeded."
                            )

        is_scanned_doc = bool(pages_info and scanned_pages_count >= max(1, len(pages_info) // 2))

        header_sample = f"{filename} " + " ".join(p["text"][:1000] for p in pages_info[:3])
        detected_year = 2026
        ym = YEAR_REGEX.search(header_sample)
        if ym:
            detected_year = int(ym.group(1))

        detected_code = "CS"
        cm = PAPER_CODE_REGEX.search(header_sample.upper())
        if cm:
            detected_code = cm.group(1).upper()

        return {
            "page_count": len(pages_info),
            "is_scanned": is_scanned_doc,
            "scanned_pages_count": scanned_pages_count,
            "ocr_recovered_pages": ocr_recovered_pages,
            "detected_year": detected_year,
            "detected_paper_code": detected_code,
            "pages": pages_info,
            "extraction_errors": extraction_errors,
        }

    @staticmethod
    def is_booklet_instruction_text(text: str) -> bool:
        cleaned = re.sub(r"\s+", " ", (text or "").strip())
        if not cleaned:
            return True
        if MARK_RANGE_BANNER_REGEX.search(cleaned):
            return True
        for pat in BOOKLET_INSTRUCTION_PATTERNS:
            if pat.search(cleaned):
                return True
        return False

    @staticmethod
    def is_cover_instruction_page(page_text: str, page_number: int) -> bool:
        if page_number > 2:
            return False
        hits = sum(1 for pat in BOOKLET_INSTRUCTION_PATTERNS if pat.search(page_text or ""))
        has_explicit_q1 = bool(re.search(r"(?:^|\n)\s*Q\.?\s*1\b(?!\s*[-–—]\s*Q|\s+to\s+Q)", page_text or ""))
        return hits >= 2 and not has_explicit_q1

    def _clean_pages_and_build_stream(
        self, pages: List[Dict[str, Any]]
    ) -> Tuple[str, List[Tuple[int, int, int]], Dict[int, float], Dict[int, Dict[str, bool]]]:
        line_counts: Counter[str] = Counter()
        for p in pages:
            lines = [ln.strip() for ln in (p.get("text") or "").splitlines() if ln.strip()]
            edges = lines[:2] + (lines[-2:] if len(lines) > 2 else [])
            for ln in set(edges):
                norm_ln = re.sub(r"\b\d+\s*/\s*\d+\b|\bPage\s+\d+\b", "<PG>", ln, flags=re.I)
                if len(norm_ln) < 90 and not EXPLICIT_Q_START_REGEX.match(ln):
                    line_counts[norm_ln] += 1

        repeated_headers = {ln for ln, cnt in line_counts.items() if cnt >= 3 and len(pages) >= 3}

        marks_by_qnum: Dict[int, float] = {}
        page_flags: Dict[int, Dict[str, bool]] = {}
        stream_parts: List[str] = []
        char_page_spans: List[Tuple[int, int, int]] = []
        cursor = 0

        for p in pages:
            p_num = int(p.get("page_number", 1))
            raw_page_text, inj_flag = sanitize_untrusted_pdf_text(p.get("text") or "")
            page_flags[p_num] = {
                "has_tables": bool(p.get("has_tables", False)),
                "ocr_used": bool(p.get("ocr_used", False)),
                "injection_flag": inj_flag,
            }

            if not raw_page_text.strip():
                continue

            if self.is_cover_instruction_page(raw_page_text, p_num):
                continue

            for m_banner in MARK_RANGE_BANNER_REGEX.finditer(raw_page_text):
                start_q = int(m_banner.group(1))
                end_q = int(m_banner.group(2))
                m_word = m_banner.group(3).lower()
                m_val = 1.0 if m_word in ("1", "one") else 2.0
                for qn in range(min(start_q, end_q), max(start_q, end_q) + 1):
                    marks_by_qnum[qn] = m_val

            cleaned_page = MARK_RANGE_BANNER_REGEX.sub("\n", raw_page_text)

            kept_lines: List[str] = []
            for ln in cleaned_page.splitlines():
                s_ln = ln.strip()
                if not s_ln:
                    kept_lines.append("")
                    continue
                norm_ln = re.sub(r"\b\d+\s*/\s*\d+\b|\bPage\s+\d+\b", "<PG>", s_ln, flags=re.I)
                if norm_ln in repeated_headers:
                    continue
                if re.fullmatch(r"(?:Page\s+\d+(?:\s+of\s+\d+)?|\d{1,2}\s*/\s*\d{1,2}|(?:19|20)\d{2}\s+[A-Z]{2}.*|[A-Z]{2}\s+\d{1,2}/\d{1,2}|GATE\s+(?:19|20)\d{2}\s+[A-Z]{2}\s*[-–—]\s*Page\s+\d+.*)", s_ln, re.I):
                    continue
                if self.is_booklet_instruction_text(s_ln) and not EXPLICIT_Q_START_REGEX.match(s_ln):
                    continue
                kept_lines.append(ln)

            page_body = "\n".join(kept_lines).strip()
            if not page_body:
                continue

            marker = f"\n<<PAGE_BREAK:{p_num}>>\n"
            chunk = marker + page_body + "\n"
            start_pos = cursor
            stream_parts.append(chunk)
            cursor += len(chunk)
            char_page_spans.append((start_pos, cursor, p_num))

        full_stream = "".join(stream_parts)
        return full_stream, char_page_spans, marks_by_qnum, page_flags

    @staticmethod
    def _page_for_offset(offset: int, spans: List[Tuple[int, int, int]]) -> int:
        for s_pos, e_pos, p_num in spans:
            if s_pos <= offset < e_pos:
                return p_num
        return spans[-1][2] if spans else 1

    def _find_question_anchors(self, full_stream: str) -> List[Tuple[int, int, int, str]]:
        explicit_matches = list(EXPLICIT_Q_START_REGEX.finditer(full_stream))
        anchors: List[Tuple[int, int, int, str]] = []

        if len(explicit_matches) >= 1:
            for m in explicit_matches:
                line_prefix_start = full_stream.rfind("\n", 0, m.start()) + 1
                prefix_str = full_stream[line_prefix_start:m.start()].strip()
                if re.search(r"(?:[-–—]|to|and|questions?)\s*$", prefix_str, re.I):
                    continue
                q_num = int(m.group(1))
                if 1 <= q_num <= 100:
                    anchors.append((m.start(), m.end(), q_num, f"Q.{q_num}"))
            return anchors

        bare_matches = list(BARE_DOT_START_REGEX.finditer(full_stream))
        for m in bare_matches:
            q_num = int(m.group(1))
            if not (1 <= q_num <= 100):
                continue
            if anchors:
                prev_end = anchors[-1][1]
                prev_qnum = anchors[-1][2]
                intervening = full_stream[prev_end:m.start()]
                has_options_between = len(OPTION_REGEX.findall(intervening)) >= 2
                has_nat_between = bool(NAT_HINT_REGEX.search(intervening))
                if not has_options_between and not has_nat_between and q_num != prev_qnum + 1:
                    continue
                if not has_options_between and not has_nat_between and q_num <= 4 and prev_qnum > 4:
                    continue
            anchors.append((m.start(), m.end(), q_num, f"Q.{q_num}"))

        return anchors

    def segment_and_extract_questions(
        self,
        pages: List[Dict[str, Any]],
        paper_code: str,
        examination_year: int,
    ) -> List[Dict[str, Any]]:
        (
            full_stream,
            char_page_spans,
            marks_by_qnum,
            page_flags,
        ) = self._clean_pages_and_build_stream(pages)

        if not full_stream.strip():
            return []

        anchors = self._find_question_anchors(full_stream)
        if not anchors:
            return []

        extracted_candidates: List[Dict[str, Any]] = []
        seen_qnums: Dict[int, int] = {}
        seen_norm_stems: set[str] = set()

        for i, (m_start, m_end, q_num, src_label) in enumerate(anchors):
            block_end = anchors[i + 1][0] if i + 1 < len(anchors) else len(full_stream)
            raw_block = full_stream[m_end:block_end].strip()
            if not raw_block:
                continue

            page_start = self._page_for_offset(m_start, char_page_spans)
            inner_pages = [int(pm.group(1)) for pm in PAGE_MARKER_REGEX.finditer(raw_block)]
            page_end = max([page_start] + inner_pages)

            clean_block = PAGE_MARKER_REGEX.sub("\n", raw_block).strip()
            clean_block = re.sub(
                r"\n\s*(?:Common\s+Data\s+for\s+Questions?|Statement\s+for\s+Linked\s+Answer\s+Questions?|General\s+Aptitude\s*\(GA\)\s*Questions?)[^\n]*$",
                "",
                clean_block,
                flags=re.I,
            ).strip()

            has_table = any(
                page_flags.get(p, {}).get("has_tables", False)
                for p in range(page_start, page_end + 1)
            )
            ocr_used = any(
                page_flags.get(p, {}).get("ocr_used", False)
                for p in range(page_start, page_end + 1)
            )
            inj_flag = any(
                page_flags.get(p, {}).get("injection_flag", False)
                for p in range(page_start, page_end + 1)
            )

            q_dict = self._parse_and_validate_question_block(
                q_num=q_num,
                source_label=src_label,
                block=clean_block,
                page_start=page_start,
                page_end=page_end,
                paper_code=paper_code,
                examination_year=examination_year,
                banner_marks=marks_by_qnum.get(q_num),
                has_table_on_page=has_table,
                ocr_used=ocr_used,
                injection_flag=inj_flag,
            )

            if q_dict["extraction_status"] == "rejected":
                continue

            norm_stem = re.sub(r"\s+", " ", q_dict["question_text"].lower()).strip()
            if len(norm_stem) > 20 and norm_stem in seen_norm_stems:
                continue

            if q_num in seen_qnums:
                prev_idx = seen_qnums[q_num]
                prev_q = extracted_candidates[prev_idx]
                prev_norm = re.sub(r"\s+", " ", prev_q["question_text"].lower()).strip()
                if prev_norm == norm_stem or prev_norm in norm_stem or norm_stem in prev_norm:
                    if q_dict["extraction_confidence"] > prev_q["extraction_confidence"]:
                        extracted_candidates[prev_idx] = q_dict
                        seen_norm_stems.add(norm_stem)
                    continue
                else:
                    q_dict["source_question_label"] = "UNKNOWN"
                    q_dict["extraction_status"] = "uncertain"
                    q_dict["needs_human_review"] = True
                    q_dict["extraction_warnings"].append(
                        f"Duplicate question number Q.{q_num} detected in paper; marked UNKNOWN for human review."
                    )
            else:
                seen_qnums[q_num] = len(extracted_candidates)

            if len(norm_stem) > 20:
                seen_norm_stems.add(norm_stem)
            extracted_candidates.append(q_dict)

        return extracted_candidates

    def _parse_and_validate_question_block(
        self,
        q_num: int,
        source_label: str,
        block: str,
        page_start: int,
        page_end: int,
        paper_code: str,
        examination_year: int,
        banner_marks: Optional[float],
        has_table_on_page: bool,
        ocr_used: bool,
        injection_flag: bool,
    ) -> Dict[str, Any]:
        warnings: List[str] = []

        if self.is_booklet_instruction_text(block):
            return {
                "question_number": q_num,
                "source_question_label": source_label,
                "question_text": block,
                "extraction_status": "rejected",
                "extraction_warnings": ["Rejected examination booklet instruction."],
            }

        mm = MARKS_REGEX.search(block)
        if mm:
            marks = float(mm.group(1))
        elif banner_marks is not None:
            marks = float(banner_marks)
        elif int(examination_year) <= 2013:
            marks = 1.0 if (1 <= q_num <= 25 or 56 <= q_num <= 60) else 2.0
        else:
            marks = 2.0 if ((6 <= q_num <= 10) or (q_num >= 36)) else 1.0

        options: List[Dict[str, Any]] = []
        stem_text = block

        # Cohesive option-sequence boundary detection:
        # Prevents parenthesized tokens inside question stems (e.g. matrices (A) and (B))
        # from prematurely truncating the stem while strictly preserving multiline option continuation,
        # nested mathematical expressions (e.g. O((V + E) log V)), and 4/5-option sets.
        marker_pattern = re.compile(
            r"(?:(?<=\n)|(?<=\A)|(?<=[ \t]))(?:\(([A-E])\)|\[([A-E])\])(?=[ \t\n\r]|$)"
        )
        candidate_markers = []
        for m in marker_pattern.finditer(block):
            lbl = (m.group(1) or m.group(2)).upper()
            is_line_start = (
                m.start() == 0
                or block[m.start() - 1] == "\n"
                or (not block[: m.start()].strip() or block[: m.start()].rstrip(" \t").endswith("\n"))
            )
            candidate_markers.append({
                "label": lbl,
                "start": m.start(),
                "end": m.end(),
                "is_line_start": is_line_start,
            })

        target_sequences = [
            ["A", "B", "C", "D", "E"],
            ["A", "B", "C", "D"],
            ["A", "B", "C"],
            ["A", "B"],
        ]

        best_sequence: Optional[Tuple[List[str], List[Dict[str, Any]]]] = None
        for seq in target_sequences:
            last_candidates = [m for m in candidate_markers if m["label"] == seq[-1]]
            if not last_candidates:
                continue

            for cand_last in reversed(last_candidates):
                current_pos = cand_last["start"]
                chosen = [cand_last]
                valid = True
                for expected_lbl in reversed(seq[:-1]):
                    prev_cands = [
                        m for m in candidate_markers
                        if m["label"] == expected_lbl and m["start"] < current_pos
                    ]
                    if not prev_cands:
                        valid = False
                        break
                    chosen_prev = prev_cands[-1]
                    chosen.append(chosen_prev)
                    current_pos = chosen_prev["start"]

                if valid:
                    chosen.reverse()
                    stem_candidate = block[: chosen[0]["start"]].strip()
                    # A 2-option sequence (A, B) requires line-start or non-NAT context
                    # to avoid matching inline mathematical pairs in question stems.
                    if len(seq) == 2:
                        if not chosen[0]["is_line_start"] and (
                            NAT_HINT_REGEX.search(block)
                            or re.search(r"\b(?:and|or|of|order|with)\s+\(?B\)?", block[: chosen[1]["end"]], re.I)
                        ):
                            continue
                    if stem_candidate:
                        best_sequence = (seq, chosen)
                        break
            if best_sequence:
                break

        if best_sequence:
            seq, chosen_markers = best_sequence
            first_opt_pos = chosen_markers[0]["start"]
            stem_text = block[:first_opt_pos].strip()
            seen_labels: set[str] = set()
            for i in range(len(chosen_markers)):
                m = chosen_markers[i]
                lbl = m["label"]
                content_start = m["end"]
                content_end = (
                    chosen_markers[i + 1]["start"]
                    if i + 1 < len(chosen_markers)
                    else len(block)
                )
                raw_text = block[content_start:content_end]
                clean_text = re.sub(r"\s+", " ", raw_text).strip()
                if lbl and lbl not in seen_labels:
                    seen_labels.add(lbl)
                    options.append(
                        {"option_label": lbl, "option_text": clean_text, "is_correct": None}
                    )
        else:
            # Fallback to OPTION_REGEX if no cohesive sequence was found
            opt_matches = list(OPTION_REGEX.finditer(block))
            if opt_matches:
                first_opt_pos = opt_matches[0].start()
                stem_candidate = block[:first_opt_pos].strip()
                if stem_candidate:
                    stem_text = stem_candidate
                    seen_labels = set()
                    for om in opt_matches:
                        lbl = (om.group(1) or om.group(2) or "").upper()
                        txt = re.sub(r"\s+", " ", om.group(3)).strip()
                        if lbl and lbl not in seen_labels and txt:
                            seen_labels.add(lbl)
                            options.append(
                                {"option_label": lbl, "option_text": txt, "is_correct": None}
                            )

        stem_text = MARKS_REGEX.sub("", stem_text).strip()
        stem_lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in stem_text.splitlines() if ln.strip()]
        stem_text = "\n".join(stem_lines)

        if self.is_booklet_instruction_text(stem_text) and len(options) == 0:
            return {
                "question_number": q_num,
                "source_question_label": source_label,
                "question_text": stem_text,
                "extraction_status": "rejected",
                "extraction_warnings": ["Rejected non-question instruction line."],
            }

        if len(options) >= 2:
            if MSQ_HINT_REGEX.search(stem_text):
                q_type = "MSQ"
            else:
                q_type = "MCQ"
        else:
            q_type = "NAT"

        neg_marks = round(marks / 3.0, 6) if q_type == "MCQ" else 0.0

        math_exprs = [m.group(0).strip() for m in MATH_EXPR_REGEX.finditer(block)]
        has_code = bool(CODE_BLOCK_REGEX.search(block))
        has_diag = has_table_on_page or bool(DIAGRAM_TABLE_REGEX.search(block))

        confidence = 0.94
        needs_review = False

        if ocr_used:
            confidence -= 0.10
            warnings.append("Extracted via OCR; verify mathematical symbols and subscripts.")

        if page_end > page_start:
            warnings.append(f"Question spans pages {page_start} to {page_end}.")

        if q_type in ("MCQ", "MSQ") and len(options) < 4:
            confidence -= 0.25
            needs_review = True
            warnings.append(f"Only {len(options)} option(s) extracted for {q_type}; expected 4.")

        if q_type == "NAT" and not NAT_HINT_REGEX.search(block) and "?" not in stem_text and len(stem_text) < 45:
            confidence -= 0.30
            needs_review = True
            warnings.append("Candidate has no options and no explicit NAT prompt; verify if diagram-based MCQ.")

        if len(stem_text) < 15:
            confidence -= 0.35
            needs_review = True
            warnings.append("Question stem is unusually short (< 15 chars).")

        if has_diag and len(stem_text) < 60:
            needs_review = True
            warnings.append("Question references a figure/diagram/table on page; verify visual context.")

        if injection_flag:
            confidence -= 0.30
            needs_review = True
            warnings.append("Untrusted instruction pattern sanitized from PDF text.")

        if len(options) == 0 and len(stem_text) < 25 and "?" not in stem_text and not NAT_HINT_REGEX.search(stem_text):
            return {
                "question_number": q_num,
                "source_question_label": source_label,
                "question_text": stem_text,
                "extraction_status": "rejected",
                "extraction_warnings": ["Rejected short fragment without options or question prompt."],
            }

        final_conf = round(max(0.1, min(1.0, confidence)), 2)
        status_val = "uncertain" if (needs_review or final_conf < 0.75) else "valid"

        return {
            "question_number": q_num,
            "source_question_label": source_label,
            "paper_code": paper_code.upper(),
            "examination_year": int(examination_year),
            "question_type": q_type,
            "question_text": stem_text,
            "options": options,
            "marks": marks,
            "negative_marks": neg_marks,
            "page_number": page_start,
            "source_page_start": page_start,
            "source_page_end": page_end,
            "math_expressions": math_exprs[:12],
            "has_diagram_or_table": has_diag or has_code,
            "extraction_status": status_val,
            "extraction_warnings": warnings,
            "extraction_confidence": final_conf,
            "needs_human_review": needs_review,
        }
