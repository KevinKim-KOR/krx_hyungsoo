#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."

LOGDIR="logs"; mkdir -p "$LOGDIR"
RUNLOG="$LOGDIR/cleanup_$(date +%F).log"

{
  echo "[RUN] cleanup_logs $(date '+%F %T')"
  # 1) 60일 지난 로그 삭제
  find "$LOGDIR" -type f -name "*.log" -mtime +60 -print -delete

  # 2) 7~60일 로그 gzip 압축 (이미 .gz면 제외)
  find "$LOGDIR" -type f -name "*.log" -mtime +7 -mtime -60 ! -name "*.gz" -print -exec gzip -f {} \;

  echo "[DONE] cleanup_logs $(date '+%F %T')"
} | tee -a "$RUNLOG"
