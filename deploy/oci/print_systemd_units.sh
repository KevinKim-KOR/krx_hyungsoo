#!/bin/bash
# =============================================================================
# KRX Alertor Modular - Print Systemd Units
# Phase C-P.41: Oracle Cloud Scheduler (Print Only - No Execution)
# =============================================================================
# 용도: systemd service/timer 유닛을 화면에 출력만 (등록하지 않음)
# 사용자가 출력 내용을 확인 후 수동으로 유닛 파일 생성
# =============================================================================

set -e

# 프로젝트 경로 (실제 경로로 수정 필요)
PROJECT_PATH="/home/opc/krx_hyungsoo"
USER="opc"

echo "============================================"
echo " KRX Alertor - Systemd Units Generator"
echo " (Print Only - DO NOT AUTO-REGISTER)"
echo "============================================"
echo ""

echo "============================================"
echo " 1. Service Unit"
echo " /etc/systemd/system/krx-ops-cycle.service"
echo "============================================"
echo ""
cat << EOF
[Unit]
Description=KRX Alertor Modular - Ops Cycle
After=network.target

[Service]
Type=oneshot
User=${USER}
WorkingDirectory=${PROJECT_PATH}
ExecStart=${PROJECT_PATH}/deploy/run_ops_cycle.sh
StandardOutput=append:${PROJECT_PATH}/logs/ops_cycle.log
StandardError=append:${PROJECT_PATH}/logs/ops_cycle.log

[Install]
WantedBy=multi-user.target
EOF
echo ""

echo "============================================"
echo " 2. Timer Unit (KST 기준)"
echo " /etc/systemd/system/krx-ops-cycle.timer"
echo " ※ 서버 TZ가 UTC면 OnCalendar=*-*-* 00:05:00 사용"
echo "============================================"
echo ""
cat << EOF
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
EOF
echo ""

echo "============================================"
echo " 등록 방법"
echo "============================================"
echo ""
echo "1. 위 내용을 각각 파일로 저장:"
echo "   sudo nano /etc/systemd/system/krx-ops-cycle.service"
echo "   sudo nano /etc/systemd/system/krx-ops-cycle.timer"
echo ""
echo "2. systemd 리로드:"
echo "   sudo systemctl daemon-reload"
echo ""
echo "3. timer 활성화:"
echo "   sudo systemctl enable krx-ops-cycle.timer"
echo "   sudo systemctl start krx-ops-cycle.timer"
echo ""
echo "4. 확인:"
echo "   systemctl status krx-ops-cycle.timer"
echo "   systemctl list-timers | grep krx"
echo ""
