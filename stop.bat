@echo off
chcp 65001 >nul
setlocal

echo ========================================
echo KRX Alertor (Observer) 종료 - Phase C
echo ========================================
echo.

echo [1/2] 서비스 종료 (Backend:8000, Bridge:8001, Cockpit:8501)...
set "found=0"

:: Listen Port 찾아서 종료 (8000, 8001, 8501)
for %%p in (8000 8001 8501) do (
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr :%%p ^| findstr LISTENING') do (
        echo    - Port %%p PID %%a 종료...
        taskkill /F /PID %%a >nul 2>&1
        set "found=1"
    )
)

if %found%==0 (
    echo    - 실행 중인 서버가 이미 정리되었습니다.
) else (
    echo    - 종료 완료.
)

echo.
echo [2/2] Worker Lock 정리 중...
:: Worker Lock 파일 삭제 (stale lock 방지)
if exist "%~dp0state\worker.lock" (
    del "%~dp0state\worker.lock" >nul 2>&1
    echo    - Worker Lock 파일 삭제 완료.
) else (
    echo    - Worker Lock 파일 없음.
)

echo.
echo ========================================
echo 종료 작업 완료
echo ========================================
timeout /t 2 >nul
