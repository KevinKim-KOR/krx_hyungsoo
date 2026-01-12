#!/bin/bash
# =============================================================================
# KRX Alertor Modular - Print Cron Install Entry
# Phase C-P.41: Oracle Cloud Scheduler (Print Only - No Execution)
# =============================================================================
# 용도: cron entry를 화면에 출력만 (등록하지 않음)
# 사용자가 출력 내용을 확인 후 수동으로 crontab -e로 등록
# =============================================================================

set -e

# 프로젝트 경로 (실제 경로로 수정 필요)
PROJECT_PATH="/home/opc/krx_hyungsoo"

echo "============================================"
echo " KRX Alertor - Cron Entry Generator"
echo " (Print Only - DO NOT AUTO-REGISTER)"
echo "============================================"
echo ""

echo "============================================"
echo " Option 1: Server TZ = Asia/Seoul (KST)"
echo "============================================"
echo ""
cat << EOF
# KRX Ops Cycle - 매일 09:05 KST
5 9 * * * cd ${PROJECT_PATH} && ./deploy/run_ops_cycle.sh >> logs/ops_cycle.log 2>&1
EOF
echo ""

echo "============================================"
echo " Option 2: Server TZ = UTC"
echo " (09:05 KST = 00:05 UTC)"
echo "============================================"
echo ""
cat << EOF
# KRX Ops Cycle - 매일 00:05 UTC (= 09:05 KST)
5 0 * * * cd ${PROJECT_PATH} && ./deploy/run_ops_cycle.sh >> logs/ops_cycle.log 2>&1
EOF
echo ""

echo "============================================"
echo " Option 3: TZ 강제 지정 (권장)"
echo "============================================"
echo ""
cat << EOF
# KRX Ops Cycle - TZ 강제 지정
TZ=Asia/Seoul
5 9 * * * cd ${PROJECT_PATH} && ./deploy/run_ops_cycle.sh >> logs/ops_cycle.log 2>&1
EOF
echo ""

echo "============================================"
echo " 등록 방법"
echo "============================================"
echo ""
echo "1. crontab -e 실행"
echo "2. 위 옵션 중 하나 복사/붙여넣기"
echo "3. 저장 후 종료"
echo ""
echo "확인: crontab -l"
echo ""
