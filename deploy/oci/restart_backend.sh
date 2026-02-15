#!/usr/bin/env bash
set -euo pipefail

SERVICE="krx-backend.service"
PORT="8000"

echo "=== [P146.4] Safe Restart: ${SERVICE} (port :${PORT}) ==="

echo "== 1) Current service status =="
sudo systemctl --no-pager -l status "${SERVICE}" || true

echo "== 2) Detect listeners on :${PORT} =="
sudo ss -lntp | grep -E "[:.]${PORT}\b" || true

echo "== 3) Kill ANY listener on :${PORT} (orphan cleanup) =="
# fuser 우선 (대부분 있음). 없으면 ss+awk로 대체.
if command -v fuser >/dev/null 2>&1; then
  sudo fuser -k "${PORT}"/tcp >/dev/null 2>&1 || true
else
  # ss에서 pid= 추출
  PIDS="$(sudo ss -lntp | awk -v p=":${PORT}" '$0 ~ p && $0 ~ /pid=/ {match($0,/pid=([0-9]+)/,a); if(a[1]!="") print a[1]}' | sort -u)"
  for pid in ${PIDS}; do
    sudo kill "${pid}" >/dev/null 2>&1 || true
    sleep 0.3
    sudo kill -9 "${pid}" >/dev/null 2>&1 || true
  done
fi

echo "== 4) Restart via systemd =="
sudo systemctl restart "${SERVICE}"
sleep 2
sudo systemctl --no-pager -l status "${SERVICE}"

echo "== 5) Verify :${PORT} owner == systemd process tree =="
MAINPID="$(systemctl show -p MainPID --value "${SERVICE}")"
echo "Service MainPID=${MAINPID}"
sudo ss -lntp | grep -E "[:.]${PORT}\b" || true

# Extract PID that owns the port
LISTENER_PID="$(sudo ss -lntp | grep -E "[:.]${PORT}\b" | grep -oP 'pid=\K[0-9]+' | head -1)" || true

if [ -z "${LISTENER_PID}" ]; then
  echo "WARN: No listener found on :${PORT} yet. Service may need more startup time."
  exit 2
fi

# Check: listener is MainPID itself, OR listener's parent (PPID) is MainPID (uvicorn worker)
LISTENER_PPID="$(ps -o ppid= -p "${LISTENER_PID}" 2>/dev/null | tr -d ' ')" || true

if [ "${LISTENER_PID}" = "${MAINPID}" ] || [ "${LISTENER_PPID}" = "${MAINPID}" ]; then
  echo "OK: backend is running under systemd and owns :${PORT} (listener=${LISTENER_PID}, parent=${LISTENER_PPID})"
else
  echo "WARN: :${PORT} is owned by PID=${LISTENER_PID} (PPID=${LISTENER_PPID}), not related to systemd MainPID=${MAINPID}. Orphan may exist."
  exit 2
fi
