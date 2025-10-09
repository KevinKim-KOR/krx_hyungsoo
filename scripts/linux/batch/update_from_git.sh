#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."
bash scripts/linux/jobs/run_with_lock.sh scripts/linux/utils/update_from_git.sh
bash scripts/linux/jobs/run_with_lock.sh scripts/linux/utils/healthcheck.sh
STATE=".state"; mkdir -p "$STATE"
date '+%F %T' > "$STATE/last_deploy.txt"
touch "$STATE/last_deploy"   # find -newer용 파일마커