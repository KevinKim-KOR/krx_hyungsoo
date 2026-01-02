#!/bin/bash

# ========================================================
# KRX Alertor Modular - Daily Automation Script
#
# [운영 규칙 / Operational Rules]
# 1. 실행 시간: KST 15:40 ~ 16:30 (종가 확정 후 실행 필수)
# 2. No-Op 원칙: 신호가 0건이어도 중단하지 않음 (명시적 EXIT 처리를 위해).
#               단, 스크립트 에러 발생 시 즉시 중단.
# 3. 장애 복구: 데이터 로딩 실패 등으로 재실행 시에는
#               python -m tools.paper_trade_phase9 --force 옵션 사용 고려.
# ========================================================

# Exit immediately if a command exits with a non-zero status
set -e

# Setup Environment
TODAY=$(date +"%Y%m%d")
LOG_DIR="logs"
LOG_FILE="${LOG_DIR}/daily_${TODAY}.log"

mkdir -p "$LOG_DIR"

# Start Logging
exec > >(tee -a "${LOG_FILE}") 2>&1

echo "========================================================"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Phase 9 Daily Run START"

# Rule Check (Time Warning)
CURRENT_HOUR=$(date +"%H")
CURRENT_MIN=$(date +"%M")
echo "[RULE Check] Ensure current time is between 15:40 ~ 16:30 KST (Current: ${CURRENT_HOUR}:${CURRENT_MIN})"

# Step 1: Signal Generation
echo ">>> [Step 1] Generating Signals..."
if python -m app.cli.alerts scan --strategy phase9 --config config/production_config.yaml; then
    echo "[Step 1] Success."
else
    echo "[Step 1] FAILED. Aborting."
    exit 1
fi

# Step 2: Execution (Paper Trade)
echo ">>> [Step 2] Executing Paper Trade..."
# Note: Paper trader script is idempotent by default (skips if already run today).
if python -m tools.paper_trade_phase9; then
    echo "[Step 2] Success."
else
    echo "[Step 2] FAILED. Aborting."
    exit 1
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Daily Run COMPLETED Successfully."
echo "========================================================"
