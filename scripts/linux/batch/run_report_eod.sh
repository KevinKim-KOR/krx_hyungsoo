#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."

# 0) env
[ -f "config/env.nas.sh" ] && source config/env.nas.sh
PYTHONBIN="${PYTHONBIN:-python3}"

# 1) 프리체크(거래일/지연 등), RC=2면 재시도
bash scripts/linux/jobs/_run_generic.sh \
  --log report_precheck \
  --retry-rc 2 --retry-max 3 --retry-sleep 300 \
  -- \
  "$PYTHONBIN" -m scripts.ops.precheck_eod_fresh --task report

# 2) 엔트리 결정 (우선순위: report_eod_cli.py > scripts/report_eod.py > reporting_eod.py)
if [ -f ./report_eod_cli.py ]; then
  CMD=( "$PYTHONBIN" -m report_eod_cli --date auto )
elif [ -f scripts/report_eod.py ]; then
  CMD=( "$PYTHONBIN" -m scripts.report_eod --date auto )
elif [ -f ./reporting_eod.py ]; then
  # 최후 폴백: generate_and_send_report_eod 직접 호출 시도
  CMD=( "$PYTHONBIN" -c "from reporting_eod import generate_and_send_report_eod as f; import sys; sys.exit(f('auto'))" )
else
  echo "[ERR] no EOD report entry found (report_eod_cli.py / scripts/report_eod.py / reporting_eod.py not present)" >&2
  exit 2
fi

# 3) 본 실행(거래일 가드 + 락 + 재시도)
bash scripts/linux/jobs/run_with_lock.sh \
  scripts/linux/jobs/_run_generic.sh \
    --log report \
    --guard td \
    --retry-rc 2 --retry-max 3 --retry-sleep 300 \
    -- \
    "${CMD[@]}"
