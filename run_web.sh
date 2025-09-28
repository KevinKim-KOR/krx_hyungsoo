#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p logs .locks
LOCK=".locks/web.lock"
if mkdir "$LOCK" 2>/dev/null; then trap 'rmdir "$LOCK"' EXIT; else
  echo "[SKIP] web already running" | tee -a "logs/web_$(date +%F).log"; exit 0; fi
[ -f "venv/bin/activate" ] && source venv/bin/activate

# 🔽🔽🔽 이 줄 추가 (config.yaml 위치가 다르면 그 절대경로로 바꾸세요)
export KRX_CONFIG="$PWD/secret/config.yaml"

LOG="logs/web_$(date +%F).log"
nohup ./venv/bin/uvicorn web.main:app --host 0.0.0.0 --port 8899 --proxy-headers >> "$LOG" 2>&1 &
echo $! > .locks/web.pid
echo "[RUN] web $(date +'%F %T') pid=$(cat .locks/web.pid)" | tee -a "$LOG"
