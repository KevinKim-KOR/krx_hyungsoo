#!/usr/bin/env bash
# KRX Report EOD (운영형 래퍼)
set -euo pipefail
cd "$(dirname "$0")/../../.."

# env
[ -f "config/env.nas.sh" ] && source config/env.nas.sh
[ -z "${PYTHONBIN:-}" ] && [ -f "config/env.pc.sh" ] && source config/env.pc.sh

# Jitter (0~120초)
JITTER_MAX_SEC="${JITTER_MAX_SEC:-120}"
if [ "${JITTER_MAX_SEC}" -gt 0 ] 2>/dev/null; then
  JITTER=$(( RANDOM % (JITTER_MAX_SEC + 1) ))
  echo "[JITTER] sleep ${JITTER}s"
  sleep "${JITTER}"
fi

# 로그 + 락 + 실행
LOGDIR="logs"; mkdir -p "$LOGDIR"
TS="$(date +%F)"
LOGFILE="$LOGDIR/report_eod_${TS}.log"

if [ ! -x "scripts/linux/batch/run_with_lock.sh" ]; then
  echo "[ERR] scripts/linux/batch/run_with_lock.sh not found or not executable" >&2
  exit 2
fi

echo "[RUN] krx_report_eod_daily $(date '+%F %T')" | tee -a "$LOGFILE"
exec scripts/linux/batch/run_with_lock.sh "bash scripts/linux/batch/run_report_eod.sh" | tee -a "$LOGFILE"
