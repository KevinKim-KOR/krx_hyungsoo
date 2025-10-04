#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."

STRATEGY="${1:-krx_ma200}"
BENCH="${2:-KOSPI,KOSDAQ}"
START="${3:-2020-01-01}"
END="${4:-2025-10-03}"   # 오늘 전일 등으로 바꿔도 됨

TODAY=$(date +%F)
LOG="logs/bt_${STRATEGY}_${TODAY}.log"
mkdir -p logs

{
  echo "[RUN] bt ${STRATEGY} $(date '+%F %T')"
  # 실제 러너 호출 (GPU는 PC에서, NAS는 CPU환경일 수 있으니 여기선 일반 python)
  python3 scripts/bt/run_bt.py --strategy "$STRATEGY" --benchmarks "$BENCH" --start "$START" --end "$END"
  echo "[DONE] bt ${STRATEGY} $(date '+%F %T')"
} | tee -a "$LOG"
