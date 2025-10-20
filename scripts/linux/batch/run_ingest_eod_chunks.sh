#!/usr/bin/env bash
# 유니버스를 작은 청크 파일로 나눈 뒤, 각 청크를 "실제 유니버스 파일"로 스왑하여
# 기존 bulk 인게스트(run_ingest_eod.sh)를 여러 번 실행합니다.
# 레이트리밋 회피를 위해 청크 간 대기 적용.
#
# 환경변수:
#   SRC        : 원본 유니버스 파일 (기본: data/universe/yf_universe.txt)
#   CHUNK_SIZE : 청크 크기(줄수)    (기본: 5)
#   GAP_SEC    : 청크 간 대기(초)    (기본: 20)
#   YF_FORCE   : 1이면 윈도우 가드 무시(수동 백필용)
set -euo pipefail
cd "$(dirname "$0")/../../.."

SRC="${SRC:-data/universe/yf_universe.txt}"
CHUNK_SIZE="${CHUNK_SIZE:-5}"
GAP_SEC="${GAP_SEC:-20}"

[ -f "$SRC" ] || { echo "[ERR] SRC not found: $SRC" >&2; exit 2; }

# 0) 야후 윈도우 체크(강제 시 우회)
bash scripts/linux/jobs/precheck_yf_window.sh || {
  echo "[SKIP] outside yf window"; exit 0;
}

# 1) 청크 생성
bash scripts/linux/maintenance/chunk_universe.sh "$SRC" "$CHUNK_SIZE"

CHUNKDIR="data/universe/chunks"
BACKUP="data/universe/.yf_universe.orig.$(date +%s)"
TARGET="data/universe/yf_universe.txt"

cp -a "$TARGET" "$BACKUP" || true

cleanup() {
  mv -f "$BACKUP" "$TARGET" 2>/dev/null || true
}
trap cleanup EXIT

echo "[RUN] ingest chunks (size=${CHUNK_SIZE}, gap=${GAP_SEC}s)"
i=0
for f in "$CHUNKDIR"/*.txt; do
  [ -f "$f" ] || continue
  i=$((i+1))
  echo "[SWAP] chunk#$i -> $TARGET  ($(wc -l < "$f") lines)"
  cp -f "$f" "$TARGET"

  # 실행 (기존 bulk 엔트리 재사용)
  bash scripts/linux/batch/run_ingest_eod.sh || true

  echo "[SLEEP] gap ${GAP_SEC}s ..."
  sleep "$GAP_SEC"
done

echo "[DONE] chunks processed: $i"
