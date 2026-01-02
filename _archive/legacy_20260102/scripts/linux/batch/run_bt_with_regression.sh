#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."
bash scripts/linux/jobs/run_with_lock.sh scripts/linux/jobs/run_bt.sh
bash scripts/linux/jobs/run_with_lock.sh scripts/linux/jobs/bt_postprocess.sh

# --- DRIFT 알림/요약 ---
STRATEGY="${STRATEGY:-krx_ma200}"          # 스크립트 상단에서 이미 세팅되어 있으면 그대로 사용
TODAY=$(date +%F)
CMPLOG="logs/compare_${STRATEGY}_${TODAY}.log"

if [ -f "$CMPLOG" ] && grep -q '\[RESULT\] DRIFT' "$CMPLOG"; then
  MSG="$("$PYTHONBIN" scripts/ops/drift_summary.py --strategy "$STRATEGY" --date "$TODAY" || true)"
  echo "$MSG" | sed -e 's/^/[DRIFT] /' >> "$CMPLOG"
  "$PYTHONBIN" scripts/ops/notify.py --title "Backtest DRIFT: ${STRATEGY}" --message "$MSG" --channel auto || true
fi

# --- NEW: 웹 인덱스 자동 갱신 (실패해도 파이프라인을 막지 않음) ---
if [ -x scripts/linux/batch/build_web_index.sh ]; then
  echo "[POST] rebuild web index"
  # build_web_index.sh 내부에서 run_with_lock + generic 사용 → 중첩 호출 OK
  bash scripts/linux/batch/build_web_index.sh || true
fi
