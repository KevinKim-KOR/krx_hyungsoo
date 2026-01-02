@echo off
REM 포트폴리오 관리 UI 실행 (Windows)

cd /d "%~dp0..\.."
streamlit run ui/portfolio_manager.py --server.port 8502
