"""
PYQ Analytics Router (/api/v1/analytics).
Provides:
- Factual SQL aggregations for syllabus subject distributions
- High-yield topic frequency breakdowns
- Year-wise question volume and mark weightage trends
- Question type (MCQ/MSQ/NAT) and marks (1-mark/2-mark) distributions
- Safe handling of empty datasets; zero speculative ML models
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query

from app.database.session import get_db_connection

router = APIRouter(tags=["analytics"])


@router.get("/analytics/distributions")
def get_pyq_distributions(
    paper_code: str = Query("CS", description="Discipline code"),
    subject_name: Optional[str] = Query(None, description="Filter topics by subject"),
) -> Dict[str, Any]:
    paper_code = paper_code if isinstance(paper_code, str) else "CS"
    subject_name = subject_name if isinstance(subject_name, str) and subject_name.strip() else None
    conn = get_db_connection()
    try:
        # 1. Total questions count
        total_q = conn.execute(
            "SELECT COUNT(*) FROM questions WHERE paper_code = ?", (paper_code,)
        ).fetchone()[0]

        if total_q == 0:
            return {
                "paper_code": paper_code,
                "total_questions": 0,
                "subject_distribution": [],
                "topic_distribution": [],
                "year_trends": [],
                "question_types": [],
                "marks_distribution": [],
            }

        # 2. Subject distribution
        subj_rows = conn.execute(
            """
            SELECT subject_name, COUNT(*) as count, SUM(marks) as total_marks
            FROM questions
            WHERE paper_code = ? AND subject_name IS NOT NULL
            GROUP BY subject_name
            ORDER BY count DESC
            """,
            (paper_code,),
        ).fetchall()

        subject_dist = []
        for r in subj_rows:
            cnt = r["count"]
            pct = round((cnt / total_q) * 100, 1)
            subject_dist.append({
                "subject_name": r["subject_name"],
                "count": cnt,
                "total_marks": r["total_marks"] or 0.0,
                "percentage": pct,
            })

        # 3. Topic distribution
        topic_params: List[Any] = [paper_code]
        topic_filter = ""
        if subject_name:
            topic_filter = "AND subject_name = ?"
            topic_params.append(subject_name)

        topic_sql = f"""
            SELECT primary_topic_name, subject_name, COUNT(*) as count, SUM(marks) as total_marks
            FROM questions
            WHERE paper_code = ? AND primary_topic_name IS NOT NULL {topic_filter}
            GROUP BY primary_topic_name
            ORDER BY count DESC
            LIMIT 15
        """
        topic_rows = conn.execute(topic_sql, tuple(topic_params)).fetchall()
        topic_dist = [
            {
                "topic_name": r["primary_topic_name"],
                "subject_name": r["subject_name"],
                "count": r["count"],
                "total_marks": r["total_marks"] or 0.0,
            }
            for r in topic_rows
        ]

        # 4. Year trends
        year_rows = conn.execute(
            """
            SELECT examination_year, COUNT(*) as count, SUM(marks) as total_marks
            FROM questions
            WHERE paper_code = ?
            GROUP BY examination_year
            ORDER BY examination_year ASC
            """,
            (paper_code,),
        ).fetchall()
        year_trends = [
            {
                "year": str(r["examination_year"]),
                "count": r["count"],
                "total_marks": r["total_marks"] or 0.0,
            }
            for r in year_rows
        ]

        # 5. Question types
        type_rows = conn.execute(
            """
            SELECT question_type, COUNT(*) as count
            FROM questions
            WHERE paper_code = ?
            GROUP BY question_type
            ORDER BY count DESC
            """,
            (paper_code,),
        ).fetchall()
        question_types = [
            {
                "type": r["question_type"],
                "count": r["count"],
                "percentage": round((r["count"] / total_q) * 100, 1),
            }
            for r in type_rows
        ]

        # 6. Marks distribution
        marks_rows = conn.execute(
            """
            SELECT marks, COUNT(*) as count
            FROM questions
            WHERE paper_code = ?
            GROUP BY marks
            ORDER BY marks ASC
            """,
            (paper_code,),
        ).fetchall()
        marks_dist = [
            {
                "marks": f"{int(r['marks'])} Mark{'s' if r['marks'] > 1 else ''}",
                "count": r["count"],
                "percentage": round((r["count"] / total_q) * 100, 1),
            }
            for r in marks_rows
        ]

        return {
            "paper_code": paper_code,
            "total_questions": total_q,
            "subject_distribution": subject_dist,
            "topic_distribution": topic_dist,
            "year_trends": year_trends,
            "question_types": question_types,
            "marks_distribution": marks_dist,
        }
    finally:
        conn.close()


@router.get("/analytics/difficulty")
def get_difficulty_analytics(paper_code: str = Query("CS")) -> Dict[str, Any]:
    paper_code = paper_code if isinstance(paper_code, str) else "CS"
    conn = get_db_connection()
    try:
        rows = conn.execute(
            """
            SELECT difficulty_level, COUNT(*) as count
            FROM questions
            WHERE paper_code = ? AND difficulty_level IS NOT NULL
            GROUP BY difficulty_level
            """,
            (paper_code,),
        ).fetchall()

        total = sum(r["count"] for r in rows)
        dist = [
            {
                "level": r["difficulty_level"],
                "count": r["count"],
                "percentage": round((r["count"] / total) * 100, 1) if total > 0 else 0.0,
            }
            for r in rows
        ]

        return {"paper_code": paper_code, "total": total, "distribution": dist}
    finally:
        conn.close()
