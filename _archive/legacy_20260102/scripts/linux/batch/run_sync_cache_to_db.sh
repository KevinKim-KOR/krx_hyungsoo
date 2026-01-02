#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."

[ -f "config/env.nas.sh" ] && source config/env.nas.sh
PY="${PYTHONBIN:-python3}"

echo "[RUN] sync_cache_to_db $(date '+%F %T')"
$PY -m scripts.ops.sync_cache_to_db
RC=$?
echo "[EXIT $RC] sync_cache_to_db $(date '+%F %T')"
exit "$RC"
