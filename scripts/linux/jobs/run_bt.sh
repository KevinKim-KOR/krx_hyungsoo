#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."

# 환경 로드 (run_with_lock.sh에서도 로드하지만, 안전하게 한 번 더)
[ -f config/env.nas.sh ] && source config/env.nas.sh
PYTHONBIN="${PYTHONBIN:-python3}"

STRATEGY="${1:-krx_ma200}"
BENCH="${2:-KOSPI,KOSDAQ}"
START="${3:-2020-01-01}"
END="${4:-$(date -d 'yesterday' +%F 2>/dev/null || date -v-1d +%F)}"

TODAY=$(date +%F)
LOG="logs/bt_${STRATEGY}_${TODAY}.log"
mkdir -p logs

{
  echo "[RUN] bt ${STRATEGY} $(date '+%F %T')"
  "$PYTHONBIN" scripts/bt/run_bt.py --strategy "$STRATEGY" --benchmarks "$BENCH" --start "$START" --end "$END"
  echo "[DONE] bt ${STRATEGY} $(date '+%F %T')"
} | tee -a "$LOG"
