@echo off
setlocal

echo ========================================
echo POC1 approval loop - start (Phase 2 / Step 3)
echo ========================================
echo.

cd /d "%~dp0"

rem 0. Cleanup existing processes on target ports
echo [0/3] Cleaning up existing processes...
cmd /c "%~dp0stop.bat" >nul 2>&1
timeout /t 1 >nul

rem 1. FastAPI backend (port 8000)
echo [1/3] Starting FastAPI backend on port 8000...
start "POC1 Backend" cmd /k ".\.venv\Scripts\python.exe -m uvicorn app.api:app --host 127.0.0.1 --port 8000 --reload"

rem 2. Next.js frontend (port 3000)
rem    NEXT_PUBLIC_API_BASE comes from frontend/.env.local (single source of truth).
rem    First-time setup requires:  copy frontend\.env.local.example frontend\.env.local
echo [2/3] Starting Next.js frontend on port 3000...
start "POC1 Frontend" cmd /k "cd frontend && npm run dev"

rem 3. Wait for boot, then open browser
echo [3/3] Waiting 5 seconds for servers to boot...
timeout /t 5 >nul
start "" "http://localhost:3000"

echo.
echo ========================================
echo Start complete
echo - Frontend : http://localhost:3000
echo - Backend  : http://127.0.0.1:8000/docs
echo Run stop.bat to shut down.
echo ========================================
pause
