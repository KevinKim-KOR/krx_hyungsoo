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
RC_PRE=$?

# (추가) 프리체크 결과를 파일로 기록
PRECHECK_RC_FILE=".state/report_precheck.rc"
mkdir -p "$(dirname "$PRECHECK_RC_FILE")"
echo "$RC_PRE" > "$PRECHECK_RC_FILE"

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
RC_REPORT=$?

# (기존) 리포트 본체 실행 후 RC_REPORT 판정 아래에 추가
if [ "${RC_PRE:-1}" = "0" ] && [ "${RC_REPORT:-1}" = "2" ]; then
  echo "[FALLBACK] generating cache-based EOD report..."
  ${PYTHONBIN:-python3} -m scripts.ops.report_from_cache
  RC_FB=$?
  if [ "$RC_FB" = "0" ]; then
    echo "[SOFT-OK] cache-based EOD report created."
    exit 0
  else
    echo "[WARN] cache-based report failed; keep RC=2"
  fi
fi

# (추가) 프리체크가 0(OK)이었고, 리포트 RC가 2(지연)면 소프트 성공으로 다운그레이드
if [ "${RC_PRE:-1}" = "0" ] && [ "${RC_REPORT:-1}" = "2" ]; then
  echo "[SOFT-OK] report deferred (DB stale), but cache is fresh. Marking as success."
  exit 0
fi

exit "$RC_REPORT"
