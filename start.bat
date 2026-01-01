@echo off
chcp 65001 >nul
setlocal

echo ========================================
echo KRX Alertor (Observer) 시작 - Phase 14
echo ========================================
echo.

:: 0. 기존 프로세스 정리 (안전장치)
echo [0/2] 기존 서버 정리 중...
call "%~dp0stop.bat" >nul 2>&1
timeout /t 1 >nul

echo [1/2] 백엔드 서버 시작 (Port 8000)...
echo.

:: 프로젝트 루트로 이동
cd /d "%~dp0"

:: 백엔드 실행 (새 창에서)
:: "KRX Backend (Do Not Close)" 라는 제목의 창으로 실행
start "KRX Backend (Do Not Close)" cmd /k "python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000"

echo [2/2] 대시보드 열기 (서버 부팅 대기 5초)...
timeout /t 5 >nul

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
