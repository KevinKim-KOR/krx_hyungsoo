#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."

# env 로드
[ -f "config/env.nas.sh" ] && source config/env.nas.sh
[ -z "${PYTHONBIN:-}" ] && [ -f "config/env.pc.sh" ] && source config/env.pc.sh

TASK="signals"
LOGFILE="logs/${TASK}_$(date +%F).log"

# 표준 가드 실행: 모듈 엔트리(-m signals.main)
bash scripts/linux/jobs/run_py_guarded.sh "$PYTHONBIN" -m signals.main \
  --mode=cron \
  2>&1 | tee -a "$LOGFILE"
