#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."

# --- 환경 로드 ---
[ -f "config/env.nas.sh" ] && source config/env.nas.sh
[ -z "${PYTHONBIN:-}" ] && [ -f "config/env.pc.sh" ] && source config/env.pc.sh

TASK="scanner"
LOGFILE="logs/${TASK}_$(date +%F).log"

echo "[RUN] ${TASK} $(date '+%F %T')" | tee -a "$LOGFILE"

# --- 설정 파일 탐색 (우선순위) ---
# 1) SCANNER_CONFIG 환경변수로 강제 지정 가능
CFG_CANDIDATES=()
[ -n "${SCANNER_CONFIG:-}" ] && CFG_CANDIDATES+=("${SCANNER_CONFIG}")
CFG_CANDIDATES+=(
  "config/scanner.yaml"
  "config/scanner.yml"
  "config/config.yaml"
  "config.yaml"
)

CFG=""
for p in "${CFG_CANDIDATES[@]}"; do
  if [ -f "$p" ]; then CFG="$p"; break; fi
done

if [ -z "$CFG" ]; then
  echo "[EXIT 2] missing_config (tried: ${CFG_CANDIDATES[*]})" | tee -a "$LOGFILE"
  echo "[HINT] 준비된 스캐너 설정 파일의 실제 경로를 찾아 SCANNER_CONFIG로 지정하세요." | tee -a "$LOGFILE"
  echo "[HINT] 예) SCANNER_CONFIG=config/my_scanner.yaml bash scripts/linux/batch/run_scanner.sh" | tee -a "$LOGFILE"
  exit 2
fi

echo "[INFO] using_config $CFG" | tee -a "$LOGFILE"

# --- 실제 실행 (app.py 스캐너 엔트리 가정) ---
# app.py는 스택트레이스 기준 루트에 존재하며, 'scanner' 서브커맨드를 받습니다.
bash scripts/linux/jobs/run_py_guarded.sh "$PYTHONBIN" app.py scanner --config "$CFG" \
  2>&1 | tee -a "$LOGFILE"

echo "[DONE] ${TASK} $(date '+%F %T')" | tee -a "$LOGFILE"
