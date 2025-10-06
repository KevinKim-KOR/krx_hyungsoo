#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."

# 환경 로드 + 기본값
[ -f config/env.nas.sh ] && source config/env.nas.sh
PYTHONBIN="${PYTHONBIN:-python3}"

# --- 1) 사전 신선도 가드: 영업일 아침 전일 EOD 미신선 → RC=2로 재시도 ---
bash scripts/linux/jobs/_run_generic.sh \
  --log scanner_precheck \
  --guard td \
  --retry-rc 2 --retry-max 2 --retry-sleep 300 \
  -- \
  "$PYTHONBIN" scripts/ops/precheck_eod_fresh.py

# --- 2) 스캐너 본 실행 (거래시간 가드) ---
# app.py scanner 가 우선, 없으면 scanner.py / scripts/scanner.py 자동 대체
CMD=( "$PYTHONBIN" app.py scanner )
if ! "$PYTHONBIN" app.py -h 2>/dev/null | grep -qi scanner; then
  if [ -f ./scanner.py ]; then
    CMD=( "$PYTHONBIN" ./scanner.py )
  elif [ -f scripts/scanner.py ]; then
    CMD=( "$PYTHONBIN" scripts/scanner.py )
  fi
fi

bash scripts/linux/jobs/run_with_lock.sh \
  scripts/linux/jobs/_run_generic.sh \
    --log scanner \
    --guard th \
    -- \
    "${CMD[@]}"
