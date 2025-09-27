#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
if [ -f ".locks/web.pid" ]; then
  PID=$(cat .locks/web.pid)
  kill "$PID" 2>/dev/null || true
  rm -f .locks/web.pid
fi
rmdir .locks/web.lock 2>/dev/null || true
echo "[STOP] web $(date +'%F %T')"
