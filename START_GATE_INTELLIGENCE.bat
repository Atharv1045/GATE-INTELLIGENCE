@echo off
title GATE Intelligence Launcher

set "PROJECT=%~dp0"
if "%PROJECT:~-1%"=="\" set "PROJECT=%PROJECT:~0,-1%"

echo ========================================================
echo          GATE INTELLIGENCE — LOCAL DESKTOP APP
echo ========================================================
echo.

echo [1/2] Starting FastAPI Backend on http://127.0.0.1:8000...
start "GATE Backend" cmd /k "cd /d %PROJECT%\backend && set PYTHONPATH=%PROJECT%\backend;%PROJECT% && %PROJECT%\backend\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"

echo [2/2] Starting React Vite Frontend on http://localhost:5173...
start "GATE Frontend" cmd /k "cd /d %PROJECT%\frontend && npm run dev"

echo.
echo Waiting for services to initialize...
timeout /t 5 /nobreak >nul

echo Opening GATE Intelligence in browser...
start http://localhost:5173

echo.
echo ========================================================
echo GATE Intelligence is running at http://localhost:5173
echo Close the Backend and Frontend windows when finished.
echo ========================================================
echo.
pause
