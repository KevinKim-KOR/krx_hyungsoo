#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."

# 환경 로드(있으면)
[ -f config/env.nas.sh ] && source config/env.nas.sh

# 공용 러너로 로그/락 관리
bash scripts/linux/jobs/run_with_lock.sh \
  scripts/linux/jobs/_run_generic.sh \
    --log health \
    --guard none \
    -- \
    bash scripts/linux/utils/healthcheck.sh
