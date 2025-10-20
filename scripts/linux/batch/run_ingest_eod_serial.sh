#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."

# env
[ -f "config/env.nas.sh" ] && source config/env.nas.sh
[ -z "${PYTHONBIN:-}" ] && [ -f "config/env.pc.sh" ] && source config/env.pc.sh

UF="data/universe/yf_universe.txt"
LOG="logs/ingest_serial_$(date +%F).log"
DELAY="${YF_DELAY_SEC:-2}"

[ -f "$UF" ] || { echo "[ERR] $UF not found" | tee -a "$LOG"; exit 2; }

# 야후 윈도우 체크는 유지하되, 강제 필요시 YF_FORCE=1로 우회
bash scripts/linux/jobs/precheck_yf_window.sh || exit 0

echo "[RUN] ingest_serial $(date '+%F %T') delay=${DELAY}s" | tee -a "$LOG"

i=0
while IFS= read -r sym; do
  sym="$(echo "$sym" | tr -d '[:space:]')"
  [ -z "$sym" ] && continue
  # 안전 필터: 티커 정규식
  if ! echo "$sym" | grep -qiE '^[A-Za-z0-9\^\.\-\_]+$'; then
    echo "[SKIP] invalid_symbol: $sym" | tee -a "$LOG"
    continue
  fi
  i=$((i+1))
  echo "[RUN] ($i) $sym" | tee -a "$LOG"
  # 단건 인게스트 (기존 엔트리 일관 유지)
  if ! bash scripts/linux/jobs/run_py_guarded.sh "$PYTHONBIN" -m ingest.main --symbol "$sym" 2>&1 | tee -a "$LOG"; then
    echo "[WARN] ingest_fail: $sym (continue)" | tee -a "$LOG"
  fi
  sleep "$DELAY"
done < "$UF"

echo "[DONE] ingest_serial $(date '+%F %T') count=$i" | tee -a "$LOG"
