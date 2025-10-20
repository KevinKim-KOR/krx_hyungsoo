#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."

# env
[ -f "config/env.nas.sh" ] && source config/env.nas.sh
[ -z "${PYTHONBIN:-}" ] && [ -f "config/env.pc.sh" ] && source config/env.pc.sh

TASK="scanner"
LOGFILE="logs/${TASK}_$(date +%F).log"

echo "[RUN] ${TASK} $(date '+%F %T')" | tee -a "$LOGFILE"

# config 존재 확인 (SPoT 링크)
if [ -f "config/config.yaml" ]; then
  echo "[INFO] using_config config/config.yaml" | tee -a "$LOGFILE"
elif [ -f "config.yaml" ]; then
  echo "[INFO] using_config ./config.yaml" | tee -a "$LOGFILE"
else
  echo "[EXIT 2] missing_config (need: config/config.yaml or ./config.yaml)" | tee -a "$LOGFILE"
  exit 2
fi

# 실행: 직접 엔트리
bash scripts/linux/jobs/run_py_guarded.sh "$PYTHONBIN" -m compat.run_scanner_direct \
  2>&1 | tee -a "$LOGFILE"

echo "[DONE] ${TASK} $(date '+%F %T')" | tee -a "$LOGFILE"
