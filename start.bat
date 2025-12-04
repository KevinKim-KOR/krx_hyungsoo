@echo off
chcp 65001 >nul
setlocal

echo ========================================
echo KRX Alertor 서버 시작 (Start) - v3 (Stable)
echo ========================================
echo.

:: 프로젝트 루트 경로 설정
set "PROJECT_ROOT=%~dp0"
cd /d "%PROJECT_ROOT%"

:: ---------------------------------------------------------
:: 1. Anaconda / Miniconda 경로 자동 탐색
:: ---------------------------------------------------------
echo [1/3] Conda 환경 설정 확인 중...

set "ACTIVATE_SCRIPT="

:: (1) 일반적인 설치 경로 탐색
set "CANDIDATE_PATHS=%USERPROFILE%\anaconda3;%USERPROFILE%\miniconda3;C:\ProgramData\anaconda3;C:\ProgramData\miniconda3;C:\Anaconda3;%LOCALAPPDATA%\Continuum\anaconda3"

for %%p in (%CANDIDATE_PATHS%) do (
    if exist "%%p\Scripts\activate.bat" (
        echo    - Conda 경로 발견: %%p
        set "ACTIVATE_SCRIPT=%%p\Scripts\activate.bat"
        goto :SET_ACTIVATE_CMD
    )
)

:: (2) 경로를 못 찾았을 경우 PATH에서 확인 시도 (불안정할 수 있음)
where conda >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo    - 시스템 PATH에서 conda 발견 (경로 탐색 실패, 기본 명령어 사용)
    set "PRE_CMD=call conda activate ai-study"
    goto :FOUND_CONDA
)

:SET_ACTIVATE_CMD
if defined ACTIVATE_SCRIPT (
    :: 중요: activate.bat에 환경 이름을 직접 전달합니다. (conda activate 명령어 사용 X)
    echo    - 활성화 스크립트: "%ACTIVATE_SCRIPT%"
    set "PRE_CMD=call "%ACTIVATE_SCRIPT%" ai-study"
) else (
    echo    [경고] Conda를 찾을 수 없습니다. 시스템 환경변수에 의존합니다.
    set "PRE_CMD=echo Conda not found..."
)

:FOUND_CONDA
echo    - 실행 명령 준비 완료.

:: ---------------------------------------------------------
:: 2. 백엔드 서버 시작
:: ---------------------------------------------------------
echo [2/3] 백엔드 서버 시작 (FastAPI, Port 8000)...
start "KRX Backend" cmd /k "cd /d "%PROJECT_ROOT%backend" && %PRE_CMD% && python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"

:: 충돌 방지를 위해 3초 대기
timeout /t 3 >nul

:: ---------------------------------------------------------
:: 3. 프론트엔드 서버 시작
:: ---------------------------------------------------------
echo [3/3] 프론트엔드 서버 시작 (React, Port 3000)...
:: 프론트엔드는 npm만 있으면 되므로, 혹시 conda 활성화가 실패해도 실행되도록 처리
start "KRX Frontend" cmd /k "cd /d "%PROJECT_ROOT%web\dashboard" && (%PRE_CMD% || echo Conda activation failed, trying system npm...) && npm run dev"

echo.
echo ========================================
echo 서버 실행 요청이 완료되었습니다.
echo.
echo - 백엔드: http://localhost:8000/api/docs
echo - 프론트엔드: http://localhost:3000
echo.
echo 서버를 종료하려면 'stop.bat'을 실행하세요.
echo ========================================
timeout /t 5 >nul
