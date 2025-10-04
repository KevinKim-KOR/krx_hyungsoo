#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."
bash scripts/linux/utils/run_with_lock.sh scripts/linux/jobs/report_eod.sh
