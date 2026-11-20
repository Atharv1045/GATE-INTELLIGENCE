# =============================================================================
# GATE Intelligence — Phase 6 Safe Non-Destructive Upgrade, Migration & Verification
# Target Directory: D:\Projects\GATE-INTELLIGENCE
# =============================================================================
$ErrorActionPreference = "Stop"

Write-Host "=== GATE Intelligence: Phase 6 Transactional Upgrade & Verification ===" -ForegroundColor Cyan

if (-not (Test-Path ".\backend\app\main.py")) {
    Write-Error "Please run this script from D:\Projects\GATE-INTELLIGENCE"
}

# 1. Automatic Non-Destructive Backup of Existing SQLite Database
$dbPath = ".\storage\gate_intelligence.db"
if (Test-Path $dbPath) {
    $ts = Get-Date -Format "yyyyMMdd_HHmmss"
    $backupPath = ".\storage\gate_intelligence_backup_$ts.db"
    Copy-Item $dbPath $backupPath -Force
    Write-Host "[OK] Backed up existing SQLite database to $backupPath" -ForegroundColor Green
}

$env:PYTHONPATH = "$PWD\backend;$PWD"

# 2. Optional: Ensure CPU RapidOCR is installed (no external binary required on Windows)
Write-Host "Checking CPU OCR dependency (rapidocr-onnxruntime)..." -ForegroundColor Yellow
& .\backend\.venv\Scripts\pip.exe install rapidocr-onnxruntime --quiet

# 3. Apply Safe Non-Destructive Schema Migration (repairs legacy 'Q.1' labels to 'UNKNOWN' & adds provenance columns)
Write-Host "Applying non-destructive SQLite schema migration..." -ForegroundColor Yellow
& .\backend\.venv\Scripts\python.exe -c "from app.database.session import init_database; init_database(); print('[OK] Safe schema migration completed.')"

# 4. Run Full 18-Test Suite (API Integration + 13-Scenario Ingestion Regression + Phase 6 Transactional/Scoring Tests)
Write-Host "Running all 18 automated test suites..." -ForegroundColor Yellow
& .\backend\.venv\Scripts\python.exe -m unittest discover -s .\backend\tests -p "test_*.py" -v

# 5. Run Local Paper Diagnostic Report on Any Uploaded PDFs in storage/gate_intelligence.db
Write-Host "Generating 11-point diagnostic report for uploaded GATE PDFs..." -ForegroundColor Yellow
& .\backend\.venv\Scripts\python.exe .\scripts\verify_local_papers.py

Write-Host "=== Phase 6 Upgrade & Verification Complete! ===" -ForegroundColor Green
