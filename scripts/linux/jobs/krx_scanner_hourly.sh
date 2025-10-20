#!/usr/bin/env bash
# KRX Scanner Hourly (운영형 래퍼)
set -euo pipefail
cd "$(dirname "$0")/../../.."

# 환경 로드
[ -f "config/env.nas.sh" ] && source config/env.nas.sh
[ -z "${PYTHONBIN:-}" ] && [ -f "config/env.pc.sh" ] && source config/env.pc.sh

# Jitter (0~15초, 필요 시 JITTER_MAX_SEC로 조정)
JITTER_MAX_SEC="${JITTER_MAX_SEC:-15}"
if [ "${JITTER_MAX_SEC}" -gt 0 ] 2>/dev/null; then
  JITTER=$(( RANDOM % (JITTER_MAX_SEC + 1) ))
  echo "[JITTER] sleep ${JITTER}s"
  sleep "${JITTER}"
fi

# (옵션) KRX 시간 가드 — 한국시간 08:55~15:35만 허용
if [ "${KRX_HOUR_GUARD:-0}" = "1" ]; then
  NOW=$(date +%H%M)
  if [ "$NOW" -lt 0855 ] || [ "$NOW" -gt 1535 ]; then
    echo "[SKIP] outside KRX hours: NOW=${NOW}"
    exit 0
  fi
fi

# 로그 + 락 실행
LOGDIR="logs"; mkdir -p "$LOGDIR"
TS="$(date +%F)"
LOGFILE="$LOGDIR/scanner_hourly_${TS}.log"

if [ ! -x "scripts/linux/batch/run_with_lock.sh" ]; then
  echo "[ERR] scripts/linux/batch/run_with_lock.sh not found or not executable" >&2
  exit 2
fi

echo "[RUN] krx_scanner_hourly $(date '+%F %T')" | tee -a "$LOGFILE"
exec scripts/linux/batch/run_with_lock.sh "bash scripts/linux/batch/run_scanner.sh" | tee -a "$LOGFILE"
