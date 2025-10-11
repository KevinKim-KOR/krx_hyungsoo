#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."   # ← 레포 루트로 이동 (scripts/linux/jobs → ../..)

# 환경 로드
[ -f config/env.nas.sh ] && source config/env.nas.sh
PYTHONBIN="${PYTHONBIN:-python3}"

LOG="logs/scanner_$(date +%F).log"
mkdir -p logs

bash scripts/linux/jobs/precheck_calendar_guard.sh
RC=$?
if [[ $RC -eq 2 ]]; then
  # 데이터 신선도 부족 → 재시도 루프에서 처리
  exit 2
fi

{
  echo "[RUN] scanner $(date '+%F %T')"

  # 1) 휴장/장시간 가드 (파이썬 한줄 스크립트)
  set +e
  "$PYTHONBIN" - <<'PY'
import sys
from utils.trading_day import is_trading_day, in_trading_hours
if not is_trading_day():
    print("[SKIP] non-trading day"); sys.exit(200)
if not in_trading_hours():
    print("[SKIP] out-of-trading-hours"); sys.exit(201)
PY
  rc=$?
  set -e
  if [ $rc -ge 200 ]; then
    echo "[DONE] scanner guarded-skip $(date '+%F %T')"
    exit 0
  fi

  # 2) 본 실행 (외부요인 → 스킵으로 전환)
  bash scripts/linux/jobs/run_py_guarded.sh "$PYTHONBIN" app.py scanner

  echo "[DONE] scanner $(date '+%F %T')"
} | tee -a "$LOG"
