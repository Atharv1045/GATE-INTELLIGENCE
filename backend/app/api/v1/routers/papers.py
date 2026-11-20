"""
Paper Library Router (/api/v1/papers).
Provides:
- Paper catalog browsing organized by year and discipline
- Accurate question counts and verified answer-key statistics
- Sequential paper question list preview and practice launch
- PDF question-paper upload and ingestion pipeline
- OCR fallback for scanned papers
- Duplicate-paper detection
- Answer-key upload and association
- Editable question review confirmation with transaction safety and pre-import backup
"""
from __future__ import annotations

import csv
import hashlib
import inspect
import io
import json
import os
import re
import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel

from app.core.config import settings
from app.database.session import get_db_connection, new_uuid, utcnow_iso
from app.pipelines.pdf_pipeline import PdfIngestionPipeline

REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from exam.gate.taxonomy_loader import GateTaxonomyLoader

router = APIRouter(tags=["papers"])


class QuestionReviewOption(BaseModel):
    option_label: str
    option_text: str
    is_correct: Optional[bool] = None


class QuestionReviewItem(BaseModel):
    id: Optional[str] = None
    question_number: int
    source_question_label: Optional[str] = None
    question_type: str = "MCQ"
    question_text: str
    marks: float = 1.0
    negative_marks: Optional[float] = None
    subject_name: Optional[str] = None
    primary_topic_name: Optional[str] = None
    subtopic_name: Optional[str] = None
    difficulty_level: Optional[str] = "Medium"
    options: Optional[List[Dict[str, Any]]] = None
    correct_options: Optional[List[str]] = None
    numerical_min: Optional[float] = None
    numerical_max: Optional[float] = None
    explanation: Optional[str] = None
    provenance: Optional[str] = "unverified"
    source_page_start: Optional[int] = 1
    source_page_end: Optional[int] = 1
    math_expressions: Optional[List[str]] = None
    has_diagram_or_table: Optional[bool] = False
    extraction_status: Optional[str] = "valid"
    extraction_warnings: Optional[List[str]] = None


class ConfirmPaperImportRequest(BaseModel):
    paper_code: str = "CS"
    examination_year: int
    session_set: str = "Set-1"
    paper_title: Optional[str] = None
    file_checksum: Optional[str] = None
    file_path: Optional[str] = None
    page_count: int = 0
    is_scanned: bool = False
    overwrite_if_exists: bool = True
    questions: List[QuestionReviewItem]


def parse_answer_key_data(
    key_bytes: Optional[bytes] = None,
    key_text: Optional[str] = None,
) -> Dict[int, Dict[str, Any]]:
    """
    Parses answer keys from JSON, CSV, or formatted plaintext.
    Returns {question_number: {correct_options: [...], numerical_min: ..., numerical_max: ..., explanation: ...}}
    """
    raw_str = ""
    if key_bytes:
        try:
            raw_str = key_bytes.decode("utf-8")
        except Exception:
            try:
                raw_str = key_bytes.decode("latin-1")
            except Exception:
                raw_str = ""
    elif key_text:
        raw_str = key_text

    raw_str = raw_str.strip()
    if not raw_str:
        return {}

    mapping: Dict[int, Dict[str, Any]] = {}

    # 1. Try JSON parsing
    if raw_str.startswith("{") or raw_str.startswith("["):
        try:
            data = json.loads(raw_str)
            if isinstance(data, list):
                for item in data:
                    qn = int(item.get("question_number") or item.get("q") or 0)
                    if qn > 0:
                        opts = item.get("correct_options") or item.get("answer") or []
                        if isinstance(opts, str):
                            opts = [o.strip().upper() for o in opts.split(",") if o.strip()]
                        mapping[qn] = {
                            "correct_options": opts,
                            "numerical_min": item.get("numerical_min"),
                            "numerical_max": item.get("numerical_max"),
                            "explanation": item.get("explanation"),
                            "provenance": item.get("provenance", "uploaded_key"),
                        }
                return mapping
            elif isinstance(data, dict):
                for k, v in data.items():
                    if str(k).isdigit():
                        qn = int(k)
                        if isinstance(v, list):
                            mapping[qn] = {"correct_options": [str(x).upper() for x in v], "provenance": "uploaded_key"}
                        elif isinstance(v, dict):
                            opts = v.get("correct_options") or v.get("answer") or []
                            if isinstance(opts, str):
                                opts = [o.strip().upper() for o in opts.split(",") if o.strip()]
                            mapping[qn] = {
                                "correct_options": opts,
                                "numerical_min": v.get("numerical_min"),
                                "numerical_max": v.get("numerical_max"),
                                "explanation": v.get("explanation"),
                                "provenance": "uploaded_key",
                            }
                        elif isinstance(v, (int, float)):
                            mapping[qn] = {"numerical_min": float(v), "numerical_max": float(v), "provenance": "uploaded_key"}
                        elif isinstance(v, str):
                            opts = [o.strip().upper() for o in v.split(",") if o.strip()]
                            mapping[qn] = {"correct_options": opts, "provenance": "uploaded_key"}
                return mapping
        except Exception:
            pass

    # 2. Try CSV parsing
    if "," in raw_str and "\n" in raw_str:
        try:
            reader = csv.reader(io.StringIO(raw_str))
            for row in reader:
                if not row or len(row) < 2:
                    continue
                first = row[0].strip().replace("Q.", "").replace("Q", "").strip()
                if first.isdigit():
                    qn = int(first)
                    ans = row[1].strip().upper()
                    expl = row[2].strip() if len(row) > 2 else None
                    if re.match(r"^[A-D](\s*,\s*[A-D])*$", ans):
                        opts = [o.strip() for o in ans.split(",") if o.strip()]
                        mapping[qn] = {"correct_options": opts, "explanation": expl, "provenance": "uploaded_key"}
                    elif re.match(r"^-?\d+(?:\.\d+)?$", ans):
                        val = float(ans)
                        mapping[qn] = {"numerical_min": val, "numerical_max": val, "explanation": expl, "provenance": "uploaded_key"}
            if mapping:
                return mapping
        except Exception:
            pass

    # 3. Plaintext line-by-line regex parsing (e.g. "Q.1: B", "1. A", "2: 42.5", "3: A, D")
    for line in raw_str.splitlines():
        line = line.strip()
        if not line:
            continue
        m = re.match(r"^(?:Q\.?\s*)?(\d{1,2})\s*[:\.\-\)]\s*([A-Za-z0-9,\.\s\-–]+)", line, re.I)
        if m:
            qn = int(m.group(1))
            ans_raw = m.group(2).strip().upper()
            if re.match(r"^[A-D](\s*,\s*[A-D])*$", ans_raw):
                opts = [o.strip() for o in ans_raw.split(",") if o.strip()]
                mapping[qn] = {"correct_options": opts, "provenance": "uploaded_key"}
            elif re.match(r"^-?\d+(?:\.\d+)?$", ans_raw):
                val = float(ans_raw)
                mapping[qn] = {"numerical_min": val, "numerical_max": val, "provenance": "uploaded_key"}
            elif re.search(r"(-?\d+(?:\.\d+)?)\s*(?:to|[-–])\s*(-?\d+(?:\.\d+)?)", ans_raw):
                m_rng = re.search(r"(-?\d+(?:\.\d+)?)\s*(?:to|[-–])\s*(-?\d+(?:\.\d+)?)", ans_raw)
                if m_rng:
                    mapping[qn] = {
                        "numerical_min": float(m_rng.group(1)),
                        "numerical_max": float(m_rng.group(2)),
                        "provenance": "uploaded_key",
                    }

    return mapping


def classify_question_taxonomy(
    q_text: str, q_num: int, paper_code: str, syllabus: Optional[Dict[str, Any]] = None
) -> Tuple[str, str]:
    """Classifies syllabus subject and topic based on question text and question numbering."""
    # Questions 56-65 in modern GATE (or 51-60 in older papers) are General Aptitude
    if q_num >= 56:
        is_verbal = bool(
            re.search(
                r"\b(word|sentence|grammar|passage|vocabulary|meaning|antonym|synonym|spelled|blank|analogy)\b",
                q_text,
                re.I,
            )
        )
        return "General Aptitude", "Verbal Aptitude" if is_verbal else "Quantitative Aptitude"

    text_lower = q_text.lower()
    best_subject = None
    best_topic = None
    max_hits = 0

    if syllabus and isinstance(syllabus, dict):
        for s in syllabus.get("subjects", []):
            s_name = s.get("name", "")
            if s_name == "General Aptitude" and q_num < 56:
                continue
            for t in s.get("topics", []):
                t_name = t.get("name", "")
                hits = 0
                if t_name.lower() in text_lower:
                    hits += 3
                for kw in t.get("keywords", []):
                    if kw.lower() in text_lower:
                        hits += 1
                for sub in t.get("subtopics", []):
                    if sub.lower() in text_lower:
                        hits += 1
                if hits > max_hits:
                    max_hits = hits
                    best_subject = s_name
                    best_topic = t_name

    if best_subject and max_hits >= 1:
        return best_subject, best_topic or "Core Concepts"

    if paper_code.upper() == "CS":
        cs_rules = [
            (r"\b(eigenvalue|matrix|determinant|vector space|rank)\b", "Engineering Mathematics", "Linear Algebra"),
            (r"\b(probability|random variable|bayes|binomial|poisson|variance|expectation)\b", "Engineering Mathematics", "Probability and Statistics"),
            (r"\b(limit|integral|differential|calculus|maxima|minima)\b", "Engineering Mathematics", "Calculus"),
            (r"\b(relation|poset|lattice|group|proposition|predicate|tautology|combinatorics|generating function)\b", "Engineering Mathematics", "Discrete Mathematics"),
            (r"\b(regular expression|dfa|nfa|finite automata|regular language)\b", "Theory of Computation", "Regular Languages and Finite Automata"),
            (r"\b(context-free|cfg|pda|pushdown automata|ambiguous grammar)\b", "Theory of Computation", "Context-Free Languages and Pushdown Automata"),
            (r"\b(turing machine|decidable|undecidable|halting problem|recursively enumerable)\b", "Theory of Computation", "Turing Machines and Undecidability"),
            (r"\b(lr\(|ll\(|parse|parsing|parser|syntax analysis|lexer|syntax-directed)\b", "Compiler Design", "Lexical Analysis and Parsing"),
            (r"\b(pipeline|instruction|hazard|branch prediction|cache|tlb|memory hierarchy|addressing mode)\b", "Computer Organization and Architecture", "Instruction Pipelining"),
            (r"\b(page fault|paging|virtual memory|deadlock|semaphore|process|thread|scheduling|fcfs|round robin)\b", "Operating System", "Memory Management and File Systems"),
            (r"\b(sql|relational algebra|bcnf|3nf|functional dependency|acid|transaction|serializability|b\+ tree)\b", "Databases", "ER Model, Relational Algebra and SQL"),
            (r"\b(tcp|udp|ip address|subnet|routing|crc|sliding window|ethernet|congestion)\b", "Computer Networks", "Transport and Application Layers"),
            (r"\b(boolean|k-map|multiplexer|decoder|flip-flop|counter|sop|pos)\b", "Digital Logic", "Boolean Algebra and Minimization"),
            (r"\b(graph|dijkstra|spanning tree|bfs|dfs|shortest path|asymptotic|recurrence|dynamic programming|greedy)\b", "Algorithms", "Graph Algorithms"),
            (r"\b(pointer|array|linked list|stack|queue|binary search tree|heap|struct|recursion)\b", "Programming and Data Structures", "Programming in C"),
        ]
        for pattern, s_name, t_name in cs_rules:
            if re.search(pattern, text_lower):
                return s_name, t_name

    defaults = {
        "CS": ("Programming and Data Structures", "General Programming"),
        "DA": ("Machine Learning", "Core ML"),
        "EC": ("Signals and Systems", "Core Concepts"),
        "EE": ("Electrical Machines", "Core Concepts"),
        "ME": ("Thermodynamics", "Core Concepts"),
        "CE": ("Structural Engineering", "Core Concepts"),
    }
    return defaults.get(paper_code.upper(), ("Core Engineering", "Core Concepts"))


@router.get("/papers")
def list_papers(
    paper_code: str = Query("CS", description="Discipline code"),
    examination_year: Optional[int] = Query(None, description="Exam year filter"),
) -> Dict[str, Any]:
    paper_code = paper_code if isinstance(paper_code, str) else "CS"
    examination_year = examination_year if isinstance(examination_year, int) else None
    conn = get_db_connection()
    try:
        where_clauses = ["qp.paper_code = ?"]
        params: List[Any] = [paper_code]

        if examination_year is not None:
            where_clauses.append("qp.examination_year = ?")
            params.append(examination_year)

        where_sql = " AND ".join(where_clauses)

        sql = f"""
            SELECT qp.*
            FROM question_papers qp
            WHERE {where_sql}
            ORDER BY qp.examination_year DESC, qp.session_set ASC
        """
        rows = conn.execute(sql, tuple(params)).fetchall()

        papers = []
        for r in rows:
            p_id = r["id"]
            p_year = r["examination_year"]

            # Real question count from questions table
            q_stats = conn.execute(
                """
                SELECT
                    COUNT(id) as q_count,
                    SUM(marks) as total_marks,
                    SUM(CASE WHEN question_type = 'MCQ' THEN 1 ELSE 0 END) as mcq_count,
                    SUM(CASE WHEN question_type = 'MSQ' THEN 1 ELSE 0 END) as msq_count,
                    SUM(CASE WHEN question_type = 'NAT' THEN 1 ELSE 0 END) as nat_count
                FROM questions
                WHERE question_paper_id = ? OR (examination_year = ? AND paper_code = ?)
                """,
                (p_id, p_year, paper_code),
            ).fetchone()

            real_count = q_stats["q_count"] or 0
            total_marks = q_stats["total_marks"] or 0.0

            # Verified keys count
            v_keys = 0
            if real_count > 0:
                v_keys = conn.execute(
                    """
                    SELECT COUNT(ak.id)
                    FROM answer_keys ak
                    JOIN questions q ON ak.question_id = q.id
                    WHERE (q.question_paper_id = ? OR (q.examination_year = ? AND q.paper_code = ?))
                      AND (ak.correct_options_json != '[]' OR ak.numerical_min IS NOT NULL)
                    """,
                    (p_id, p_year, paper_code),
                ).fetchone()[0]

            is_ready = real_count > 0
            papers.append({
                "id": p_id,
                "paper_code": r["paper_code"],
                "examination_year": p_year,
                "session_set": r["session_set"],
                "title": r["title"] or f"GATE {paper_code} {p_year} ({r['session_set']})",
                "question_count": real_count,
                "total_marks": total_marks,
                "verified_keys_count": v_keys,
                "mcq_count": q_stats["mcq_count"] or 0,
                "msq_count": q_stats["msq_count"] or 0,
                "nat_count": q_stats["nat_count"] or 0,
                "status": "ready" if is_ready else "unextracted",
                "is_available": is_ready,
                "answer_key_status": f"{v_keys}/{real_count} verified" if real_count > 0 else "N/A",
            })

        return {
            "paper_code": paper_code,
            "total": len(papers),
            "papers": papers,
        }
    finally:
        conn.close()


@router.get("/papers/{paper_id}")
def get_paper_details(paper_id: str) -> Dict[str, Any]:
    conn = get_db_connection()
    try:
        qp = conn.execute("SELECT * FROM question_papers WHERE id = ?", (paper_id,)).fetchone()
        if not qp:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paper not found")

        p_year = qp["examination_year"]
        p_code = qp["paper_code"]

        questions = conn.execute(
            """
            SELECT id, question_number, question_type, marks, negative_marks, subject_name, primary_topic_name
            FROM questions
            WHERE question_paper_id = ? OR (examination_year = ? AND paper_code = ?)
            ORDER BY question_number ASC
            """,
            (paper_id, p_year, p_code),
        ).fetchall()

        q_list = [dict(q) for q in questions]

        return {
            "id": qp["id"],
            "paper_code": p_code,
            "examination_year": p_year,
            "session_set": qp["session_set"],
            "title": qp["title"],
            "total_questions": len(q_list),
            "questions": q_list,
        }
    finally:
        conn.close()


@router.get("/papers/{paper_id}/questions")
def get_paper_questions(paper_id: str) -> Dict[str, Any]:
    conn = get_db_connection()
    try:
        qp = conn.execute("SELECT * FROM question_papers WHERE id = ?", (paper_id,)).fetchone()
        if not qp:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paper not found")

        p_year = qp["examination_year"]
        p_code = qp["paper_code"]

        rows = conn.execute(
            """
            SELECT q.*, ak.correct_options_json, ak.numerical_min, ak.numerical_max, ak.provenance, ak.explanation
            FROM questions q
            LEFT JOIN answer_keys ak ON ak.question_id = q.id
            WHERE q.question_paper_id = ? OR (q.examination_year = ? AND q.paper_code = ?)
            ORDER BY q.question_number ASC
            """,
            (paper_id, p_year, p_code),
        ).fetchall()

        q_ids = [r["id"] for r in rows]
        options_by_qid: Dict[str, List[Dict[str, Any]]] = {}
        assets_by_qid: Dict[str, List[Dict[str, Any]]] = {}

        if q_ids:
            placeholders = ",".join(["?"] * len(q_ids))
            opt_rows = conn.execute(
                f"SELECT * FROM question_options WHERE question_id IN ({placeholders}) ORDER BY option_label ASC",
                tuple(q_ids),
            ).fetchall()
            for opt in opt_rows:
                options_by_qid.setdefault(opt["question_id"], []).append({
                    "id": opt["id"],
                    "option_label": opt["option_label"],
                    "option_text": opt["option_text"],
                    "is_correct": opt["is_correct"],
                })

            asset_rows = conn.execute(
                f"SELECT * FROM question_visual_assets WHERE question_id IN ({placeholders})",
                tuple(q_ids),
            ).fetchall()
            for asset in asset_rows:
                assets_by_qid.setdefault(asset["question_id"], []).append({
                    "id": asset["id"],
                    "asset_role": asset["asset_role"],
                    "asset_type": asset["asset_type"],
                    "option_label": asset["option_label"],
                    "relative_path": asset["relative_path"],
                })

        questions = []
        for r in rows:
            qid = r["id"]
            correct_opts = []
            if r["correct_options_json"]:
                try:
                    correct_opts = json.loads(r["correct_options_json"])
                except Exception:
                    correct_opts = []

            questions.append({
                "id": qid,
                "question_number": r["question_number"],
                "source_question_label": r["source_question_label"],
                "question_type": r["question_type"],
                "question_text": r["question_text"],
                "marks": r["marks"],
                "negative_marks": r["negative_marks"],
                "subject_name": r["subject_name"],
                "primary_topic_name": r["primary_topic_name"],
                "subtopic_name": r["subtopic_name"],
                "difficulty_level": r["difficulty_level"],
                "options": options_by_qid.get(qid, []),
                "visual_assets": assets_by_qid.get(qid, []),
                "answer_key": {
                    "is_verified": bool(correct_opts) or (r["numerical_min"] is not None),
                    "correct_options": correct_opts,
                    "numerical_min": r["numerical_min"],
                    "numerical_max": r["numerical_max"],
                    "provenance": r["provenance"],
                    "explanation": r["explanation"],
                },
            })

        return {
            "paper_id": paper_id,
            "paper_title": qp["title"],
            "total_questions": len(questions),
            "questions": questions,
        }
    finally:
        conn.close()


@router.post("/papers/upload-pdf")
def upload_pdf_paper(
    file: UploadFile = File(..., description="PDF question paper file"),
    paper_code: str = Form("CS"),
    examination_year: int = Form(2012),
    session_set: str = Form("Set-1"),
    title: Optional[str] = Form(None),
    answer_key_file: Optional[UploadFile] = File(None),
    answer_key_text: Optional[str] = Form(None),
    enable_ocr: bool = Form(False),
) -> Dict[str, Any]:
    """
    Ingests and stages a GATE question paper PDF:
    1. Computes SHA-256 and detects duplicate papers.
    2. Runs 16-stage extraction with OCR fallback.
    3. Segments questions, options, formulas, and marks.
    4. Auto-classifies subjects and topics from syllabus.
    5. Associates provided answer keys (JSON, CSV, or plaintext).
    6. Returns staged preview data for human review before database commitment.
    """
    # 1. Read PDF bytes safely (supporting FastAPI UploadFile, bytes, or file paths)
    if hasattr(file, "file") and hasattr(file.file, "read"):
        content = file.file.read()
    elif hasattr(file, "read"):
        content = file.read()
    elif isinstance(file, bytes):
        content = file
    elif isinstance(file, str) and os.path.exists(file):
        with open(file, "rb") as f:
            content = f.read()
    else:
        raise HTTPException(status_code=400, detail="Invalid file provided.")

    filename = getattr(file, "filename", "paper.pdf") or "paper.pdf"

    # Sanitize Form inputs
    paper_code = str(paper_code).upper() if isinstance(paper_code, str) else "CS"
    try:
        examination_year = int(examination_year)
    except Exception:
        examination_year = 2012
    session_set = str(session_set) if isinstance(session_set, str) else "Set-1"
    title_str = str(title) if isinstance(title, str) else f"GATE {paper_code} {examination_year} ({session_set})"
    enable_ocr = bool(enable_ocr) if isinstance(enable_ocr, bool) else (str(enable_ocr).lower() in ("true", "1"))

    file_checksum = hashlib.sha256(content).hexdigest()

    # 2. Check for duplicate paper
    conn = get_db_connection()
    try:
        existing = conn.execute(
            """
            SELECT id, title, paper_code, examination_year, session_set, file_checksum
            FROM question_papers
            WHERE file_checksum = ? OR (paper_code = ? AND examination_year = ? AND session_set = ?)
            """,
            (file_checksum, paper_code, examination_year, session_set),
        ).fetchone()

        is_duplicate = False
        duplicate_reason = ""
        existing_paper_id = None
        existing_q_count = 0

        if existing:
            existing_paper_id = existing["id"]
            existing_q_count = conn.execute(
                "SELECT COUNT(*) FROM questions WHERE question_paper_id = ?",
                (existing_paper_id,),
            ).fetchone()[0]

            if existing_q_count > 0:
                is_duplicate = True
                if existing["file_checksum"] == file_checksum:
                    duplicate_reason = (
                        f"Paper with identical file checksum already registered: '{existing['title']}' "
                        f"({existing['paper_code']} {existing['examination_year']} {existing['session_set']}) "
                        f"with {existing_q_count} questions."
                    )
                else:
                    duplicate_reason = (
                        f"Paper for {paper_code} {examination_year} ({session_set}) already exists "
                        f"with {existing_q_count} questions. Importing with overwrite enabled will replace it."
                    )
            else:
                is_duplicate = False
                duplicate_reason = ""
    finally:
        conn.close()

    # 3. Save uploaded file to storage/uploads/papers/
    upload_dir = Path("storage/uploads/papers")
    try:
        upload_dir.mkdir(parents=True, exist_ok=True)
        saved_file_path = upload_dir / f"{paper_code}_{examination_year}_{session_set}_{file_checksum[:8]}.pdf"
        saved_file_path.write_bytes(content)
        saved_path_str = str(saved_file_path).replace("\\", "/")
    except Exception:
        saved_path_str = f"storage/uploads/{filename}"

    # 4. Extract pages & segment questions
    pipeline = PdfIngestionPipeline()
    extracted_res = pipeline.extract_pages_from_pdf(content, filename=filename)
    pages = extracted_res.get("pages", [])
    raw_questions = pipeline.segment_and_extract_questions(
        pages, paper_code=paper_code, examination_year=examination_year
    )

    # 5. Parse answer key if provided
    answer_keys_map: Dict[int, Dict[str, Any]] = {}
    if answer_key_file:
        if hasattr(answer_key_file, "file") and hasattr(answer_key_file.file, "read"):
            ak_bytes = answer_key_file.file.read()
        elif hasattr(answer_key_file, "read"):
            ak_bytes = answer_key_file.read()
        elif isinstance(answer_key_file, bytes):
            ak_bytes = answer_key_file
        else:
            ak_bytes = b""
        answer_keys_map = parse_answer_key_data(key_bytes=ak_bytes)
    elif answer_key_text and isinstance(answer_key_text, str) and answer_key_text.strip():
        answer_keys_map = parse_answer_key_data(key_text=answer_key_text)

    # 6. Load syllabus for taxonomy classification
    loader = GateTaxonomyLoader(settings.EXAM_GATE_DIR)
    try:
        syllabus = loader.load_syllabus(paper_code)
    except Exception:
        syllabus = {}

    review_questions: List[Dict[str, Any]] = []
    keys_attached = 0

    for idx, q in enumerate(raw_questions):
        q_num = q.get("question_number", idx + 1)
        stem = q.get("question_text", "")
        subj, topic = classify_question_taxonomy(stem, q_num, paper_code, syllabus)

        ak_info = answer_keys_map.get(q_num)
        corr_opts = []
        num_min = None
        num_max = None
        explanation = None
        provenance = "unverified"

        if ak_info:
            corr_opts = ak_info.get("correct_options") or []
            num_min = ak_info.get("numerical_min")
            num_max = ak_info.get("numerical_max")
            explanation = ak_info.get("explanation")
            provenance = ak_info.get("provenance", "uploaded_key")
            keys_attached += 1

        opts = []
        for opt in q.get("options", []):
            lbl = opt.get("option_label", "")
            is_c = (lbl in corr_opts) if corr_opts else opt.get("is_correct")
            opts.append({
                "option_label": lbl,
                "option_text": opt.get("option_text", ""),
                "is_correct": bool(is_c) if is_c is not None else None,
            })

        review_item = {
            "id": str(uuid.uuid4()),
            "question_number": q_num,
            "source_question_label": q.get("source_question_label") or f"Q.{q_num}",
            "question_type": q.get("question_type", "MCQ"),
            "question_text": stem,
            "marks": q.get("marks", 1.0),
            "negative_marks": q.get("negative_marks", round(q.get("marks", 1.0) / 3.0, 6) if q.get("question_type") == "MCQ" else 0.0),
            "subject_name": subj,
            "primary_topic_name": topic,
            "subtopic_name": None,
            "difficulty_level": "Medium",
            "options": opts,
            "correct_options": corr_opts,
            "numerical_min": num_min,
            "numerical_max": num_max,
            "explanation": explanation,
            "provenance": provenance,
            "source_page_start": q.get("source_page_start", 1),
            "source_page_end": q.get("source_page_end", 1),
            "math_expressions": q.get("math_expressions", []),
            "has_diagram_or_table": q.get("has_diagram_or_table", False),
            "extraction_status": q.get("extraction_status", "valid"),
            "extraction_warnings": q.get("extraction_warnings", []),
        }
        review_questions.append(review_item)

    return {
        "staging_id": str(uuid.uuid4()),
        "is_duplicate": is_duplicate,
        "duplicate_reason": duplicate_reason,
        "existing_paper_id": existing_paper_id,
        "existing_question_count": existing_q_count,
        "paper_metadata": {
            "paper_code": paper_code,
            "examination_year": examination_year,
            "session_set": session_set,
            "title": title_str,
            "filename": filename,
            "file_path": saved_path_str,
            "file_checksum": file_checksum,
            "page_count": extracted_res.get("page_count", len(pages)),
            "is_scanned": extracted_res.get("is_scanned", False),
            "scanned_pages_count": extracted_res.get("scanned_pages_count", 0),
            "ocr_recovered_pages": extracted_res.get("ocr_recovered_pages", 0),
        },
        "extracted_page_count": len(pages),
        "total_questions": len(review_questions),
        "answer_keys_attached": keys_attached,
        "ocr_used": extracted_res.get("ocr_recovered_pages", 0) > 0,
        "questions": review_questions,
    }


@router.post("/papers/confirm-import")
def confirm_paper_import(payload: ConfirmPaperImportRequest) -> Dict[str, Any]:
    """
    Commits staged questions to the database inside an atomic transaction:
    1. Creates a pre-import database backup.
    2. Upserts question_papers record.
    3. If overwrite_if_exists is True, cascades old questions cleanly.
    4. Inserts reviewed questions, options, and answer keys.
    5. Returns audit summary.
    """
    # 1. Pre-import backup
    now_ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_path = f"storage/backups/gate_intelligence_backup_pre_import_{now_ts}.db"
    try:
        os.makedirs("storage/backups", exist_ok=True)
        shutil.copy2(str(settings.SQLITE_DB_PATH), backup_path)
    except Exception:
        backup_path = f"scratch/backup_pre_import_{now_ts}.db"
        try:
            shutil.copy2(str(settings.SQLITE_DB_PATH), backup_path)
        except Exception:
            backup_path = "N/A"

    conn = get_db_connection()
    try:
        # Check gate_papers entry
        gate_paper = conn.execute(
            "SELECT id FROM gate_papers WHERE code = ?", (payload.paper_code,)
        ).fetchone()
        gate_paper_id = gate_paper["id"] if gate_paper else None
        if not gate_paper_id:
            gate_paper_id = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO gate_papers (id, code, name, category, created_at, updated_at)
                VALUES (?, ?, ?, 'Engineering', ?, ?)
                """,
                (gate_paper_id, payload.paper_code, f"{payload.paper_code} Discipline", utcnow_iso(), utcnow_iso()),
            )

        existing = conn.execute(
            """
            SELECT id FROM question_papers
            WHERE file_checksum = ? OR (paper_code = ? AND examination_year = ? AND session_set = ?)
            """,
            (payload.file_checksum, payload.paper_code, payload.examination_year, payload.session_set),
        ).fetchone()

        if existing and not payload.overwrite_if_exists:
            raise HTTPException(
                status_code=409,
                detail=f"Paper for {payload.paper_code} {payload.examination_year} ({payload.session_set}) already exists.",
            )

        with conn:
            if existing:
                paper_id = existing["id"]
                q_rows = conn.execute("SELECT id FROM questions WHERE question_paper_id = ?", (paper_id,)).fetchall()
                if q_rows:
                    q_ids = [r["id"] for r in q_rows]
                    placeholders = ",".join(["?"] * len(q_ids))
                    conn.execute(f"DELETE FROM question_options WHERE question_id IN ({placeholders})", tuple(q_ids))
                    conn.execute(f"DELETE FROM answer_keys WHERE question_id IN ({placeholders})", tuple(q_ids))
                    conn.execute(f"DELETE FROM question_visual_assets WHERE question_id IN ({placeholders})", tuple(q_ids))
                    conn.execute(f"DELETE FROM test_questions WHERE question_id IN ({placeholders})", tuple(q_ids))
                    conn.execute(f"DELETE FROM student_responses WHERE question_id IN ({placeholders})", tuple(q_ids))
                    conn.execute(f"DELETE FROM question_topics WHERE question_id IN ({placeholders})", tuple(q_ids))
                    conn.execute(f"DELETE FROM questions WHERE question_paper_id = ?", (paper_id,))

                conn.execute(
                    """
                    UPDATE question_papers
                    SET title = ?, filename = ?, file_path = ?, file_checksum = ?, page_count = ?,
                        is_scanned = ?, processing_status = 'processed', total_extracted_questions = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        payload.paper_title or f"GATE {payload.paper_code} {payload.examination_year} ({payload.session_set})",
                        os.path.basename(payload.file_path or f"{payload.examination_year}_{payload.paper_code}.pdf"),
                        payload.file_path or f"storage/uploads/papers/{payload.examination_year}_{payload.paper_code}.pdf",
                        payload.file_checksum or new_uuid(),
                        payload.page_count,
                        1 if payload.is_scanned else 0,
                        len(payload.questions),
                        utcnow_iso(),
                        paper_id,
                    ),
                )
            else:
                paper_id = str(uuid.uuid4())
                conn.execute(
                    """
                    INSERT INTO question_papers (
                        id, uploaded_by, paper_id, paper_code, examination_year, session_set, title,
                        filename, file_path, file_checksum, page_count, is_scanned, processing_status,
                        total_extracted_questions, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'processed', ?, ?, ?)
                    """,
                    (
                        paper_id,
                        None,
                        gate_paper_id,
                        payload.paper_code,
                        payload.examination_year,
                        payload.session_set,
                        payload.paper_title or f"GATE {payload.paper_code} {payload.examination_year} ({payload.session_set})",
                        os.path.basename(payload.file_path or f"{payload.examination_year}_{payload.paper_code}.pdf"),
                        payload.file_path or f"storage/uploads/papers/{payload.examination_year}_{payload.paper_code}.pdf",
                        payload.file_checksum or new_uuid(),
                        payload.page_count,
                        1 if payload.is_scanned else 0,
                        len(payload.questions),
                        utcnow_iso(),
                        utcnow_iso(),
                    ),
                )

            inserted_count = 0
            verified_keys_count = 0
            total_marks = 0.0

            for q in payload.questions:
                q_id = q.id if q.id and len(q.id) > 10 else str(uuid.uuid4())
                q_type = (q.question_type or "MCQ").upper()
                q_marks = float(q.marks or 1.0)
                total_marks += q_marks
                q_neg = (
                    float(q.negative_marks)
                    if q.negative_marks is not None
                    else (round(q_marks / 3.0, 6) if q_type == "MCQ" else 0.0)
                )

                conn.execute(
                    """
                    INSERT INTO questions (
                        id, question_paper_id, paper_code, examination_year, question_number, source_question_label,
                        question_type, question_text, marks, negative_marks, page_number, source_page_start,
                        source_page_end, subject_name, primary_topic_name, subtopic_name, difficulty_level,
                        syllabus_version_tag, extraction_status, extraction_warnings, extraction_confidence,
                        needs_human_review, is_verified, is_ai_generated, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '2026.1', ?, ?, 1.0, 0, 1, 0, ?, ?)
                    """,
                    (
                        q_id,
                        paper_id,
                        payload.paper_code,
                        payload.examination_year,
                        q.question_number,
                        q.source_question_label or f"Q.{q.question_number}",
                        q_type,
                        q.question_text,
                        q_marks,
                        q_neg,
                        q.source_page_start or 1,
                        q.source_page_start or 1,
                        q.source_page_end or 1,
                        q.subject_name or "General Aptitude",
                        q.primary_topic_name or "Core Concepts",
                        q.subtopic_name,
                        q.difficulty_level or "Medium",
                        q.extraction_status or "valid",
                        json.dumps(q.extraction_warnings or []),
                        utcnow_iso(),
                        utcnow_iso(),
                    ),
                )
                inserted_count += 1

                corr_labels = set(q.correct_options or [])
                for opt in (q.options or []):
                    opt_id = str(uuid.uuid4())
                    opt_lbl = opt.get("option_label", "") if isinstance(opt, dict) else getattr(opt, "option_label", "")
                    opt_txt = opt.get("option_text", "") if isinstance(opt, dict) else getattr(opt, "option_text", "")
                    is_c = 1 if (opt_lbl in corr_labels or (isinstance(opt, dict) and opt.get("is_correct"))) else 0
                    conn.execute(
                        """
                        INSERT INTO question_options (id, question_id, option_label, option_text, is_correct, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (opt_id, q_id, opt_lbl, opt_txt, is_c, utcnow_iso(), utcnow_iso()),
                    )

                has_key = bool(corr_labels) or (q.numerical_min is not None)
                if has_key:
                    ak_id = str(uuid.uuid4())
                    conn.execute(
                        """
                        INSERT INTO answer_keys (
                            id, question_id, answer_type, correct_options_json, numerical_min, numerical_max,
                            tolerance, provenance, explanation, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, 0.01, ?, ?, ?, ?)
                        """,
                        (
                            ak_id,
                            q_id,
                            q_type,
                            json.dumps(list(corr_labels)),
                            q.numerical_min,
                            q.numerical_max,
                            q.provenance or "uploaded_key",
                            q.explanation,
                            utcnow_iso(),
                            utcnow_iso(),
                        ),
                    )
                    verified_keys_count += 1

            conn.execute("UPDATE question_papers SET total_extracted_questions = ? WHERE id = ?", (inserted_count, paper_id))

        return {
            "success": True,
            "message": f"Successfully imported GATE {payload.paper_code} {payload.examination_year} ({payload.session_set}) with {inserted_count} questions.",
            "paper_id": paper_id,
            "questions_imported": inserted_count,
            "total_marks": total_marks,
            "verified_keys_count": verified_keys_count,
            "backup_path": backup_path,
        }
    finally:
        conn.close()
