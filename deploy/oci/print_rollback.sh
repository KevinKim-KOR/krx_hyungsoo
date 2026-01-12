#!/bin/bash
# =============================================================================
# KRX Alertor Modular - Print Rollback Commands
# Phase C-P.42: Oracle Cloud Scheduler (Print Only - No Execution)
# =============================================================================
# ⚠️ PRINT-ONLY: 이 스크립트는 명령을 출력만 합니다. 실행하지 않습니다!
# =============================================================================

set -euo pipefail

PROJECT_PATH="/home/opc/krx_hyungsoo"

echo ""
echo "###############################################"
echo "### PRINT-ONLY: ROLLBACK COMMANDS ###"
echo "### DO NOT EXECUTE IN THIS PHASE ###"
echo "###############################################"
echo ""

echo "============================================"
echo " CRON ROLLBACK (출력만)"
echo "============================================"
echo ""
echo "# 1. 현재 cron 확인"
echo "crontab -l"
echo ""
echo "# 2. cron 편집하여 KRX 관련 라인 삭제"
echo "crontab -e"
echo ""
echo "# 3. 삭제 후 확인"
echo "crontab -l | grep -v krx"
echo ""

echo "============================================"
echo " SYSTEMD ROLLBACK (출력만)"
echo "============================================"
echo ""
echo "# 1. Timer 중지"
echo "sudo systemctl stop krx-ops-cycle.timer"
echo ""
echo "# 2. Timer 비활성화"
echo "sudo systemctl disable krx-ops-cycle.timer"
echo ""
echo "# 3. 상태 확인"
echo "systemctl status krx-ops-cycle.timer"
echo "systemctl status krx-ops-cycle.service"
echo ""
echo "# 4. (선택) 유닛 파일 삭제"
echo "# sudo rm /etc/systemd/system/krx-ops-cycle.timer"
echo "# sudo rm /etc/systemd/system/krx-ops-cycle.service"
echo "# sudo systemctl daemon-reload"
echo ""

echo "============================================"
echo " 로그 확인 (출력만)"
echo "============================================"
echo ""
echo "# Ops Cycle 로그"
echo "tail -50 ${PROJECT_PATH}/logs/ops_cycle.log"
echo ""
echo "# Systemd 로그"
echo "journalctl -u krx-ops-cycle.service -n 50"
echo "journalctl -u krx-ops-cycle.timer -n 50"
echo ""

echo "============================================"
echo " 상태 재확인 (출력만)"
echo "============================================"
echo ""
echo "# Health 확인"
echo "curl http://127.0.0.1:8000/api/ops/health"
echo ""
echo "# 안전장치 확인"
echo "cat ${PROJECT_PATH}/state/real_sender_enable.json"
echo "cat ${PROJECT_PATH}/state/execution_gate.json"
echo "cat ${PROJECT_PATH}/state/emergency_stop.json"
echo ""

echo "###############################################"
echo "### END OF ROLLBACK COMMANDS ###"
echo "###############################################"
