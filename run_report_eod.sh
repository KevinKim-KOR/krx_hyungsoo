#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"

mkdir -p .locks logs
LOCKDIR=".locks/report_eod.lock"
if mkdir "$LOCKDIR" 2>/dev/null; then trap 'rmdir "$LOCKDIR"' EXIT; else
  echo "[SKIP] another report-eod is running" | tee -a "logs/report_$(date +%F).log"; exit 0; fi

[ -f "venv/bin/activate" ] && source venv/bin/activate

TS="$(date +%F)"; LOG="logs/report_${TS}.log"
echo "[RUN] report-eod $(date +'%F %T')" | tee -a "$LOG"

# run_report_eod.sh (핵심 실행부만 발췌)
RETRY_MAX="${RETRY_MAX:-2}"      # 기본 2회 추가 시도
RETRY_SLEEP="${RETRY_SLEEP:-300}"# 기본 300초(5분)

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

if [ $rc -ne 0 ] && grep -qE "Traceback|ERROR" "$LOG"; then
  ./venv/bin/python - <<'PY' >> "$LOG" 2>&1
from reporting_eod import _load_cfg, _send_notify
_send_notify("❗️EOD 리포트 실패 감지: 로그 확인 필요", _load_cfg())
PY
fi

echo "[DONE] report-eod $(date +'%F %T')" | tee -a "$LOG"
echo "[EXIT $rc] report-eod $(date +'%F %T')" | tee -a "$LOG"