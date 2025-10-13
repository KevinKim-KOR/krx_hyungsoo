#!/usr/bin/env bash
set -euo pipefail
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular

[ -f "config/env.nas.sh" ] && source config/env.nas.sh
[ -z "${PYTHONBIN:-}" ] && [ -f "config/env.pc.sh" ] && source config/env.pc.sh

JITTER_MAX_SEC=${JITTER_MAX_SEC:-10}
if [ "$JITTER_MAX_SEC" -gt 0 ]; then
  SLEEP_SEC=$(( RANDOM % JITTER_MAX_SEC ))
  echo "[INFO] Random sleep ${SLEEP_SEC}s before run_signals.sh"
  sleep "$SLEEP_SEC"
fi

bash scripts/linux/batch/run_signals.sh
