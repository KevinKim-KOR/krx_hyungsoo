@echo off
REM ============================================
REM 백테스트 실행 스크립트 (Windows)
REM ============================================

echo ========================================
echo KRX Alertor - 백테스트 실행
echo ========================================
echo.

REM 프로젝트 루트로 이동
cd /d "%~dp0.."

echo [1/3] 환경 확인 중...
python --version
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Python이 설치되어 있지 않습니다.
    pause
    exit /b 1
)

echo.
echo [2/3] 백테스트 실행 중... (5~10분 소요)
echo - 전략: 하이브리드 레짐 전략
echo - 기간: 2022-01-01 ~ 현재
echo.

REM 백테스트 실행
python scripts/phase2/run_backtest_hybrid.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: 백테스트 실행 실패
    echo 로그를 확인하세요: logs/
    pause
    exit /b 1
)

echo.
echo [3/3] 완료!
echo.
echo 결과 파일: data/output/backtest/hybrid_backtest_results.json
echo 웹 UI에서 확인: http://localhost:3000/backtest
echo.
echo ========================================
echo 백테스트 완료
echo ========================================

pause
