@echo off
chcp 65001 >nul
setlocal

echo ========================================
echo KRX Alertor 서버 종료 (Stop)
echo ========================================
echo.

:: 1. 백엔드 (Port 8000) 종료
echo [1/2] 백엔드 서버 종료 (Port 8000)...
set "found_backend=0"
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING') do (
    echo    PID %%a 종료 중...
    taskkill /F /PID %%a >nul 2>&1
    set "found_backend=1"
)
if %found_backend%==0 (
    echo    실행 중인 백엔드 서버가 없습니다.
)

:: 2. 프론트엔드 (Port 3000) 종료
echo [2/2] 프론트엔드 서버 종료 (Port 3000)...
set "found_frontend=0"
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :3000 ^| findstr LISTENING') do (
    echo    PID %%a 종료 중...
    taskkill /F /PID %%a >nul 2>&1
    set "found_frontend=1"
)
if %found_frontend%==0 (
    echo    실행 중인 프론트엔드 서버가 없습니다.
)

echo.
echo ========================================
echo 모든 서버 종료 작업이 완료되었습니다.
echo ========================================
timeout /t 3 >nul
