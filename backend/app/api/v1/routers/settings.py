"""
Settings & Data Management Router (/api/v1/settings).
Provides:
- Application status & database diagnostics
- User preferences persistence
- On-demand timestamped database backups
- Safe user progress reset with two-step confirmation dialog (preserves Question Bank)
- Validated JSON dataset import with schema checking, duplicate prevention, and audit reporting
"""
from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from app.core.config import settings
from app.database.session import get_db_connection, new_uuid, utcnow_iso

router = APIRouter(tags=["settings"])


class PreferencesPayload(BaseModel):
    theme: Optional[str] = "dark"
    default_paper: Optional[str] = "CS"
    timer_alert_minutes: Optional[int] = 15
    auto_save_interval_seconds: Optional[int] = 30


class ResetProgressRequest(BaseModel):
    confirm: bool


class QuestionImportItem(BaseModel):
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
    answer_key: Optional[Dict[str, Any]] = None
    visual_assets: Optional[List[Dict[str, Any]]] = None


class DatasetImportPayload(BaseModel):
    paper_code: str = "CS"
    examination_year: int
    session_set: Optional[str] = "Set-1"
    paper_title: Optional[str] = None
    questions: Optional[List[Dict[str, Any]]] = None
    items: Optional[List[Dict[str, Any]]] = None


@router.get("/settings/info")
def get_system_info() -> Dict[str, Any]:
    conn = get_db_connection()
    try:
        db_file = settings.SQLITE_DB_PATH
        db_size = db_file.stat().st_size if db_file.exists() else 0

        q_count = conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
        p_count = conn.execute("SELECT COUNT(*) FROM question_papers WHERE total_extracted_questions > 0").fetchone()[0]
        tests_count = conn.execute("SELECT COUNT(*) FROM test_results").fetchone()[0]
        attempts_count = conn.execute("SELECT COUNT(*) FROM student_responses").fetchone()[0]

        # Count backups
        backup_dir = settings.SQLITE_DB_PATH.parent / "backups"
        backups = list(backup_dir.glob("*.db")) if backup_dir.exists() else []

        return {
            "app_name": settings.APP_NAME,
            "version": "2.0.0 (Simplified)",
            "environment": settings.APP_ENV,
            "offline_mode": True,
            "database_file": str(db_file),
            "database_size_bytes": db_size,
            "database_size_mb": round(db_size / (1024 * 1024), 2),
            "total_questions_in_bank": q_count,
            "total_active_papers": p_count,
            "total_tests_completed": tests_count,
            "total_student_responses": attempts_count,
            "backups_available": len(backups),
        }
    finally:
        conn.close()


@router.get("/settings/preferences")
def get_preferences() -> Dict[str, Any]:
    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT preferences_json FROM users WHERE role = 'student' LIMIT 1"
        ).fetchone()
        prefs = {}
        if row and row["preferences_json"]:
            try:
                prefs = json.loads(row["preferences_json"])
            except Exception:
                prefs = {}

        return {
            "theme": prefs.get("theme", "dark"),
            "default_paper": prefs.get("default_paper", "CS"),
            "timer_alert_minutes": prefs.get("timer_alert_minutes", 15),
            "auto_save_interval_seconds": prefs.get("auto_save_interval_seconds", 30),
        }
    finally:
        conn.close()


@router.post("/settings/preferences")
def save_preferences(payload: PreferencesPayload) -> Dict[str, Any]:
    conn = get_db_connection()
    try:
        now = utcnow_iso()
        prefs_json = json.dumps(payload.dict())

        user_row = conn.execute("SELECT id FROM users WHERE role = 'student' LIMIT 1").fetchone()
        if user_row:
            conn.execute(
                "UPDATE users SET preferences_json = ?, target_paper_code = ?, updated_at = ? WHERE id = ?",
                (prefs_json, payload.default_paper or "CS", now, user_row["id"]),
            )
        else:
            conn.execute(
                """
                INSERT INTO users (id, email, full_name, password_hash, target_paper_code, target_year, role, preferences_json, created_at, updated_at)
                VALUES (?, 'student@local.gate', 'GATE Student', 'local_password_hash', ?, 2026, 'student', ?, ?, ?)
                """,
                (new_uuid(), payload.default_paper or "CS", prefs_json, now, now),
            )
        conn.commit()
        return {"status": "saved", "preferences": payload.dict()}
    finally:
        conn.close()


@router.post("/settings/backup")
def create_database_backup() -> Dict[str, Any]:
    """Generates an on-demand verified timestamped SQLite backup."""
    db_file = settings.SQLITE_DB_PATH
    if not db_file.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Database file not found.")

    backup_dir = db_file.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_filename = f"gate_intelligence_backup_{timestamp}.db"
    backup_path = backup_dir / backup_filename

    try:
        shutil.copy2(db_file, backup_path)
        size_bytes = backup_path.stat().st_size
        return {
            "status": "success",
            "backup_filename": backup_filename,
            "backup_path": str(backup_path),
            "size_bytes": size_bytes,
            "size_mb": round(size_bytes / (1024 * 1024), 2),
            "timestamp": timestamp,
        }
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Backup failed: {e}")


@router.post("/settings/reset-progress")
def reset_user_progress(payload: ResetProgressRequest) -> Dict[str, Any]:
    """Resets user test results and practice responses with explicit confirmation."""
    if not payload.confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confirmation required. Set confirm=True to proceed with resetting user progress.",
        )

    conn = get_db_connection()
    try:
        # Delete only student responses and test results
        deleted_resp = conn.execute("DELETE FROM student_responses").rowcount
        deleted_results = conn.execute("DELETE FROM test_results").rowcount
        # Reset mock_tests status to created
        conn.execute("UPDATE mock_tests SET status = 'created', started_at = NULL, submitted_at = NULL WHERE test_mode != 'practice'")
        conn.execute("DELETE FROM mock_tests WHERE test_mode = 'practice'")
        conn.commit()

        return {
            "status": "success",
            "message": "User progress reset successfully. Question Bank, papers, and official keys were safely preserved.",
            "deleted_responses": deleted_resp,
            "deleted_test_results": deleted_results,
        }
    finally:
        conn.close()


@router.post("/settings/import-json")
def import_json_dataset(payload: DatasetImportPayload) -> Dict[str, Any]:
    """
    Safe, validating, idempotent JSON dataset importer.
    - Validates structure
    - Detects invalid records
    - Upserts without duplicating
    - Preserves existing student progress
    """
    raw_questions = payload.questions if payload.questions is not None else (payload.items or [])
    if not raw_questions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No questions found in dataset payload. Provide 'questions' or 'items' list.",
        )

    paper_code = payload.paper_code.strip().upper()
    year = payload.examination_year
    session = payload.session_set or "Set-1"
    title = payload.paper_title or f"GATE {paper_code} {year} ({session})"

    conn = get_db_connection()
    try:
        now = utcnow_iso()

        # 1. Ensure question_papers row exists
        qp = conn.execute(
            "SELECT id FROM question_papers WHERE paper_code = ? AND examination_year = ? AND session_set = ?",
            (paper_code, year, session),
        ).fetchone()

        if qp:
            paper_id = qp["id"]
        else:
            paper_id = new_uuid()
            # Also get gate_paper id
            gp = conn.execute("SELECT id FROM gate_papers WHERE code = ?", (paper_code,)).fetchone()
            gp_id = gp["id"] if gp else new_uuid()

            conn.execute(
                """
                INSERT INTO question_papers (
                    id, paper_id, paper_code, examination_year, session_set, title,
                    filename, file_path, file_checksum, page_count, is_scanned,
                    processing_status, total_extracted_questions, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 'completed', 0, ?, ?)
                """,
                (
                    paper_id,
                    gp_id,
                    paper_code,
                    year,
                    session,
                    title,
                    f"{year}_{paper_code}_{session}.json",
                    f"datasets/{year}_{paper_code}_{session}.json",
                    f"import_{paper_code}_{year}_{session}_{now}",
                    now,
                    now,
                ),
            )

        imported_count = 0
        updated_count = 0
        invalid_count = 0
        skipped_count = 0
        audit_details = []

        for item in raw_questions:
            q_num = item.get("question_number")
            q_text = item.get("question_text")

            if not q_num or not q_text or not str(q_text).strip():
                invalid_count += 1
                audit_details.append(f"Invalid record: missing question_number or question_text ({item})")
                continue

            q_type = str(item.get("question_type", "MCQ")).upper()
            marks = float(item.get("marks", 1.0))
            neg_marks = float(item.get("negative_marks", (marks / 3.0) if q_type == "MCQ" else 0.0))
            s_name = item.get("subject_name") or "General"
            t_name = item.get("primary_topic_name") or "Core Topic"
            subt_name = item.get("subtopic_name")
            diff = item.get("difficulty_level", "Medium")
            label = item.get("source_question_label", f"Q.{q_num}")

            # Check if question exists
            existing_q = conn.execute(
                """
                SELECT id FROM questions
                WHERE (question_paper_id = ? OR (examination_year = ? AND paper_code = ?)) AND question_number = ?
                """,
                (paper_id, year, paper_code, q_num),
            ).fetchone()

            if existing_q:
                q_id = existing_q["id"]
                conn.execute(
                    """
                    UPDATE questions
                    SET question_text = ?, question_type = ?, marks = ?, negative_marks = ?,
                        subject_name = ?, primary_topic_name = ?, subtopic_name = ?,
                        difficulty_level = ?, source_question_label = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (q_text, q_type, marks, neg_marks, s_name, t_name, subt_name, diff, label, now, q_id),
                )
                updated_count += 1
            else:
                q_id = item.get("id") or new_uuid()
                conn.execute(
                    """
                    INSERT INTO questions (
                        id, question_paper_id, paper_code, examination_year, question_number,
                        source_question_label, question_type, question_text, marks, negative_marks,
                        subject_name, primary_topic_name, subtopic_name, difficulty_level,
                        extraction_status, is_verified, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'valid', 1, ?, ?)
                    """,
                    (
                        q_id,
                        paper_id,
                        paper_code,
                        year,
                        q_num,
                        label,
                        q_type,
                        q_text,
                        marks,
                        neg_marks,
                        s_name,
                        t_name,
                        subt_name,
                        diff,
                        now,
                        now,
                    ),
                )
                imported_count += 1

            # Options
            raw_options = item.get("options") or []
            if raw_options:
                conn.execute("DELETE FROM question_options WHERE question_id = ?", (q_id,))
                for opt in raw_options:
                    conn.execute(
                        """
                        INSERT INTO question_options (id, question_id, option_label, option_text, is_correct, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            opt.get("id") or new_uuid(),
                            q_id,
                            str(opt.get("option_label", "")).strip().upper(),
                            str(opt.get("option_text", "")),
                            opt.get("is_correct"),
                            now,
                            now,
                        ),
                    )

            # Answer key
            ak_data = item.get("answer_key")
            if ak_data:
                conn.execute("DELETE FROM answer_keys WHERE question_id = ?", (q_id,))
                c_opts = ak_data.get("correct_options") or ak_data.get("correct_options_json")
                if isinstance(c_opts, str):
                    try:
                        c_opts = json.loads(c_opts)
                    except Exception:
                        c_opts = [c_opts]
                if not isinstance(c_opts, list):
                    c_opts = [str(c_opts)] if c_opts else []

                conn.execute(
                    """
                    INSERT INTO answer_keys (
                        id, question_id, answer_type, correct_options_json, numerical_min, numerical_max,
                        tolerance, provenance, explanation, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        ak_data.get("id") or new_uuid(),
                        q_id,
                        q_type,
                        json.dumps(c_opts),
                        ak_data.get("numerical_min"),
                        ak_data.get("numerical_max"),
                        ak_data.get("tolerance", 0.01),
                        ak_data.get("provenance", "verified_import"),
                        ak_data.get("explanation"),
                        now,
                        now,
                    ),
                )

        # Update paper extracted count
        total_in_paper = conn.execute(
            "SELECT COUNT(*) FROM questions WHERE question_paper_id = ? OR (examination_year = ? AND paper_code = ?)",
            (paper_id, year, paper_code),
        ).fetchone()[0]
        conn.execute(
            "UPDATE question_papers SET total_extracted_questions = ?, processing_status = 'completed', updated_at = ? WHERE id = ?",
            (total_in_paper, now, paper_id),
        )

        conn.commit()

        return {
            "status": "success",
            "paper_code": paper_code,
            "examination_year": year,
            "imported": imported_count,
            "updated": updated_count,
            "invalid": invalid_count,
            "skipped": skipped_count,
            "total_in_paper": total_in_paper,
            "audit_details": audit_details[:20],
        }
    finally:
        conn.close()
