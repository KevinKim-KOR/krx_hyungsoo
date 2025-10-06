#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."

[ -f "config/env.nas.sh" ] && source config/env.nas.sh
PYTHONBIN="${PYTHONBIN:-python3}"

# 1) 프리체크(공통 정책, RC=2면 재시도)
bash scripts/linux/jobs/_run_generic.sh \
  --log report_precheck \
  --retry-rc 2 --retry-max 3 --retry-sleep 300 \
  -- \
  "$PYTHONBIN" -m scripts.ops.precheck_eod_fresh --task report

# 2) 엔트리 결정(기존 동작 유지)
CMD=( "$PYTHONBIN" app.py report-eod )
if ! "$PYTHONBIN" app.py -h 2>/dev/null | grep -qi "report-eod"; then
  if [ -f "scripts/report_eod.py" ]; then
    CMD=( "$PYTHONBIN" scripts/report_eod.py )
  elif [ -f "./report_eod.py" ]; then
    CMD=( "$PYTHONBIN" ./report_eod.py )
  else
    echo "[ERROR] report-eod entry not found (app.py report-eod / scripts/report_eod.py)"; exit 2
  fi
fi

# 3) 본 실행(거래일 가드, RC=2 재시도)
bash scripts/linux/jobs/run_with_lock.sh \
  scripts/linux/jobs/_run_generic.sh \
    --log report \
    --guard td \
    --retry-rc 2 --retry-max 3 --retry-sleep 300 \
    -- \
    "${CMD[@]}"
