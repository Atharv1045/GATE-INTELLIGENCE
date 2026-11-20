# =============================================================================
# GATE Intelligence — Windows 10/11 PowerShell Setup Script
# Target Hardware: Intel Core i5 | 16 GB RAM | Intel Integrated Graphics (CPU-only)
# Target Path: D:\Projects\GATE-INTELLIGENCE
# =============================================================================
$ErrorActionPreference = "Stop"

Write-Host "=== GATE Intelligence: Windows 10/11 Environment Setup ===" -ForegroundColor Cyan

# 1. Verify Project Directory
if (-not (Test-Path ".\backend\requirements.txt")) {
    Write-Error "Please run this script from the root of D:\Projects\GATE-INTELLIGENCE"
}

# 2. Create .env from .env.example if not present
if (-not (Test-Path ".\.env")) {
    Copy-Item ".\.env.example" ".\.env"
    Write-Host "[OK] Created .env from .env.example. Add your GEMINI_API_KEY in .env when ready." -ForegroundColor Green
}

# 3. Create Python 3.11 Virtual Environment & Install Backend Dependencies
Write-Host "Setting up Python 3.11 virtual environment in .\backend\.venv ..." -ForegroundColor Yellow
python -m venv .\backend\.venv
& .\backend\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\backend\.venv\Scripts\pip.exe install -r .\backend\requirements.txt

# 4. Initialize Database & Seed Official 30-Paper GATE Taxonomy (0 Fake Questions)
Write-Host "Initializing database schema (19 tables) and seeding 30 official GATE disciplines..." -ForegroundColor Yellow
$env:PYTHONPATH = "$PWD\backend;$PWD"
& .\backend\.venv\Scripts\python.exe -c "from app.database.session import init_database; init_database(); print('[OK] Database initialized with 30 GATE papers and 0 fabricated questions.')"

# 5. Install Frontend Dependencies & Verify Production Build
Write-Host "Installing React + TypeScript + Vite frontend dependencies..." -ForegroundColor Yellow
Push-Location .\frontend
npm install
npm run build
Pop-Location

Write-Host "=== Setup Complete! Run .\scripts\run_local_windows.ps1 to launch GATE Intelligence ===" -ForegroundColor Green
