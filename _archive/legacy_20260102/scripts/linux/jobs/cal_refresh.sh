#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"

# env
# shellcheck disable=SC1091
source config/env.nas.sh
PY="${PYTHONBIN:-python3}"

LOGDIR="$ROOT/logs"; mkdir -p "$LOGDIR"
LOG="$LOGDIR/cal_refresh_$(date +%F).log"

{
  echo "[RUN] cal-refresh $(date '+%F %T') ROOT=$ROOT"
  set +e
  "$PY" "$ROOT/web/cal_refresh.py"
  RC=$?
  set -e
  if [[ $RC -eq 0 ]]; then
    echo "[EXIT] RC=0"
    exit 0
  elif [[ $RC -eq 3 ]]; then
    echo "[SKIP] external-data-unavailable (no calendar source available)"
    echo "[EXIT] RC=0"
    exit 0
  else
    echo "[EXIT] RC=2 (cal refresh failed with $RC)"
    exit 2
  fi
} | tee -a "$LOG"
