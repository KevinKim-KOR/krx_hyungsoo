#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."

echo "[RUN] verify_signal_job $(date '+%F %T')"

WRAPPER="scripts/linux/batch/run_signal_wrapper.sh"
TARGET="scripts/linux/batch/run_signals.sh"

[ -f "$WRAPPER" ] || { echo "[EXIT] missing $WRAPPER"; exit 2; }
[ -x "$WRAPPER" ] || { echo "[EXIT] no exec perm on $WRAPPER"; exit 2; }
[ -f "$TARGET" ]  || { echo "[EXIT] missing $TARGET"; exit 2; }

echo "[INFO] wrapper found: $WRAPPER"
echo "[INFO] target found : $TARGET"

echo "[INFO] 안전 실행 가이드"
echo "      - 아래 커맨드는 실제 푸시를 발생시킬 수 있습니다."
echo "      - dry-run 변수가 구현되어 있지 않다면 수동 실행은 주의하세요."
echo "예) JITTER_MAX_SEC=0 bash $WRAPPER"
echo "[DONE] verify_signal_job"
