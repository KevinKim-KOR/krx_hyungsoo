@echo off
setlocal enabledelayedexpansion

echo ========================================
echo POC1 approval loop - stop
echo ========================================

rem 2026-08-16 주인 확인 추가 — 3000(Next/React/Express) 과 8000(FastAPI/Django) 은
rem 가장 흔한 개발 포트다. 포트 번호만 보고 taskkill 하면 다른 프로젝트의 서버를
rem 종료시킨다. 아래 2단계로 이 프로젝트 것만 종료한다.
rem   1) start.bat 이 붙인 창 제목("POC1 Backend"/"POC1 Frontend")으로 트리 종료
rem   2) 그래도 포트가 남아 있으면, 실행 파일 경로가 이 프로젝트 밑일 때만 종료
rem 확인이 안 되면 죽이지 않는다 — 남의 것을 죽이는 쪽보다 안전하다.

set "PROJECT_DIR=%~dp0"
if "%PROJECT_DIR:~-1%"=="\" set "PROJECT_DIR=%PROJECT_DIR:~0,-1%"

set "found=0"
set "skipped=0"

rem ── 1단계: start.bat 이 띄운 창을 제목으로 종료 (트리 포함) ──────────────
for %%T in ("POC1 Backend" "POC1 Frontend") do (
    taskkill /FI "WINDOWTITLE eq %%~T*" /T /F >nul 2>&1
    if not errorlevel 1 (
        echo    - %%~T window terminated.
        set "found=1"
    )
)

rem ── 2단계: 남은 포트 점유 프로세스 검사 ─────────────────────────────────
rem findstr /C:"..." 로 리터럴 매치 (공백을 OR 로 해석하지 않게).
for %%p in (3000 8000) do (
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr /C:":%%p " ^| findstr /C:"LISTENING"') do (
        rem 실행 파일 경로 조회. 이 프로젝트의 .venv\Scripts\python.exe 는 여기서 걸린다.
        set "EXEPATH="
        for /f "usebackq delims=" %%e in (`powershell -NoProfile -Command ^
            "(Get-CimInstance Win32_Process -Filter 'ProcessId=%%a').ExecutablePath" 2^>nul`) do set "EXEPATH=%%e"

        set "MINE=0"
        if defined EXEPATH (
            echo !EXEPATH! | findstr /I /C:"%PROJECT_DIR%" >nul && set "MINE=1"
        )

        if "!MINE!"=="1" (
            echo    - Port %%p PID %%a terminated.
            taskkill /F /PID %%a >nul 2>&1
            set "found=1"
        ) else (
            if defined EXEPATH (
                echo    - Port %%p PID %%a 는 이 프로젝트가 아님 - 건너뜀 ^(!EXEPATH!^)
            ) else (
                echo    - Port %%p PID %%a 는 경로 확인 불가 - 건너뜀
            )
            set "skipped=1"
        )
    )
)

if "%found%%skipped%"=="00" (
    echo    - No matching server running.
) else (
    if "%found%"=="0" (
        echo    - 종료한 프로세스 없음. 위 포트는 다른 프로젝트가 쓰고 있다.
    ) else (
        echo    - Stop complete.
    )
)

echo.
echo ========================================
echo POC1 stop done
echo ========================================
timeout /t 1 >nul
