#!/usr/bin/env bash
# 사용: bash scripts/linux/maintenance/chunk_universe.sh [SRC] [CHUNK_SIZE]
# 옵션: SHUFFLE=1 로 줄 순서 랜덤화
set -euo pipefail
cd "$(dirname "$0")/../../.."

SRC="${1:-data/universe/yf_universe.txt}"
CHUNK="${2:-5}"
[ -f "$SRC" ] || { echo "[ERR] not found: $SRC" >&2; exit 2; }

OUTDIR="data/universe/chunks"; rm -rf "$OUTDIR"; mkdir -p "$OUTDIR"

TMP="data/universe/.clean.$(date +%s)"
sed -e 's/\r$//' -e 's/^[ \t]*//;s/[ \t]*$//' "$SRC" \
| grep -Ev '^(#|$|EOF)' \
| grep -E '^[A-Za-z0-9^.\-]+$' \
| tr '[:lower:]' '[:upper:]' > "$TMP"

CNT=$(wc -l < "$TMP" || echo 0)
[ "$CNT" -gt 0 ] || { echo "[ERR] cleaned list is empty"; rm -f "$TMP"; exit 3; }

if [ "${SHUFFLE:-0}" = "1" ] && command -v shuf >/dev/null 2>&1; then
  SHU="data/universe/.shuf.$(date +%s)"
  shuf "$TMP" > "$SHU"
  mv -f "$SHU" "$TMP"
fi

split -l "$CHUNK" -a 2 -d "$TMP" "$OUTDIR/chunk_"
for f in "$OUTDIR"/chunk_*; do mv "$f" "${f}.txt"; done
rm -f "$TMP"

echo "[DONE] chunks in $OUTDIR (count=$(ls -1 "$OUTDIR"/*.txt | wc -l)) size=$CHUNK"
ls -1 "$OUTDIR"/*.txt
