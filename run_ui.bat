@echo off
REM KRX Alertor UI 실행 스크립트 (Windows)

echo ========================================
echo KRX Alertor UI Dashboard
echo ========================================
echo.

REM 프로젝트 루트로 이동
cd /d "%~dp0"

echo 현재 디렉토리: %CD%
echo.

REM Streamlit 실행
echo UI 서버 시작 중...
echo 브라우저에서 http://localhost:8501 접속
echo.
echo 종료하려면 Ctrl+C 누르세요
echo ========================================
echo.

streamlit run extensions/ui/app.py

pause
