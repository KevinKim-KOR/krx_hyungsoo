#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."

# 환경 로드 (중복 무해)
[ -f "config/env.nas.sh" ] && source config/env.nas.sh
[ -z "${PYTHONBIN:-}" ] && [ -f "config/env.pc.sh" ] && source config/env.pc.sh

TASK="signals"
LOGFILE="logs/${TASK}_$(date +%F).log"

# 파일 직접 실행 대신 모듈 실행(-m)로 import 충돌 방지
bash scripts/linux/jobs/run_py_guarded.sh "$PYTHONBIN" -m web.signals \
  --mode=cron \
  2>&1 | tee -a "$LOGFILE"
