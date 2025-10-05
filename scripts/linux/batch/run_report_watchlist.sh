#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."

# 환경 로드 + PYTHONBIN 기본값
[ -f config/env.nas.sh ] && source config/env.nas.sh
PYTHONBIN="${PYTHONBIN:-python3}"

# 락 + 제너릭 러너 + 거래일 가드(td)
# 신선도 실패(RC=2)시 5분 간격 2회 재시도
bash scripts/linux/jobs/run_with_lock.sh \
  scripts/linux/jobs/_run_generic.sh \
    --log watchlist \
    --guard td \
    --retry-rc 2 --retry-max 2 --retry-sleep 300 \
    -- \
    bash scripts/linux/jobs/run_watchlist_with_freshness.sh
