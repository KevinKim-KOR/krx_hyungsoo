#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."

STRATEGY="${1:-krx_ma200}"
BT_DIR="backtests"
mkdir -p "$BT_DIR" logs

# 최신/이전 실행 디렉토리 찾기
latest="$(ls -dt ${BT_DIR}/*_${STRATEGY} 2>/dev/null | head -n1 || true)"
prev="$(ls -dt ${BT_DIR}/*_${STRATEGY} 2>/dev/null | sed -n '2p' || true)"
[ -z "$latest" ] && { echo "[POST] no latest run found"; exit 0; }

# 매니페스트 생성
python3 scripts/bt/make_manifest.py --run_dir "$latest"

# 이전 실행이 있으면 비교
if [ -n "$prev" ]; then
  out="logs/compare_${STRATEGY}_$(date +%F).log"
  set +e
  python3 scripts/bt/compare_runs.py --a "$prev" --b "$latest" --report_out "$out"
  RC=$?
  set -e

  if [ $RC -ne 0 ]; then
    echo "[POST] DRIFT detected (see $out)"
    # 텔레그램 알림(존재 시)
    if [ -x scripts/linux/jobs/ping_telegram.sh ]; then
      head -n 20 "$out" | scripts/linux/jobs/ping_telegram.sh "BT DRIFT ${STRATEGY}"
    fi
    # 드리프트를 실패로 처리하려면 아래 줄 주석 해제
    # exit $RC
  else
    echo "[POST] compare OK"
  fi
else
  echo "[POST] prev run not found; compare skipped"
fi
