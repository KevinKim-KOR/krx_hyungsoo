#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."

[ -f config/env.nas.sh ] && source config/env.nas.sh
PYTHONBIN="${PYTHONBIN:-python3}"

# ---- 옵션 파싱 ----
LOG_PREFIX="task"
GUARD="none"           # none | td | th   (td=거래일만, th=거래일+장시간)
RETRY_RC="-777"        # -777이면 비활성화, 그 외 값이면 해당 RC에서 재시도
RETRY_MAX=0
RETRY_SLEEP=300        # 초

while [[ $# -gt 0 ]]; do
  case "$1" in
    --log|--log-prefix) LOG_PREFIX="${2}"; shift 2;;
    --guard)            GUARD="${2}"; shift 2;;
    --retry-rc)         RETRY_RC="${2}"; shift 2;;
    --retry-max)        RETRY_MAX="${2}"; shift 2;;
    --retry-sleep)      RETRY_SLEEP="${2}"; shift 2;;
    --)                 shift; break;;
    *)                  break;;
  esac
done

# 남은 인자 전체가 실행할 실제 커맨드
if [[ $# -lt 1 ]]; then
  echo "Usage: $0 [--log NAME] [--guard none|td|th] [--retry-rc N] [--retry-max K] [--retry-sleep S] -- <CMD ...>"
  exit 2
fi
CMD=( "$@" )

LOG="logs/${LOG_PREFIX}_$(date +%F).log"
mkdir -p logs

{
  echo "[RUN] ${LOG_PREFIX} $(date '+%F %T')"
  # ---- 가드 처리 ----
  if [[ "$GUARD" == "td" || "$GUARD" == "th" ]]; then
    set +e
    "$PYTHONBIN" - <<'PY'
import sys
try:
    from utils.trading_day import is_trading_day, in_trading_hours
except Exception:
    # 가드 모듈이 없으면 통과(개발환경 호환)
    sys.exit(0)

if not is_trading_day():
    print("[SKIP] non-trading day"); sys.exit(200)

# th면 장중 여부도 본다
if __import__('os').environ.get('GENERIC_GUARD_MODE','')=='th':
    if not in_trading_hours():
        print("[SKIP] out-of-trading-hours"); sys.exit(201)
PY
    rc=$?
    set -e
    if [[ "$GUARD" == "th" ]]; then export GENERIC_GUARD_MODE="th"; fi
    if [ $rc -ge 200 ]; then
      echo "[DONE] ${LOG_PREFIX} guarded-skip $(date '+%F %T')"
      exit 0
    fi
  fi

  # ---- 실행 + (선택) 재시도 ----
  attempt=0
  while : ; do
    attempt=$((attempt+1))
    echo "[TRY $attempt] ${LOG_PREFIX} $(date '+%F %T')"
    set +e
    # 외부요인은 run_py_guarded.sh가 RC=0으로 전환해 줌
    bash scripts/linux/jobs/run_py_guarded.sh "${CMD[@]}"
    rc=$?
    set -e

    if [ "$RETRY_RC" != "-777" ] && [ $rc -eq "$RETRY_RC" ] && [ $attempt -le "$RETRY_MAX" ]; then
      echo "[RETRY] rc=$rc -> sleep ${RETRY_SLEEP}s"
      sleep "$RETRY_SLEEP"
      continue
    fi
    break
  done

  echo "[DONE] ${LOG_PREFIX} $(date '+%F %T')"
  echo "[EXIT $rc] ${LOG_PREFIX} $(date '+%F %T')"
  exit $rc
} | tee -a "$LOG"
