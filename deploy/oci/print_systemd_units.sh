#!/bin/bash
# =============================================================================
# KRX Alertor Modular - Print Systemd Units
# Phase C-P.42: Oracle Cloud Scheduler (Print Only - No Execution)
# =============================================================================
# ⚠️ PRINT-ONLY: 이 스크립트는 명령을 출력만 합니다. 실행하지 않습니다!
# =============================================================================

set -euo pipefail

# 프로젝트 경로 (실제 경로로 수정 필요)
PROJECT_PATH="/home/opc/krx_hyungsoo"
USER="opc"

echo ""
echo "###############################################"
echo "### PRINT-ONLY: DO NOT EXECUTE IN THIS PHASE ###"
echo "###############################################"
echo ""

echo "============================================"
echo " PREFLIGHT COMMANDS (출력만)"
echo "============================================"
echo ""
echo "# 1. Timezone 확인"
echo "timedatectl"
echo "date"
echo ""
echo "# 2. systemd 상태 확인"
echo "systemctl --version"
echo ""

echo "============================================"
echo " SERVICE UNIT (출력만)"
echo " 파일: /etc/systemd/system/krx-ops-cycle.service"
echo "============================================"
echo ""
cat << 'UNIT_EOF'
[Unit]
Description=KRX Alertor Modular - Ops Cycle
After=network.target

[Service]
Type=oneshot
User=opc
WorkingDirectory=/home/opc/krx_hyungsoo
ExecStart=/home/opc/krx_hyungsoo/deploy/run_ops_cycle.sh
StandardOutput=append:/home/opc/krx_hyungsoo/logs/ops_cycle.log
StandardError=append:/home/opc/krx_hyungsoo/logs/ops_cycle.log

[Install]
WantedBy=multi-user.target
UNIT_EOF
echo ""

echo "============================================"
echo " TIMER UNIT (출력만)"
echo " 파일: /etc/systemd/system/krx-ops-cycle.timer"
echo " ※ 서버 TZ가 UTC면 OnCalendar=*-*-* 00:05:00 사용"
echo "============================================"
echo ""
cat << 'TIMER_EOF'
[Unit]
Description=KRX Alertor Modular - Daily Ops Cycle Timer (09:05 KST)

[Timer]
# 서버 TZ가 Asia/Seoul인 경우
OnCalendar=*-*-* 09:05:00

# 서버 TZ가 UTC인 경우 (주석 해제 후 사용)
# OnCalendar=*-*-* 00:05:00

Persistent=true

[Install]
WantedBy=timers.target
TIMER_EOF
echo ""

echo "============================================"
echo " INSTALL COMMANDS (출력만)"
echo "============================================"
echo ""
echo "# 1. 유닛 파일 생성 (위 내용을 각각 파일로 저장)"
echo "sudo nano /etc/systemd/system/krx-ops-cycle.service"
echo "sudo nano /etc/systemd/system/krx-ops-cycle.timer"
echo ""
echo "# 2. systemd 리로드"
echo "sudo systemctl daemon-reload"
echo ""
echo "# 3. timer 활성화"
echo "sudo systemctl enable krx-ops-cycle.timer"
echo "sudo systemctl start krx-ops-cycle.timer"
echo ""

echo "============================================"
echo " POST-INSTALL PROOF (출력만)"
echo "============================================"
echo ""
echo "# 1. timer 상태 확인"
echo "systemctl status krx-ops-cycle.timer"
echo "systemctl list-timers | grep krx"
echo ""
echo "# 2. 최초 실행 후 결과 확인"
echo "cat ${PROJECT_PATH}/reports/ops/scheduler/latest/ops_run_latest.json | jq .overall_status"
echo ""

echo "============================================"
echo " ROLLBACK COMMANDS (출력만)"
echo "============================================"
echo ""
echo "# 1. timer 중지"
echo "sudo systemctl stop krx-ops-cycle.timer"
echo ""
echo "# 2. timer 비활성화"
echo "sudo systemctl disable krx-ops-cycle.timer"
echo ""
echo "# 3. 상태 확인"
echo "systemctl status krx-ops-cycle.timer"
echo ""

echo "###############################################"
echo "### END OF PRINT-ONLY OUTPUT ###"
echo "###############################################"
