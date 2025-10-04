#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."

[ -f config/env.nas.sh ] && source config/env.nas.sh
PYTHONBIN="${PYTHONBIN:-python3}"

bash scripts/linux/jobs/run_with_lock.sh \
  scripts/linux/jobs/_run_generic.sh \
    --log report \
    --guard td \
    --retry-rc 2 \
    --retry-max 2 \
    --retry-sleep 300 \
    -- \
    "$PYTHONBIN" report_eod_cli.py --date auto
