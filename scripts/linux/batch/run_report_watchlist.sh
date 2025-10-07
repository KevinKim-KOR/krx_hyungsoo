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
pick_watchlist_cmd() {
  # 2-1) app.py 서브커맨드
  if "$PYTHONBIN" app.py -h 2>/dev/null | grep -qiE 'report-?watchlist'; then
    CMD=( "$PYTHONBIN" app.py report-watchlist )
    return 0
  fi

  # 2-2) 개별 스크립트들
  if [ -f "scripts/report_watchlist.py" ]; then
    CMD=( "$PYTHONBIN" scripts/report_watchlist.py )
    return 0
  fi
  if [ -f "scripts/reporting_watchlist.py" ]; then
    CMD=( "$PYTHONBIN" scripts/reporting_watchlist.py )
    return 0
  fi

  # 2-3) reporting_eod.py 안에 watchlist 모드가 있는 케이스
  if [ -f "scripts/reporting_eod.py" ]; then
    # 우선 --help로 존재여부 힌트 체크(없어도 대부분 --watchlist가 일반적으로 쓰임)
    if "$PYTHONBIN" scripts/reporting_eod.py -h 2>/dev/null | grep -qi 'watchlist'; then
      CMD=( "$PYTHONBIN" scripts/reporting_eod.py --watchlist )
    else
      # help에서 발견 못 해도 관례적으로 --watchlist 시도
      CMD=( "$PYTHONBIN" scripts/reporting_eod.py --watchlist )
    fi
    return 0
  fi

  # 2-4) 루트 경로(레거시)도 탐색
  if [ -f "./report_watchlist.py" ]; then
    CMD=( "$PYTHONBIN" ./report_watchlist.py )
    return 0
  fi
  if [ -f "./reporting_watchlist.py" ]; then
    CMD=( "$PYTHONBIN" ./reporting_watchlist.py )
    return 0
  fi
  if [ -f "./reporting_eod.py" ]; then
    CMD=( "$PYTHONBIN" ./reporting_eod.py --watchlist )
    return 0
  fi

  return 1
}

if ! pick_watchlist_cmd; then
  echo "[ERROR] watchlist entry not found (app.py report-watchlist / scripts/report_watchlist.py / reporting_watchlist.py / reporting_eod.py --watchlist)"
  exit 2
fi

# 3) 본 실행(거래일 가드만, 휴일이면 guarded-skip)
bash scripts/linux/jobs/run_with_lock.sh \
  scripts/linux/jobs/_run_generic.sh \
    --log watchlist \
    --guard td \
    --retry-rc 2 --retry-max 3 --retry-sleep 300 \
    -- \
    "${CMD[@]}"
