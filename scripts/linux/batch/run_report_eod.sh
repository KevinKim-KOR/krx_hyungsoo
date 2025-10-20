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
# 기본은 app.py report-eod 사용
CMD=( "$PYTHONBIN" app.py report-eod --date auto )
if ! "$PYTHONBIN" app.py -h 2>/dev/null | grep -qi 'report-eod'; then
  # 우선: report_eod_cli.py가 있으면 모듈 실행(권장)
  if [ -f ./report_eod_cli.py ]; then
    CMD=( "$PYTHONBIN" -m report_eod_cli --date auto )
  elif [ -f ./reporting_eod.py ]; then
    # 래퍼를 통해 reporting_eod의 generate_and_send_report_eod 호출
    CMD=( "$PYTHONBIN" -m scripts.report_eod --date auto )
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
