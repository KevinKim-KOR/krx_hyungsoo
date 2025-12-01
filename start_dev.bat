@echo off
chcp 65001 >nul
echo ========================================
echo KRX Alertor 개발 서버 시작
echo ========================================
echo.

:: 작업 디렉토리 설정
cd /d "E:\AI Study\krx_alertor_modular"

:: 가상환경 활성화 확인 (ai-study 우선)
echo [0/2] 가상환경 활성화 중...
echo    ai-study 환경 활성화 시도...
call conda activate ai-study 2>nul
if %ERRORLEVEL% neq 0 (
    echo    ai-study 실패, base 환경 시도...
    call conda activate base 2>nul
    if %ERRORLEVEL% neq 0 (
        echo    conda 실패, venv 확인 중...
        if exist "venv\Scripts\activate.bat" (
            echo    venv 가상환경 활성화...
            call venv\Scripts\activate.bat
        ) else if exist "backend\venv\Scripts\activate.bat" (
            echo    backend\venv 가상환경 활성화...
            call backend\venv\Scripts\activate.bat
        ) else (
            echo    경고: 가상환경을 찾을 수 없습니다. 시스템 Python을 사용합니다.
            echo    필요한 패키지가 설치되어 있지 않을 수 있습니다.
        )
    )
)

:: 3초 대기 (환경 활성화 대기)
timeout /t 3 /nobreak >nul

:: 1. 백엔드 서버 시작 (reload 옵션)
echo [1/2] 백엔드 서버 시작 (포트 8000, reload)...
start "Backend Server" cmd /k "cd /d E:\AI Study\krx_alertor_modular\backend && conda activate ai-study && python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"

:: 2초 대기
timeout /t 2 /nobreak >nul

:: 2. 프론트엔드 개발 서버 시작
echo [2/2] 프론트엔트 개발 서버 시작 (포트 3000)...
start "Frontend Server" cmd /k "cd /d E:\AI Study\krx_alertor_modular\web\dashboard && npm run dev"

echo.
echo ========================================
echo 개발 서버들이 시작되었습니다!
echo - 백엔드: http://localhost:8000
echo - 프론트엔트: http://localhost:3000
echo - API 문서: http://localhost:8000/docs
echo ========================================
echo.
echo ※ 백엔드는 --reload 모드로 실행됩니다 (코드 변경 시 자동 재시작)
echo 서버를 종료하려면 각 창을 닫거나 Ctrl+C를 누르세요.
echo 이 창은 5초 후 자동으로 닫힙니다...
timeout /t 5 /nobreak >nul
