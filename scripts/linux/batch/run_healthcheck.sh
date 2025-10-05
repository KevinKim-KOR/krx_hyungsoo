#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."
# 결과를 일별 파일로 남기기
mkdir -p logs
bash scripts/linux/jobs/run_with_lock.sh scripts/linux/utils/healthcheck.sh | tee -a "logs/health_$(date +%F).log"
