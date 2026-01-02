#!/usr/bin/env bash
set -euo pipefail
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular

# --- 환경 로드 ---
[ -f "config/env.nas.sh" ] && source config/env.nas.sh
[ -z "${PYTHONBIN:-}" ] && [ -f "config/env.pc.sh" ] && source config/env.pc.sh

LOGFILE="logs/signals_$(date +%F).log"

# --- Jitter (optional) ---
JITTER_MAX_SEC=${JITTER_MAX_SEC:-10}
if [ "$JITTER_MAX_SEC" -gt 0 ]; then
  SLEEP_SEC=$(( RANDOM % JITTER_MAX_SEC ))
  echo "[INFO] Random sleep ${SLEEP_SEC}s before run_signals.sh" | tee -a "$LOGFILE"
  sleep "$SLEEP_SEC"
fi

echo "[RUN] signal-wrapper $(date '+%F %T')" | tee -a "$LOGFILE"
# 실제 실행 (내부에서 조용히 끝나더라도 wrapper가 RC 기록)
if bash scripts/linux/batch/run_signals.sh 2>&1 | tee -a "$LOGFILE"; then
  echo "[DONE] signal-wrapper $(date '+%F %T')" | tee -a "$LOGFILE"
  exit 0
else
  rc=$?
  echo "[EXIT $rc] signal-wrapper $(date '+%F %T')" | tee -a "$LOGFILE"
  exit "$rc"
fi
