#!/bin/bash
# Robust single-instance launcher for uvicorn web.main:app
set -euo pipefail
cd "$(dirname "$0")"

mkdir -p logs .locks
LOCK=".locks/web.lock"
PIDFILE=".locks/web.pid"
LOG="logs/web_$(date +%F).log"

# 0) 기존 pidfile 검증(좀비/스테일 정리)
if [[ -s "$PIDFILE" ]]; then
  oldpid="$(cat "$PIDFILE" 2>/dev/null || true)"
  if [[ -n "${oldpid:-}" ]] && kill -0 "$oldpid" 2>/dev/null; then
    echo "[SKIP] web already running (pid=$oldpid)" | tee -a "$LOG"
    exit 0
  else
    echo "[WARN] stale pidfile for pid=$oldpid -> cleaning" | tee -a "$LOG"
    rm -f "$PIDFILE"
  fi
fi

# 1) 락으로 중복 기동 방지
if mkdir "$LOCK" 2>/dev/null; then
  trap 'rmdir "$LOCK"' EXIT
else
  echo "[SKIP] web already starting (lock held)" | tee -a "$LOG"
  exit 0
fi

# 2) 포트(8899) 점유 프로세스 강제 정리 (있다면)
pids=""
if command -v lsof >/dev/null 2>&1; then
  pids="$(lsof -t -iTCP:8899 -sTCP:LISTEN || true)"
elif command -v fuser >/dev/null 2>&1; then
  pids="$(fuser -n tcp 8899 2>/dev/null || true)"
fi
if [[ -n "${pids// /}" ]]; then
  echo "[INFO] killing pids on :8899 -> $pids" | tee -a "$LOG"
  kill $pids 2>/dev/null || true
  sleep 1
  kill -9 $pids 2>/dev/null || true
fi

# 3) 가상환경/환경변수
[ -f "venv/bin/activate" ] && source venv/bin/activate || true
export KRX_CONFIG="$PWD/secret/config.yaml"
export KRX_WATCHLIST="$PWD/secret/watchlist.yaml"

# 4) 기동
nohup ./venv/bin/uvicorn web.main:app \
  --host 0.0.0.0 --port 8899 --proxy-headers >> "$LOG" 2>&1 &

echo $! > "$PIDFILE"
echo "[RUN] web $(date +'%F %T') pid=$(cat "$PIDFILE")" | tee -a "$LOG"
