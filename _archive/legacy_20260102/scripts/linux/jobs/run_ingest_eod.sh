#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."
[ -f config/env.nas.sh ] && source config/env.nas.sh
PYTHONBIN="${PYTHONBIN:-python3}"

# 1) 수집 (영업일 가드 td + 외부요인 가드)
bash scripts/linux/jobs/run_with_lock.sh \
  scripts/linux/jobs/_run_generic.sh \
    --log ingest_eod \
    --guard td \
    -- \
    bash scripts/linux/jobs/run_py_guarded.sh \
      "$PYTHONBIN" app.py ingest-eod --date auto

# 1.5) 휴일이면 사후검증 생략 (두 패턴 모두 인정)
TODAY=$(date +%F)
LOG="logs/ingest_eod_${TODAY}.log"
# [SKIP] non-trading day  또는  [DONE] ... guarded-skip  둘 다 허용
if grep -qE '(\[SKIP\].*non-trading day|guarded-skip)' "$LOG" 2>/dev/null; then
  echo "[INFO] postcheck skipped (non-trading day/guarded-skip)"
  exit 0
fi


# 2) 사후 검증(전일 데이터 실제 반영 확인) → 실패 시 RC=2로 재시도 유도
set +e
"$PYTHONBIN" scripts/ops/postcheck_eod.py
RC=$?
set -e
if [ "$RC" -ne 0 ]; then
  echo "[POSTCHECK] EOD not fresh → exit 2 for retry"
  exit 2
fi
