#!/bin/bash
set -e
LOCK="/tmp/krx_report.lock"
if ! mkdir "$LOCK" 2>/dev/null; then exit 0; fi
trap 'r=$?; rm -rf "$LOCK"; exit $r' INT TERM EXIT

cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular
source venv/bin/activate
LOG="logs/report_$(date +%F).log"

# run_report_eod.sh 중 실행 라인만 교체
./venv/bin/python app.py report-eod --date auto >> "$LOG" 2>&1 || \
./venv/bin/python - <<'PY' >> "$LOG" 2>&1
from reporting_eod import generate_and_send_report_eod
raise SystemExit(generate_and_send_report_eod("auto"))
PY


if grep -qE "Traceback|ERROR" "$LOG"; then
python - <<'PY'
from scanner import load_config_yaml
from notifications import send_notify
cfg = load_config_yaml("config.yaml")
send_notify("❗️EOD 리포트 실패 감지: 로그 확인 필요", cfg)
PY
fi
