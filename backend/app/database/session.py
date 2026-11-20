"""
Parameterized Relational Database Engine & Repository for GATE Intelligence.
Creates and manages all 19 required tables with UUID primary keys, foreign keys, indexes,
timestamps, and cosine vector similarity queries.
"""
from __future__ import annotations

import json
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.config import settings

# Add repo root so exam.gate.taxonomy_loader is importable
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from exam.gate.taxonomy_loader import GateTaxonomyLoader


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_uuid() -> str:
    return str(uuid.uuid4())


SCHEMA_DDL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    full_name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    target_paper_code TEXT NOT NULL DEFAULT 'CS',
    target_year INTEGER NOT NULL DEFAULT 2026,
    role TEXT NOT NULL DEFAULT 'student',
    preferences_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_users_email ON users(email);

CREATE TABLE IF NOT EXISTS gate_papers (
    id TEXT PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'Engineering',
    active_from INTEGER NOT NULL DEFAULT 1984,
    active_to INTEGER,
    ga_marks INTEGER NOT NULL DEFAULT 15,
    eng_math_marks INTEGER NOT NULL DEFAULT 13,
    subject_marks INTEGER NOT NULL DEFAULT 72,
    allowed_second_papers TEXT NOT NULL DEFAULT '[]',
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_gate_papers_code ON gate_papers(code);

CREATE TABLE IF NOT EXISTS syllabus_versions (
    id TEXT PRIMARY KEY,
    paper_id TEXT NOT NULL REFERENCES gate_papers(id) ON DELETE CASCADE,
    version_tag TEXT NOT NULL,
    valid_from_year INTEGER NOT NULL,
    valid_to_year INTEGER,
    source_url TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(paper_id, version_tag)
);
CREATE INDEX IF NOT EXISTS ix_syllabus_versions_paper ON syllabus_versions(paper_id);

CREATE TABLE IF NOT EXISTS subjects (
    id TEXT PRIMARY KEY,
    paper_id TEXT NOT NULL REFERENCES gate_papers(id) ON DELETE CASCADE,
    syllabus_version_id TEXT NOT NULL REFERENCES syllabus_versions(id) ON DELETE CASCADE,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    weightage_estimate REAL NOT NULL DEFAULT 0.1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_subjects_paper ON subjects(paper_id);
CREATE INDEX IF NOT EXISTS ix_subjects_name ON subjects(name);

CREATE TABLE IF NOT EXISTS topics (
    id TEXT PRIMARY KEY,
    subject_id TEXT NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    subtopics_json TEXT NOT NULL DEFAULT '[]',
    keywords_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_topics_subject ON topics(subject_id);
CREATE INDEX IF NOT EXISTS ix_topics_name ON topics(name);

CREATE TABLE IF NOT EXISTS question_papers (
    id TEXT PRIMARY KEY,
    uploaded_by TEXT REFERENCES users(id) ON DELETE SET NULL,
    paper_id TEXT NOT NULL REFERENCES gate_papers(id) ON DELETE RESTRICT,
    paper_code TEXT NOT NULL,
    examination_year INTEGER NOT NULL,
    session_set TEXT NOT NULL DEFAULT 'Set-1',
    title TEXT NOT NULL,
    filename TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_checksum TEXT UNIQUE NOT NULL,
    page_count INTEGER NOT NULL DEFAULT 0,
    is_scanned INTEGER NOT NULL DEFAULT 0,
    processing_status TEXT NOT NULL DEFAULT 'pending',
    total_extracted_questions INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(paper_code, examination_year, session_set, file_checksum)
);
CREATE INDEX IF NOT EXISTS ix_qp_paper_code ON question_papers(paper_code);
CREATE INDEX IF NOT EXISTS ix_qp_year ON question_papers(examination_year);
CREATE INDEX IF NOT EXISTS ix_qp_checksum ON question_papers(file_checksum);

CREATE TABLE IF NOT EXISTS questions (
    id TEXT PRIMARY KEY,
    question_paper_id TEXT REFERENCES question_papers(id) ON DELETE CASCADE,
    paper_code TEXT NOT NULL,
    examination_year INTEGER NOT NULL,
    question_number INTEGER NOT NULL,
    source_question_label TEXT NOT NULL DEFAULT 'UNKNOWN',
    question_type TEXT NOT NULL,
    question_text TEXT NOT NULL,
    math_expressions_json TEXT NOT NULL DEFAULT '[]',
    has_diagram_or_table INTEGER NOT NULL DEFAULT 0,
    marks REAL NOT NULL DEFAULT 1.0,
    negative_marks REAL NOT NULL DEFAULT 0.3333333333,
    page_number INTEGER NOT NULL DEFAULT 1,
    source_page_start INTEGER NOT NULL DEFAULT 1,
    source_page_end INTEGER NOT NULL DEFAULT 1,
    subject_name TEXT,
    primary_topic_name TEXT,
    subtopic_name TEXT,
    difficulty_level TEXT NOT NULL DEFAULT 'Medium',
    syllabus_version_tag TEXT NOT NULL DEFAULT '2026.1',
    extraction_status TEXT NOT NULL DEFAULT 'uncertain',
    extraction_warnings TEXT NOT NULL DEFAULT '[]',
    extraction_confidence REAL NOT NULL DEFAULT 0.9,
    classification_confidence REAL NOT NULL DEFAULT 0.85,
    needs_human_review INTEGER NOT NULL DEFAULT 0,
    is_verified INTEGER NOT NULL DEFAULT 0,
    is_ai_generated INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_questions_paper_year ON questions(paper_code, examination_year);
CREATE INDEX IF NOT EXISTS ix_questions_subject ON questions(subject_name);
CREATE INDEX IF NOT EXISTS ix_questions_topic ON questions(primary_topic_name);
CREATE INDEX IF NOT EXISTS ix_questions_type ON questions(question_type);

CREATE TABLE IF NOT EXISTS question_options (
    id TEXT PRIMARY KEY,
    question_id TEXT NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    option_label TEXT NOT NULL,
    option_text TEXT NOT NULL,
    is_correct INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_question_options_qid ON question_options(question_id);

CREATE TABLE IF NOT EXISTS answer_keys (
    id TEXT PRIMARY KEY,
    question_id TEXT NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    answer_type TEXT NOT NULL,
    correct_options_json TEXT NOT NULL DEFAULT '[]',
    numerical_min REAL,
    numerical_max REAL,
    tolerance REAL NOT NULL DEFAULT 0.01,
    provenance TEXT NOT NULL DEFAULT 'unverified',
    explanation TEXT,
    verified_by TEXT REFERENCES users(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_answer_keys_qid ON answer_keys(question_id);

CREATE TABLE IF NOT EXISTS question_topics (
    id TEXT PRIMARY KEY,
    question_id TEXT NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    topic_id TEXT REFERENCES topics(id) ON DELETE CASCADE,
    subject_name TEXT NOT NULL,
    topic_name TEXT NOT NULL,
    subtopic_name TEXT,
    confidence REAL NOT NULL DEFAULT 0.85,
    is_primary INTEGER NOT NULL DEFAULT 1,
    syllabus_version_tag TEXT NOT NULL DEFAULT '2026.1',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_question_topics_qid ON question_topics(question_id);

CREATE TABLE IF NOT EXISTS question_embeddings (
    id TEXT PRIMARY KEY,
    question_id TEXT NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    model_name TEXT NOT NULL,
    embedding_version TEXT NOT NULL,
    dimension INTEGER NOT NULL DEFAULT 384,
    embedding_vector TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(question_id, embedding_version)
);
CREATE INDEX IF NOT EXISTS ix_question_embeddings_qid ON question_embeddings(question_id);

CREATE TABLE IF NOT EXISTS question_similarities (
    id TEXT PRIMARY KEY,
    source_question_id TEXT NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    target_question_id TEXT NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    similarity_type TEXT NOT NULL,
    similarity_score REAL NOT NULL,
    tfidf_score REAL NOT NULL DEFAULT 0.0,
    embedding_score REAL NOT NULL DEFAULT 0.0,
    verification_notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_qsim_source ON question_similarities(source_question_id);
CREATE INDEX IF NOT EXISTS ix_qsim_target ON question_similarities(target_question_id);

CREATE TABLE IF NOT EXISTS mock_tests (
    id TEXT PRIMARY KEY,
    created_by TEXT REFERENCES users(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    paper_code TEXT NOT NULL,
    test_mode TEXT NOT NULL,
    duration_minutes INTEGER NOT NULL DEFAULT 180,
    total_questions INTEGER NOT NULL DEFAULT 65,
    total_marks REAL NOT NULL DEFAULT 100.0,
    config_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'created',
    started_at TEXT,
    submitted_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_mock_tests_user ON mock_tests(created_by);

CREATE TABLE IF NOT EXISTS test_questions (
    id TEXT PRIMARY KEY,
    mock_test_id TEXT NOT NULL REFERENCES mock_tests(id) ON DELETE CASCADE,
    question_id TEXT NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    display_order INTEGER NOT NULL,
    section_name TEXT NOT NULL DEFAULT 'Technical',
    marks REAL NOT NULL DEFAULT 1.0,
    negative_marks REAL NOT NULL DEFAULT 0.3333333333,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_test_questions_test ON test_questions(mock_test_id);

CREATE TABLE IF NOT EXISTS student_responses (
    id TEXT PRIMARY KEY,
    mock_test_id TEXT NOT NULL REFERENCES mock_tests(id) ON DELETE CASCADE,
    question_id TEXT NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
    selected_options_json TEXT NOT NULL DEFAULT '[]',
    numerical_answer REAL,
    marked_for_review INTEGER NOT NULL DEFAULT 0,
    time_spent_seconds INTEGER NOT NULL DEFAULT 0,
    is_correct INTEGER,
    marks_awarded REAL NOT NULL DEFAULT 0.0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_student_responses_test ON student_responses(mock_test_id);

CREATE TABLE IF NOT EXISTS test_results (
    id TEXT PRIMARY KEY,
    mock_test_id TEXT NOT NULL REFERENCES mock_tests(id) ON DELETE CASCADE,
    user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
    total_marks REAL NOT NULL,
    marks_obtained REAL NOT NULL,
    accuracy_percent REAL NOT NULL,
    attempted_count INTEGER NOT NULL,
    correct_count INTEGER NOT NULL,
    incorrect_count INTEGER NOT NULL,
    unattempted_count INTEGER NOT NULL,
    time_taken_seconds INTEGER NOT NULL DEFAULT 0,
    weak_subjects_json TEXT NOT NULL DEFAULT '[]',
    weak_topics_json TEXT NOT NULL DEFAULT '[]',
    subject_breakdown_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_test_results_test ON test_results(mock_test_id);

CREATE TABLE IF NOT EXISTS study_plans (
    id TEXT PRIMARY KEY,
    user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
    paper_code TEXT NOT NULL,
    target_year INTEGER NOT NULL DEFAULT 2026,
    available_days INTEGER NOT NULL DEFAULT 60,
    daily_hours REAL NOT NULL DEFAULT 4.0,
    roadmap_json TEXT NOT NULL DEFAULT '[]',
    weak_topics_json TEXT NOT NULL DEFAULT '[]',
    recommended_tests_json TEXT NOT NULL DEFAULT '[]',
    progress_percent REAL NOT NULL DEFAULT 0.0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_study_plans_user ON study_plans(user_id);

CREATE TABLE IF NOT EXISTS agent_runs (
    id TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL,
    agent_name TEXT NOT NULL,
    status TEXT NOT NULL,
    input_summary TEXT,
    output_summary TEXT,
    prompt_tokens INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    duration_ms INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_agent_runs_workflow ON agent_runs(workflow_id);
CREATE INDEX IF NOT EXISTS ix_agent_runs_agent ON agent_runs(agent_name);

CREATE TABLE IF NOT EXISTS processing_jobs (
    id TEXT PRIMARY KEY,
    question_paper_id TEXT REFERENCES question_papers(id) ON DELETE CASCADE,
    user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
    job_type TEXT NOT NULL DEFAULT 'pdf_ingestion',
    status TEXT NOT NULL DEFAULT 'queued',
    current_stage TEXT NOT NULL DEFAULT 'initialized',
    progress_percent REAL NOT NULL DEFAULT 0.0,
    retry_count INTEGER NOT NULL DEFAULT 0,
    logs_json TEXT NOT NULL DEFAULT '[]',
    error_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_processing_jobs_qp ON processing_jobs(question_paper_id);
CREATE INDEX IF NOT EXISTS ix_processing_jobs_status ON processing_jobs(status);
"""


def get_db_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    target = db_path or settings.SQLITE_DB_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(target), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_database(db_path: Optional[Path] = None) -> None:
    """Create all 19 tables and seed official GATE paper taxonomy & syllabi (never fake questions)."""
    conn = get_db_connection(db_path)
    try:
        conn.executescript(SCHEMA_DDL)
        conn.commit()
        ensure_schema_migrations(conn)

        loader = GateTaxonomyLoader(settings.EXAM_GATE_DIR)
        papers = loader.list_papers()
        now = utcnow_iso()

        for p in papers:
            row = conn.execute(
                "SELECT id FROM gate_papers WHERE code = ?", (p["code"],)
            ).fetchone()
            if row is None:
                paper_id = new_uuid()
                conn.execute(
                    """
                    INSERT INTO gate_papers (
                        id, code, name, category, active_from, active_to,
                        ga_marks, eng_math_marks, subject_marks, allowed_second_papers, notes,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        paper_id,
                        p["code"],
                        p["name"],
                        p.get("category", "Engineering"),
                        p.get("active_from", 1984),
                        p.get("active_to"),
                        p.get("ga_marks", 15),
                        p.get("eng_math_marks", 13),
                        p.get("subject_marks", 72),
                        json.dumps(p.get("allowed_second_papers", [])),
                        p.get("notes"),
                        now,
                        now,
                    ),
                )
            else:
                paper_id = row["id"]

            # Seed official syllabus for papers that have detailed syllabus JSONs
            syllabus = loader.load_syllabus(p["code"], 2026)
            v_tag = syllabus.get("syllabus_version", "2026.1")
            sv_row = conn.execute(
                "SELECT id FROM syllabus_versions WHERE paper_id = ? AND version_tag = ?",
                (paper_id, v_tag),
            ).fetchone()
            if sv_row is None:
                sv_id = new_uuid()
                valid_years = syllabus.get("valid_years", [2026])
                conn.execute(
                    """
                    INSERT INTO syllabus_versions (
                        id, paper_id, version_tag, valid_from_year, valid_to_year,
                        source_url, is_active, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
                    """,
                    (
                        sv_id,
                        paper_id,
                        v_tag,
                        min(valid_years),
                        max(valid_years),
                        syllabus.get("source_url"),
                        now,
                        now,
                    ),
                )
                for subj in syllabus.get("subjects", []):
                    subj_id = new_uuid()
                    conn.execute(
                        """
                        INSERT INTO subjects (
                            id, paper_id, syllabus_version_id, code, name, weightage_estimate, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            subj_id,
                            paper_id,
                            sv_id,
                            subj["code"],
                            subj["name"],
                            float(subj.get("weightage_estimate", 0.1)),
                            now,
                            now,
                        ),
                    )
                    for top in subj.get("topics", []):
                        conn.execute(
                            """
                            INSERT INTO topics (
                                id, subject_id, name, subtopics_json, keywords_json, created_at, updated_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                new_uuid(),
                                subj_id,
                                top["name"],
                                json.dumps(top.get("subtopics", [])),
                                json.dumps(top.get("keywords", [])),
                                now,
                                now,
                            ),
                        )
        conn.commit()
    finally:
        conn.close()


def ensure_schema_migrations(conn: sqlite3.Connection) -> None:
    """
    Safe, non-destructive schema migration for existing SQLite databases.
    Requirements enforced:
    1. Existing records that lacked `source_question_label` prior to migration receive `'UNKNOWN'`
       (NEVER `'Q.1'`), `extraction_status = 'uncertain'`, and `needs_human_review = 1`.
    2. Existing records that were damaged by the previous `'Q.1'` default migration (where
       `question_number != 1` or where multiple unverified rows in the same paper defaulted to `'Q.1'`)
       are automatically repaired to `'UNKNOWN'` and marked for review.
    3. Valid original question labels and all existing records/relationships are strictly preserved.
    """
    existing_cols = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(questions);").fetchall()
    }
    had_label_col = "source_question_label" in existing_cols
    had_status_col = "extraction_status" in existing_cols
    had_warnings_col = "extraction_warnings" in existing_cols
    had_pstart_col = "source_page_start" in existing_cols
    had_pend_col = "source_page_end" in existing_cols

    if not had_label_col:
        conn.execute("ALTER TABLE questions ADD COLUMN source_question_label TEXT NOT NULL DEFAULT 'UNKNOWN';")
    if not had_status_col:
        conn.execute("ALTER TABLE questions ADD COLUMN extraction_status TEXT NOT NULL DEFAULT 'uncertain';")
    if not had_warnings_col:
        conn.execute("ALTER TABLE questions ADD COLUMN extraction_warnings TEXT NOT NULL DEFAULT '[]';")
    if not had_pstart_col:
        conn.execute("ALTER TABLE questions ADD COLUMN source_page_start INTEGER;")
    if not had_pend_col:
        conn.execute("ALTER TABLE questions ADD COLUMN source_page_end INTEGER;")

    # Backfill source_page_start and source_page_end from page_number where NULL
    conn.execute(
        "UPDATE questions SET source_page_start = COALESCE(source_page_start, page_number), "
        "source_page_end = COALESCE(source_page_end, page_number) "
        "WHERE source_page_start IS NULL OR source_page_end IS NULL;"
    )

    # If migrating a table that did NOT previously have `source_question_label`, all pre-existing
    # rows have unknown original label provenance -> mark them UNKNOWN and flag for human review.
    if not had_label_col:
        conn.execute(
            """
            UPDATE questions
            SET source_question_label = 'UNKNOWN',
                extraction_status = 'uncertain',
                needs_human_review = 1,
                extraction_warnings = '["Legacy record migrated without original question label; marked UNKNOWN for review."]'
            WHERE is_verified = 0;
            """
        )

    # Repair any rows corrupted by the previous unsafe DEFAULT 'Q.1' migration:
    # Case A: question_number != 1 but source_question_label == 'Q.1'
    conn.execute(
        """
        UPDATE questions
        SET source_question_label = 'UNKNOWN',
            extraction_status = 'uncertain',
            needs_human_review = 1
        WHERE source_question_label = 'Q.1' AND question_number != 1 AND is_verified = 0;
        """
    )

    # Case B: multiple unverified questions in the same paper having question_number = 1 and label = 'Q.1'
    dup_q1_papers = [
        r["question_paper_id"]
        for r in conn.execute(
            """
            SELECT question_paper_id
            FROM questions
            WHERE question_paper_id IS NOT NULL AND question_number = 1 AND source_question_label = 'Q.1'
            GROUP BY question_paper_id
            HAVING COUNT(*) > 1
            """
        ).fetchall()
    ]
    for pid in dup_q1_papers:
        conn.execute(
            """
            UPDATE questions
            SET source_question_label = 'UNKNOWN',
                extraction_status = 'uncertain',
                needs_human_review = 1
            WHERE question_paper_id = ? AND question_number = 1 AND is_verified = 0;
            """,
            (pid,),
        )

    # Ensure any row with source_question_label == 'UNKNOWN' is flagged for review
    conn.execute(
        """
        UPDATE questions
        SET extraction_status = 'uncertain',
            needs_human_review = 1
        WHERE source_question_label = 'UNKNOWN' AND is_verified = 0;
        """
    )

    conn.execute("CREATE INDEX IF NOT EXISTS ix_questions_extraction_status ON questions(extraction_status);")

    # Phase 8: question visual asset metadata.
    # Additive migration: does not modify existing questions, options or answer keys.
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS question_visual_assets (
            id TEXT PRIMARY KEY,
            question_id TEXT NOT NULL,
            asset_role TEXT NOT NULL DEFAULT 'option'
                CHECK (asset_role IN ('stem', 'option', 'full_page')),
            asset_type TEXT NOT NULL DEFAULT 'other',
            option_label TEXT,
            relative_path TEXT NOT NULL,
            source_page INTEGER NOT NULL,
            bbox_json TEXT NOT NULL,
            confidence REAL,
            review_status TEXT NOT NULL DEFAULT 'pending'
                CHECK (review_status IN ('pending', 'approved', 'rejected')),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (question_id)
                REFERENCES questions(id)
                ON DELETE CASCADE
        );
        """
    )

    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_question_visual_assets_question
        ON question_visual_assets(question_id);
        """
    )

    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_question_visual_assets_review
        ON question_visual_assets(review_status);
        """
    )

    conn.commit()
