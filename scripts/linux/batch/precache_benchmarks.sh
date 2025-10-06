#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."

# 환경 + 파이썬
[ -f config/env.nas.sh ] && source config/env.nas.sh
PYTHONBIN="${PYTHONBIN:-python3}"

# 지터: 기본 0~300초 (환경변수로 조절 가능)
JITTER_MAX="${JITTER_MAX_SEC:-300}"
if [[ "$JITTER_MAX" =~ ^[0-9]+$ ]] && [ "$JITTER_MAX" -gt 0 ]; then
  J=$(( RANDOM % (JITTER_MAX + 1) ))
  echo "[JITTER] sleep ${J}s"
  sleep "$J"
fi

# 락 + 제너릭 + 영업일 가드(td) + 실패(RC=2) 재시도(5분 x 2회)
bash scripts/linux/jobs/run_with_lock.sh \
  scripts/linux/jobs/_run_generic.sh \
    --log precache_bm \
    --guard td \
    --retry-rc 2 --retry-max 2 --retry-sleep 300 \
    -- \
    "$PYTHONBIN" scripts/ops/precache_benchmarks.py
