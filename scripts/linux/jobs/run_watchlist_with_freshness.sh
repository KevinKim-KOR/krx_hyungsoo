#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."

# 환경 로드 + PYTHONBIN 기본값
[ -f config/env.nas.sh ] && source config/env.nas.sh
PYTHONBIN="${PYTHONBIN:-python3}"

# 1) 신선도 가드 (최신 거래일 캐시 미충족 시 RC=2)
set +e
"$PYTHONBIN" scripts/ops/freshness_guard.py
RC=$?
set -e
if [ "$RC" -ne 0 ]; then
  # RC=2는 _run_generic 의 --retry-rc 와 연동됨 (재시도 유도)
  exit 2
fi

# 2) 실제 워치리스트 실행 (외부요인은 run_py_guarded 가 가드)
exec bash scripts/linux/jobs/run_py_guarded.sh \
  "$PYTHONBIN" report_watchlist_cli.py --date auto
