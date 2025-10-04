#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."

# 먼저 환경 로드 + 기본값 보장
[ -f config/env.nas.sh ] && source config/env.nas.sh
PYTHONBIN="${PYTHONBIN:-python3}"

bash scripts/linux/jobs/run_with_lock.sh \
  scripts/linux/jobs/_run_generic.sh \
    --log scanner \
    --guard th \
    -- \
    "$PYTHONBIN" app.py scanner
