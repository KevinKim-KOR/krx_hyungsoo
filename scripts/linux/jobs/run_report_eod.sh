#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."

[ -f config/env.nas.sh ] && source config/env.nas.sh
PYTHONBIN="${PYTHONBIN:-python3}"

LOG="logs/report_$(date +%F).log"
mkdir -p logs

{
  echo "[RUN] report-eod $(date '+%F %T')"

  # 1) 휴장 가드
  set +e
  "$PYTHONBIN" - <<'PY'
import sys
from utils.trading_day import is_trading_day
if not is_trading_day():
    print("[SKIP] non-trading day"); sys.exit(200)
PY
  rc=$?
  set -e
  if [ $rc -ge 200 ]; then
    echo "[DONE] report-eod guarded-skip $(date '+%F %T')"
    exit 0
  fi

  # 2) 재시도: 데이터 정합(wait)만 재시도. 네트워크/외부오류는 가드가 곧바로 스킵(0)으로 변환하여 루프 종료
  RETRY_MAX="${RETRY_MAX:-2}"
  RETRY_SLEEP="${RETRY_SLEEP:-300}"  # 5분
  attempt=0
  while : ; do
    attempt=$((attempt+1))
    echo "[TRY $attempt] report-eod $(date '+%F %T')"
    set +e
    bash scripts/linux/jobs/run_py_guarded.sh "$PYTHONBIN" report_eod_cli.py --date auto
    rc=$?
    set -e

    # rc==2 는 'stale data' 같은 내부 신호라고 가정 → 재시도
    if [ $rc -eq 2 ] && [ $attempt -le $RETRY_MAX ]; then
      echo "[RETRY] stale data -> sleep ${RETRY_SLEEP}s"
      sleep "$RETRY_SLEEP"
      continue
    fi
    break
  done

  # 3) 실패 로그에 에러 패턴이 있으면 알림(선택)
  if [ $rc -ne 0 ] && grep -qE "Traceback|ERROR" "$LOG"; then
    "$PYTHONBIN" - <<'PY'
from reporting_eod import _load_cfg, _send_notify
_send_notify("❗️EOD 리포트 실패 감지: 로그 확인 필요", _load_cfg())
PY
  fi

  echo "[DONE] report-eod $(date '+%F %T')"
  echo "[EXIT $rc] report-eod $(date '+%F %T')"
  exit $rc
} | tee -a "$LOG"
