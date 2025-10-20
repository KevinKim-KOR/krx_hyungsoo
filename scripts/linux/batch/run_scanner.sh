#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."

# --- 환경 로드 ---
[ -f "config/env.nas.sh" ] && source config/env.nas.sh
[ -z "${PYTHONBIN:-}" ] && [ -f "config/env.pc.sh" ] && source config/env.pc.sh

TASK="scanner"
LOGFILE="logs/${TASK}_$(date +%F).log"

echo "[RUN] ${TASK} $(date '+%F %T')" | tee -a "$LOGFILE"

# --- 설정 파일 존재 확인 (고정 경로: config/config.yaml 또는 ./config.yaml) ---
CFG=""
if [ -f "config/config.yaml" ]; then
  CFG="config/config.yaml"
elif [ -f "config.yaml" ]; then
  CFG="config.yaml"
fi

if [ -z "$CFG" ]; then
  echo "[EXIT 2] missing_config (need: config/config.yaml or ./config.yaml)" | tee -a "$LOGFILE"
  echo "[HINT] ln -sf scanner.yaml config/config.yaml  # link to your SPoT config" | tee -a "$LOGFILE"
  exit 2
fi
echo "[INFO] using_config $CFG" | tee -a "$LOGFILE"

# --- 실제 실행 (top-level app.py, subcommand: scanner, 인자 없음) ---
bash scripts/linux/jobs/run_py_guarded.sh "$PYTHONBIN" app.py scanner \
  2>&1 | tee -a "$LOGFILE"

echo "[DONE] ${TASK} $(date '+%F %T')" | tee -a "$LOGFILE"
