#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p .locks logs

# ── venv / ENV ─────────────────────────────────────────────
[ -f "venv/bin/activate" ] && source venv/bin/activate
export KRX_CONFIG="${KRX_CONFIG:-$PWD/secret/config.yaml}"

LOG="logs/report_$(date +%F).log"
LOCK=".locks/report_eod.lock"

# ── lock ───────────────────────────────────────────────────
if mkdir "$LOCK" 2>/dev/null; then
  trap 'rmdir "$LOCK"' EXIT
else
  echo "[SKIP] another report-eod is running" | tee -a "$LOG"
  exit 0
fi

echo "[RUN] report-eod $(date +'%F %T')" | tee -a "$LOG"

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
  echo "[DONE] report-eod guarded-skip $(date +'%F %T')" | tee -a "$LOG"
  exit 0
fi

# ── 재시도 루프 ────────────────────────────────────────────
RETRY_MAX="${RETRY_MAX:-2}"       # 추가 시도 횟수
RETRY_SLEEP="${RETRY_SLEEP:-300}" # 300s(5분)

attempt=0
rc=1
while [ $attempt -le $RETRY_MAX ]; do
  attempt=$((attempt+1))
  echo "[TRY $attempt] report-eod $(date +'%F %T')" | tee -a "$LOG"
  ./venv/bin/python report_eod_cli.py --date auto >> "$LOG" 2>&1
  rc=$?
  if [ $rc -eq 2 ]; then
    echo "[RETRY] stale data -> sleep ${RETRY_SLEEP}s" | tee -a "$LOG"
    sleep "$RETRY_SLEEP"
    continue
  fi
  break
done

# ── 실패 시 알림 ───────────────────────────────────────────
if [ $rc -ne 0 ] && grep -qE "Traceback|ERROR" "$LOG"; then
  ./venv/bin/python - <<'PY' >> "$LOG" 2>&1
from reporting_eod import _load_cfg, _send_notify
_send_notify("❗️EOD 리포트 실패 감지: 로그 확인 필요", _load_cfg())
PY
fi

echo "[DONE] report-eod $(date +'%F %T')" | tee -a "$LOG"
echo "[EXIT $rc] report-eod $(date +'%F %T')" | tee -a "$LOG"
exit $rc
