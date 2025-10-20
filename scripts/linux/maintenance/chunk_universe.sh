#!/usr/bin/env bash
# 분할 대상 유니버스를 정리 후 N줄씩 청크로 쪼갭니다.
# 사용: bash scripts/linux/maintenance/chunk_universe.sh [SRC] [CHUNK_SIZE]
# 예:   bash scripts/linux/maintenance/chunk_universe.sh data/universe/yf_universe.txt 5
set -euo pipefail
cd "$(dirname "$0")/../../.."

SRC="${1:-data/universe/yf_universe.txt}"
CHUNK="${2:-5}"

[ -f "$SRC" ] || { echo "[ERR] not found: $SRC" >&2; exit 2; }
OUTDIR="data/universe/chunks"; rm -rf "$OUTDIR"; mkdir -p "$OUTDIR"

# 1) 정리(주석/빈줄/EOF 제거, 공백트림, 대문자)
TMP="data/universe/.clean.$(date +%s)"
sed -e 's/\r$//' -e 's/^[ \t]*//;s/[ \t]*$//' "$SRC" \
| grep -Ev '^(#|$|EOF)' \
| grep -E '^[A-Za-z0-9^.\-]+$' \
| tr '[:lower:]' '[:upper:]' > "$TMP"

CNT=$(wc -l < "$TMP" || echo 0)
[ "$CNT" -gt 0 ] || { echo "[ERR] cleaned list is empty"; rm -f "$TMP"; exit 3; }

# 2) 청크 생성
split -l "$CHUNK" -a 2 -d "$TMP" "$OUTDIR/chunk_"
# 확장자 통일
for f in "$OUTDIR"/chunk_*; do mv "$f" "${f}.txt"; done
rm -f "$TMP"

echo "[DONE] chunks in $OUTDIR (count=$(ls -1 "$OUTDIR"/*.txt | wc -l)) size=$CHUNK"
ls -1 "$OUTDIR"/*.txt
