#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."
bash scripts/linux/jobs/run_with_lock.sh scripts/linux/jobs/run_bt.sh
bash scripts/linux/jobs/run_with_lock.sh scripts/linux/jobs/bt_postprocess.sh
