#!/bin/bash
# =============================================================================
# KRX Alertor Modular - Print Cron Install Entry
# Phase C-P.42: Oracle Cloud Scheduler (Print Only - No Execution)
# =============================================================================
# ⚠️ PRINT-ONLY: 이 스크립트는 명령을 출력만 합니다. 실행하지 않습니다!
# =============================================================================

set -euo pipefail

# 프로젝트 경로 (실제 경로로 수정 필요)
PROJECT_PATH="/home/ubuntu/krx_hyungsoo"

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
echo "# 2. Python 확인"
echo "python3 --version"
echo "ls -la ${PROJECT_PATH}/.venv/"
echo ""
echo "# 3. 안전장치 확인"
echo "cat ${PROJECT_PATH}/state/real_sender_enable.json"
echo "cat ${PROJECT_PATH}/state/execution_gate.json"
echo "cat ${PROJECT_PATH}/state/emergency_stop.json"
echo ""

echo "============================================"
echo " INSTALL OPTIONS (출력만)"
echo "============================================"
echo ""

echo "--- Option 1: Server TZ = Asia/Seoul (KST) ---"
echo ""
echo "# crontab -e 실행 후 아래 내용 추가:"
echo "# KRX Ops Cycle - 매일 09:05 KST"
echo "5 9 * * * cd ${PROJECT_PATH} && ./deploy/run_ops_cycle.sh >> logs/ops_cycle.log 2>&1"
echo ""

echo "--- Option 2: Server TZ = UTC ---"
echo "# (09:05 KST = 00:05 UTC)"
echo ""
echo "# crontab -e 실행 후 아래 내용 추가:"
echo "# KRX Ops Cycle - 매일 00:05 UTC (= 09:05 KST)"
echo "5 0 * * * cd ${PROJECT_PATH} && ./deploy/run_ops_cycle.sh >> logs/ops_cycle.log 2>&1"
echo ""

echo "--- Option 3: TZ 강제 지정 (권장) ---"
echo ""
echo "# crontab -e 실행 후 아래 내용 추가:"
echo "TZ=Asia/Seoul"
echo "5 9 * * * cd ${PROJECT_PATH} && ./deploy/run_ops_cycle.sh >> logs/ops_cycle.log 2>&1"
echo ""

echo "============================================"
echo " POST-INSTALL PROOF (출력만)"
echo "============================================"
echo ""
echo "# 1. cron 등록 확인"
echo "crontab -l | grep krx"
echo ""
echo "# 2. 최초 실행 후 결과 확인"
echo "cat ${PROJECT_PATH}/reports/ops/scheduler/latest/ops_run_latest.json | jq .overall_status"
echo ""
echo "# 3. Health 확인"
echo "curl http://127.0.0.1:8000/api/ops/health"
echo ""

echo "============================================"
echo " ROLLBACK COMMANDS (출력만)"
echo "============================================"
echo ""
echo "# cron 제거"
echo "crontab -e  # 해당 라인 삭제"
echo ""
echo "# 또는 전체 초기화 (주의!)"
echo "# crontab -r"
echo ""

echo "###############################################"
echo "### END OF PRINT-ONLY OUTPUT ###"
echo "###############################################"
