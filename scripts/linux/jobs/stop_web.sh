#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"

# 기존 run_web.sh에 stop을 위임 (과거 호환용)
bash "$ROOT/scripts/linux/jobs/run_web.sh" stop
