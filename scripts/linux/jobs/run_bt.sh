#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."

[ -f config/env.nas.sh ] && source config/env.nas.sh
PYTHONBIN="${PYTHONBIN:-python3}"

STRATEGY="${1:-krx_ma200}"
BENCH="${2:-KOSPI,S&P500}"
START="${3:-2020-01-01}"
END="${4:-$(date -d 'yesterday' +%F 2>/dev/null || date -v-1d +%F)}"

TODAY=$(date +%F)
LOG="logs/bt_${STRATEGY}_${TODAY}.log"
mkdir -p logs

{
  echo "[RUN] bt ${STRATEGY} $(date '+%F %T')"
  "$PYTHONBIN" -m scripts.bt.run_bt --strategy "$STRATEGY" --benchmarks "$BENCH" --start "$START" --end "$END"
  echo "[DONE] bt ${STRATEGY} $(date '+%F %T')"
} | tee -a "$LOG"
