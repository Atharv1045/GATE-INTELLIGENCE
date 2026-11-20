# =============================================================================
# GATE Intelligence — Local Windows 10/11 Launcher (Low RAM / CPU-Friendly)
# =============================================================================
Write-Host "Starting GATE Intelligence Backend (FastAPI on http://127.0.0.1:8000) and Frontend (Vite on http://localhost:5173)..." -ForegroundColor Cyan

# Optional: Start PostgreSQL + pgvector and Redis containers if Docker Desktop is running
if (Get-Command docker -ErrorAction SilentlyContinue) {
    Write-Host "Starting PostgreSQL (pgvector) & Redis via Docker Compose..." -ForegroundColor Yellow
    docker compose up -d postgres redis
}

# Launch FastAPI Backend in a new PowerShell window
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PWD\backend'; `$env:PYTHONPATH='$PWD\backend;$PWD'; .\.venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8000 --reload"

# Launch React Vite Frontend in a new PowerShell window
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PWD\frontend'; npm run dev"

Write-Host "[OK] Backend API Docs: http://127.0.0.1:8000/docs" -ForegroundColor Green
Write-Host "[OK] Frontend Web UI:  http://localhost:5173" -ForegroundColor Green
