"""
Lightweight Deterministic Agents for GATE Intelligence.
Replaces heavy LangGraph / external LLM dependencies with fast, deterministic,
pure-Python and SQLite-backed analytical services:
1. PYQ Analysis Agent (topic frequencies, year trends, subject weightage)
2. Performance Agent (user accuracy evaluation, weak area detection, revision recommendations)
3. Question Assistant (question decomposition, official answer & solution breakdown)
4. Paper Analysis Agent (paper structural composition, GA vs Core balance, type distributions)
"""
from __future__ import annotations

import json
import sqlite3
from typing import Any, Dict, List, Optional
from app.database.session import get_db_connection


class PYQAnalysisAgent:
    """Deterministic agent that analyzes historical PYQ distributions and recurring patterns."""

    @staticmethod
    def analyze(paper_code: str = "CS", subject_name: Optional[str] = None) -> Dict[str, Any]:
        conn = get_db_connection()
        try:
            # Subject distribution
            subj_query = """
                SELECT subject_name, COUNT(*) as count, SUM(marks) as total_marks
                FROM questions
                WHERE paper_code = ? AND subject_name IS NOT NULL
                GROUP BY subject_name
                ORDER BY count DESC
            """
            subject_dist = [
                {"subject_name": r["subject_name"], "count": r["count"], "total_marks": r["total_marks"]}
                for r in conn.execute(subj_query, (paper_code,)).fetchall()
            ]

            # Top recurring topics
            topic_filter = ""
            params: List[Any] = [paper_code]
            if subject_name:
                topic_filter = "AND subject_name = ?"
                params.append(subject_name)

            topic_query = f"""
                SELECT primary_topic_name, subject_name, COUNT(*) as count, SUM(marks) as total_marks
                FROM questions
                WHERE paper_code = ? AND primary_topic_name IS NOT NULL {topic_filter}
                GROUP BY primary_topic_name
                ORDER BY count DESC
                LIMIT 15
            """
            top_topics = [
                {
                    "topic_name": r["primary_topic_name"],
                    "subject_name": r["subject_name"],
                    "count": r["count"],
                    "total_marks": r["total_marks"],
                }
                for r in conn.execute(topic_query, tuple(params)).fetchall()
            ]

            # Year-wise trends
            year_query = """
                SELECT examination_year, COUNT(*) as count, SUM(marks) as total_marks
                FROM questions
                WHERE paper_code = ?
                GROUP BY examination_year
                ORDER BY examination_year ASC
            """
            year_trends = [
                {"year": r["examination_year"], "count": r["count"], "total_marks": r["total_marks"]}
                for r in conn.execute(year_query, (paper_code,)).fetchall()
            ]

            # Question types & marks breakdown
            type_query = """
                SELECT question_type, COUNT(*) as count
                FROM questions
                WHERE paper_code = ?
                GROUP BY question_type
            """
            type_breakdown = {r["question_type"]: r["count"] for r in conn.execute(type_query, (paper_code,)).fetchall()}

            marks_query = """
                SELECT marks, COUNT(*) as count
                FROM questions
                WHERE paper_code = ?
                GROUP BY marks
            """
            marks_breakdown = {f"{int(r['marks'])} Mark": r["count"] for r in conn.execute(marks_query, (paper_code,)).fetchall()}

            total_q = sum(s["count"] for s in subject_dist)

            return {
                "agent_name": "PYQ Analysis Agent",
                "discipline": paper_code,
                "total_questions_analyzed": total_q,
                "subject_distribution": subject_dist,
                "top_recurring_topics": top_topics,
                "year_trends": year_trends,
                "question_types": type_breakdown,
                "marks_breakdown": marks_breakdown,
                "insights": [
                    f"Analyzed {total_q} questions across {len(subject_dist)} subjects.",
                    f"Most frequent subject is '{subject_dist[0]['subject_name']}' with {subject_dist[0]['count']} questions."
                    if subject_dist else "No subject data available.",
                    f"Top high-yield topic is '{top_topics[0]['topic_name']}' ({top_topics[0]['count']} questions)."
                    if top_topics else "No topic data available.",
                ],
            }
        finally:
            conn.close()


class PerformanceAgent:
    """Deterministic agent that evaluates candidate practice & test history to recommend targeted revisions."""

    @staticmethod
    def evaluate(paper_code: str = "CS") -> Dict[str, Any]:
        conn = get_db_connection()
        try:
            # Query student responses joined with questions
            resp_query = """
                SELECT sr.is_correct, sr.marks_awarded, q.subject_name, q.primary_topic_name, q.question_type, q.marks
                FROM student_responses sr
                JOIN questions q ON sr.question_id = q.id
                WHERE q.paper_code = ?
            """
            responses = conn.execute(resp_query, (paper_code,)).fetchall()

            total_attempts = len(responses)
            if total_attempts == 0:
                # Return empty state with syllabus starter guide
                top_subjs = conn.execute(
                    "SELECT name FROM subjects WHERE code LIKE ? LIMIT 5", (f"{paper_code}%",)
                ).fetchall()
                starter_subjects = [s["name"] for s in top_subjs] or [
                    "Engineering Mathematics",
                    "Discrete Mathematics",
                    "Algorithms",
                    "Programming and Data Structures",
                ]
                return {
                    "agent_name": "Performance Agent",
                    "status": "no_attempts_recorded",
                    "total_attempts": 0,
                    "accuracy_percentage": 0.0,
                    "weak_subjects": [],
                    "weak_topics": [],
                    "recommendations": [
                        "No test attempts or practice questions recorded yet.",
                        "Start by solving questions from foundational subjects in the Question Bank.",
                        f"Recommended starting subjects: {', '.join(starter_subjects)}.",
                        "Take a diagnostic CBT mock test in Mock Tests to establish your baseline.",
                    ],
                }

            correct_count = sum(1 for r in responses if r["is_correct"] == 1)
            overall_accuracy = round((correct_count / total_attempts) * 100, 1)

            # Subject breakdown
            subject_stats: Dict[str, Dict[str, int]] = {}
            topic_stats: Dict[str, Dict[str, Any]] = {}

            for r in responses:
                s_name = r["subject_name"] or "General"
                t_name = r["primary_topic_name"] or "General"

                if s_name not in subject_stats:
                    subject_stats[s_name] = {"attempted": 0, "correct": 0}
                subject_stats[s_name]["attempted"] += 1
                if r["is_correct"] == 1:
                    subject_stats[s_name]["correct"] += 1

                if t_name not in topic_stats:
                    topic_stats[t_name] = {"topic_name": t_name, "subject_name": s_name, "attempted": 0, "correct": 0}
                topic_stats[t_name]["attempted"] += 1
                if r["is_correct"] == 1:
                    topic_stats[t_name]["correct"] += 1

            # Identify weak subjects (< 50% accuracy with at least 2 attempts, or lowest accuracy)
            subject_performance = []
            for s_name, st in subject_stats.items():
                acc = round((st["correct"] / st["attempted"]) * 100, 1) if st["attempted"] > 0 else 0.0
                subject_performance.append({
                    "subject_name": s_name,
                    "attempted": st["attempted"],
                    "correct": st["correct"],
                    "accuracy_percent": acc,
                })
            subject_performance.sort(key=lambda x: x["accuracy_percent"])

            weak_subjects = [s for s in subject_performance if s["accuracy_percent"] < 60.0]
            if not weak_subjects and subject_performance:
                weak_subjects = [subject_performance[0]]

            # Identify weak topics
            topic_performance = []
            for t_name, st in topic_stats.items():
                acc = round((st["correct"] / st["attempted"]) * 100, 1) if st["attempted"] > 0 else 0.0
                topic_performance.append({
                    "topic_name": t_name,
                    "subject_name": st["subject_name"],
                    "attempted": st["attempted"],
                    "correct": st["correct"],
                    "accuracy_percent": acc,
                })
            topic_performance.sort(key=lambda x: x["accuracy_percent"])
            weak_topics = [t for t in topic_performance if t["accuracy_percent"] < 50.0][:6]

            # Generate structured recommendations
            recommendations = []
            for ws in weak_subjects[:3]:
                recommendations.append(
                    f"Prioritize '{ws['subject_name']}': Current accuracy is {ws['accuracy_percent']}% ({ws['correct']}/{ws['attempted']} correct). Revisit core formulas and practice 1-mark PYQs."
                )
            for wt in weak_topics[:3]:
                recommendations.append(
                    f"Drill topic '{wt['topic_name']}' ({wt['subject_name']}): Accuracy is {wt['accuracy_percent']}%. Solve related questions in the Question Bank."
                )

            # Query test count
            test_count = conn.execute("SELECT COUNT(*) FROM test_results").fetchone()[0]

            return {
                "agent_name": "Performance Agent",
                "status": "active",
                "total_attempts": total_attempts,
                "correct_count": correct_count,
                "incorrect_count": total_attempts - correct_count,
                "accuracy_percentage": overall_accuracy,
                "tests_completed": test_count,
                "subject_performance": subject_performance,
                "weak_subjects": weak_subjects,
                "weak_topics": weak_topics,
                "recommendations": recommendations,
            }
        finally:
            conn.close()


class QuestionAssistant:
    """Deterministic agent that decomposes questions and provides step-by-step verified explanations."""

    @staticmethod
    def assist(question_id: str) -> Dict[str, Any]:
        conn = get_db_connection()
        try:
            q_row = conn.execute("SELECT * FROM questions WHERE id = ?", (question_id,)).fetchone()
            if not q_row:
                return {"error": "Question not found", "question_id": question_id}

            q_data = dict(q_row)

            # Options
            opts = conn.execute(
                "SELECT option_label, option_text, is_correct FROM question_options WHERE question_id = ? ORDER BY option_label",
                (question_id,),
            ).fetchall()
            options = [dict(o) for o in opts]

            # Answer key
            ak_row = conn.execute("SELECT * FROM answer_keys WHERE question_id = ?", (question_id,)).fetchone()
            ak_data = dict(ak_row) if ak_row else None

            # Assets
            asset_rows = conn.execute(
                "SELECT id, asset_role, asset_type, option_label, relative_path FROM question_visual_assets WHERE question_id = ?",
                (question_id,),
            ).fetchall()
            visual_assets = [dict(a) for a in asset_rows]

            correct_opts = []
            if ak_data and ak_data.get("correct_options_json"):
                try:
                    correct_opts = json.loads(ak_data["correct_options_json"])
                except Exception:
                    correct_opts = []

            provenance = ak_data.get("provenance") if ak_data else "unverified"
            stored_explanation = ak_data.get("explanation") if ak_data else None

            # Build structured conceptual breakdown
            has_official_key = bool(correct_opts) or (ak_data and ak_data.get("numerical_min") is not None)

            # Decomposition
            breakdown = {
                "agent_name": "Question Assistant Agent",
                "question_id": question_id,
                "paper_code": q_data.get("paper_code"),
                "year": q_data.get("examination_year"),
                "question_number": q_data.get("question_number"),
                "question_type": q_data.get("question_type"),
                "marks": q_data.get("marks"),
                "negative_marks": q_data.get("negative_marks"),
                "subject_name": q_data.get("subject_name"),
                "primary_topic_name": q_data.get("primary_topic_name"),
                "subtopic_name": q_data.get("subtopic_name"),
                "difficulty_level": q_data.get("difficulty_level"),
                "question_text": q_data.get("question_text"),
                "options": options,
                "visual_assets": visual_assets,
                "official_answer": {
                    "is_verified": has_official_key,
                    "correct_options": correct_opts,
                    "numerical_range": [ak_data.get("numerical_min"), ak_data.get("numerical_max")] if ak_data and ak_data.get("numerical_min") is not None else None,
                    "provenance": provenance,
                },
                "official_explanation": stored_explanation,
                "explanation_available": bool(stored_explanation),
                "guidance": (
                    f"Official GATE Answer: {', '.join(correct_opts)}."
                    if correct_opts else
                    f"Official numerical range: [{ak_data.get('numerical_min')}, {ak_data.get('numerical_max')}]."
                    if ak_data and ak_data.get("numerical_min") is not None else
                    "Official answer key unverified for this question in active dataset."
                ),
                "concepts": [
                    f"Discipline: GATE {q_data.get('paper_code')}",
                    f"Syllabus Subject: {q_data.get('subject_name')}",
                    f"Key Concept: {q_data.get('primary_topic_name')}",
                    f"Evaluation: {q_data.get('question_type')} ({q_data.get('marks')} Mark{'s' if q_data.get('marks', 1) > 1 else ''})",
                ],
                "hints": [
                    f"Review fundamentals of {q_data.get('primary_topic_name', 'this topic')}.",
                    f"Check standard theorems and relations in {q_data.get('subject_name', 'this subject')}.",
                ],
            }

            return breakdown
        finally:
            conn.close()


class PaperAnalysisAgent:
    """Deterministic agent that provides deep structural analysis of any selected GATE paper."""

    @staticmethod
    def analyze(paper_id: Optional[str] = None, year: Optional[int] = None, paper_code: str = "CS") -> Dict[str, Any]:
        conn = get_db_connection()
        try:
            # Locate paper
            if paper_id:
                qp = conn.execute("SELECT * FROM question_papers WHERE id = ?", (paper_id,)).fetchone()
            elif year:
                qp = conn.execute("SELECT * FROM question_papers WHERE examination_year = ? AND paper_code = ?", (year, paper_code)).fetchone()
            else:
                qp = conn.execute("SELECT * FROM question_papers WHERE paper_code = ? ORDER BY examination_year DESC LIMIT 1", (paper_code,)).fetchone()

            if not qp:
                return {
                    "agent_name": "Paper Analysis Agent",
                    "status": "not_found",
                    "message": "No matching question paper found in the database.",
                }

            qp_data = dict(qp)
            paper_real_id = qp_data["id"]
            p_year = qp_data["examination_year"]
            p_code = qp_data["paper_code"]

            # Query questions for this paper
            questions = conn.execute(
                "SELECT * FROM questions WHERE question_paper_id = ? OR (examination_year = ? AND paper_code = ?) ORDER BY question_number ASC",
                (paper_real_id, p_year, p_code),
            ).fetchall()

            total_q = len(questions)
            if total_q == 0:
                return {
                    "agent_name": "Paper Analysis Agent",
                    "paper_title": qp_data.get("title", f"GATE {p_code} {p_year}"),
                    "year": p_year,
                    "paper_code": p_code,
                    "total_questions": 0,
                    "status": "incomplete_or_pending",
                    "message": "Paper record exists in catalog, but digital questions have not been ingested yet.",
                }

            total_marks = sum(q["marks"] for q in questions if q["marks"])

            # Subject breakdown
            subj_counts: Dict[str, Dict[str, Any]] = {}
            ga_questions = 0
            ga_marks = 0.0
            core_questions = 0
            core_marks = 0.0

            type_counts: Dict[str, int] = {}
            marks_counts: Dict[str, int] = {}

            # Answer key coverage
            q_ids = [q["id"] for q in questions]
            verified_keys = 0
            if q_ids:
                placeholders = ",".join(["?"] * len(q_ids))
                ak_count = conn.execute(
                    f"SELECT COUNT(*) FROM answer_keys WHERE question_id IN ({placeholders}) AND (correct_options_json != '[]' OR numerical_min IS NOT NULL)",
                    tuple(q_ids),
                ).fetchone()[0]
                verified_keys = ak_count

            for q in questions:
                s_name = q["subject_name"] or "General Aptitude"
                m = q["marks"] or 1.0
                q_type = q["question_type"] or "MCQ"

                is_ga = "aptitude" in s_name.lower() or "general" in s_name.lower() or (q["question_number"] and q["question_number"] >= 56)
                if is_ga:
                    ga_questions += 1
                    ga_marks += m
                else:
                    core_questions += 1
                    core_marks += m

                if s_name not in subj_counts:
                    subj_counts[s_name] = {"subject_name": s_name, "count": 0, "marks": 0.0}
                subj_counts[s_name]["count"] += 1
                subj_counts[s_name]["marks"] += m

                type_counts[q_type] = type_counts.get(q_type, 0) + 1
                m_label = f"{int(m)} Mark"
                marks_counts[m_label] = marks_counts.get(m_label, 0) + 1

            sorted_subjects = sorted(subj_counts.values(), key=lambda x: x["count"], reverse=True)

            return {
                "agent_name": "Paper Analysis Agent",
                "paper_title": qp_data.get("title", f"GATE {p_code} {p_year}"),
                "paper_code": p_code,
                "year": p_year,
                "session": qp_data.get("session_set", "Set-1"),
                "total_questions": total_q,
                "total_marks": total_marks,
                "general_aptitude": {
                    "question_count": ga_questions,
                    "marks": ga_marks,
                    "target_marks": 15,
                },
                "core_subject": {
                    "question_count": core_questions,
                    "marks": core_marks,
                    "target_marks": 85,
                },
                "question_types": type_counts,
                "marks_distribution": marks_counts,
                "subject_breakdown": sorted_subjects,
                "verified_answer_keys": verified_keys,
                "answer_key_coverage_percent": round((verified_keys / total_q) * 100, 1) if total_q > 0 else 0.0,
                "summary": [
                    f"Paper contains {total_q} questions totaling {int(total_marks)} marks.",
                    f"General Aptitude: {ga_questions} questions ({int(ga_marks)} marks); Core: {core_questions} questions ({int(core_marks)} marks).",
                    f"Answer key coverage: {verified_keys}/{total_q} ({round((verified_keys/total_q)*100, 1)}%).",
                ],
            }
        finally:
            conn.close()
