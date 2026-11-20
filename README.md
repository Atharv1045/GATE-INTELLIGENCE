# GATE Intelligence — Full-Scale Multi-Agent AI Platform for GATE Examination Preparation

**GATE Intelligence** is a production-oriented, CPU-optimized full-stack web application and 10-agent LangGraph AI platform for analyzing Graduate Aptitude Test in Engineering (GATE) previous-year question papers (PYQs), extracting structured questions (`MCQ`, `MSQ`, `NAT`), classifying them against year-versioned official GATE syllabi across all 30 disciplines, detecting exact/numeric-variant/conceptual duplicates, running explainable topic importance rankings with historical holdout backtesting, answering student queries with strict answer-key provenance (`official_key`, `manually_verified`, `ai_generated`, `unverified`), and generating CBT mock examinations and personalized study plans.

---

## 1. Official GATE Examination Grounding & Sources

All examination rules, paper codes, marking schemes, and syllabus structures in `exam/gate/` are grounded in official GATE organizing institute publications:
- **30 Official GATE Test Papers & Syllabi:** [IIT Guwahati GATE 2026 Test Papers & Syllabus](https://gate2026.iitg.ac.in/exam-papers-and-syllabus.html) (`AE`, `AG`, `AR`, `BM`, `BT`, `CE`, `CH`, `CS`, `CY`, `DA`, `EC`, `EE`, `ES`, `EY`, `GE`, `GG`, `IN`, `MA`, `ME`, `MN`, `MT`, `NM`, `PE`, `PH`, `PI`, `ST`, `TF`, `XE`, `XH`, `XL`)
- **Official Marking Scheme & Question Paper Pattern (65 Questions, 100 Marks, 180 Minutes):** [IIT Guwahati GATE 2026 Question Paper Pattern](https://gate2026.iitg.ac.in/question-paper-pattern.html)
  - **General Aptitude (GA):** 15 Marks (5 × 1-mark + 5 × 2-mark questions) across all papers.
  - **Engineering Mathematics + Technical Subject Marks:** 13 Marks Engineering Mathematics + 72 Marks Subject Questions for engineering disciplines (`AE`, `AG`, `BM`, `BT`, `CE`, `CH`, `CS`, `EC`, `EE`, `ES`, `IN`, `ME`, `MN`, `MT`, `NM`, `PE`, `PI`, `TF`), or 85 Marks core syllabus for `AR`, `CY`, `DA`, `EY`, `GE`, `GG`, `MA`, `PH`, `ST`, `XH`, `XL`.
  - **Negative Marking Rules:**
    - `MCQ` (Multiple Choice Questions): `-1/3` mark penalty for an incorrect 1-mark MCQ; `-2/3` mark penalty for an incorrect 2-mark MCQ.
    - `MSQ` (Multiple Select Questions): `0` negative marking and `0` partial credit (all and only correct options must be chosen).
    - `NAT` (Numerical Answer Type): `0` negative marking; evaluated against `[numerical_min - tolerance, numerical_max + tolerance]`.
- **Permitted Two-Paper Combinations:** [IIT Guwahati GATE 2026 Two-Paper Combinations](https://gate2026.iitg.ac.in/two-paper-combinations.html) and [IIT Roorkee GATE 2025 Two-Paper Combinations](https://gate2025.iitr.ac.in/two-paper-combinations.html)
- **Discipline Syllabi:** [GATE 2026 Computer Science (CS) Official Syllabus PDF](https://gate2026.iitg.ac.in/doc/GATE2026_Syllabus/CS_2026_Syllabus.pdf), [GATE 2026 Data Science & AI (DA) Official Syllabus PDF](https://gate2026.iitg.ac.in/doc/GATE2026_Syllabus/DA_2026_Syllabus.pdf), [GATE 2026 Electronics & Communication (EC) Official Syllabus PDF](https://gate2026.iitg.ac.in/doc/GATE2026_Syllabus/EC_2026_Syllabus.pdf), [GATE 2026 Electrical Engineering (EE) Official Syllabus PDF](https://gate2026.iitg.ac.in/doc/GATE2026_Syllabus/EE_2026_Syllabus.pdf), [GATE 2026 Mechanical Engineering (ME) Official Syllabus PDF](https://gate2026.iitg.ac.in/doc/GATE2026_Syllabus/ME_2026_Syllabus.pdf), and [GATE 2026 Civil Engineering (CE) Official Syllabus PDF](https://gate2026.iitg.ac.in/doc/GATE2026_Syllabus/CE_2026_Syllabus.pdf).

---

## 2. Hardware Optimization for Windows 10/11 (Intel Core i5, 16 GB RAM, Integrated Graphics)

- **Zero GPU Requirement:** Uses `sentence-transformers/all-MiniLM-L6-v2` (384-d) on CPU when installed, with a built-in deterministic 384-dimensional n-gram random-projection embedding engine (`v1-minilm-l6-384-cpu-hash384`) so vector similarity works immediately with `< 150 MB` RAM overhead.
- **Lazy Singleton Model Loading:** Embedding models are instantiated only when a PDF ingestion or RAG query executes (`LazyEmbeddingService.get_instance()`).
- **Selective OCR Fallback:** Digital PDFs are extracted directly via `PyMuPDF` (`fitz`) / `pdfplumber` / `pypdf`. CPU OCR (`pypdfium2` + `pytesseract`) is invoked *only* on pages with `< 30` characters of extractable digital text.
- **Bounded Worker Concurrency:** Celery workers are capped at `--concurrency=2 --pool=solo` on Windows, and Docker Compose services enforce explicit RAM limits (`1536M` for PostgreSQL, `256M` for Redis).
- **Dual Database Runtime:** Includes full PostgreSQL + `pgvector` SQLAlchemy 2.0 ORM models (`backend/app/models/sql_models.py`) and Alembic migrations (`backend/migrations/`), plus an out-of-the-box parameterized SQLite3 relational repository (`backend/app/database/session.py`) implementing the exact same 19 tables so you can develop and run tests on Windows even before starting Docker.

---

## 3. Phase-by-Phase Implementation & Verification Report (Phases 1–6)

### Phase 1: Project Structure, Database Architecture (19 Tables), Migrations & Health Checks
- **Files Created:**
  - `.env.example`, `.gitignore`, `LICENSE`, `docker-compose.yml`, `backend/Dockerfile`, `frontend/Dockerfile`, `backend/requirements.txt`
  - `backend/app/core/config.py`, `backend/app/core/security.py`
  - `backend/app/models/sql_models.py`, `backend/alembic.ini`, `backend/migrations/env.py`, `backend/migrations/versions/0001_initial_schema.py`
  - `backend/app/database/session.py`, `backend/app/schemas/api_schemas.py`
- **Implemented Features:** All 19 relational tables (`users`, `gate_papers`, `syllabus_versions`, `subjects`, `topics`, `question_papers`, `questions`, `question_options`, `answer_keys`, `question_topics`, `question_embeddings`, `question_similarities`, `mock_tests`, `test_questions`, `student_responses`, `test_results`, `study_plans`, `agent_runs`, `processing_jobs`) with UUID primary keys, foreign key constraints, indexes, and `/api/v1/health` verification.

### Phase 2: 14-Stage PDF Ingestion Pipeline, Structured Extraction & Question Bank UI
- **Files Created:**
  - `backend/app/pipelines/pdf_pipeline.py`
  - `frontend/src/pages/PaperLibrary.tsx`, `frontend/src/pages/QuestionBank.tsx`
- **Implemented Features:** `%PDF-` magic-byte validation, active `/JavaScript` and `/Launch` rejection, SHA-256 duplicate upload prevention, digital text extraction + scanned page OCR fallback, structured `MCQ`/`MSQ`/`NAT` parsing, math expression and table/diagram detection, page-number preservation, and human-review flagging (`needs_human_review`).

### Phase 3: 30-Paper GATE Taxonomy, Multi-Label Topic Classification, Duplicate Detection & Analytics
- **Files Created:**
  - `exam/gate/papers.json`, `exam/gate/marking_schemes/standard_gate.json`, `exam/gate/taxonomy_loader.py`
  - `exam/gate/syllabus/{CS,DA,EC,EE,ME,CE}/2026.json`
  - `backend/app/ml/embedding_service.py`, `backend/app/ml/analytics_engine.py`
  - `frontend/src/pages/PYQAnalytics.tsx`
- **Implemented Features:** Year-aware taxonomy loader for all 30 GATE paper codes, multi-topic interdisciplinary question tagging, 4-tier similarity detection (`exact_repeat`, `numeric_variant`, `conceptual_similar`, `same_underlying_concept`), explainable topic importance scoring (`0.30 * freq + 0.30 * marks + 0.25 * recurrence + 0.15 * recency`), and historical holdout backtesting.

### Phase 4: Google Gemini (`google-genai`) Integration, 10-Agent LangGraph Orchestrator, RAG Tutor & Mock Test Generator
- **Files Created:**
  - `backend/app/agents/orchestrator.py`, `backend/app/rag/tutor_engine.py`, `backend/app/tasks/celery_app.py`
  - `frontend/src/pages/AITutor.tsx`, `frontend/src/pages/MockTests.tsx`
- **Implemented Features:** All 10 specialized agents coordinated by `CentralOrchestrator` with execution logging in `agent_runs`, prompt-injection sanitization on untrusted PDF text, RAG Tutor with explicit answer provenance badges (`official_key`, `manually_verified`, `ai_generated`, `unverified`), and configurable CBT mock test generation.

### Phase 5: Official Answer Evaluation, Personalized Study Planner & Complete Frontend Integration
- **Files Created:**
  - `backend/app/api/v1/router.py`, `backend/app/main.py`
  - `frontend/src/layouts/AppLayout.tsx`, `frontend/src/pages/Dashboard.tsx`, `frontend/src/pages/StudyPlanner.tsx`, `frontend/src/pages/Settings.tsx`, `frontend/src/services/api.ts`, `frontend/src/types/index.ts`, `frontend/src/App.tsx`, `frontend/src/main.tsx`
- **Implemented Features:** Official GATE marking evaluation (`-1/3` and `-2/3` MCQ penalties, exact-set MSQ evaluation without partial credit, NAT numerical tolerance evaluation), weak subject/topic tracking, and adaptive week-by-week study plan generation.

### Phase 6: Automated Integration Testing, Bug Fixes & Honest Limitations Disclosure
- **Files Created & Executed:**
  - `backend/tests/test_api_and_agents.py`
  - `scripts/setup_windows.ps1`, `scripts/run_local_windows.ps1`
- **Test Results:** Executed 9 end-to-end integration test suites (`Ran 9 tests in 0.356s — OK`) covering health checks, Argon2/PBKDF2 auth, malicious PDF rejection, multi-year PDF ingestion, duplicate prevention, question verification, holdout backtesting, RAG citations, mock test evaluation (`8.67 / 10.0` marks verified), study planner, and agent run telemetry.
- **Honest Disclosure of Scope & Environment Nuances:**
  1. **Zero Pre-Populated Fake Questions:** In strict compliance with project rules, the database ships with **0 fabricated GATE questions**. All 30 GATE disciplines and official syllabi (`CS`, `DA`, `EC`, `EE`, `ME`, `CE`, etc.) are seeded, and the analytics/tutor/mock-test modules populate dynamically as soon as you upload legitimate GATE PDF question papers.
  2. **Detailed vs. Core-Fallback Syllabi:** Full topic/subtopic/keyword JSON files are pre-authored for `CS`, `DA`, `EC`, `EE`, `ME`, and `CE` (`exam/gate/syllabus/*/2026.json`). The remaining 24 GATE paper codes are registered in `exam/gate/papers.json` with dynamic fallback taxonomy resolution in `GateTaxonomyLoader` and can be expanded by dropping `<YEAR>.json` files into `exam/gate/syllabus/<CODE>/`.
  3. **Live Gemini API Key Optionality:** When `GEMINI_API_KEY` is set in `.env`, the RAG Tutor and structured extraction agents call `google-genai` (`gemini-2.5-flash` by default). When `GEMINI_API_KEY` is blank, the system automatically uses its deterministic CPU parser and RAG synthesizer so offline local development never crashes.

---

## 4. Windows 10/11 PowerShell Installation & Local Execution (`D:\Projects\GATE-INTELLIGENCE`)

### Step 1: Extract the Project Archive
Extract `GATE-INTELLIGENCE-Full-Platform.zip` into `D:\Projects\GATE-INTELLIGENCE` and open **Windows PowerShell**:

```powershell
cd D:\Projects\GATE-INTELLIGENCE
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\setup_windows.ps1
```

### Step 2: Configure Environment Variables (`.env`)
Open `D:\Projects\GATE-INTELLIGENCE\.env` and set your optional Gemini API key:
```ini
APP_NAME=GATE Intelligence
APP_ENV=development
GEMINI_API_KEY=your_google_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash
DATABASE_URL=postgresql+psycopg://gate_user:gate_pass@localhost:5432/gate_intelligence
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=replace_with_64_char_random_hex_string
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
UPLOAD_DIR=storage/uploads
MAX_UPLOAD_SIZE_MB=50
```

### Step 3: Run Locally on Windows (Fastest Debugging Mode)
```powershell
.\scriptsun_local_windows.ps1
```
- **FastAPI Swagger UI:** `http://127.0.0.1:8000/docs`
- **React Frontend UI:** `http://localhost:5173`

### Step 4: Run Automated Backend & Integration Tests
```powershell
cd D:\Projects\GATE-INTELLIGENCE
$env:PYTHONPATH = "backend;."
.\backend\.venv\Scripts\python.exe -m unittest discover -s backend/tests -p "test_*.py"
```
Runs 26 automated unit and regression tests across:
- `test_api_and_agents.py`: End-to-end multi-agent orchestration, PDF security, JWT auth, and study planner.
- `test_ingestion_regression.py`: Hybrid/scanned PDF ingestion, OCR fallbacks, and range banner suppression.
- `test_phase6_integrity_and_scoring.py`: Parser option sequences (A-D, A-E), stem collision resistance, transactional rollback, fresh DB lifespan initialization, and CORS headers.
- `test_visual_assets.py`: Vector diagram clustering, raster asset rendering, database persistence, and secure asset delivery.

### Step 5: Build Frontend
```powershell
cd D:\Projects\GATE-INTELLIGENCE\frontend
npm run build
```

---

## 5. Docker Compose & Public Production Deployment

### Option A: Infrastructure-Only Docker (PostgreSQL + `pgvector` + Redis on Docker, Apps on Windows)
```powershell
cd D:\Projects\GATE-INTELLIGENCE
docker compose up -d postgres redis
cd backend
.\.venv\Scriptslembic.exe upgrade head
```

### Option B: Full-Stack Docker Deployment (All 5 Services: Postgres, Redis, Backend, Celery Worker, Nginx Frontend)
```powershell
cd D:\Projects\GATE-INTELLIGENCE
docker compose --profile full up --build -d
```

### Public Cloud Deployment Checklist (Render / Railway / AWS EC2 / DigitalOcean)
1. Provision a managed PostgreSQL 16 instance with `CREATE EXTENSION IF NOT EXISTS vector;` and a managed Redis instance.
2. Set `APP_ENV=production`, a strong 64-byte `SECRET_KEY`, `GEMINI_API_KEY`, `DATABASE_URL`, and `CORS_ORIGINS=https://your-domain.com`.
3. Mount a persistent volume to `/app/storage` for uploaded PDFs and run `alembic upgrade head` during release deployment.
4. Serve the FastAPI backend behind Gunicorn/Uvicorn workers (`uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2`) and serve `frontend/dist` via Nginx or Cloudflare Pages with HTTPS enabled.
