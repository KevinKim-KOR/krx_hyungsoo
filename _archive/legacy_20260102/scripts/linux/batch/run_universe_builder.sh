#!/usr/bin/env bash
# scripts/linux/batch/run_universe_builder.sh
set -euo pipefail
cd "$(dirname "$0")/../../.."

[ -f "config/env.nas.sh" ] && source config/env.nas.sh
[ -z "${PYTHONBIN:-}" ] && [ -f "config/env.pc.sh" ] && source config/env.pc.sh
PYTHONBIN="${PYTHONBIN:-python3}"

LOGDIR="logs"
mkdir -p "$LOGDIR"
TS="$(date +%F)"
LOGFILE="$LOGDIR/universe_builder_${TS}.log"

# run_with_lock.sh 존재 가정(기존 배치들과 동일 패턴)
if [ ! -x "scripts/linux/batch/run_with_lock.sh" ]; then
  echo "[ERR] scripts/linux/batch/run_with_lock.sh not found or not executable" >&2
  exit 2
fi

echo "[RUN] universe_builder $(date '+%F %T')" | tee -a "$LOGFILE"
exec scripts/linux/batch/run_with_lock.sh "$PYTHONBIN web/universe_builder.py --config config/data_sources.yaml" | tee -a "$LOGFILE"
