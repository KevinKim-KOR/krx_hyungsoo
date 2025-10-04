#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."

# 환경 로드 (있으면 항상 로드)
[ -f "config/env.nas.sh" ] && source config/env.nas.sh
# NAS가 아닌 경우를 대비해, PYTHONBIN이 비어 있으면 PC용도 로드
[ -z "${PYTHONBIN:-}" ] && [ -f "config/env.pc.sh" ] && source config/env.pc.sh

LOCKDIR=".locks"
mkdir -p "$LOCKDIR"

TARGET="${1:-}"
[ -z "$TARGET" ] && { echo "Usage: $0 <script_to_run>"; exit 2; }

LOCKFILE="$LOCKDIR/$(basename "$TARGET").lock"
exec 9>"$LOCKFILE"
if ! flock -n 9; then
  echo "[SKIP] Another instance is running: $TARGET"
  exit 0
fi

set +e
bash "$TARGET"
RC=$?
set -e

# 휴장/스킵은 정상 종료로 정규화
TODAY=$(date +%F)
if grep -qE "\[SKIP\] (non-trading day|guarded-skip)" "logs/"*"_${TODAY}.log" 2>/dev/null; then
  echo "[INFO] Skip detected, normalize RC -> 0"
  exit 0
fi

exit "$RC"
