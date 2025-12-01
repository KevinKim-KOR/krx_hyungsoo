@echo off
echo ========================================
echo KRX Alertor 서버 종료
echo ========================================
echo.

:: 8000 포트 프로세스 종료
echo [1/2] 백엔드 서버 종료 (포트 8000)...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING') do (
    echo    PID %%a 종료 중...
    taskkill /F /PID %%a >nul 2>&1
)

:: 3000 포트 프로세스 종료
echo [2/2] 프론트엔드 서버 종료 (포트 3000)...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :3000 ^| findstr LISTENING') do (
    echo    PID %%a 종료 중...
    taskkill /F /PID %%a >nul 2>&1
)

echo.
echo ========================================
echo 모든 서버가 종료되었습니다!
echo ========================================
echo.
echo 3초 후 창이 닫힙니다...
timeout /t 3 /nobreak >nul
