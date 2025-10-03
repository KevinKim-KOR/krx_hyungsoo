# stop_web.sh (전체내용)
#!/bin/bash
# Robust stopper for uvicorn web.main:app
set -euo pipefail
cd "$(dirname "$0")"

PIDFILE=".locks/web.pid"
LOG="logs/web_$(date +%F).log"

# 1) pidfile에서 읽기
pids=""
if [[ -s "$PIDFILE" ]]; then
  pids="$(cat "$PIDFILE" 2>/dev/null || true)"
fi

# 2) 포트(8899) 점유 프로세스 추가 탐지
if command -v lsof >/dev/null 2>&1; then
  more="$(lsof -t -iTCP:8899 -sTCP:LISTEN || true)"
elif command -v fuser >/dev/null 2>&1; then
  more="$(fuser -n tcp 8899 2>/dev/null || true)"
else
  more=""
fi
pids="${pids} ${more}"

# 3) 종료
if [[ -n "${pids// /}" ]]; then
  echo "[STOP] web $(date +'%F %T') pids: $pids" | tee -a "$LOG"
  kill $pids 2>/dev/null || true
  sleep 1
  kill -9 $pids 2>/dev/null || true
else
  echo "[STOP] web $(date +'%F %T') (no pid)" | tee -a "$LOG"
fi

# 4) 락/파일 정리
rm -f "$PIDFILE" .locks/web.lock 2>/dev/null || true
