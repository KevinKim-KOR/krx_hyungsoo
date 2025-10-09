#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."

# 1) git 업데이트 (락으로 보호)
bash scripts/linux/jobs/run_with_lock.sh scripts/linux/utils/update_from_git.sh

# 2) 배포 마커 기록 (헬스체크가 이 시점 이후 로그만 검사)
STATE=".state"; mkdir -p "$STATE"
date '+%F %T' > "$STATE/last_deploy.txt"
touch "$STATE/last_deploy"   # find -newer 기준 파일

# 3) 헬스체크 실행 (배포 이후 로그만 스캔)
bash scripts/linux/jobs/run_with_lock.sh scripts/linux/utils/healthcheck.sh
