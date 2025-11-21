@echo off
chcp 65001 > nul
REM ============================================
REM Daily Regime Check Script (Windows)
REM ============================================

echo ========================================
echo Daily Regime Check Started
echo ========================================
echo.

REM 프로젝트 루트로 이동
cd /d "%~dp0..\.."

REM Python 실행
python scripts\nas\daily_regime_check.py

echo.
echo ========================================
echo Daily Regime Check Completed
echo ========================================

pause
