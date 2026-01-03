@echo off
chcp 65001 >nul
setlocal

echo ========================================
echo KRX Alertor (Observer) 종료 - Phase C
echo ========================================
echo.

echo [1/2] 포트 8000 (백엔드) 프로세스 종료 중...
set "found=0"

:: 1. Uvicorn/Python 프로세스 강제 종료 (포트 8000 사용 중인 것)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING') do (
    echo    - PID %%a 종료...
    taskkill /F /PID %%a >nul 2>&1
    set "found=1"
)

if %found%==0 (
    echo    - 실행 중인 서버(Port 8000)가 없거나 이미 종료되었습니다.
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
