"""
Question Bank Router (/api/v1/questions).
Provides:
- Multi-filter question browsing (subject, topic, year, session, type, marks)
- Full-text question search
- Question detail with options and visual assets
- Interactive answer checking with official GATE negative-marking rules
- Practice attempt tracking into student_responses
- Asset image serving
- Taxonomy (papers, subjects, topics)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.core.config import settings
from app.database.session import get_db_connection, new_uuid, utcnow_iso

router = APIRouter(tags=["questions"])


class AnswerCheckRequest(BaseModel):
    selected_options: Optional[List[str]] = None
    numerical_answer: Optional[float] = None
    time_spent_seconds: Optional[int] = 0


@router.get("/questions")
def list_questions(
    paper_code: str = Query("CS", description="Discipline code, e.g. CS"),
    examination_year: Optional[int] = Query(None, description="Exam year"),
    subject_name: Optional[str] = Query(None, description="Syllabus subject name"),
    topic_name: Optional[str] = Query(None, description="Topic name"),
    question_type: Optional[str] = Query(None, description="MCQ, MSQ, or NAT"),
    marks: Optional[float] = Query(None, description="1.0 or 2.0"),
    q: Optional[str] = Query(None, description="Text search query"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
) -> Dict[str, Any]:
    paper_code = paper_code if isinstance(paper_code, str) else "CS"
    examination_year = examination_year if isinstance(examination_year, int) else None
    subject_name = subject_name if isinstance(subject_name, str) and subject_name.strip() else None
    topic_name = topic_name if isinstance(topic_name, str) and topic_name.strip() else None
    question_type = question_type if isinstance(question_type, str) and question_type.strip() else None
    marks = float(marks) if isinstance(marks, (int, float)) else None
    q = q if isinstance(q, str) and q.strip() else None
    page = int(page) if isinstance(page, int) and page >= 1 else 1
    page_size = int(page_size) if isinstance(page_size, int) and 1 <= page_size <= 100 else 20

    conn = get_db_connection()
    try:
        where_clauses = ["q.paper_code = ?"]
        params: List[Any] = [paper_code]

        if examination_year is not None:
            where_clauses.append("q.examination_year = ?")
            params.append(examination_year)
        if subject_name:
            where_clauses.append("q.subject_name = ?")
            params.append(subject_name)
        if topic_name:
            where_clauses.append("q.primary_topic_name = ?")
            params.append(topic_name)
        if question_type:
            where_clauses.append("q.question_type = ?")
            params.append(question_type.upper())
        if marks is not None:
            where_clauses.append("q.marks = ?")
            params.append(marks)
        if q and q.strip():
            where_clauses.append("(q.question_text LIKE ? OR q.primary_topic_name LIKE ? OR q.subject_name LIKE ?)")
            term = f"%{q.strip()}%"
            params.extend([term, term, term])

        where_sql = " AND ".join(where_clauses)

        # Count total
        count_sql = f"SELECT COUNT(*) FROM questions q WHERE {where_sql}"
        total = conn.execute(count_sql, tuple(params)).fetchone()[0]

        # Fetch questions
        offset = (page - 1) * page_size
        fetch_sql = f"""
            SELECT q.*, ak.correct_options_json, ak.numerical_min, ak.numerical_max, ak.tolerance,
                   ak.provenance, ak.explanation
            FROM questions q
            LEFT JOIN answer_keys ak ON ak.question_id = q.id
            WHERE {where_sql}
            ORDER BY q.examination_year DESC, q.question_number ASC
            LIMIT ? OFFSET ?
        """
        fetch_params = params + [page_size, offset]
        rows = conn.execute(fetch_sql, tuple(fetch_params)).fetchall()

        # Batch load options and visual assets for loaded questions
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
                qid = opt["question_id"]
                options_by_qid.setdefault(qid, []).append({
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
                qid = asset["question_id"]
                assets_by_qid.setdefault(qid, []).append({
                    "id": asset["id"],
                    "asset_role": asset["asset_role"],
                    "asset_type": asset["asset_type"],
                    "option_label": asset["option_label"],
                    "relative_path": asset["relative_path"],
                })

        items = []
        for r in rows:
            qid = r["id"]
            correct_opts = []
            if r["correct_options_json"]:
                try:
                    correct_opts = json.loads(r["correct_options_json"])
                except Exception:
                    correct_opts = []

            items.append({
                "id": qid,
                "question_paper_id": r["question_paper_id"],
                "paper_code": r["paper_code"],
                "examination_year": r["examination_year"],
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
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": items,
        }
    finally:
        conn.close()


@router.get("/questions/search")
def search_questions(
    q: str = Query(..., min_length=1, description="Search term"),
    paper_code: str = Query("CS", description="Discipline code"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> Dict[str, Any]:
    return list_questions(paper_code=paper_code, q=q, page=page, page_size=page_size)


@router.get("/questions/{question_id}")
def get_question_details(question_id: str) -> Dict[str, Any]:
    conn = get_db_connection()
    try:
        q = conn.execute("SELECT * FROM questions WHERE id = ?", (question_id,)).fetchone()
        if not q:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")

        opts = conn.execute(
            "SELECT * FROM question_options WHERE question_id = ? ORDER BY option_label ASC",
            (question_id,),
        ).fetchall()
        options = [
            {
                "id": o["id"],
                "option_label": o["option_label"],
                "option_text": o["option_text"],
                "is_correct": o["is_correct"],
            }
            for o in opts
        ]

        assets = conn.execute(
            "SELECT * FROM question_visual_assets WHERE question_id = ?", (question_id,)
        ).fetchall()
        visual_assets = [
            {
                "id": a["id"],
                "asset_role": a["asset_role"],
                "asset_type": a["asset_type"],
                "option_label": a["option_label"],
                "relative_path": a["relative_path"],
            }
            for a in assets
        ]

        ak = conn.execute("SELECT * FROM answer_keys WHERE question_id = ?", (question_id,)).fetchone()
        correct_opts = []
        if ak and ak["correct_options_json"]:
            try:
                correct_opts = json.loads(ak["correct_options_json"])
            except Exception:
                correct_opts = []

        return {
            "id": q["id"],
            "question_paper_id": q["question_paper_id"],
            "paper_code": q["paper_code"],
            "examination_year": q["examination_year"],
            "question_number": q["question_number"],
            "source_question_label": q["source_question_label"],
            "question_type": q["question_type"],
            "question_text": q["question_text"],
            "marks": q["marks"],
            "negative_marks": q["negative_marks"],
            "subject_name": q["subject_name"],
            "primary_topic_name": q["primary_topic_name"],
            "subtopic_name": q["subtopic_name"],
            "difficulty_level": q["difficulty_level"],
            "options": options,
            "visual_assets": visual_assets,
            "answer_key": {
                "is_verified": bool(correct_opts) or (ak and ak["numerical_min"] is not None),
                "correct_options": correct_opts,
                "numerical_min": ak["numerical_min"] if ak else None,
                "numerical_max": ak["numerical_max"] if ak else None,
                "provenance": ak["provenance"] if ak else "unverified",
                "explanation": ak["explanation"] if ak else None,
            },
        }
    finally:
        conn.close()


@router.post("/questions/{question_id}/check")
def check_question_answer(question_id: str, payload: AnswerCheckRequest) -> Dict[str, Any]:
    """Authoritative answer checking for interactive Question Bank practice."""
    conn = get_db_connection()
    try:
        q = conn.execute("SELECT * FROM questions WHERE id = ?", (question_id,)).fetchone()
        if not q:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")

        ak = conn.execute("SELECT * FROM answer_keys WHERE question_id = ?", (question_id,)).fetchone()
        q_type = (q["question_type"] or "MCQ").upper()
        marks = float(q["marks"] or 1.0)
        neg_marks = float(q["negative_marks"] if q["negative_marks"] is not None else (marks / 3.0))

        correct_options: List[str] = []
        if ak and ak["correct_options_json"]:
            try:
                correct_options = json.loads(ak["correct_options_json"])
            except Exception:
                correct_options = []

        is_verified = bool(correct_options) or (ak and ak["numerical_min"] is not None)
        provenance = ak["provenance"] if ak else "unverified"
        explanation = ak["explanation"] if ak else None

        if not is_verified:
            return {
                "question_id": question_id,
                "status": "unverified",
                "is_correct": None,
                "marks_awarded": 0.0,
                "message": "Official answer key is not yet verified for this question. It has not been marked right or wrong.",
                "official_options": [],
                "explanation": explanation or "Official solution is currently unavailable.",
                "provenance": provenance,
            }

        is_correct: bool = False
        marks_awarded: float = 0.0

        if q_type == "MCQ":
            selected = [s.strip().upper() for s in (payload.selected_options or [])]
            expected = [e.strip().upper() for e in correct_options]
            # Check if selected set matches
            if selected and set(selected) == set(expected):
                is_correct = True
                marks_awarded = marks
            elif selected:
                is_correct = False
                marks_awarded = -neg_marks
            else:
                # Unattempted
                is_correct = False
                marks_awarded = 0.0

        elif q_type == "MSQ":
            selected = [s.strip().upper() for s in (payload.selected_options or [])]
            expected = [e.strip().upper() for e in correct_options]
            # Exact match only; NO negative marks
            if selected and set(selected) == set(expected):
                is_correct = True
                marks_awarded = marks
            else:
                is_correct = False
                marks_awarded = 0.0

        elif q_type == "NAT":
            ans_val = payload.numerical_answer
            if ans_val is not None:
                n_min = ak["numerical_min"] if ak and ak["numerical_min"] is not None else None
                n_max = ak["numerical_max"] if ak and ak["numerical_max"] is not None else None
                tol = ak["tolerance"] if ak and ak["tolerance"] is not None else 0.01

                if n_min is not None and n_max is not None:
                    is_correct = (n_min <= ans_val <= n_max)
                elif n_min is not None:
                    is_correct = abs(ans_val - n_min) <= tol
                else:
                    is_correct = False

                marks_awarded = marks if is_correct else 0.0  # NAT has NO negative marks
            else:
                is_correct = False
                marks_awarded = 0.0

        # Persist student response for practice attempt tracking
        now = utcnow_iso()
        # Find or create a default practice mock_test session record
        practice_test = conn.execute("SELECT id FROM mock_tests WHERE test_mode = 'practice' LIMIT 1").fetchone()
        if not practice_test:
            p_id = new_uuid()
            conn.execute(
                """
                INSERT INTO mock_tests (id, title, paper_code, test_mode, duration_minutes, total_questions, total_marks, created_at, updated_at)
                VALUES (?, 'Daily Practice Session', ?, 'practice', 180, 0, 0.0, ?, ?)
                """,
                (p_id, q["paper_code"], now, now),
            )
            practice_test_id = p_id
        else:
            practice_test_id = practice_test["id"]

        resp_id = new_uuid()
        conn.execute(
            """
            INSERT INTO student_responses (
                id, mock_test_id, question_id, selected_options_json, numerical_answer,
                marked_for_review, time_spent_seconds, is_correct, marks_awarded, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?)
            """,
            (
                resp_id,
                practice_test_id,
                question_id,
                json.dumps(payload.selected_options or []),
                payload.numerical_answer,
                payload.time_spent_seconds or 0,
                1 if is_correct else 0,
                marks_awarded,
                now,
                now,
            ),
        )
        conn.commit()

        return {
            "question_id": question_id,
            "status": "evaluated",
            "is_correct": is_correct,
            "marks_awarded": round(marks_awarded, 4),
            "correct_options": correct_options,
            "numerical_range": [ak["numerical_min"], ak["numerical_max"]] if ak and ak["numerical_min"] is not None else None,
            "explanation": explanation or "Official answer verified. Step-by-step written derivation pending.",
            "provenance": provenance,
        }
    finally:
        conn.close()


@router.get("/questions/{question_id}/assets")
def get_question_assets(question_id: str) -> Dict[str, Any]:
    conn = get_db_connection()
    try:
        assets = conn.execute(
            "SELECT * FROM question_visual_assets WHERE question_id = ?", (question_id,)
        ).fetchall()
        return {"question_id": question_id, "visual_assets": [dict(a) for a in assets]}
    finally:
        conn.close()


@router.get("/assets/{asset_id}/image")
def get_asset_image(asset_id: str) -> FileResponse:
    conn = get_db_connection()
    try:
        asset = conn.execute(
            "SELECT * FROM question_visual_assets WHERE id = ?", (asset_id,)
        ).fetchone()
        if not asset:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Visual asset not found")

        rel_path = asset["relative_path"]
        cleaned_rel = rel_path.replace("visual_assets/", "").replace("visual_assets\\", "").lstrip("/\\")
        file_path = (settings.VISUAL_ASSETS_DIR / cleaned_rel).resolve()
        assets_dir_resolved = settings.VISUAL_ASSETS_DIR.resolve()

        if not str(file_path).startswith(str(assets_dir_resolved)):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

        if not file_path.is_file():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset file missing on disk")

        return FileResponse(file_path, media_type="image/png")
    finally:
        conn.close()


@router.get("/taxonomy/papers")
def list_taxonomy_papers() -> Dict[str, Any]:
    conn = get_db_connection()
    try:
        rows = conn.execute("SELECT code, name, category, ga_marks, subject_marks FROM gate_papers ORDER BY code ASC").fetchall()
        papers = [dict(r) for r in rows]
        if not papers:
            papers = [
                {"code": "CS", "name": "Computer Science and Information Technology", "category": "Engineering"},
                {"code": "DA", "name": "Data Science and Artificial Intelligence", "category": "Engineering"},
                {"code": "EC", "name": "Electronics and Communication Engineering", "category": "Engineering"},
                {"code": "EE", "name": "Electrical Engineering", "category": "Engineering"},
                {"code": "ME", "name": "Mechanical Engineering", "category": "Engineering"},
                {"code": "CE", "name": "Civil Engineering", "category": "Engineering"},
            ]
        return {"total": len(papers), "papers": papers}
    finally:
        conn.close()


@router.get("/taxonomy/subjects")
def list_taxonomy_subjects(paper_code: str = Query("CS")) -> Dict[str, Any]:
    paper_code = paper_code if isinstance(paper_code, str) else "CS"
    conn = get_db_connection()
    try:
        # Get subjects and topics for this paper
        p_row = conn.execute("SELECT id FROM gate_papers WHERE code = ?", (paper_code,)).fetchone()
        if not p_row:
            # Fallback to distinct subjects in questions table
            q_subjs = conn.execute(
                "SELECT DISTINCT subject_name FROM questions WHERE paper_code = ? AND subject_name IS NOT NULL",
                (paper_code,),
            ).fetchall()
            return {"paper_code": paper_code, "subjects": [{"name": r["subject_name"], "topics": []} for r in q_subjs]}

        paper_id = p_row["id"]
        subj_rows = conn.execute(
            "SELECT id, name, code, weightage_estimate FROM subjects WHERE paper_id = ? ORDER BY name ASC",
            (paper_id,),
        ).fetchall()

        subjects = []
        for s in subj_rows:
            top_rows = conn.execute(
                "SELECT id, name FROM topics WHERE subject_id = ? ORDER BY name ASC",
                (s["id"],),
            ).fetchall()
            subjects.append({
                "id": s["id"],
                "name": s["name"],
                "code": s["code"],
                "topics": [{"id": t["id"], "name": t["name"]} for t in top_rows],
            })

        # If subjects table has no records for this paper, fallback to questions table distinct values
        if not subjects:
            q_subjs = conn.execute(
                "SELECT DISTINCT subject_name FROM questions WHERE paper_code = ? AND subject_name IS NOT NULL",
                (paper_code,),
            ).fetchall()
            for qs in q_subjs:
                s_name = qs["subject_name"]
                t_rows = conn.execute(
                    "SELECT DISTINCT primary_topic_name FROM questions WHERE paper_code = ? AND subject_name = ? AND primary_topic_name IS NOT NULL",
                    (paper_code, s_name),
                ).fetchall()
                subjects.append({
                    "name": s_name,
                    "topics": [{"name": tr["primary_topic_name"]} for tr in t_rows],
                })

        return {"paper_code": paper_code, "subjects": subjects}
    finally:
        conn.close()
