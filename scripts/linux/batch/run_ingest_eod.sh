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

# 2) 랜덤 지터 (동시호출 완화)
JITTER_MAX_SEC=${JITTER_MAX_SEC:-60}
if [ "$JITTER_MAX_SEC" -gt 0 ]; then
  s=$(( RANDOM % JITTER_MAX_SEC ))
  echo "[INFO] jitter_sleep ${s}s" | tee -a "$LOGFILE"
  sleep "$s"
fi

# 3) 본 실행(최대 3회 지수 백오프)
MAX_TRY=${MAX_TRY:-3}
BASE_BACKOFF=${BASE_BACKOFF:-60} # sec
i=1
while :; do
  echo "[TRY $i] ${TASK} $(date '+%F %T')" | tee -a "$LOGFILE"

  # 기존 파이썬 엔트리 (여기서는 코드 변경 없음)
  # * 향후 하이브리드 적용 시 -m ingest.yf_hybrid 로 교체 예정
  if bash scripts/linux/jobs/run_py_guarded.sh "$PYTHONBIN" -m web.ingest_eod 2>&1 | tee -a "$LOGFILE"; then
    echo "[DONE] ${TASK} $(date '+%F %T')" | tee -a "$LOGFILE"
    exit 0
  fi

  # 실패 원인 판독 (레이트리밋/네트워크 → 외부요인)
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

  # 로직 오류는 즉시 종료(RC=2)
  echo "[EXIT 2] logic_error $(date '+%F %T')" | tee -a "$LOGFILE"
  exit 2
done
