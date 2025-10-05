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

# 2) 사후 검증(전일 데이터 실제 반영 확인) → 실패 시 RC=2로 재시도 유도
set +e
"$PYTHONBIN" scripts/ops/postcheck_eod.py
RC=$?
set -e
# 재시도는 스케줄러/상위 잡에서 담당(여기서는 메시지 남기고 RC만 반영)
if [ "$RC" -ne 0 ]; then
  echo "[POSTCHECK] EOD not fresh → exit 2 for retry"
  exit 2
fi
