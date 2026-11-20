"""
CBT Mock Test Router (/api/v1/tests).
Provides:
- Test creation: Full-Length (65Q), Paper-Based, or Custom Subject Drill
- Authoritative backend scoring strictly enforcing official GATE marking rules:
  * 1-Mark MCQ: +1.0 / -0.333333 (-1/3)
  * 2-Mark MCQ: +2.0 / -0.666667 (-2/3)
  * MSQ: Exact set match for full marks; 0 partial; NO negative marks
  * NAT: Official range/tolerance match for full marks; NO negative marks
  * Unattempted: 0 marks
- Client-submitted scores are never trusted
- Comprehensive scorecard generation and question-by-question review
"""
from __future__ import annotations

import json
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from app.database.session import get_db_connection, new_uuid, utcnow_iso

router = APIRouter(tags=["tests"])


class TestStartRequest(BaseModel):
    paper_code: str = "CS"
    test_mode: str = "full"  # "full", "paper", "subject"
    paper_id: Optional[str] = None
    year: Optional[int] = None
    subject_name: Optional[str] = None
    duration_minutes: int = 180


class CandidateQuestionResponse(BaseModel):
    question_id: str
    selected_options: Optional[List[str]] = None
    numerical_answer: Optional[float] = None
    marked_for_review: bool = False
    time_spent_seconds: int = 0


class TestSubmitRequest(BaseModel):
    responses: List[CandidateQuestionResponse]


@router.post("/tests/start")
def start_test(payload: TestStartRequest) -> Dict[str, Any]:
    conn = get_db_connection()
    try:
        paper_code = payload.paper_code
        questions = []
        test_title = f"GATE {paper_code} Mock Test"

        if payload.test_mode == "paper" or payload.paper_id or payload.year:
            if payload.paper_id:
                qp = conn.execute("SELECT * FROM question_papers WHERE id = ?", (payload.paper_id,)).fetchone()
            else:
                qp = conn.execute(
                    "SELECT * FROM question_papers WHERE examination_year = ? AND paper_code = ?",
                    (payload.year, paper_code),
                ).fetchone()

            if qp:
                test_title = qp["title"] or f"GATE {paper_code} {qp['examination_year']} Exam"
                q_rows = conn.execute(
                    """
                    SELECT q.* FROM questions q
                    WHERE q.question_paper_id = ? OR (q.examination_year = ? AND q.paper_code = ?)
                    ORDER BY q.question_number ASC
                    """,
                    (qp["id"], qp["examination_year"], paper_code),
                ).fetchall()
                questions = [dict(q) for q in q_rows]

        elif payload.test_mode == "subject" and payload.subject_name:
            test_title = f"GATE {paper_code} — {payload.subject_name} Drill"
            q_rows = conn.execute(
                """
                SELECT q.* FROM questions q
                WHERE q.paper_code = ? AND q.subject_name = ?
                ORDER BY q.question_number ASC
                LIMIT 30
                """,
                (paper_code, payload.subject_name),
            ).fetchall()
            questions = [dict(q) for q in q_rows]

        # Full-length fallback or selection
        if not questions:
            # Prefer 2012 CS (which has full 65 questions and verified answer keys)
            full_paper = conn.execute(
                "SELECT id, title, examination_year FROM question_papers WHERE paper_code = ? AND total_extracted_questions >= 65 LIMIT 1",
                (paper_code,),
            ).fetchone()
            if full_paper:
                test_title = full_paper["title"] or f"GATE {paper_code} Official Exam"
                q_rows = conn.execute(
                    "SELECT * FROM questions WHERE question_paper_id = ? OR (examination_year = ? AND paper_code = ?) ORDER BY question_number ASC",
                    (full_paper["id"], full_paper["examination_year"], paper_code),
                ).fetchall()
                questions = [dict(q) for q in q_rows]
            else:
                # Load whatever questions exist without duplicating
                q_rows = conn.execute(
                    "SELECT * FROM questions WHERE paper_code = ? ORDER BY examination_year DESC, question_number ASC LIMIT 65",
                    (paper_code,),
                ).fetchall()
                questions = [dict(q) for q in q_rows]

        if not questions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No questions available in the database for discipline '{paper_code}'.",
            )

        now = utcnow_iso()
        test_id = new_uuid()
        total_q = len(questions)
        total_marks = sum(float(q["marks"] or 1.0) for q in questions)

        # Create mock_test record
        conn.execute(
            """
            INSERT INTO mock_tests (
                id, title, paper_code, test_mode, duration_minutes, total_questions, total_marks,
                status, started_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'in_progress', ?, ?, ?)
            """,
            (
                test_id,
                test_title,
                paper_code,
                payload.test_mode,
                payload.duration_minutes,
                total_q,
                total_marks,
                now,
                now,
                now,
            ),
        )

        # Create test_questions mapping
        q_ids = [q["id"] for q in questions]
        for idx, q in enumerate(questions):
            section = "General Aptitude" if (q["subject_name"] and "aptitude" in q["subject_name"].lower()) or (q["question_number"] and q["question_number"] >= 56) else "Core CS"
            conn.execute(
                """
                INSERT INTO test_questions (id, mock_test_id, question_id, display_order, section_name, marks, negative_marks, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_uuid(),
                    test_id,
                    q["id"],
                    idx + 1,
                    section,
                    q["marks"] or 1.0,
                    q["negative_marks"] or 0.333333,
                    now,
                    now,
                ),
            )

        # Batch load options and visual assets (OMITTING correct answer flags!)
        placeholders = ",".join(["?"] * len(q_ids))
        options_rows = conn.execute(
            f"SELECT id, question_id, option_label, option_text FROM question_options WHERE question_id IN ({placeholders}) ORDER BY option_label ASC",
            tuple(q_ids),
        ).fetchall()
        options_map: Dict[str, List[Dict[str, Any]]] = {}
        for opt in options_rows:
            options_map.setdefault(opt["question_id"], []).append({
                "id": opt["id"],
                "option_label": opt["option_label"],
                "option_text": opt["option_text"],
            })

        assets_rows = conn.execute(
            f"SELECT id, question_id, asset_role, asset_type, option_label, relative_path FROM question_visual_assets WHERE question_id IN ({placeholders})",
            tuple(q_ids),
        ).fetchall()
        assets_map: Dict[str, List[Dict[str, Any]]] = {}
        for ast in assets_rows:
            assets_map.setdefault(ast["question_id"], []).append({
                "id": ast["id"],
                "asset_role": ast["asset_role"],
                "asset_type": ast["asset_type"],
                "option_label": ast["option_label"],
                "relative_path": ast["relative_path"],
            })

        conn.commit()

        # Sanitize question objects for test taking (NO answer keys or correct flags!)
        cbt_questions = []
        for idx, q in enumerate(questions):
            qid = q["id"]
            section = "General Aptitude" if (q["subject_name"] and "aptitude" in q["subject_name"].lower()) or (q["question_number"] and q["question_number"] >= 56) else "Core CS"
            cbt_questions.append({
                "index": idx + 1,
                "question_id": qid,
                "question_number": q["question_number"],
                "question_type": q["question_type"],
                "marks": q["marks"],
                "negative_marks": q["negative_marks"],
                "section": section,
                "subject_name": q["subject_name"],
                "primary_topic_name": q["primary_topic_name"],
                "question_text": q["question_text"],
                "options": options_map.get(qid, []),
                "visual_assets": assets_map.get(qid, []),
            })

        return {
            "test_id": test_id,
            "title": test_title,
            "paper_code": paper_code,
            "test_mode": payload.test_mode,
            "duration_seconds": payload.duration_minutes * 60,
            "total_questions": total_q,
            "total_marks": total_marks,
            "questions": cbt_questions,
        }
    finally:
        conn.close()



@router.get("/tests/history")
def list_test_history(paper_code: str = Query("CS")) -> Dict[str, Any]:
    paper_code = paper_code if isinstance(paper_code, str) else "CS"
    conn = get_db_connection()
    try:
        rows = conn.execute(
            """
            SELECT tr.*, mt.title as test_title, mt.test_mode, mt.paper_code
            FROM test_results tr
            JOIN mock_tests mt ON tr.mock_test_id = mt.id
            WHERE mt.paper_code = ?
            ORDER BY tr.created_at DESC
            """,
            (paper_code,),
        ).fetchall()

        history = [
            {
                "id": r["id"],
                "test_id": r["mock_test_id"],
                "mock_test_id": r["mock_test_id"],
                "title": r["test_title"],
                "test_mode": r["test_mode"],
                "total_marks": r["total_marks"],
                "marks_obtained": r["marks_obtained"],
                "accuracy_percent": r["accuracy_percent"],
                "attempted_count": r["attempted_count"],
                "correct_count": r["correct_count"],
                "incorrect_count": r["incorrect_count"],
                "unattempted_count": r["unattempted_count"],
                "time_taken_seconds": r["time_taken_seconds"],
                "created_at": r["created_at"],
            }
            for r in rows
        ]

        return {"total": len(history), "history": history}
    finally:
        conn.close()


@router.get("/tests/{test_id}")
def get_test_state(test_id: str) -> Dict[str, Any]:
    conn = get_db_connection()
    try:
        mt = conn.execute("SELECT * FROM mock_tests WHERE id = ?", (test_id,)).fetchone()
        if not mt:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mock test not found")

        # Questions for this test
        tq_rows = conn.execute(
            """
            SELECT tq.display_order, tq.section_name, q.*
            FROM test_questions tq
            JOIN questions q ON tq.question_id = q.id
            WHERE tq.mock_test_id = ?
            ORDER BY tq.display_order ASC
            """,
            (test_id,),
        ).fetchall()

        q_ids = [r["id"] for r in tq_rows]
        options_map: Dict[str, List[Dict[str, Any]]] = {}
        assets_map: Dict[str, List[Dict[str, Any]]] = {}

        if q_ids:
            placeholders = ",".join(["?"] * len(q_ids))
            opt_rows = conn.execute(
                f"SELECT id, question_id, option_label, option_text FROM question_options WHERE question_id IN ({placeholders}) ORDER BY option_label ASC",
                tuple(q_ids),
            ).fetchall()
            for opt in opt_rows:
                options_map.setdefault(opt["question_id"], []).append({
                    "id": opt["id"],
                    "option_label": opt["option_label"],
                    "option_text": opt["option_text"],
                })

            ast_rows = conn.execute(
                f"SELECT id, question_id, asset_role, asset_type, option_label, relative_path FROM question_visual_assets WHERE question_id IN ({placeholders})",
                tuple(q_ids),
            ).fetchall()
            for ast in ast_rows:
                assets_map.setdefault(ast["question_id"], []).append({
                    "id": ast["id"],
                    "asset_role": ast["asset_role"],
                    "asset_type": ast["asset_type"],
                    "option_label": ast["option_label"],
                    "relative_path": ast["relative_path"],
                })

        questions = []
        for r in tq_rows:
            qid = r["id"]
            questions.append({
                "index": r["display_order"],
                "question_id": qid,
                "question_number": r["question_number"],
                "question_type": r["question_type"],
                "marks": r["marks"],
                "negative_marks": r["negative_marks"],
                "section": r["section_name"],
                "subject_name": r["subject_name"],
                "primary_topic_name": r["primary_topic_name"],
                "question_text": r["question_text"],
                "options": options_map.get(qid, []),
                "visual_assets": assets_map.get(qid, []),
            })

        return {
            "test_id": test_id,
            "title": mt["title"],
            "status": mt["status"],
            "duration_minutes": mt["duration_minutes"],
            "total_questions": mt["total_questions"],
            "total_marks": mt["total_marks"],
            "questions": questions,
        }
    finally:
        conn.close()


@router.post("/tests/{test_id}/submit")
def submit_test(test_id: str, payload: TestSubmitRequest) -> Dict[str, Any]:
    """Authoritative backend scoring strictly enforcing official GATE exam rules."""
    conn = get_db_connection()
    try:
        mt = conn.execute("SELECT * FROM mock_tests WHERE id = ?", (test_id,)).fetchone()
        if not mt:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mock test not found")

        # Load all test questions with answer keys
        tq_rows = conn.execute(
            """
            SELECT tq.display_order, tq.section_name, tq.marks as tq_marks, tq.negative_marks as tq_neg,
                   q.*, ak.correct_options_json, ak.numerical_min, ak.numerical_max, ak.tolerance,
                   ak.provenance, ak.explanation
            FROM test_questions tq
            JOIN questions q ON tq.question_id = q.id
            LEFT JOIN answer_keys ak ON ak.question_id = q.id
            WHERE tq.mock_test_id = ?
            ORDER BY tq.display_order ASC
            """,
            (test_id,),
        ).fetchall()

        if not tq_rows:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Test has no associated questions.")

        response_by_qid: Dict[str, CandidateQuestionResponse] = {
            r.question_id: r for r in payload.responses
        }

        total_marks: float = 0.0
        marks_obtained: float = 0.0
        attempted_count: int = 0
        correct_count: int = 0
        incorrect_count: int = 0
        unattempted_count: int = 0
        total_time_seconds: int = 0

        section_scores: Dict[str, Dict[str, Any]] = {
            "General Aptitude": {"total_marks": 0.0, "marks_obtained": 0.0, "attempted": 0, "correct": 0},
            "Core CS": {"total_marks": 0.0, "marks_obtained": 0.0, "attempted": 0, "correct": 0},
        }

        subject_scores: Dict[str, Dict[str, Any]] = {}
        question_reviews = []
        now = utcnow_iso()

        # Delete any previous student_responses for this test_id
        conn.execute("DELETE FROM student_responses WHERE mock_test_id = ?", (test_id,))

        for row in tq_rows:
            qid = row["id"]
            q_type = (row["question_type"] or "MCQ").upper()
            m = float(row["tq_marks"] or 1.0)
            neg_m = float(row["tq_neg"] if row["tq_neg"] is not None else (m / 3.0))
            total_marks += m

            sec_name = row["section_name"] or "Core CS"
            if sec_name not in section_scores:
                section_scores[sec_name] = {"total_marks": 0.0, "marks_obtained": 0.0, "attempted": 0, "correct": 0}
            section_scores[sec_name]["total_marks"] += m

            s_name = row["subject_name"] or "General"
            if s_name not in subject_scores:
                subject_scores[s_name] = {"total_marks": 0.0, "marks_obtained": 0.0, "attempted": 0, "correct": 0}
            subject_scores[s_name]["total_marks"] += m

            user_resp = response_by_qid.get(qid)
            selected_opts = [s.strip().upper() for s in (user_resp.selected_options or [])] if user_resp and user_resp.selected_options else []
            num_ans = user_resp.numerical_answer if user_resp else None
            time_spent = user_resp.time_spent_seconds if user_resp else 0
            is_marked_review = user_resp.marked_for_review if user_resp else False
            total_time_seconds += time_spent

            # Official correct options
            correct_opts: List[str] = []
            if row["correct_options_json"]:
                try:
                    correct_opts = json.loads(row["correct_options_json"])
                except Exception:
                    correct_opts = []

            is_verified = bool(correct_opts) or (row["numerical_min"] is not None)

            # Check if attempted
            is_attempted = bool(selected_opts) or (num_ans is not None)

            q_is_correct: Optional[bool] = None
            q_marks_awarded: float = 0.0

            if not is_attempted:
                unattempted_count += 1
                q_is_correct = False
                q_marks_awarded = 0.0
            elif not is_verified:
                # Unverified answer key -> cannot falsely penalize or reward candidate
                attempted_count += 1
                q_is_correct = None
                q_marks_awarded = 0.0
            else:
                attempted_count += 1
                section_scores[sec_name]["attempted"] += 1
                subject_scores[s_name]["attempted"] += 1

                if q_type == "MCQ":
                    expected = [e.strip().upper() for e in correct_opts]
                    if selected_opts and set(selected_opts) == set(expected):
                        q_is_correct = True
                        q_marks_awarded = m
                        correct_count += 1
                        section_scores[sec_name]["correct"] += 1
                        subject_scores[s_name]["correct"] += 1
                    else:
                        q_is_correct = False
                        q_marks_awarded = -neg_m
                        incorrect_count += 1

                elif q_type == "MSQ":
                    expected = [e.strip().upper() for e in correct_opts]
                    # Exact match required; NO negative marks
                    if selected_opts and set(selected_opts) == set(expected):
                        q_is_correct = True
                        q_marks_awarded = m
                        correct_count += 1
                        section_scores[sec_name]["correct"] += 1
                        subject_scores[s_name]["correct"] += 1
                    else:
                        q_is_correct = False
                        q_marks_awarded = 0.0
                        incorrect_count += 1

                elif q_type == "NAT":
                    n_min = row["numerical_min"]
                    n_max = row["numerical_max"]
                    tol = row["tolerance"] or 0.01

                    nat_correct = False
                    if num_ans is not None:
                        if n_min is not None and n_max is not None:
                            nat_correct = (n_min <= num_ans <= n_max)
                        elif n_min is not None:
                            nat_correct = abs(num_ans - n_min) <= tol

                    if nat_correct:
                        q_is_correct = True
                        q_marks_awarded = m
                        correct_count += 1
                        section_scores[sec_name]["correct"] += 1
                        subject_scores[s_name]["correct"] += 1
                    else:
                        q_is_correct = False
                        q_marks_awarded = 0.0
                        incorrect_count += 1

            marks_obtained += q_marks_awarded
            section_scores[sec_name]["marks_obtained"] += q_marks_awarded
            subject_scores[s_name]["marks_obtained"] += q_marks_awarded

            # Persist student_response
            conn.execute(
                """
                INSERT INTO student_responses (
                    id, mock_test_id, question_id, selected_options_json, numerical_answer,
                    marked_for_review, time_spent_seconds, is_correct, marks_awarded, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_uuid(),
                    test_id,
                    qid,
                    json.dumps(selected_opts),
                    num_ans,
                    1 if is_marked_review else 0,
                    time_spent,
                    1 if q_is_correct is True else (0 if q_is_correct is False else None),
                    round(q_marks_awarded, 4),
                    now,
                    now,
                ),
            )

            # Build review item
            question_reviews.append({
                "index": row["display_order"],
                "question_id": qid,
                "question_number": row["question_number"],
                "question_type": q_type,
                "section": sec_name,
                "subject_name": s_name,
                "primary_topic_name": row["primary_topic_name"],
                "question_text": row["question_text"],
                "marks": m,
                "negative_marks": neg_m,
                "is_attempted": is_attempted,
                "user_selected_options": selected_opts,
                "user_numerical_answer": num_ans,
                "official_correct_options": correct_opts,
                "official_numerical_range": [row["numerical_min"], row["numerical_max"]] if row["numerical_min"] is not None else None,
                "is_correct": q_is_correct,
                "marks_awarded": round(q_marks_awarded, 4),
                "is_verified": is_verified,
                "provenance": row["provenance"],
                "explanation": row["explanation"],
            })

        accuracy = round((correct_count / attempted_count) * 100, 1) if attempted_count > 0 else 0.0

        # Save test_result
        result_id = new_uuid()
        conn.execute(
            """
            INSERT INTO test_results (
                id, mock_test_id, total_marks, marks_obtained, accuracy_percent,
                attempted_count, correct_count, incorrect_count, unattempted_count,
                time_taken_seconds, subject_breakdown_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result_id,
                test_id,
                total_marks,
                round(marks_obtained, 4),
                accuracy,
                attempted_count,
                correct_count,
                incorrect_count,
                unattempted_count,
                total_time_seconds,
                json.dumps(subject_scores),
                now,
                now,
            ),
        )

        # Update mock_test status
        conn.execute(
            "UPDATE mock_tests SET status = 'completed', submitted_at = ?, updated_at = ? WHERE id = ?",
            (now, now, test_id),
        )

        conn.commit()

        return {
            "test_result_id": result_id,
            "mock_test_id": test_id,
            "test_title": mt["title"],
            "total_marks": total_marks,
            "marks_obtained": round(marks_obtained, 2),
            "accuracy_percent": accuracy,
            "attempted_count": attempted_count,
            "correct_count": correct_count,
            "incorrect_count": incorrect_count,
            "unattempted_count": unattempted_count,
            "time_taken_seconds": total_time_seconds,
            "section_breakdown": section_scores,
            "subject_breakdown": subject_scores,
            "question_reviews": question_reviews,
        }
    finally:
        conn.close()


@router.get("/tests/results/{result_id}")
def get_test_result(result_id: str) -> Dict[str, Any]:
    conn = get_db_connection()
    try:
        tr = conn.execute(
            "SELECT * FROM test_results WHERE id = ? OR mock_test_id = ? ORDER BY created_at DESC LIMIT 1",
            (result_id, result_id),
        ).fetchone()
        if not tr:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test result not found")

        test_id = tr["mock_test_id"]
        mt = conn.execute("SELECT * FROM mock_tests WHERE id = ?", (test_id,)).fetchone()

        # Load question reviews from student_responses joined with questions
        rows = conn.execute(
            """
            SELECT sr.*, q.question_number, q.question_type, q.question_text, q.marks, q.negative_marks,
                   q.subject_name, q.primary_topic_name,
                   ak.correct_options_json, ak.numerical_min, ak.numerical_max, ak.provenance, ak.explanation
            FROM student_responses sr
            JOIN questions q ON sr.question_id = q.id
            LEFT JOIN answer_keys ak ON ak.question_id = q.id
            WHERE sr.mock_test_id = ?
            ORDER BY q.question_number ASC
            """,
            (test_id,),
        ).fetchall()

        reviews = []
        for idx, r in enumerate(rows):
            correct_opts = []
            if r["correct_options_json"]:
                try:
                    correct_opts = json.loads(r["correct_options_json"])
                except Exception:
                    correct_opts = []

            user_opts = []
            if r["selected_options_json"]:
                try:
                    user_opts = json.loads(r["selected_options_json"])
                except Exception:
                    user_opts = []

            reviews.append({
                "index": idx + 1,
                "question_id": r["question_id"],
                "question_number": r["question_number"],
                "question_type": r["question_type"],
                "subject_name": r["subject_name"],
                "primary_topic_name": r["primary_topic_name"],
                "question_text": r["question_text"],
                "marks": r["marks"],
                "negative_marks": r["negative_marks"],
                "user_selected_options": user_opts,
                "user_numerical_answer": r["numerical_answer"],
                "official_correct_options": correct_opts,
                "official_numerical_range": [r["numerical_min"], r["numerical_max"]] if r["numerical_min"] is not None else None,
                "is_correct": bool(r["is_correct"]) if r["is_correct"] is not None else None,
                "marks_awarded": r["marks_awarded"],
                "provenance": r["provenance"],
                "explanation": r["explanation"],
            })

        subj_breakdown = {}
        if tr["subject_breakdown_json"]:
            try:
                subj_breakdown = json.loads(tr["subject_breakdown_json"])
            except Exception:
                subj_breakdown = {}

        return {
            "test_result_id": tr["id"],
            "mock_test_id": test_id,
            "test_title": mt["title"] if mt else "GATE Mock Test",
            "total_marks": tr["total_marks"],
            "marks_obtained": tr["marks_obtained"],
            "accuracy_percent": tr["accuracy_percent"],
            "attempted_count": tr["attempted_count"],
            "correct_count": tr["correct_count"],
            "incorrect_count": tr["incorrect_count"],
            "unattempted_count": tr["unattempted_count"],
            "time_taken_seconds": tr["time_taken_seconds"],
            "subject_breakdown": subj_breakdown,
            "question_reviews": reviews,
            "created_at": tr["created_at"],
        }
    finally:
        conn.close()

