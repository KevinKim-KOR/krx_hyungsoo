#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."
mkdir -p logs
TODAY=$(date +%F)
LOG="logs/report_${TODAY}.log"

{
  echo "[RUN] report-eod $(date '+%F %T')"
  # === 실제 리포트 로직 ===
  # $PYTHONBIN -m app.report_eod
  # 장마감이 아닐 때:
  echo "[SKIP] non-trading day"
  echo "[DONE] report-eod guarded-skip $(date '+%F %T')"
} | tee -a "$LOG"
