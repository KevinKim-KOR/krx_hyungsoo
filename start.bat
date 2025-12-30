@echo off
chcp 65001 >nul
setlocal

echo ========================================
echo KRX Alertor (Observer) 시작 - Phase 14
echo ========================================
echo.
echo [1/2] 백엔드 서버 시작 (Port 8000)...
echo.

:: 프로젝트 루트로 이동
cd /d "%~dp0"

:: 가상환경 활성화 (필요시)
:: call conda activate ai-study 2>nul

:: 백엔드 실행 (새 창에서)
start "KRX Backend (Do Not Close)" cmd /k "python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000"

echo [2/2] 대시보드 열기 (잠시 후)...
timeout /t 3 >nul

start http://localhost:8000/dashboard/index.html

echo.
echo ========================================
echo 실행 요청 완료
echo - UI: http://localhost:8000/dashboard/index.html
echo - Backend: http://localhost:8000/docs
echo.
echo 종료하려면 stop.bat을 실행하거나 창을 닫으세요.
echo ========================================
timeout /t 5 >nul
