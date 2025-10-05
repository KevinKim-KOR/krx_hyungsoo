#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."

LOGDIR="${LOGDIR:-logs}"
RETENTION_DAYS="${LOG_RETENTION_DAYS:-14}"

bash scripts/linux/jobs/run_with_lock.sh \
  scripts/linux/jobs/_run_generic.sh \
    --log cleanup_logs \
    --guard none \
    -- \
    bash -c '
      set -e
      mkdir -p "'"$LOGDIR"'"
      find "'"$LOGDIR"'" -type f -mtime +'"$RETENTION_DAYS"' -print -delete || true
      echo "[OK] pruned logs older than '"$RETENTION_DAYS"' days under '"$LOGDIR"'"
    '
