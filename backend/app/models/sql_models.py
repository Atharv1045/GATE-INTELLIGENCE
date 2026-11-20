"""
PostgreSQL + pgvector SQLAlchemy 2.0 ORM Models for GATE Intelligence.
Defines all 19 required tables with UUID primary keys, foreign key constraints, indexes,
timestamps, provenance fields, and versioned vector embeddings.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from sqlalchemy import (
        Boolean,
        Column,
        DateTime,
        Float,
        ForeignKey,
        Index,
        Integer,
        String,
        Text,
        UniqueConstraint,
        JSON,
    )
    from sqlalchemy.dialects.postgresql import UUID as PG_UUID
    from sqlalchemy.orm import declarative_base, relationship

    try:
        from pgvector.sqlalchemy import Vector
    except ImportError:
        Vector = None

    Base = declarative_base()

    def utcnow() -> datetime:
        return datetime.now(timezone.utc)

    class User(Base):
        __tablename__ = "users"
        id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
        email = Column(String(255), unique=True, nullable=False, index=True)
        full_name = Column(String(255), nullable=False)
        password_hash = Column(String(512), nullable=False)
        target_paper_code = Column(String(16), nullable=False, default="CS")
        target_year = Column(Integer, nullable=False, default=2026)
        role = Column(String(32), nullable=False, default="student")
        preferences_json = Column(JSON, nullable=True)
        created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
        updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    class GatePaper(Base):
        __tablename__ = "gate_papers"
        id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
        code = Column(String(16), unique=True, nullable=False, index=True)
        name = Column(String(255), nullable=False)
        category = Column(String(64), nullable=False, default="Engineering")
        active_from = Column(Integer, nullable=False, default=1984)
        active_to = Column(Integer, nullable=True)
        ga_marks = Column(Integer, nullable=False, default=15)
        eng_math_marks = Column(Integer, nullable=False, default=13)
        subject_marks = Column(Integer, nullable=False, default=72)
        allowed_second_papers = Column(JSON, nullable=True)
        created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
        updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    class SyllabusVersion(Base):
        __tablename__ = "syllabus_versions"
        id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
        paper_id = Column(PG_UUID(as_uuid=True), ForeignKey("gate_papers.id", ondelete="CASCADE"), nullable=False, index=True)
        version_tag = Column(String(64), nullable=False)
        valid_from_year = Column(Integer, nullable=False)
        valid_to_year = Column(Integer, nullable=True)
        source_url = Column(String(512), nullable=True)
        is_active = Column(Boolean, default=True, nullable=False)
        created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
        updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
        __table_args__ = (UniqueConstraint("paper_id", "version_tag", name="uq_paper_syllabus_version"),)

    class Subject(Base):
        __tablename__ = "subjects"
        id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
        paper_id = Column(PG_UUID(as_uuid=True), ForeignKey("gate_papers.id", ondelete="CASCADE"), nullable=False, index=True)
        syllabus_version_id = Column(PG_UUID(as_uuid=True), ForeignKey("syllabus_versions.id", ondelete="CASCADE"), nullable=False, index=True)
        code = Column(String(32), nullable=False)
        name = Column(String(255), nullable=False, index=True)
        weightage_estimate = Column(Float, nullable=False, default=0.1)
        created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
        updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    class Topic(Base):
        __tablename__ = "topics"
        id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
        subject_id = Column(PG_UUID(as_uuid=True), ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True)
        name = Column(String(255), nullable=False, index=True)
        subtopics_json = Column(JSON, nullable=True)
        keywords_json = Column(JSON, nullable=True)
        created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
        updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    class QuestionPaper(Base):
        __tablename__ = "question_papers"
        id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
        uploaded_by = Column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
        paper_id = Column(PG_UUID(as_uuid=True), ForeignKey("gate_papers.id", ondelete="RESTRICT"), nullable=False, index=True)
        paper_code = Column(String(16), nullable=False, index=True)
        examination_year = Column(Integer, nullable=False, index=True)
        session_set = Column(String(32), nullable=False, default="Set-1")
        title = Column(String(255), nullable=False)
        filename = Column(String(255), nullable=False)
        file_path = Column(String(512), nullable=False)
        file_checksum = Column(String(64), unique=True, nullable=False, index=True)
        page_count = Column(Integer, nullable=False, default=0)
        is_scanned = Column(Boolean, nullable=False, default=False)
        processing_status = Column(String(32), nullable=False, default="pending", index=True)
        total_extracted_questions = Column(Integer, nullable=False, default=0)
        created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
        updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
        __table_args__ = (
            UniqueConstraint("paper_code", "examination_year", "session_set", "file_checksum", name="uq_unique_paper_ident"),
        )

    class Question(Base):
        __tablename__ = "questions"
        id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
        question_paper_id = Column(PG_UUID(as_uuid=True), ForeignKey("question_papers.id", ondelete="CASCADE"), nullable=True, index=True)
        paper_code = Column(String(16), nullable=False, index=True)
        examination_year = Column(Integer, nullable=False, index=True)
        question_number = Column(Integer, nullable=False)
        source_question_label = Column(String(32), nullable=False, default="UNKNOWN")
        question_type = Column(String(16), nullable=False, index=True)  # MCQ, MSQ, NAT
        question_text = Column(Text, nullable=False)
        math_expressions_json = Column(JSON, nullable=True)
        has_diagram_or_table = Column(Boolean, nullable=False, default=False)
        marks = Column(Float, nullable=False, default=1.0)
        negative_marks = Column(Float, nullable=False, default=0.3333333333)
        page_number = Column(Integer, nullable=False, default=1)
        source_page_start = Column(Integer, nullable=False, default=1)
        source_page_end = Column(Integer, nullable=False, default=1)
        subject_name = Column(String(255), nullable=True, index=True)
        primary_topic_name = Column(String(255), nullable=True, index=True)
        subtopic_name = Column(String(255), nullable=True)
        difficulty_level = Column(String(32), nullable=False, default="Medium")
        syllabus_version_tag = Column(String(64), nullable=False, default="2026.1")
        extraction_status = Column(String(32), nullable=False, default="uncertain", index=True)
        extraction_warnings = Column(JSON, nullable=True)
        extraction_confidence = Column(Float, nullable=False, default=0.9)
        classification_confidence = Column(Float, nullable=False, default=0.85)
        needs_human_review = Column(Boolean, nullable=False, default=False, index=True)
        is_verified = Column(Boolean, nullable=False, default=False, index=True)
        is_ai_generated = Column(Boolean, nullable=False, default=False, index=True)
        created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
        updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    class QuestionOption(Base):
        __tablename__ = "question_options"
        id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
        question_id = Column(PG_UUID(as_uuid=True), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True)
        option_label = Column(String(8), nullable=False)  # A, B, C, D
        option_text = Column(Text, nullable=False)
        is_correct = Column(Boolean, nullable=True)
        created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
        updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    class AnswerKey(Base):
        __tablename__ = "answer_keys"
        id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
        question_id = Column(PG_UUID(as_uuid=True), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True)
        answer_type = Column(String(16), nullable=False)  # MCQ, MSQ, NAT
        correct_options_json = Column(JSON, nullable=True)  # e.g. ["A"] or ["A", "C"]
        numerical_min = Column(Float, nullable=True)
        numerical_max = Column(Float, nullable=True)
        tolerance = Column(Float, nullable=False, default=0.01)
        provenance = Column(String(32), nullable=False, default="unverified")  # official_key, manually_verified, ai_generated, unverified
        explanation = Column(Text, nullable=True)
        verified_by = Column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
        created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
        updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    class QuestionTopic(Base):
        __tablename__ = "question_topics"
        id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
        question_id = Column(PG_UUID(as_uuid=True), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True)
        topic_id = Column(PG_UUID(as_uuid=True), ForeignKey("topics.id", ondelete="CASCADE"), nullable=True, index=True)
        subject_name = Column(String(255), nullable=False)
        topic_name = Column(String(255), nullable=False)
        subtopic_name = Column(String(255), nullable=True)
        confidence = Column(Float, nullable=False, default=0.85)
        is_primary = Column(Boolean, nullable=False, default=True)
        syllabus_version_tag = Column(String(64), nullable=False, default="2026.1")
        created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
        updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    class QuestionEmbedding(Base):
        __tablename__ = "question_embeddings"
        id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
        question_id = Column(PG_UUID(as_uuid=True), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True)
        model_name = Column(String(128), nullable=False)
        embedding_version = Column(String(64), nullable=False, index=True)
        dimension = Column(Integer, nullable=False, default=384)
        embedding_vector = Column(Vector(384) if Vector is not None else JSON, nullable=False)
        created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
        updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
        __table_args__ = (UniqueConstraint("question_id", "embedding_version", name="uq_question_embedding_version"),)

    class QuestionSimilarity(Base):
        __tablename__ = "question_similarities"
        id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
        source_question_id = Column(PG_UUID(as_uuid=True), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True)
        target_question_id = Column(PG_UUID(as_uuid=True), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True)
        similarity_type = Column(String(32), nullable=False, index=True)  # exact_repeat, numeric_variant, conceptual_similar, same_underlying_concept
        similarity_score = Column(Float, nullable=False)
        tfidf_score = Column(Float, nullable=False, default=0.0)
        embedding_score = Column(Float, nullable=False, default=0.0)
        verification_notes = Column(Text, nullable=True)
        created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
        updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    class MockTest(Base):
        __tablename__ = "mock_tests"
        id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
        created_by = Column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
        title = Column(String(255), nullable=False)
        paper_code = Column(String(16), nullable=False, index=True)
        test_mode = Column(String(32), nullable=False)  # full_length, subject_wise, topic_wise, mixed_topic, difficulty_based, pyq_only, ai_practice
        duration_minutes = Column(Integer, nullable=False, default=180)
        total_questions = Column(Integer, nullable=False, default=65)
        total_marks = Column(Float, nullable=False, default=100.0)
        config_json = Column(JSON, nullable=True)
        status = Column(String(32), nullable=False, default="created")  # created, in_progress, submitted
        started_at = Column(DateTime(timezone=True), nullable=True)
        submitted_at = Column(DateTime(timezone=True), nullable=True)
        created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
        updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    class TestQuestion(Base):
        __tablename__ = "test_questions"
        id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
        mock_test_id = Column(PG_UUID(as_uuid=True), ForeignKey("mock_tests.id", ondelete="CASCADE"), nullable=False, index=True)
        question_id = Column(PG_UUID(as_uuid=True), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True)
        display_order = Column(Integer, nullable=False)
        section_name = Column(String(64), nullable=False, default="Technical")
        marks = Column(Float, nullable=False, default=1.0)
        negative_marks = Column(Float, nullable=False, default=0.3333333333)
        created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
        updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    class StudentResponse(Base):
        __tablename__ = "student_responses"
        id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
        mock_test_id = Column(PG_UUID(as_uuid=True), ForeignKey("mock_tests.id", ondelete="CASCADE"), nullable=False, index=True)
        question_id = Column(PG_UUID(as_uuid=True), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True)
        user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
        selected_options_json = Column(JSON, nullable=True)
        numerical_answer = Column(Float, nullable=True)
        marked_for_review = Column(Boolean, nullable=False, default=False)
        time_spent_seconds = Column(Integer, nullable=False, default=0)
        is_correct = Column(Boolean, nullable=True)
        marks_awarded = Column(Float, nullable=False, default=0.0)
        created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
        updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    class TestResult(Base):
        __tablename__ = "test_results"
        id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
        mock_test_id = Column(PG_UUID(as_uuid=True), ForeignKey("mock_tests.id", ondelete="CASCADE"), nullable=False, index=True)
        user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
        total_marks = Column(Float, nullable=False)
        marks_obtained = Column(Float, nullable=False)
        accuracy_percent = Column(Float, nullable=False)
        attempted_count = Column(Integer, nullable=False)
        correct_count = Column(Integer, nullable=False)
        incorrect_count = Column(Integer, nullable=False)
        unattempted_count = Column(Integer, nullable=False)
        time_taken_seconds = Column(Integer, nullable=False, default=0)
        weak_subjects_json = Column(JSON, nullable=True)
        weak_topics_json = Column(JSON, nullable=True)
        subject_breakdown_json = Column(JSON, nullable=True)
        created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
        updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    class StudyPlan(Base):
        __tablename__ = "study_plans"
        id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
        user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
        paper_code = Column(String(16), nullable=False, index=True)
        target_year = Column(Integer, nullable=False, default=2026)
        available_days = Column(Integer, nullable=False, default=60)
        daily_hours = Column(Float, nullable=False, default=4.0)
        roadmap_json = Column(JSON, nullable=False)
        weak_topics_json = Column(JSON, nullable=True)
        recommended_tests_json = Column(JSON, nullable=True)
        progress_percent = Column(Float, nullable=False, default=0.0)
        created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
        updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    class AgentRun(Base):
        __tablename__ = "agent_runs"
        id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
        workflow_id = Column(String(64), nullable=False, index=True)
        agent_name = Column(String(128), nullable=False, index=True)
        status = Column(String(32), nullable=False, index=True)  # running, completed, needs_review, failed
        input_summary = Column(Text, nullable=True)
        output_summary = Column(Text, nullable=True)
        prompt_tokens = Column(Integer, nullable=False, default=0)
        completion_tokens = Column(Integer, nullable=False, default=0)
        duration_ms = Column(Integer, nullable=False, default=0)
        error_message = Column(Text, nullable=True)
        created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
        updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    class ProcessingJob(Base):
        __tablename__ = "processing_jobs"
        id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
        question_paper_id = Column(PG_UUID(as_uuid=True), ForeignKey("question_papers.id", ondelete="CASCADE"), nullable=True, index=True)
        user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
        job_type = Column(String(64), nullable=False, default="pdf_ingestion")
        status = Column(String(32), nullable=False, default="queued", index=True)  # queued, running, completed, failed, needs_review
        current_stage = Column(String(128), nullable=False, default="initialized")
        progress_percent = Column(Float, nullable=False, default=0.0)
        retry_count = Column(Integer, nullable=False, default=0)
        logs_json = Column(JSON, nullable=True)
        error_message = Column(Text, nullable=True)
        created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
        updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

except ImportError:
    Base = None
