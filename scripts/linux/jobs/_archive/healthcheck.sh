#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."

TODAY=$(date +%F)
echo "=== HEALTHCHECK $(date '+%F %T') ==="
echo "[1] Disk"; df -h . | tail -n +2
echo "[2] Logs today"
for f in logs/scanner_${TODAY}.log logs/report_${TODAY}.log; do
  if [ -f "$f" ]; then
    echo " - OK: $f"
  else
    echo " - MISS: $f"
  fi
done
echo "[3] Recent errors"
( tail -n 100 logs/scanner_${TODAY}.log 2>/dev/null; tail -n 100 logs/report_${TODAY}.log 2>/dev/null ) \
  | grep -E "ERROR|Exception|Traceback|CRITICAL" || echo " - none"
echo "[4] Locks"; ls -l .locks 2>/dev/null || echo " - none"
echo "=== END ==="
