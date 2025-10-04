#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."

LOCKDIR=".locks"
mkdir -p "$LOCKDIR"

TARGET="${1:-}"              # 예: scripts/linux/jobs/scanner.sh
[ -z "$TARGET" ] && { echo "Usage: $0 <script_to_run>"; exit 2; }

LOCKFILE="$LOCKDIR/$(basename "$TARGET").lock"
exec 9>"$LOCKFILE"
if ! flock -n 9; then
  echo "[SKIP] Another instance is running: $TARGET"
  exit 0
fi

# 환경 로드 (PC/NAS 구분)
if [ -f "config/env.nas.sh" ] && [ "${ENV:=}" = "nas" ]; then
  source config/env.nas.sh
elif [ -f "config/env.pc.sh" ] && [ "${ENV:=}" = "pc" ]; then
  source config/env.pc.sh
fi

set +e
bash "$TARGET"
RC=$?
set -e

# 휴장/가드 스킵은 정상 종료로 정규화
TODAY=$(date +%F)
if grep -qE "\[SKIP\] (non-trading day|guarded-skip)" "logs/"*"_${TODAY}.log" 2>/dev/null; then
  echo "[INFO] Skip detected, normalize RC -> 0"
  exit 0
fi

exit "$RC"
