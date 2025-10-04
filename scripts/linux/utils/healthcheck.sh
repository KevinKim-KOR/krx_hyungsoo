#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."

TODAY=$(date +%F)
echo "=== HEALTHCHECK $(date '+%F %T') ==="
echo "[1] Git"
( git rev-parse --abbrev-ref HEAD; git rev-parse --short HEAD ) || echo " - git info error"

echo "[2] Disk"; df -h . | tail -n +2

echo "[3] Today logs"
for f in logs/scanner_${TODAY}.log logs/report_${TODAY}.log; do
  if [ -f "$f" ]; then echo " - OK: $f"; else echo " - MISS: $f"; fi
done

echo "[4] Recent errors"
ERRS=$(
  ( tail -n 200 logs/scanner_${TODAY}.log 2>/dev/null; tail -n 200 logs/report_${TODAY}.log 2>/dev/null ) \
    | grep -E "ERROR|Exception|Traceback|CRITICAL" || true
)
if [ -n "$ERRS" ]; then
  echo "$ERRS"
  # 텔레그램 알림 (선택): jobs/ping_telegram.sh를 이미 쓰고 계셔서 재활용
  if [ -x scripts/linux/jobs/ping_telegram.sh ]; then
    echo "[ALERT] send telegram"
    echo "$ERRS" | head -n 20 | scripts/linux/jobs/ping_telegram.sh "HEALTHCHECK ERRORS on $(hostname)"
  fi
else
  echo " - none"
fi

echo "[5] Locks"; ls -l .locks 2>/dev/null || echo " - none"
echo "=== END ==="
exit 0
