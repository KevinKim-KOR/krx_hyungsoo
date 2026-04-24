@echo off
setlocal

echo ========================================
echo POC1 approval loop - stop
echo ========================================

set "found=0"

rem Stop by port - 3000 (Next.js dev), 8000 (FastAPI)
rem Use findstr /C:"..." to force LITERAL match (no OR).
rem Default findstr treats spaces as OR separators, so ":3000 " without /C:
rem would match :30000 lines too. /C: keeps trailing space as a literal char,
rem which guarantees only exact port rows match.
for %%p in (3000 8000) do (
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr /C:":%%p " ^| findstr /C:"LISTENING"') do (
        echo    - Port %%p PID %%a terminated.
        taskkill /F /PID %%a >nul 2>&1
        set "found=1"
    )
)

if %found%==0 (
    echo    - No matching server running.
) else (
    echo    - Stop complete.
)

echo.
echo ========================================
echo POC1 stop done
echo ========================================
timeout /t 1 >nul
