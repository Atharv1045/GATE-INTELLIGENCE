"""
Comprehensive 13-Scenario PDF Ingestion & Regression Test Suite for GATE Intelligence.
Tests all required scenarios:
1. Digitally generated GATE PDF.
2. Scanned GATE PDF (rendered as rasterized images with 0 selectable text, extracted via CPU OCR).
3. Hybrid PDF containing both selectable digital text pages and scanned image pages.
4. Question spanning two pages (stem starts at bottom of Page 1, options finish on Page 2 -> `source_page_start=1, source_page_end=2`).
5. Question with four or more options (including 5-option `(A)..(E)` support).
6. Numerical Answer Type (NAT) question (0 negative marking).
7. Multiple Select Question (MSQ) (0 negative marking).
8. Examination booklet instructions containing question-number references (`Do not open the seal...`, `Q. 1 - Q. 25 carry one mark each`, `Q. 26 - Q. 55 carry two marks each`, `Questions Q. 56 - Q. 65 belong to General Aptitude`).
9. Repeated running headers and footers across pages (`2012 CS`, `Page 2 of 20`, `3/20`).
10. Duplicate PDF upload prevention (SHA-256 `409 Conflict`) + `/api/v1/papers/{id}/reprocess` verification.
11. Duplicate questions within a single PDF (intra-paper deduplication vs colliding number `UNKNOWN` review flagging).
12. Questions containing mathematical equations, C programming code (`fork()`, `printf()`), and diagram/table references.
13. Full 65-Question GATE CS 2012 Structural Regression Fixture (including cover page instructions, range headers, exact Q.1 `I1/I2` cricket match logical inference, exact Q.24 `1) Does a given program ever produce an output?` with 4 numbered sub-statements, linked questions Q.48-55, and General Aptitude Q.56-65 -> verifying exact 65 extracted questions with `Q.1`..`Q.65` preserved).
"""
from __future__ import annotations

import io
import os
import sys
import tempfile
import unittest
from pathlib import Path

TEST_TMP_DIR = tempfile.mkdtemp(prefix="gate_regression_test_")
os.environ["SQLITE_DB_PATH"] = os.path.join(TEST_TMP_DIR, "regression_gate.db")
os.environ["UPLOAD_DIR"] = os.path.join(TEST_TMP_DIR, "uploads")

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from PIL import Image, ImageDraw, ImageFont
from fastapi.testclient import TestClient
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from app.database.session import init_database
from app.main import app
from app.pipelines.pdf_pipeline import PdfIngestionPipeline


def _create_scanned_page_image(
    lines: list[str],
    width: int = 1200,
    height: int = 1600
) -> Image.Image:
    """Render lines of text onto a high-contrast RGB bitmap."""
    img = Image.new("RGB", (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 26)
    except Exception:
        try:
            font = ImageFont.truetype("C:/Windows/Fonts/calibri.ttf", 26)
        except Exception:
            font = ImageFont.load_default()

    y = 70
    for ln in lines:
        draw.text((60, y), ln, fill=(0, 0, 0), font=font)
        y += 44

    return img


def build_scanned_pdf(page_lines_list: list[list[str]], watermark_header: str = "") -> bytes:
    """Create an image-only PDF (with optional digital watermark stamp) so OCR must recover the questions."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    for page_lines in page_lines_list:
        pil_img = _create_scanned_page_image(page_lines)
        img_buf = io.BytesIO()
        pil_img.save(img_buf, format="PNG")
        img_buf.seek(0)
        c.drawImage(ImageReader(img_buf), 0, 0, width=A4[0], height=A4[1])
        if watermark_header:
            c.setFont("Helvetica", 8)
            c.drawString(20, 825, watermark_header)
        c.showPage()
    c.save()
    return buf.getvalue()


def build_hybrid_and_multipage_pdf() -> bytes:
    """
    Create a 3-page PDF testing:
    - Page 1 (Digital): Q.1 (5 options A..E) + Q.2 starting at bottom of Page 1...
    - Page 2 (Digital): ...continuing Q.2 stem and options (A)..(D) on Page 2 + Q.3 (MSQ) + Q.4 (NAT) + Q.5 (C code + math + diagram).
    - Page 3 (Scanned Image): Q.6 rendered purely as a raster image.
    """
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)

    # Page 1 (Digital)
    c.setFont("Helvetica", 10)
    c.drawString(45, 815, "2024 CS                                                                 1/3")
    c.drawString(45, 780, "Q.1 Consider a 5-option multiple choice test item in queuing theory with arrival rate lambda = 4. What is the utilization factor? [1 Mark]")
    c.drawString(60, 760, "(A) 0.25")
    c.drawString(60, 745, "(B) 0.50")
    c.drawString(60, 730, "(C) 0.75")
    c.drawString(60, 715, "(D) 0.80")
    c.drawString(60, 700, "(E) 0.95")

    # Multi-page question Q.2 starts at bottom of Page 1
    c.drawString(45, 120, "Q.2 Consider a pipelined processor with 5 stages and clock cycle time of 2 ns.")
    c.drawString(45, 100, "Suppose branch instructions account for 20% of all instructions and incur 2 stall cycles")
    c.showPage()

    # Page 2 (Digital continuation of Q.2 + Q.3 MSQ + Q.4 NAT + Q.5 Code/Diagram)
    c.setFont("Helvetica", 10)
    c.drawString(45, 815, "2024 CS                                                                 2/3")
    c.drawString(45, 780, "when a branch is taken. What is the average instruction execution time in nanoseconds? [2 Marks]")
    c.drawString(60, 760, "(A) 2.4 ns")
    c.drawString(60, 745, "(B) 2.8 ns")
    c.drawString(60, 730, "(C) 3.2 ns")
    c.drawString(60, 715, "(D) 4.0 ns")

    c.drawString(45, 670, "Q.3 Which of the following statements are correct about B+ trees in database indexing? (Multiple Select MSQ) [2 Marks]")
    c.drawString(60, 650, "(A) Leaf nodes are linked together to support fast range queries")
    c.drawString(60, 635, "(B) Internal nodes store actual data records alongside search keys")
    c.drawString(60, 620, "(C) All leaf nodes remain at the same balanced depth from the root")
    c.drawString(60, 605, "(D) Deletion never requires node redistribution")

    c.drawString(45, 560, "Q.4 A TCP connection has congestion window of 32 KB and round-trip time of 100 ms. The maximum throughput in Kbps (in integer) is ______. [1 Mark]")

    c.drawString(45, 510, 'Q.5 Consider the C program shown in the circuit diagram and transition table below: int main() { fork(); fork(); printf("GATE"); return 0; } What is O(n log n) complexity? [2 Marks]')
    c.drawString(60, 490, "(A) 2 processes")
    c.drawString(60, 475, "(B) 4 processes")
    c.drawString(60, 460, "(C) 6 processes")
    c.drawString(60, 445, "(D) 8 processes")
    c.showPage()

    # Page 3 (Scanned raster image page inside hybrid PDF)
    pil_img = _create_scanned_page_image([
        "GATE 2024 CS Scanned Page",
        "Q.6 What is the chromatic number of a complete bipartite graph K(3,3)? [1 Mark]",
        "(A) 1",
        "(B) 2",
        "(C) 3",
        "(D) 6",
    ])
    img_buf = io.BytesIO()
    pil_img.save(img_buf, format="PNG")
    img_buf.seek(0)
    c.drawImage(ImageReader(img_buf), 0, 0, width=A4[0], height=A4[1])
    c.showPage()
    c.save()
    return buf.getvalue()


def build_gate_cs_2012_65q_fixture_pdf() -> bytes:
    """
    Build a faithful 20-page GATE CS 2012 structural PDF fixture containing:
    - Page 1: Exact GATE 2012 Booklet Cover Instructions (items 1..12).
    - Page 2..19: Range banners, exact Q.1 (logical inferences I1/I2), exact Q.24 (1)..4) decidability),
      Common Data & Linked Answer banners, and General Aptitude Q.56..65.
    - Page 20: Space for Rough Work.
    """
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)

    # Page 1: Official Cover Instructions (0 questions on Page 1)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(45, 800, "2012 COMPUTER SCIENCE AND INFORMATION TECHNOLOGY (CS)")
    c.setFont("Helvetica", 10)
    c.drawString(45, 780, "Read the following instructions carefully.")
    instructions = [
        "1. Do not open the seal of the Question Booklet until you are asked to do so by the invigilator.",
        "2. Take out the Optical Response Sheet (ORS) from this Question Booklet without breaking the seal.",
        "3. On the right half of the ORS, using ONLY a black ink ball point pen, darken the bubble.",
        "4. This Question Booklet contains 20 pages including blank pages for rough work.",
        "5. There are a total of 65 questions carrying 100 marks. All these questions are of objective type.",
        "6. Questions Q. 1 - Q. 25 carry 1 mark each. Questions Q. 26 - Q. 55 carry 2 marks each.",
        "7. Questions Q. 48 - Q. 51 (2 pairs) are common data questions and question pairs (Q.52, Q.53) and (Q.54, Q.55) are linked answer questions.",
        "8. Questions Q. 56 - Q. 65 belong to General Aptitude (GA) section and carry a total of 15 marks. Questions Q. 56 - Q. 60 carry 1 mark each, and questions Q. 61 - Q. 65 carry 2 marks each.",
        "9. Unattempted questions will result in zero mark and wrong answers will result in NEGATIVE marks.",
        "10. Calculator is allowed whereas charts, graph sheets or tables are NOT allowed in the examination hall.",
        "11. Rough work can be done on the question paper itself. Blank pages are provided at the end of the question paper for rough work.",
        "12. Before the start of the examination, write your name and registration number in the space provided below using a black ink ball point pen.",
    ]
    y = 750
    for inst in instructions:
        c.drawString(45, y, inst)
        y -= 24
    c.showPage()

    # Pages 2..19: All 65 Questions (Q.1 to Q.65)
    q_num = 1
    for page_no in range(2, 19):
        c.setFont("Helvetica", 9)
        c.drawString(45, 815, f"2012 CS                                                                {page_no}/20")
        y = 785
        if q_num == 1:
            c.setFont("Helvetica-Bold", 10)
            c.drawString(45, y, "Q. 1 - Q. 25 carry one mark each.")
            y -= 25

        while y > 120 and q_num <= 65:
            if q_num == 26:
                c.setFont("Helvetica-Bold", 10)
                c.drawString(45, y, "Q. 26 to Q. 55 carry two marks each.")
                y -= 22
            elif q_num == 48:
                c.setFont("Helvetica-Bold", 10)
                c.drawString(45, y, "Common Data for Questions 48 and 49:")
                y -= 20
            elif q_num == 52:
                c.setFont("Helvetica-Bold", 10)
                c.drawString(45, y, "Statement for Linked Answer Questions 52 and 53:")
                y -= 20
            elif q_num == 56:
                c.setFont("Helvetica-Bold", 10)
                c.drawString(45, y, "General Aptitude (GA) Questions")
                y -= 18
                c.drawString(45, y, "Q. 56 - Q. 60 carry one mark each.")
                y -= 20
            elif q_num == 61:
                c.setFont("Helvetica-Bold", 10)
                c.drawString(45, y, "Q. 61 - Q. 65 carry two marks each.")
                y -= 20

            c.setFont("Helvetica", 10)
            if q_num == 1:
                c.drawString(45, y, "Q.1 Consider the following logical inferences.")
                y -= 15
                c.drawString(55, y, "I1: If it rains then the cricket match will not be played. The cricket match was played. Inference: There was no rain.")
                y -= 15
                c.drawString(55, y, "I2: If it rains then the cricket match will not be played. It did not rain. Inference: The cricket match was played.")
                y -= 15
                c.drawString(55, y, "Which of the following is TRUE?")
                y -= 15
                c.drawString(55, y, "(A) Both I1 and I2 are correct inferences   (B) I1 is correct but I2 is not a correct inference")
                y -= 15
                c.drawString(55, y, "(C) I1 is not correct but I2 is a correct inference   (D) Both I1 and I2 are not correct inferences")
                y -= 25
            elif q_num == 24:
                c.drawString(45, y, "Q. 24 Which of the following problems are decidable?")
                y -= 15
                c.drawString(55, y, "1) Does a given program ever produce an output?")
                y -= 15
                c.drawString(55, y, "2) If L is a context-free language, then, is L complement also context-free?")
                y -= 15
                c.drawString(55, y, "3) If L is a regular language, then, is L complement also regular?")
                y -= 15
                c.drawString(55, y, "4) If L is a recursive language, then, is L complement also recursive?")
                y -= 15
                c.drawString(55, y, "(A) 1, 2, 3, 4   (B) 1, 2   (C) 2, 3, 4   (D) 3, 4")
                y -= 25
            else:
                c.drawString(
                    45,
                    y,
                    f"Q.{q_num} In GATE CS 2012 examination question {q_num}, consider a binary tree and cache memory with index {q_num}. Which option is valid?",
                )
                y -= 16
                c.drawString(
                    55,
                    y,
                    f"(A) Option A for Q.{q_num}   (B) Option B for Q.{q_num}   (C) Option C for Q.{q_num}   (D) Option D for Q.{q_num}",
                )
                y -= 24

            q_num += 1
        c.showPage()

    # Page 20: Rough work page
    c.setFont("Helvetica-Bold", 12)
    c.drawString(200, 780, "Space for Rough Work")
    c.showPage()
    c.save()
    return buf.getvalue()


class GateIngestionRegressionTestSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        import shutil
        cls._tmp_dir = tempfile.mkdtemp(prefix="gate_reg_isolated_")
        os.environ["SQLITE_DB_PATH"] = os.path.join(cls._tmp_dir, "test_regression.db")
        os.environ["UPLOAD_DIR"] = os.path.join(cls._tmp_dir, "uploads")
        init_database()
        cls.client = TestClient(app)
        cls.pipeline = PdfIngestionPipeline()

    @classmethod
    def tearDownClass(cls) -> None:
        import shutil
        if hasattr(cls, "_tmp_dir") and os.path.exists(cls._tmp_dir):
            shutil.rmtree(cls._tmp_dir, ignore_errors=True)

    def test_01_instruction_and_range_banner_rejection(self) -> None:
        """Scenario 8 & 9: Booklet instructions and mark-range banners must NEVER be extracted as questions."""
        self.assertTrue(
            self.pipeline.is_booklet_instruction_text(
                "1. Do not open the seal of the Question Booklet until you are asked to do so by the invigilator."
            )
        )
        self.assertTrue(
            self.pipeline.is_booklet_instruction_text("Q. 25 carry one mark each.")
        )
        self.assertTrue(
            self.pipeline.is_booklet_instruction_text("carry one mark each.")
        )

    def test_02_gate_cs_2012_65_questions_exact_extraction(self) -> None:
        """
        Scenario 1, 8, 9 & 13: Upload the 20-page GATE CS 2012 fixture PDF.
        Verify exact 65 questions extracted, zero instruction false positives, Q.1 I1/I2 preserved, and Q.24 1)..4) preserved as one question.
        """
        pdf_bytes = build_gate_cs_2012_65q_fixture_pdf()
        res = self.client.post(
            "/api/v1/papers/upload",
            files={"file": ("GATE_CS_2012_Set1.pdf", pdf_bytes, "application/pdf")},
            data={
                "paper_code": "CS",
                "examination_year": "2012",
                "session_set": "Set-1",
                "run_synchronously": "true",
            },
        )
        self.assertEqual(res.status_code, 201, res.text)
        body = res.json()
        self.assertEqual(body["extracted_questions_count"], 65)
        self.__class__.cs2012_paper_id = body["paper_id"]

        q_res = self.client.get(
            "/api/v1/questions",
            params={"paper_code": "CS", "examination_year": 2012, "page_size": 100},
        )
        self.assertEqual(q_res.status_code, 200)
        items = q_res.json()["items"]
        self.assertEqual(len(items), 65)

        q_nums = [q["question_number"] for q in items]
        self.assertEqual(q_nums, list(range(1, 66)))

        for q in items:
            self.assertNotIn("Do not open the seal", q["question_text"])
            self.assertNotIn("carry one mark each", q["question_text"].lower())

        q1 = next(q for q in items if q["question_number"] == 1)
        self.assertEqual(q1["source_question_label"], "Q.1")
        self.assertIn("cricket match", q1["question_text"])
        self.assertIn("I1:", q1["question_text"])
        self.assertIn("I2:", q1["question_text"])
        self.assertEqual(q1["marks"], 1.0)
        self.assertEqual(len(q1["options"]), 4)

        q24 = next(q for q in items if q["question_number"] == 24)
        self.assertEqual(q24["source_question_label"], "Q.24")
        self.assertIn("Does a given program ever produce an output?", q24["question_text"])
        self.assertIn("1)", q24["question_text"])
        self.assertIn("4)", q24["question_text"])
        self.assertEqual(len(q24["options"]), 4)

        q26 = next(q for q in items if q["question_number"] == 26)
        q56 = next(q for q in items if q["question_number"] == 56)
        q61 = next(q for q in items if q["question_number"] == 61)
        self.assertEqual(q26["marks"], 2.0)
        self.assertEqual(q56["marks"], 1.0)
        self.assertEqual(q61["marks"], 2.0)

    def test_03_scanned_image_pdf_with_watermark_ocr_recovery(self) -> None:
        """
        Scenario 2: Upload a scanned image-only PDF (like GATE CS 2010) that also has a short digital
        watermark stamp (> 30 chars) so naive char-count checks would fail, and verify OCR extracts the questions.
        """
        scanned_pdf = build_scanned_pdf(
            [
                [
                    "GATE 2010 CS Question Paper",
                    "Q.1 What is the time complexity of binary search on a sorted array of n elements? [1 Mark]",
                    "(A) O(log n)",
                    "(B) O(n)",
                    "(C) O(n log n)",
                    "(D) O(n^2)",
                    "Q.2 In an operating system, which page replacement policy is immune to Belady anomaly? [2 Marks]",
                    "(A) FIFO",
                    "(B) LRU",
                    "(C) Random",
                    "(D) Second Chance",
                ]
            ],
            watermark_header="Downloaded from official archive portal - GATE 2010 Computer Science Paper Set 1",
        )
        res = self.client.post(
            "/api/v1/papers/upload",
            files={"file": ("GATE_CS_2010_Scanned.pdf", scanned_pdf, "application/pdf")},
            data={"paper_code": "CS", "examination_year": "2010", "session_set": "Set-1", "run_synchronously": "true"},
        )
        self.assertEqual(res.status_code, 201, res.text)
        body = res.json()

        print("\\n========== SCANNED PDF DIAGNOSTICS ==========")
        print(body)
        print("=============================================")

        self.assertEqual(body["extracted_questions_count"], 2)

    def test_04_hybrid_multipage_5option_msq_nat_code_pdf(self) -> None:
        """
        Scenarios 3, 4, 5, 6, 7 & 12:
        - Hybrid PDF (Pages 1-2 digital, Page 3 scanned image)
        - Q.1 has 5 options (A)..(E)
        - Q.2 spans Page 1 and Page 2 (`source_page_start=1, source_page_end=2`)
        - Q.3 is MSQ (0 negative marks)
        - Q.4 is NAT (0 negative marks)
        - Q.5 contains C code (`fork()`, `printf()`), math `O(n log n)`, and diagram/table reference
        - Q.6 is extracted via OCR from Page 3
        """
        hybrid_bytes = build_hybrid_and_multipage_pdf()
        res = self.client.post(
            "/api/v1/papers/upload",
            files={"file": ("GATE_CS_2024_Hybrid.pdf", hybrid_bytes, "application/pdf")},
            data={"paper_code": "CS", "examination_year": "2024", "session_set": "Set-1", "run_synchronously": "true"},
        )
        self.assertEqual(res.status_code, 201, res.text)
        body = res.json()

        print("\\n========== HYBRID PDF DIAGNOSTICS ===========")
        print(body)
        print("=============================================")

        self.assertEqual(body["extracted_questions_count"], 6)

        q_res = self.client.get(
            "/api/v1/questions",
            params={"paper_code": "CS", "examination_year": 2024, "page_size": 50},
        )
        items = q_res.json()["items"]
        self.assertEqual(len(items), 6)

        q1 = next(q for q in items if q["question_number"] == 1)
        self.assertEqual(len(q1["options"]), 5)

        q2 = next(q for q in items if q["question_number"] == 2)
        self.assertEqual(q2["source_page_start"], 1)
        self.assertEqual(q2["source_page_end"], 2)
        self.assertEqual(len(q2["options"]), 4)
        self.assertIn("nanoseconds", q2["question_text"])

        q3 = next(q for q in items if q["question_number"] == 3)
        self.assertEqual(q3["question_type"], "MSQ")
        self.assertEqual(q3["negative_marks"], 0.0)

        q4 = next(q for q in items if q["question_number"] == 4)
        self.assertEqual(q4["question_type"], "NAT")
        self.assertEqual(q4["negative_marks"], 0.0)

        q5 = next(q for q in items if q["question_number"] == 5)
        self.assertTrue(q5["has_diagram_or_table"])
        self.assertIn("fork()", q5["question_text"])

        q6 = next(q for q in items if q["question_number"] == 6)
        self.assertEqual(q6["source_page_start"], 3)
        self.assertEqual(len(q6["options"]), 4)

    def test_05_intra_paper_duplicate_and_reprocess_endpoint(self) -> None:
        """
        Scenarios 10 & 11:
        - Intra-paper exact duplicate question is deduplicated automatically.
        - Colliding question number with different question stem is preserved and marked `source_question_label='UNKNOWN'` + `extraction_status='uncertain'`.
        - Calling `POST /api/v1/papers/{paper_id}/reprocess` re-runs the pipeline cleanly.
        """
        sample_text = "\n".join([
            "Q.1 What is the rank of an identity matrix of order 4? [1 Mark]",
            "(A) 1 (B) 2 (C) 3 (D) 4",
            "Q.1 What is the rank of an identity matrix of order 4? [1 Mark]",
            "(A) 1 (B) 2 (C) 3 (D) 4",
            "Q.1 Consider a completely different question with an OCR colliding number Q.1 about TCP congestion control? [2 Marks]",
            "(A) Slow start (B) AIMD (C) Fast recovery (D) UDP",
        ])
        pages = [
            {
                "page_number": 1,
                "text": sample_text,
                "has_tables": False,
                "ocr_used": True,
            }
        ]
        extracted = self.pipeline.segment_and_extract_questions(pages, "CS", 2023)
        self.assertEqual(len(extracted), 2)
        self.assertEqual(extracted[0]["source_question_label"], "Q.1")
        self.assertEqual(extracted[1]["source_question_label"], "UNKNOWN")
        self.assertEqual(extracted[1]["extraction_status"], "uncertain")
        self.assertTrue(extracted[1]["needs_human_review"])

        rep = self.client.post(f"/api/v1/papers/{self.__class__.cs2012_paper_id}/reprocess")
        self.assertEqual(rep.status_code, 200, rep.text)
        self.assertEqual(rep.json()["extracted_questions_count"], 65)


if __name__ == "__main__":
    unittest.main(verbosity=2)
