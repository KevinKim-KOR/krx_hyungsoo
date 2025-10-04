#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p logs .locks

# ── venv / ENV ─────────────────────────────────────────────
[ -f "venv/bin/activate" ] && source venv/bin/activate
export KRX_CONFIG="${KRX_CONFIG:-$PWD/secret/config.yaml}"
export KRX_WATCHLIST="${KRX_WATCHLIST:-$PWD/secret/watchlist.yaml}"

LOG="logs/signals_$(date +%F).log"
LOCK=".locks/signals.lock"

# ── lock ───────────────────────────────────────────────────
if mkdir "$LOCK" 2>/dev/null; then
  trap 'rmdir "$LOCK"' EXIT
else
  echo "[SKIP] signals already running" | tee -a "$LOG"
  exit 0
fi

echo "[RUN] signals $(date +'%F %T')" | tee -a "$LOG"

# ── 휴장 가드 ───────────────────────────────────────────────
set +e
./venv/bin/python - <<'PY' >> "$LOG" 2>&1
import sys
from utils.trading_day import is_trading_day
if not is_trading_day():
    print("[SKIP] non-trading day"); sys.exit(200)
PY
rc=$?
set -e
if [ $rc -ge 200 ]; then
  echo "[DONE] signals guarded-skip $(date +'%F %T')" | tee -a "$LOG"
  exit 0
fi

# ── 실행 (score_abs → 실패시 rank 1회 대체) ─────────────────
MODE1="${MODE1:-score_abs}"
MODE2="${MODE2:-rank}"
WL="${WL:-1}"
TOP="${TOP:-5}"

if ! ./venv/bin/python signals_cli.py --mode "$MODE1" --wl "$WL" --top "$TOP" >> "$LOG" 2>&1 ; then
  if ! ./venv/bin/python signals_cli.py --mode "$MODE2" --wl "$WL" --top "$TOP" >> "$LOG" 2>&1 ; then
    ./venv/bin/python - <<'PY' >> "$LOG" 2>&1
from reporting_eod import _load_cfg, _send_notify
_send_notify("❗️Signals 전송 실패 감지: 로그 확인 필요", _load_cfg())
PY
  fi
fi

# ── 에러 감지 시 푸시(선택) ─────────────────────────────────
if grep -qE "Traceback|ERROR" "$LOG"; then
  ./venv/bin/python - <<'PY' >> "$LOG" 2>&1
from reporting_eod import _load_cfg, _send_notify
_send_notify("❗️Signals 처리 중 오류 감지: 로그 확인 필요", _load_cfg())
PY
fi

echo "[DONE] signals $(date +'%F %T')" | tee -a "$LOG"
