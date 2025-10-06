#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."

# 0) env + python 강제
[ -f "config/env.nas.sh" ] && source config/env.nas.sh
PYTHONBIN="${PYTHONBIN:-python3}"

# 1) 프리체크(공통 정책, RC=2면 재시도)
bash scripts/linux/jobs/_run_generic.sh \
  --log watchlist_precheck \
  --retry-rc 2 --retry-max 3 --retry-sleep 300 \
  -- \
  "$PYTHONBIN" -m scripts.ops.precheck_eod_fresh --task watchlist

# 2) 엔트리 결정(기존 동작 유지)
CMD=( "$PYTHONBIN" app.py report-watchlist )
if ! "$PYTHONBIN" app.py -h 2>/dev/null | grep -qi "report-watchlist"; then
  if [ -f "scripts/report_watchlist.py" ]; then
    CMD=( "$PYTHONBIN" scripts/report_watchlist.py )
  elif [ -f "./report_watchlist.py" ]; then
    CMD=( "$PYTHONBIN" ./report_watchlist.py )
  else
    echo "[ERROR] watchlist entry not found (app.py report-watchlist / scripts/report_watchlist.py)"; exit 2
  fi
fi

# 3) 본 실행(거래일 가드만, 휴일이면 guarded-skip)
bash scripts/linux/jobs/run_with_lock.sh \
  scripts/linux/jobs/_run_generic.sh \
    --log watchlist \
    --guard td \
    --retry-rc 2 --retry-max 3 --retry-sleep 300 \
    -- \
    "${CMD[@]}"
