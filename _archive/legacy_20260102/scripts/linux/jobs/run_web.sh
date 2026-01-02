#!/usr/bin/env bash
set -euo pipefail

# ---------------------------------------
# KRX Web launcher (uvicorn)
# - start/stop/restart/status/logs
# - health check & crash diagnostics
# ---------------------------------------

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"

LOGDIR="$ROOT/logs"; mkdir -p "$LOGDIR"
PIDFILE="$ROOT/web.pid"
PORT="${PORT:-8899}"
APP_MODULE="${APP_MODULE:-web.main:app}"   # 필요시 환경변수로 override

# venv + env 설정
if [[ -f "config/env.nas.sh" ]]; then
  # shellcheck disable=SC1091
  source "config/env.nas.sh"
else
  echo "[WARN] config/env.nas.sh not found; trying system python" >&2
  PYTHONBIN="${PYTHONBIN:-python3}"
fi
PY="${PYTHONBIN:-python3}"

logfile() { echo "$LOGDIR/web_$(date +%F).log"; }

is_listening() {
  # ss/lsof 없는 NAS 대비 netstat 사용
  netstat -ltnp 2>/dev/null | grep -q ":${PORT} "
}

is_running() {
  [[ -f "$PIDFILE" ]] || return 1
  local p; p="$(cat "$PIDFILE" 2>/dev/null || true)"
  [[ -n "${p:-}" ]] && kill -0 "$p" 2>/dev/null
}

start() {
  # stale pid 정리
  if [[ -f "$PIDFILE" ]]; then
    local p; p="$(cat "$PIDFILE" 2>/dev/null || true)"
    if [[ -n "${p:-}" ]] && kill -0 "$p" 2>/dev/null; then
      echo "[SKIP] already running pid=$p"
      exit 0
    else
      echo "[WARN] stale pidfile for pid=${p:-?} -> cleaning"
      rm -f "$PIDFILE"
    fi
  fi

  # 기존 리스너가 있으면 중지 유도
  if is_listening; then
    echo "[WARN] port ${PORT} already in use. Showing processes:"
    netstat -ltnp 2>/dev/null | grep ":${PORT} " || true
    exit 2
  fi

  local logf; logf="$(logfile)"
  echo "[RUN] web $(date '+%F %T') port=${PORT} logfile=$(basename "$logf")"

  # 백그라운드 기동
  nohup "$PY" -m uvicorn "$APP_MODULE" \
      --host 0.0.0.0 --port "$PORT" --workers 1 --proxy-headers \
      >> "$logf" 2>&1 &

  echo $! > "$PIDFILE"
  sleep 1

  # 빠른 크래시 감지
  if ! is_running; then
    echo "[EXIT] uvicorn crashed immediately. Tail of log:"
    tail -n 200 "$logf" || true
    exit 2
  fi

  # 헬스체크(최대 10초 대기)
  for i in {1..20}; do
    if curl -fsS "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
      echo "[OK] health check passed"
      is_listening && netstat -ltnp 2>/dev/null | grep ":${PORT} " || true
      exit 0
    fi
    sleep 0.5
    # 중간에 죽었는지 재확인
    if ! is_running; then
      echo "[EXIT] uvicorn terminated during warmup. Tail of log:"
      tail -n 200 "$logf" || true
      exit 2
    fi
  done

  echo "[WARN] health check timed out (10s). Tail of log:"
  tail -n 200 "$logf" || true
  exit 2
}

stop() {
  if ! is_running; then
    echo "[SKIP] not running"
    rm -f "$PIDFILE"
    exit 0
  fi
  local p; p="$(cat "$PIDFILE")"
  kill "$p" 2>/dev/null || true
  sleep 1
  if kill -0 "$p" 2>/dev/null; then
    echo "[WARN] force kill pid=$p"
    kill -9 "$p" 2>/dev/null || true
  fi
  rm -f "$PIDFILE"
  echo "[DONE] stopped"
}

status() {
  if is_running; then
    local p; p="$(cat "$PIDFILE")"
    echo "[STATUS] running pid=$p"
  else
    echo "[STATUS] not running"
  fi
  is_listening && netstat -ltnp 2>/dev/null | grep ":${PORT} " || true
  exit 0
}

logs() {
  tail -n 200 -F "$(logfile)"
}

case "${1:-start}" in
  start) start ;;
  stop) stop ;;
  restart) stop; start ;;
  status) status ;;
  logs) logs ;;
  *) echo "usage: $0 {start|stop|restart|status|logs}" ; exit 2 ;;
esac
