# run_report_watchlist.sh
#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"

mkdir -p .locks logs
LOCK=".locks/report_watchlist.lock"
if mkdir "$LOCK" 2>/dev/null; then trap 'rmdir "$LOCK"' EXIT; else
  echo "[SKIP] another report-watchlist is running" | tee -a "logs/watchlist_$(date +%F).log"; exit 0; fi

[ -f "venv/bin/activate" ] && source venv/bin/activate

LOG="logs/watchlist_$(date +%F).log"
echo "[RUN] report-watchlist $(date +'%F %T')" | tee -a "$LOG"
./venv/bin/python report_watchlist_cli.py --date auto >> "$LOG" 2>&1 || true

# 실패 경보(선택)
if grep -qE "Traceback|ERROR" "$LOG"; then
  ./venv/bin/python - <<'PY' >> "$LOG" 2>&1
from reporting_eod import _load_cfg, _send_notify
_send_notify("❗️Watchlist 리포트 실패: 로그 확인 필요", _load_cfg())
PY
fi

echo "[DONE] report-watchlist $(date +'%F %T')" | tee -a "$LOG"
