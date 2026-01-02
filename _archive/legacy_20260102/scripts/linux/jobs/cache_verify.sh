#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."
MAN="data/cache_manifest.sha"
LOG="logs/cache_verify_$(date +%F).log"
mkdir -p logs
[ -f "$MAN" ] || { echo "[MISS] $MAN not found" | tee -a "$LOG"; exit 0; }

set +e
sha256sum -c "$MAN" 2>&1 | tee -a "$LOG"
RC=${PIPESTATUS[0]}
set -e

if [ $RC -ne 0 ]; then
  echo "[ALERT] cache integrity mismatch (see $LOG)"
  if [ -x scripts/linux/jobs/ping_telegram.sh ]; then
    echo "cache verify failed: $(hostname)" | scripts/linux/jobs/ping_telegram.sh "CACHE VERIFY FAIL"
  fi
fi
exit 0  # 알림만 하고 실패로 처리하지 않으려면 0 유지, 강하게 막으려면 exit $RC
