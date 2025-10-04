#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."

[ -f config/env.nas.sh ] && source config/env.nas.sh
PYTHONBIN="${PYTHONBIN:-python3}"

STRATEGY="${1:-krx_ma200}"
BT_DIR="backtests"
mkdir -p "$BT_DIR" logs

latest="$(ls -dt ${BT_DIR}/*_${STRATEGY} 2>/dev/null | head -n1 || true)"
prev="$(ls -dt ${BT_DIR}/*_${STRATEGY} 2>/dev/null | sed -n '2p' || true)"
[ -z "$latest" ] && { echo "[POST] no latest run found"; exit 0; }

# 최신/이전 모두 manifest 보장
"$PYTHONBIN" scripts/bt/make_manifest.py --run_dir "$latest"
if [ -n "$prev" ] && [ ! -f "$prev/manifest.json" ]; then
  "$PYTHONBIN" scripts/bt/make_manifest.py --run_dir "$prev" || true
fi

if [ -n "$prev" ]; then
  out="logs/compare_${STRATEGY}_$(date +%F).log"
  set +e
  "$PYTHONBIN" scripts/bt/compare_runs.py --a "$prev" --b "$latest" --report_out "$out"
  RC=$?
  set -e

  if [ $RC -ne 0 ]; then
    echo "[POST] DRIFT detected (see $out)"
    [ -f "$out" ] && head -n 20 "$out" || echo "[POST] compare report not found"
    # 알림 훅이 있으면 여기서 호출
  else
    echo "[POST] compare OK"
  fi
else
  echo "[POST] prev run not found; compare skipped"
fi
