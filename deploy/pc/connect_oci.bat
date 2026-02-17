@echo off
chcp 65001 >nul
echo ========================================
echo [OCI Bridge] SSH Tunneling Connection
echo ========================================
echo.
echo Local Port 8001 -> Remote Port 8000 (OCI Backend)
echo.
echo NOTICE: This window MUST remain open for OCI connection.
echo.

cd /d "%~dp0..\.."

ssh -i "..\orcle cloud\oracle_cloud_key" -N -L 8001:localhost:8000 ubuntu@168.107.51.68

if errorlevel 1 (
    echo.
    echo [ERROR] Connection Failed. Check key file or network.
    pause
)
