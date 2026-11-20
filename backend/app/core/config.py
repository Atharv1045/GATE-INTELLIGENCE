"""
Simplified, offline-capable configuration for GATE Intelligence.
Eliminates external cloud services (Gemini, Redis, Celery, HuggingFace embeddings).
Standardized exclusively on local SQLite.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import List
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(REPO_ROOT / ".env")


class Settings:
    def __init__(self) -> None:
        self.APP_NAME: str = os.getenv("APP_NAME", "GATE Intelligence")
        self.APP_ENV: str = os.getenv("APP_ENV", "development")
        self.API_V1_STR: str = "/api/v1"
        self._default_sqlite_path: Path = REPO_ROOT / "storage" / "gate_intelligence.db"
        self._default_upload_dir: Path = REPO_ROOT / os.getenv("UPLOAD_DIR", "storage/uploads")
        self.PROCESSED_DIR: Path = REPO_ROOT / os.getenv("PROCESSED_DIR", "storage/processed")
        self.TEMP_DIR: Path = REPO_ROOT / os.getenv("TEMP_DIR", "storage/temp")
        self.EXAM_GATE_DIR: Path = REPO_ROOT / "exam" / "gate"
        self.VISUAL_ASSETS_DIR: Path = REPO_ROOT / os.getenv("VISUAL_ASSETS_DIR", "storage/visual_assets")
        self.SECRET_KEY: str = os.getenv(
            "SECRET_KEY",
            "gate-intelligence-dev-secret-key-change-in-production-9876543210",
        )
        self.ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))
        self.EMBEDDING_VERSION: str = "v1-deterministic-sql"
        self.MAX_UPLOAD_SIZE_MB: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "50"))
        self.RATE_LIMIT_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "120"))
        self.ENABLE_OCR_FALLBACK: bool = os.getenv("ENABLE_OCR_FALLBACK", "true").lower() in ("true", "1", "yes")
        self.TESSERACT_CMD: str = os.getenv("TESSERACT_CMD", r"C:\Program Files\Tesseract-OCR\tesseract.exe")
        self.GEMINI_API_KEY: Optional[str] = os.getenv("GEMINI_API_KEY", None)
        self.GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        cors_raw = os.getenv(
            "CORS_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000",
        )
        self.CORS_ORIGINS: List[str] = [
            c.strip() for c in cors_raw.split(",") if c.strip()
        ]

        # Ensure directories exist
        for d in [self.PROCESSED_DIR, self.TEMP_DIR, self.VISUAL_ASSETS_DIR]:
            try:
                d.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass

    @property
    def SQLITE_DB_PATH(self) -> Path:
        env_path = os.getenv("SQLITE_DB_PATH")
        target = Path(env_path) if env_path else self._default_sqlite_path
        if not target.is_absolute():
            target = REPO_ROOT / target
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        return target

    @property
    def UPLOAD_DIR(self) -> Path:
        env_dir = os.getenv("UPLOAD_DIR")
        target = Path(env_dir) if env_dir else self._default_upload_dir
        if not target.is_absolute():
            target = REPO_ROOT / target
        try:
            target.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        return target


settings = Settings()
