#!/bin/bash
# =============================================================================
# KRX Alertor Modular - Print Systemd Backend Service
# Phase C-P.44: OCI Operations Lock (Print Only - No Execution)
# =============================================================================
# ⚠️ PRINT-ONLY: 이 스크립트는 명령을 출력만 합니다. 실행하지 않습니다!
# =============================================================================

set -euo pipefail

PROJECT_PATH="/home/ubuntu/krx_hyungsoo"
USER="ubuntu"

echo ""
echo "###############################################"
echo "### PRINT-ONLY: BACKEND SYSTEMD SERVICE ###"
echo "### DO NOT EXECUTE IN THIS PHASE ###"
echo "###############################################"
echo ""

echo "============================================"
echo " SERVICE UNIT (출력만)"
echo " 파일: /etc/systemd/system/krx-backend.service"
echo "============================================"
echo ""
cat << 'UNIT_EOF'
[Unit]
Description=KRX Alertor Modular - FastAPI Backend
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/krx_hyungsoo
Environment="PATH=/home/ubuntu/krx_hyungsoo/.venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=/home/ubuntu/krx_hyungsoo/.venv/bin/python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5
StandardOutput=append:/home/ubuntu/krx_hyungsoo/logs/backend.log
StandardError=append:/home/ubuntu/krx_hyungsoo/logs/backend.log

[Install]
WantedBy=multi-user.target
UNIT_EOF
echo ""

echo "============================================"
echo " INSTALL COMMANDS (출력만)"
echo "============================================"
echo ""
echo "# 1. 유닛 파일 생성"
echo "sudo nano /etc/systemd/system/krx-backend.service"
echo ""
echo "# 2. systemd 리로드"
echo "sudo systemctl daemon-reload"
echo ""
echo "# 3. 서비스 활성화 및 시작"
echo "sudo systemctl enable krx-backend.service"
echo "sudo systemctl start krx-backend.service"
echo ""

echo "============================================"
echo " STATUS CHECK COMMANDS (출력만)"
echo "============================================"
echo ""
echo "# 서비스 상태 확인"
echo "sudo systemctl status krx-backend.service"
echo ""
echo "# 로그 확인"
echo "journalctl -u krx-backend.service -n 50"
echo ""
echo "# Health Check"
echo "curl http://127.0.0.1:8000/api/ops/health"
echo ""

echo "============================================"
echo " RESTART / STOP COMMANDS (출력만)"
echo "============================================"
echo ""
echo "# 재시작"
echo "sudo systemctl restart krx-backend.service"
echo ""
echo "# 중지"
echo "sudo systemctl stop krx-backend.service"
echo ""
echo "# 비활성화 (부팅 시 자동시작 해제)"
echo "sudo systemctl disable krx-backend.service"
echo ""

echo "###############################################"
echo "### END OF PRINT-ONLY OUTPUT ###"
echo "###############################################"
