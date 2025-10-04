#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."

[ -f config/env.nas.sh ] && source config/env.nas.sh
PYTHONBIN="${PYTHONBIN:-python3}"

bash scripts/linux/jobs/run_with_lock.sh \
  scripts/linux/jobs/_run_generic.sh \
    --log watchlist \
    -- \
    "$PYTHONBIN" report_watchlist_cli.py --date auto
