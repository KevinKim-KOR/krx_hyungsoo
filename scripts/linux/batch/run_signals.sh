#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."

# 환경 로드 (래퍼가 불러와도 중복 무해)
[ -f "config/env.nas.sh" ] && source config/env.nas.sh
[ -z "${PYTHONBIN:-}" ] && [ -f "config/env.pc.sh" ] && source config/env.pc.sh

TASK="signals"
LOGFILE="logs/${TASK}_$(date +%F).log"

# 표준 가드 실행: 첫 인자는 반드시 PYTHONBIN 이어야 함
bash scripts/linux/jobs/run_py_guarded.sh "$PYTHONBIN" web/signals.py \
  --mode=cron \
  2>&1 | tee -a "$LOGFILE"
