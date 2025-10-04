#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p logs .locks

# ── venv / ENV ─────────────────────────────────────────────────────────
[ -f "venv/bin/activate" ] && source venv/bin/activate
export KRX_CONFIG="${KRX_CONFIG:-$PWD/secret/config.yaml}"
export KRX_WATCHLIST="${KRX_WATCHLIST:-$PWD/secret/watchlist.yaml}"

LOGNAME="scanner_$(date +%F).log"
LOG="logs/${LOGNAME}"
LOCK=".locks/scanner.lock"

# ── lock ───────────────────────────────────────────────────────────────
if mkdir "$LOCK" 2>/dev/null; then
  trap 'rmdir "$LOCK"' EXIT
else
  echo "[SKIP] scanner already running" | tee -a "$LOG"
  exit 0
fi

echo "[RUN] scanner $(date +'%F %T')" | tee -a "$LOG"

# ── 거래일/장시간 가드 ───────────────────────────────────────────────
./venv/bin/python - <<'PY' >> "$LOG" 2>&1
import sys
from utils.trading_day import is_trading_day, in_trading_hours
if not is_trading_day():
    print("[SKIP] non-trading day"); sys.exit(200)
if not in_trading_hours():
    print("[SKIP] out-of-trading-hours"); sys.exit(201)
PY
rc=$?
if [ $rc -ge 200 ]; then
  echo "[DONE] scanner guarded-skip $(date +'%F %T')" | tee -a "$LOG"
  exit 0
fi

# ── 본 실행 (계산 전용: 전송은 run_signals.sh에서) ────────────────────
# 기존 레포 명령에 맞춰 선택:
# 1) app.py scanner  (원래 커맨드)
./venv/bin/python app.py scanner >> "$LOG" 2>&1 || true
# 2) signals_cli.py 만 쓰고 싶으면 위 줄 대신 아래로 교체:
# ./venv/bin/python signals_cli.py --dry-run >> "$LOG" 2>&1 || true

# ── 에러 감지시 텔레그램 알림(선택, cfg 없으면 콘솔만) ────────────────
if grep -qE "Traceback|ERROR" "$LOG"; then
  ./venv/bin/python - <<'PY' >> "$LOG" 2>&1
from reporting_eod import _load_cfg, _send_notify
_send_notify("❗️Scanner 오류 감지: 로그 확인 필요", _load_cfg())
PY
fi

echo "[DONE] scanner $(date +'%F %T')" | tee -a "$LOG"
