#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."

LOCKDIR=".locks"
mkdir -p "$LOCKDIR"

if [ $# -lt 1 ]; then
  echo "Usage: $0 <script_to_run> [args...]" ; exit 2
fi

TARGET="$1"
shift

LOCKFILE="$LOCKDIR/$(basename "$TARGET").lock"
exec 9>"$LOCKFILE"
if ! flock -n 9; then
  echo "[SKIP] Another instance is running: $TARGET"
  exit 0
fi

bash -c "$TARGET" "$@"
