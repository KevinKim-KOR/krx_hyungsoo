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

# 기록
PRECHECK_RC_FILE=".state/report_precheck.rc"
mkdir -p "$(dirname "$PRECHECK_RC_FILE")"
echo "$RC_PRE" > "$PRECHECK_RC_FILE"

# 프리체크 결과에 따라 리포트 재시도 정책 결정
if [ "${RC_PRE:-1}" = "0" ]; then
  RETRY_MAX_REPORT=0
  RETRY_SLEEP_REPORT=0
else
  RETRY_MAX_REPORT=3
  RETRY_SLEEP_REPORT=300
fi

# 2) 엔트리 결정
if [ -f ./report_eod_cli.py ]; then
  CMD=( "$PYTHONBIN" -m report_eod_cli --date auto )
elif [ -f scripts/report_eod.py ]; then
  CMD=( "$PYTHONBIN" -m scripts.report_eod --date auto )
elif [ -f ./reporting_eod.py ]; then
  CMD=( "$PYTHONBIN" -c "from reporting_eod import generate_and_send_report_eod as f; import sys; sys.exit(f('auto'))" )
else
  echo "[ERR] no EOD report entry found (report_eod_cli.py / scripts/report_eod.py / reporting_eod.py not present)" >&2
  exit 2
fi

# 3) 본 실행
bash scripts/linux/jobs/run_with_lock.sh \
  scripts/linux/jobs/_run_generic.sh \
    --log report \
    --guard td \
    --retry-rc 2 --retry-max ${RETRY_MAX_REPORT} --retry-sleep ${RETRY_SLEEP_REPORT} \
    -- \
    "${CMD[@]}"
RC_REPORT=$?

# 3.5) 프리체크 OK & RC=2이면: DB 싱크 후 1회 재시도
if [ "${RC_PRE:-1}" = "0" ] && [ "${RC_REPORT:-1}" = "2" ]; then
  echo "[BRIDGE] cache -> DB sync (to lift latest date)"
  bash scripts/linux/batch/run_sync_cache_to_db.sh || true

  echo "[RETRY] report once after DB sync"
  "${CMD[@]}"
  RC_REPORT=$?
fi

# 4) 프리체크 OK & 여전히 RC=2이면: 캐시 리포트 백업 생성 → 성공 마킹
if [ "${RC_PRE:-1}" = "0" ] && [ "${RC_REPORT:-1}" = "2" ]; then
  echo "[FALLBACK] generating cache-based EOD report..."
  ${PYTHONBIN:-python3} -m scripts.ops.report_from_cache || true
  echo "[SOFT-OK] report deferred (DB stale), but cache is fresh. Marking as success."
  exit 0
fi

exit "$RC_REPORT"
