#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"

mkdir -p .locks logs
LOCKDIR=".locks/report_eod.lock"
if mkdir "$LOCKDIR" 2>/dev/null; then
  trap 'rmdir "$LOCKDIR"' EXIT
else
  echo "[SKIP] another report-eod is running" | tee -a "logs/report_$(date +%F).log"
  exit 0
fi

# venv
if [ -f "venv/bin/activate" ]; then
  source venv/bin/activate
fi

TS="$(date +%F)"
LOG="logs/report_${TS}.log"
echo "[RUN] report-eod $(date +'%F %T')" | tee -a "$LOG"

# app.py에 서브커맨드가 등록된 경우에만 app 경로로 실행, 아니면 모듈 폴백
if ./venv/bin/python app.py -h | grep -q "report-eod"; then
  ./venv/bin/python app.py report-eod --date auto >> "$LOG" 2>&1 || true
else
  ./venv/bin/python - <<'PY' >> "$LOG" 2>&1
from reporting_eod import generate_and_send_report_eod
raise SystemExit(generate_and_send_report_eod("auto"))
PY
fi

# 에러 키워드 감지 시 알림
if grep -qE "Traceback|ERROR" "$LOG"; then
  ./venv/bin/python - <<'PY' >> "$LOG" 2>&1
from scanner import load_config_yaml
from notifications import send_notify
cfg = load_config_yaml("config.yaml")
send_notify("❗️EOD 리포트 실패 감지: 로그 확인 필요", cfg)
PY
fi

echo "[DONE] report-eod $(date +'%F %T')" | tee -a "$LOG"
