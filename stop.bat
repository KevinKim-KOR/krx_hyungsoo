@echo off
chcp 65001 >nul
setlocal

echo ========================================
echo KRX Alertor (Observer) 종료
echo ========================================
echo.

echo [1/1] 포트 8000 (백엔드) 프로세스 종료 중...
set "found=0"

for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING') do (
    echo    - PID %%a 종료...
    taskkill /F /PID %%a >nul 2>&1
    set "found=1"
)

if %found%==0 (
    echo    - 실행 중인 서버(Port 8000)가 없습니다.
) else (
    echo    - 종료 완료.
)

echo.
echo ========================================
echo 종료 작업 완료
echo ========================================
timeout /t 3 >nul
