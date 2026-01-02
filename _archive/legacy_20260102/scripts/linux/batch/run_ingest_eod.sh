#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."

# env 로드
[ -f "config/env.nas.sh" ] && source config/env.nas.sh
[ -z "${PYTHONBIN:-}" ] && [ -f "config/env.pc.sh" ] && source config/env.pc.sh

TASK="ingest"
LOGFILE="logs/${TASK}_$(date +%F).log"

# 1) 야간 윈도우/거래일 가드 (반환코드 정확히 판독; set -e 일시 해제)
set +e
PRECHECK_OUT="$(bash scripts/linux/jobs/precheck_yf_window.sh 2>&1)"
PRE_RC=$?
set -e
echo "$PRECHECK_OUT" | tee -a "$LOGFILE"

case "$PRE_RC" in
  0)    : ;;              # 통과 → 계속
  100)  exit 0 ;;         # 윈도우 밖 → 정상 종료(RC=0)
  *)    echo "[EXIT 2] precheck_failed rc=${PRE_RC}" | tee -a "$LOGFILE"; exit 2 ;;
esac

# 2) 랜덤 지터
JITTER_MAX_SEC=${JITTER_MAX_SEC:-60}
if [ "$JITTER_MAX_SEC" -gt 0 ]; then
  s=$(( RANDOM % JITTER_MAX_SEC ))
  echo "[INFO] jitter_sleep ${s}s" | tee -a "$LOGFILE"
  sleep "$s"
fi

# 3) 파이썬 엔트리 자동탐색
pick_entry() {
  for m in web.ingest_eod ingest.eod ingest.main ingest_eod app.ingest_eod; do
    if "$PYTHONBIN" - <<PY >/dev/null 2>&1
import importlib, sys
try: importlib.import_module("$m")
except Exception: sys.exit(1)
PY
    then echo "-m $m"; return 0; fi
  done
  for f in web/ingest_eod.py web/ingest.py ingest/eod.py ingest/main.py ingest/ingest_eod.py tools/ingest_eod.py scripts/python/ingest_eod.py; do
    [ -f "$f" ] && { echo "$f"; return 0; }
  done
  return 1
}

ENTRY=$(pick_entry || true)
if [ -z "${ENTRY:-}" ]; then
  echo "[EXIT 2] ingest_entry_not_found" | tee -a "$LOGFILE"; exit 2
fi
echo "[INFO] ingest_entry=${ENTRY}" | tee -a "$LOGFILE"

# 4) 최대 3회 지수 백오프 재시도
MAX_TRY=${MAX_TRY:-3}
BASE_BACKOFF=${BASE_BACKOFF:-60}
i=1
while :; do
  echo "[TRY $i] ${TASK} $(date '+%F %T')" | tee -a "$LOGFILE"
  if bash scripts/linux/jobs/run_py_guarded.sh "$PYTHONBIN" $ENTRY 2>&1 | tee -a "$LOGFILE"; then
    echo "[DONE] ${TASK} $(date '+%F %T')" | tee -a "$LOGFILE"; exit 0
  fi
  if grep -qE "YFRateLimitError|429|Read timed out|Temporary failure in name resolution|Connection reset by peer" "$LOGFILE"; then
    if [ "$i" -lt "$MAX_TRY" ]; then
      backoff=$(( BASE_BACKOFF * 2 ** (i-1) ))
      echo "[WARN] external_issue_retry sleep=${backoff}s (try=$i/$MAX_TRY)" | tee -a "$LOGFILE"
      sleep "$backoff"; i=$((i+1)); continue
    else
      echo "[SKIP] external_issue_after_retries RC=0 $(date '+%F %T')" | tee -a "$LOGFILE"; exit 0
    fi
  fi
  echo "[EXIT 2] logic_error $(date '+%F %T')" | tee -a "$LOGFILE"; exit 2
done
