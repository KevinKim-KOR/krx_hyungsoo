#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."

[ -f config/env.nas.sh ] && source config/env.nas.sh
PYTHONBIN="${PYTHONBIN:-python3}"

STRATEGY="${1:-krx_ma200}"
BT_DIR="${2:-backtests}"
mkdir -p "$BT_DIR" logs

# 1) 실행 디렉토리 스냅샷 (mtime 고정)
mapfile -t runs < <(ls -dt ${BT_DIR}/*_"${STRATEGY}" 2>/dev/null || true)

if [ "${#runs[@]}" -lt 2 ]; then
  # 최신 1건만 있으면 비교는 스킵하고 종료
  if [ "${#runs[@]}" -eq 1 ]; then
    "$PYTHONBIN" scripts/bt/make_manifest.py --run_dir "${runs[0]}" || true
  fi
  echo "[POST] prev run not found; compare skipped"
  exit 0
fi

latest="${runs[0]}"
prev="${runs[1]}"

# 2) 매니페스트 생성 (이제 mtime 바뀌어도 스냅샷에는 영향 없음)
"$PYTHONBIN" scripts/bt/make_manifest.py --run_dir "$latest" || true
[ -f "$prev/manifest.json" ] || "$PYTHONBIN" scripts/bt/make_manifest.py --run_dir "$prev" || true

# 3) 비교 (A=prev baseline, B=latest candidate)
out="logs/compare_${STRATEGY}_$(date +%F).log"
set +e
"$PYTHONBIN" scripts/bt/compare_runs.py --a "$prev" --b "$latest" --report_out "$out"
RC=$?
set -e

if [ $RC -ne 0 ]; then
  echo "[POST] DRIFT detected (see $out)"
  [ -f "$out" ] && head -n 20 "$out" || echo "[POST] compare report not found"
else
  echo "[POST] compare OK"
fi
