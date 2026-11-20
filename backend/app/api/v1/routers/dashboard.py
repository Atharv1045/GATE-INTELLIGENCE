"""
Dashboard Router (/api/v1/dashboard).
Provides:
- Real preparation metrics (total questions, attempted, correct, accuracy %, tests completed)
- Subject-wise syllabus progress bars
- Chronological recent activity log (practice answers & mock test submissions)
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query

from app.database.session import get_db_connection

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard/metrics")
def get_dashboard_metrics(paper_code: str = Query("CS")) -> Dict[str, Any]:
    paper_code = paper_code if isinstance(paper_code, str) else "CS"
    conn = get_db_connection()
    try:
        # Total questions available in question bank
        total_questions = conn.execute(
            "SELECT COUNT(*) FROM questions WHERE paper_code = ?", (paper_code,)
        ).fetchone()[0]

        # Student responses statistics
        resp_stats = conn.execute(
            """
            SELECT
                COUNT(sr.id) as total_attempts,
                SUM(CASE WHEN sr.is_correct = 1 THEN 1 ELSE 0 END) as correct_count,
                SUM(CASE WHEN sr.is_correct = 0 THEN 1 ELSE 0 END) as incorrect_count
            FROM student_responses sr
            JOIN questions q ON sr.question_id = q.id
            WHERE q.paper_code = ?
            """,
            (paper_code,),
        ).fetchone()

        total_attempted = resp_stats["total_attempts"] or 0
        correct_count = resp_stats["correct_count"] or 0
        incorrect_count = resp_stats["incorrect_count"] or 0
        accuracy = round((correct_count / total_attempted) * 100, 1) if total_attempted > 0 else 0.0

        # Mock tests completed
        tests_completed = conn.execute(
            """
            SELECT COUNT(tr.id)
            FROM test_results tr
            JOIN mock_tests mt ON tr.mock_test_id = mt.id
            WHERE mt.paper_code = ?
            """,
            (paper_code,),
        ).fetchone()[0]

        # Latest test result
        latest_test_row = conn.execute(
            """
            SELECT tr.*, mt.title as test_title
            FROM test_results tr
            JOIN mock_tests mt ON tr.mock_test_id = mt.id
            WHERE mt.paper_code = ?
            ORDER BY tr.created_at DESC
            LIMIT 1
            """,
            (paper_code,),
        ).fetchone()

        latest_test = None
        if latest_test_row:
            latest_test = {
                "id": latest_test_row["id"],
                "mock_test_id": latest_test_row["mock_test_id"],
                "test_title": latest_test_row["test_title"],
                "total_marks": latest_test_row["total_marks"],
                "marks_obtained": latest_test_row["marks_obtained"],
                "accuracy_percent": latest_test_row["accuracy_percent"],
                "correct_count": latest_test_row["correct_count"],
                "incorrect_count": latest_test_row["incorrect_count"],
                "unattempted_count": latest_test_row["unattempted_count"],
                "created_at": latest_test_row["created_at"],
            }

        # Available papers count
        available_papers = conn.execute(
            "SELECT COUNT(*) FROM question_papers WHERE paper_code = ? AND total_extracted_questions > 0",
            (paper_code,),
        ).fetchone()[0]

        return {
            "paper_code": paper_code,
            "total_questions": total_questions,
            "total_attempted": total_attempted,
            "correct_answers": correct_count,
            "incorrect_answers": incorrect_count,
            "accuracy_percent": accuracy,
            "tests_completed": tests_completed,
            "available_papers": available_papers,
            "latest_test": latest_test,
        }
    finally:
        conn.close()


@router.get("/dashboard/progress")
def get_dashboard_progress(paper_code: str = Query("CS")) -> Dict[str, Any]:
    paper_code = paper_code if isinstance(paper_code, str) else "CS"
    conn = get_db_connection()
    try:
        # Subject-wise questions and attempts
        subj_rows = conn.execute(
            """
            SELECT
                q.subject_name,
                COUNT(q.id) as total_questions,
                COUNT(sr.id) as attempted_questions,
                SUM(CASE WHEN sr.is_correct = 1 THEN 1 ELSE 0 END) as correct_questions
            FROM questions q
            LEFT JOIN student_responses sr ON q.id = sr.question_id
            WHERE q.paper_code = ? AND q.subject_name IS NOT NULL
            GROUP BY q.subject_name
            ORDER BY total_questions DESC
            """,
            (paper_code,),
        ).fetchall()

        subjects_progress = []
        for r in subj_rows:
            tot = r["total_questions"]
            att = r["attempted_questions"] or 0
            corr = r["correct_questions"] or 0
            coverage = round((att / tot) * 100, 1) if tot > 0 else 0.0
            acc = round((corr / att) * 100, 1) if att > 0 else 0.0
            subjects_progress.append({
                "subject_name": r["subject_name"],
                "total_questions": tot,
                "attempted_questions": att,
                "correct_questions": corr,
                "coverage_percent": coverage,
                "accuracy_percent": acc,
            })

        return {
            "paper_code": paper_code,
            "subjects": subjects_progress,
        }
    finally:
        conn.close()


@router.get("/dashboard/recent")
def get_dashboard_recent_activity(paper_code: str = Query("CS"), limit: int = Query(10, ge=1, le=50)) -> Dict[str, Any]:
    paper_code = paper_code if isinstance(paper_code, str) else "CS"
    limit = int(limit) if isinstance(limit, int) else 10
    conn = get_db_connection()
    try:
        # Recent student responses joined with questions
        rows = conn.execute(
            """
            SELECT
                sr.id, sr.created_at, sr.is_correct, sr.marks_awarded,
                q.id as question_id, q.question_number, q.subject_name, q.primary_topic_name,
                q.examination_year, q.marks, mt.test_mode, mt.title as test_title
            FROM student_responses sr
            JOIN questions q ON sr.question_id = q.id
            LEFT JOIN mock_tests mt ON sr.mock_test_id = mt.id
            WHERE q.paper_code = ?
            ORDER BY sr.created_at DESC
            LIMIT ?
            """,
            (paper_code, limit),
        ).fetchall()

        activity = []
        for r in rows:
            activity.append({
                "id": r["id"],
                "type": "practice" if r["test_mode"] == "practice" else "test_attempt",
                "title": f"{r['test_title'] or 'Practice'}: Q.{r['question_number']} ({r['examination_year']})",
                "question_id": r["question_id"],
                "subject_name": r["subject_name"] or "General",
                "topic_name": r["primary_topic_name"] or "Topic",
                "is_correct": bool(r["is_correct"]),
                "marks_awarded": r["marks_awarded"],
                "max_marks": r["marks"],
                "created_at": r["created_at"],
            })

        return {
            "paper_code": paper_code,
            "activity": activity,
        }
    finally:
        conn.close()
