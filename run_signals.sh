#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"

mkdir -p logs .locks
LOCK=".locks/signals.lock"
if mkdir "$LOCK" 2>/dev/null; then trap 'rmdir "$LOCK"' EXIT; else
  echo "[SKIP] signals already running" | tee -a "logs/signals_$(date +%F).log"; exit 0; fi

[ -f "venv/bin/activate" ] && source venv/bin/activate
export KRX_CONFIG="$PWD/secret/config.yaml"

TS="$(date +%F)"; LOG="logs/signals_${TS}.log"
echo "[RUN] signals $(date +'%F %T')" | tee -a "$LOG"

# 1차: score_abs → 실패하면 rank로 1회 대체
./venv/bin/python signals_cli.py --mode score_abs --wl 1 --top 5 >> "$LOG" 2>&1 || \
./venv/bin/python signals_cli.py --mode rank      --wl 1 --top 5 >> "$LOG" 2>&1 || \
./venv/bin/python - <<'PY' >> "$LOG" 2>&1
from reporting_eod import _load_cfg, _send_notify
_send_notify("❗️Signals 전송 실패 감지: 로그 확인 필요", _load_cfg())
PY

echo "[DONE] signals $(date +'%F %T')" | tee -a "$LOG"
