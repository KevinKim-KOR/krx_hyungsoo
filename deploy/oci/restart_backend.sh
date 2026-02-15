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
sleep 1
sudo systemctl --no-pager -l status "${SERVICE}"

echo "== 5) Verify :${PORT} owner == systemd MainPID =="
MAINPID="$(systemctl show -p MainPID --value "${SERVICE}")"
echo "Service MainPID=${MAINPID}"
sudo ss -lntp | grep -E "[:.]${PORT}\b" || true

if ! sudo ss -lntp | grep -E "[:.]${PORT}\b" | grep -q "pid=${MAINPID},"; then
  echo "WARN: :${PORT} is not owned by systemd MainPID. Orphan may still exist."
  exit 2
fi

echo "OK: backend is running under systemd and owns :${PORT}"
