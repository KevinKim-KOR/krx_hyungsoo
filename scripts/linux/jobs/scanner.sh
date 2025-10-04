#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."
mkdir -p logs
TODAY=$(date +%F)
LOG="logs/scanner_${TODAY}.log"

{
  echo "[RUN] scanner $(date '+%F %T')"
  # === 실제 스캐너 로직 시작 ===
  # 휴장일 감지는 내부에서 하거나, 별도 유틸로 분리
  # $PYTHONBIN -m app.scanner --mode live
  # (임시) non-trading-day 예시:
  if [ "$(date +%u)" -ge 6 ]; then
    echo "[SKIP] non-trading day"
    echo "[DONE] scanner guarded-skip $(date '+%F %T')"
    exit 0
  fi
  # === 실제 스캐너 로직 끝 ===
  echo "[DONE] scanner $(date '+%F %T')"
} | tee -a "$LOG"
