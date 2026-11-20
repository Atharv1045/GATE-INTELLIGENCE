"""
GATE Intelligence FastAPI Entrypoint (Simplified 2.0).
Configures:
- Automatic SQLite database schema initialization & taxonomy seeding on startup
- CORS middleware
- Health check (`/health` and `/api/v1/health`)
- Versioned REST API router under `/api/v1` for all 7 functional pillars
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import router as api_v1_router
from app.core.config import settings
from app.database.session import get_db_connection, init_database

app = FastAPI(
    title=settings.APP_NAME,
    version="2.0.0",
    description="Offline-Capable Examination Preparation & Analytics Platform for GATE Aspirants",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    init_database()


@app.get("/health")
@app.get("/api/v1/health")
def health_check() -> dict:
    conn = get_db_connection()
    try:
        papers_cnt = conn.execute("SELECT COUNT(*) FROM gate_papers").fetchone()[0]
        questions_cnt = conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
        active_papers = conn.execute(
            "SELECT COUNT(*) FROM question_papers WHERE total_extracted_questions > 0"
        ).fetchone()[0]
        tests_completed = conn.execute("SELECT COUNT(*) FROM test_results").fetchone()[0]

        return {
            "status": "healthy",
            "app_name": settings.APP_NAME,
            "version": "2.0.0",
            "environment": settings.APP_ENV,
            "database_connected": True,
            "offline_mode": True,
            "supported_disciplines": papers_cnt,
            "active_papers_in_library": active_papers,
            "total_questions_in_bank": questions_cnt,
            "tests_completed": tests_completed,
        }
    finally:
        conn.close()


app.include_router(api_v1_router, prefix=settings.API_V1_STR)
