#!/usr/bin/env bash
# macOS/Linux 版 stop — 기존 stop.bat 과 동일 목적 (포트 3000 / 8000 정리).
# Windows 는 netstat + taskkill, 여기서는 lsof + kill 로 같은 일을 한다.
set -uo pipefail

echo "========================================"
echo "POC1 approval loop - stop"
echo "========================================"

found=0
for port in 3000 8000; do
    # -t: PID 만 / -i: 네트워크 / -sTCP:LISTEN: LISTEN 상태만 (연결 중인 클라이언트 제외)
    pids=$(lsof -t -i :"$port" -sTCP:LISTEN 2>/dev/null || true)
    for pid in $pids; do
        echo "   - Port $port PID $pid terminated."
        kill "$pid" 2>/dev/null || true
        found=1
    done
done

if [ "$found" -eq 0 ]; then
    echo "   - No matching server running."
else
    echo "   - Stop complete."
fi

echo
echo "========================================"
echo "POC1 stop done"
echo "========================================"
