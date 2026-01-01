@echo off
chcp 65001 >nul
setlocal

echo ========================================
echo KRX Alertor (Observer) 종료
echo ========================================
echo.

echo [1/1] 포트 8000 (백엔드) 프로세스 종료 중...
set "found=0"

:: 1. Uvicorn/Python 프로세스 강제 종료 (포트 8000 사용 중인 것)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING') do (
    echo    - PID %%a 종료...
    taskkill /F /PID %%a >nul 2>&1
    set "found=1"
)

:: 2. 혹시 남아있을 수 있는 uvicorn 관련 python 프로세스 정리 (선택적)
:: 주의: 다른 python 작업이 있다면 이 부분은 주석 처리하세요.
:: taskkill /F /IM python.exe /FI "WINDOWTITLE eq KRX Backend*" >nul 2>&1

if %found%==0 (
    echo    - 실행 중인 서버(Port 8000)가 없거나 이미 종료되었습니다.
) else (
    echo    - 종료 완료.
)

echo.
echo ========================================
echo 종료 작업 완료
echo ========================================
timeout /t 2 >nul
