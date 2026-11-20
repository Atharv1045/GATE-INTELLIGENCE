"""
Background Task Queue (Celery + Redis) with CPU Concurrency Limits & Local Synchronous Fallback.
Optimized for Windows 10/11 (Intel Core i5, 16 GB RAM) using `--pool=solo` / `--concurrency=2`.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from app.core.config import settings
from app.database.session import get_db_connection
from app.agents.orchestrator import CentralOrchestrator

try:
    from celery import Celery

    celery_app = Celery(
        "gate_intelligence_tasks",
        broker=settings.REDIS_URL,
        backend=settings.REDIS_URL,
    )
    celery_app.conf.update(
        worker_concurrency=settings.WORKER_CONCURRENCY,
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        task_track_started=True,
        worker_prefetch_multiplier=1,
    )
except ImportError:
    celery_app = None


def process_uploaded_paper_sync(
    question_paper_id: str,
    job_id: str,
    file_path: str,
    filename: str,
    paper_code: str,
    examination_year: int,
    user_id: Optional[str] = None,
    allow_empty_replace: bool = False,
) -> dict:
    conn = get_db_connection()
    try:
        pdf_bytes = Path(file_path).read_bytes()
        orchestrator = CentralOrchestrator()
        state = orchestrator.execute_ingestion_workflow(
            conn=conn,
            question_paper_id=question_paper_id,
            job_id=job_id,
            pdf_bytes=pdf_bytes,
            filename=filename,
            paper_code=paper_code,
            examination_year=examination_year,
            user_id=user_id,
            allow_empty_replace=allow_empty_replace,
        )
        return {
            "job_id": job_id,
            "question_paper_id": question_paper_id,
            "status": state.get("status"),
            "extracted_count": len(state.get("persisted_question_ids", [])),
            "errors": state.get("errors", []),
        }
    finally:
        conn.close()


if celery_app is not None:
    @celery_app.task(name="gate_intelligence.process_uploaded_paper")
    def process_uploaded_paper_task(
        question_paper_id: str,
        job_id: str,
        file_path: str,
        filename: str,
        paper_code: str,
        examination_year: int,
        user_id: Optional[str] = None,
        allow_empty_replace: bool = False,
    ) -> dict:
        return process_uploaded_paper_sync(
            question_paper_id=question_paper_id,
            job_id=job_id,
            file_path=file_path,
            filename=filename,
            paper_code=paper_code,
            examination_year=examination_year,
            user_id=user_id,
            allow_empty_replace=allow_empty_replace,
        )
