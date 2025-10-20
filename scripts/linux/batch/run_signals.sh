#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."

[ -f "config/env.nas.sh" ] && source config/env.nas.sh
[ -z "${PYTHONBIN:-}" ] && [ -f "config/env.pc.sh" ] && source config/env.pc.sh

TASK="signals"
LOGFILE="logs/${TASK}_$(date +%F).log"

bash scripts/linux/jobs/run_py_guarded.sh "$PYTHONBIN" -m signals.main \
  --mode=cron --force \
  2>&1 | tee -a "$LOGFILE"
