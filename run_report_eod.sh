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

# app.py 우회: 전용 CLI 사용
./venv/bin/python report_eod_cli.py --date auto >> "$LOG" 2>&1 || true

# 에러 키워드 감지 시 알림(선택)
if grep -qE "Traceback|ERROR" "$LOG"; then
  ./venv/bin/python - <<'PY' >> "$LOG" 2>&1
from reporting_eod import _load_cfg, _send_notify
_send_notify("❗️EOD 리포트 실패 감지: 로그 확인 필요", _load_cfg())
PY
fi

echo "[DONE] report-eod $(date +'%F %T')" | tee -a "$LOG"
