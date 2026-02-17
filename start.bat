@echo off
chcp 65001 >nul
setlocal

echo ========================================
echo KRX Alertor (Observer) 시작 - Phase C
echo ========================================
echo.

:: 0. 기존 프로세스 정리 (안전장치)
echo [0/4] 기존 서버 정리 중...
cmd /c "%~dp0stop.bat" >nul 2>&1
timeout /t 2 >nul

echo [1/4] 백엔드 서버 시작 (Port 8000)...
echo.

:: 프로젝트 루트로 이동
cd /d "%~dp0"

:: 백엔드 실행 (venv Python 사용, 새 창에서)
start "KRX Backend" cmd /k ".\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000"

:: OCI Bridge (SSH Tunnel) 실행
echo [2/4] OCI Bridge (SSH Tunnel) 연결...
start "OCI Bridge" cmd /k "deploy\pc\connect_oci.bat"

echo [3/4] PC Cockpit 실행 (Streamlit)...
start "PC Cockpit" cmd /k ".\.venv\Scripts\python.exe -m streamlit run pc_cockpit/cockpit.py --server.headless true"

echo.
echo [4/4] 대시보드 및 Cockpit 열기 (서버 부팅 대기 5초)...
timeout /t 5 >nul

start "" "http://localhost:8000/operator"
start "" "http://localhost:8501"

echo.
echo ========================================
echo 실행 요청 완료
echo - OCI Dashboard (Black): http://localhost:8000/operator
echo - PC Cockpit (White): http://localhost:8501
echo - Backend API: http://localhost:8000/docs
echo.
echo 종료하려면 창을 닫거나 Ctrl+C를 누르세요.
echo ========================================
pause
