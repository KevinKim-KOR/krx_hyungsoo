#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."

# env 로드
[ -f "config/env.nas.sh" ] && source config/env.nas.sh
[ -z "${PYTHONBIN:-}" ] && [ -f "config/env.pc.sh" ] && source config/env.pc.sh

TASK="ingest"
LOGFILE="logs/${TASK}_$(date +%F).log"

# 1) 야간 윈도우/거래일 가드
bash scripts/linux/jobs/precheck_yf_window.sh 2>&1 | tee -a "$LOGFILE"

# 2) 랜덤 지터
JITTER_MAX_SEC=${JITTER_MAX_SEC:-60}
if [ "$JITTER_MAX_SEC" -gt 0 ]; then
  s=$(( RANDOM % JITTER_MAX_SEC ))
  echo "[INFO] jitter_sleep ${s}s" | tee -a "$LOGFILE"
  sleep "$s"
fi

# 3) 파이썬 엔트리 자동탐색 (모듈 우선 → 스크립트 경로 폴백)
pick_entry() {
  # 모듈 후보
  for m in web.ingest_eod ingest.eod ingest.main ingest_eod; do
    if "$PYTHONBIN" -c "import importlib; importlib.import_module('$m')" >/dev/null 2>&1; then
      echo "-m $m"; return 0
    fi
  done
  # 스크립트 후보
  for f in web/ingest_eod.py ingest/eod.py ingest/main.py tools/ingest_eod.py; do
    [ -f "$f" ] && { echo "$f"; return 0; }
  done
  return 1
}

ENTRY=$(pick_entry || true)
if [ -z "${ENTRY:-}" ]; then
  echo "[EXIT 2] ingest_entry_not_found" | tee -a "$LOGFILE"
  exit 2
fi
echo "[INFO] ingest_entry=${ENTRY}" | tee -a "$LOGFILE"

# 4) 최대 3회 지수 백오프 재시도
MAX_TRY=${MAX_TRY:-3}
BASE_BACKOFF=${BASE_BACKOFF:-60}
i=1
while :; do
  echo "[TRY $i] ${TASK} $(date '+%F %T')" | tee -a "$LOGFILE"

  if bash scripts/linux/jobs/run_py_guarded.sh "$PYTHONBIN" $ENTRY 2>&1 | tee -a "$LOGFILE"; then
    echo "[DONE] ${TASK} $(date '+%F %T')" | tee -a "$LOGFILE"
    exit 0
  fi

  # 외부요인 판독 → 재시도
  if grep -qE "YFRateLimitError|429|Read timed out|Temporary failure in name resolution|Connection reset by peer" "$LOGFILE"; then
    if [ "$i" -lt "$MAX_TRY" ]; then
      backoff=$(( BASE_BACKOFF * 2 ** (i-1) ))
      echo "[WARN] external_issue_retry sleep=${backoff}s (try=$i/$MAX_TRY)" | tee -a "$LOGFILE"
      sleep "$backoff"
      i=$((i+1))
      continue
    else
      echo "[SKIP] external_issue_after_retries RC=0 $(date '+%F %T')" | tee -a "$LOGFILE"
      exit 0
    fi
  fi

  echo "[EXIT 2] logic_error $(date '+%F %T')" | tee -a "$LOGFILE"
  exit 2
done
