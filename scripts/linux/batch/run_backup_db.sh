#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."
[ -f config/env.nas.sh ] && source config/env.nas.sh

DB_PATH="${DB_PATH:-data/app.db}"
BACKUP_DIR="${BACKUP_DIR:-backups/db}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"

mkdir -p "$BACKUP_DIR"

# 제너릭으로 래핑(락/로그 포함), 외부요인 X → guard none
bash scripts/linux/jobs/run_with_lock.sh \
  scripts/linux/jobs/_run_generic.sh \
    --log backup_db \
    --guard none \
    -- \
    bash -c '
      set -e
      if [ ! -f "'"$DB_PATH"'" ]; then
        echo "[SKIP] no DB at '"$DB_PATH"'"
        exit 0
      fi
      ts=$(date +%F_%H%M%S)
      dst="'"$BACKUP_DIR"'/$(basename "'"$DB_PATH"'").${ts}.bak"
      cp -a "'"$DB_PATH"'" "$dst"
      echo "[OK] backup -> $dst"
      find "'"$BACKUP_DIR"'" -type f -mtime +'"$RETENTION_DAYS"' -print -delete || true
    '
