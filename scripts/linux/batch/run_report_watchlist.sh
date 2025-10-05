#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."

# 환경 로드 + PYTHONBIN 기본값
[ -f config/env.nas.sh ] && source config/env.nas.sh
PYTHONBIN="${PYTHONBIN:-python3}"

# 락 + 제너릭 러너 + 거래일 가드(td) + 외부요인 스킵(run_py_guarded)
bash scripts/linux/jobs/run_with_lock.sh \
  scripts/linux/jobs/_run_generic.sh \
    --log watchlist \
    --guard td \
    -- \
    bash scripts/linux/jobs/run_py_guarded.sh \
      "$PYTHONBIN" report_watchlist_cli.py --date auto
