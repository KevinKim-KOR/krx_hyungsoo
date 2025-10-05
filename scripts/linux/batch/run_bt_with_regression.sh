#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."
bash scripts/linux/jobs/run_with_lock.sh scripts/linux/jobs/run_bt.sh
bash scripts/linux/jobs/run_with_lock.sh scripts/linux/jobs/bt_postprocess.sh
# ... (기존 내용 동일: 후보/베이스라인 비교 및 로그 남김)

# --- NEW: 웹 인덱스 자동 갱신 (실패해도 파이프라인을 막지 않음) ---
if [ -x scripts/linux/batch/build_web_index.sh ]; then
  echo "[POST] rebuild web index"
  # build_web_index.sh 내부에서 run_with_lock + generic 사용 → 중첩 호출 OK
  bash scripts/linux/batch/build_web_index.sh || true
fi
