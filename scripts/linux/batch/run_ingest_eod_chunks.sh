#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."

SRC="${SRC:-data/universe/yf_universe.txt}"
CHUNK_SIZE="${CHUNK_SIZE:-1}"     # 기본 1종
GAP_SEC="${GAP_SEC:-60}"          # 청크 간 대기
RETRY_MAX="${RETRY_MAX:-3}"       # 청크 실패 시 재시도 횟수
RETRY_SLEEP="${RETRY_SLEEP:-45}"  # 재시도 간격
JITTER_MAX="${JITTER_MAX:-7}"     # 각 실행 전 랜덤 추가 딜레이

[ -f "$SRC" ] || { echo "[ERR] SRC not found: $SRC" >&2; exit 2; }

# 야후 윈도우 체크(강제 시 YF_FORCE=1로 우회)
bash scripts/linux/jobs/precheck_yf_window.sh || { echo "[SKIP] outside yf window"; exit 0; }

# 분할(랜덤 순서 권장)
SHUFFLE=1 bash scripts/linux/maintenance/chunk_universe.sh "$SRC" "$CHUNK_SIZE"

CHUNKDIR="data/universe/chunks"
BACKUP="data/universe/.yf_universe.orig.$(date +%s)"
TARGET="data/universe/yf_universe.txt"
cp -a "$TARGET" "$BACKUP" || true
cleanup(){ mv -f "$BACKUP" "$TARGET" 2>/dev/null || true; }
trap cleanup EXIT

echo "[RUN] ingest chunks (size=${CHUNK_SIZE}, gap=${GAP_SEC}s, retry=${RETRY_MAX}x${RETRY_SLEEP}s, jitter<=${JITTER_MAX}s)"
i=0
for f in "$CHUNKDIR"/*.txt; do
  [ -f "$f" ] || continue
  i=$((i+1))
  echo "[SWAP] chunk#$i -> $TARGET ($(wc -l < "$f") lines)"
  cp -f "$f" "$TARGET"

  # 실행 전 지터
  if [ "$JITTER_MAX" -gt 0 ] 2>/dev/null; then
    J=$(( RANDOM % (JITTER_MAX + 1) ))
    echo "[JITTER] +${J}s"
    sleep "$J"
  fi

  # 청크 실행 + 재시도
  attempt=0
  success=0
  while [ $attempt -le "$RETRY_MAX" ]; do
    attempt=$((attempt+1))
    echo "[RUN] chunk#$i attempt=$attempt"
    if bash scripts/linux/batch/run_ingest_eod.sh; then
      # 간단 성공판정: parquet/csv 행수 > 0
      rows_parq=$( (python3 - <<'PY'
import os, glob, pyarrow.parquet as pq
f=sorted(glob.glob('data/tmp/ingest_last.parquet'))[-1:] or []
if f:
    try:
        print(pq.read_table(f[0]).num_rows)
    except Exception:
        print(0)
else:
    print(0)
PY
) 2>/dev/null || echo 0 )
      rows_csv=$( ( [ -f data/tmp/ingest_last.csv ] && tail -n +2 data/tmp/ingest_last.csv | wc -l ) || echo 0 )
      if [ "${rows_parq:-0}" -gt 0 ] || [ "${rows_csv:-0}" -gt 0 ]; then
        echo "[OK] chunk#$i rows(parq=${rows_parq:-0}, csv=${rows_csv:-0})"
        success=1; break
      fi
    fi
    if [ $attempt -le "$RETRY_MAX" ]; then
      echo "[RETRY] chunk#$i sleep ${RETRY_SLEEP}s"
      sleep "$RETRY_SLEEP"
    fi
  done

  echo "[SLEEP] gap ${GAP_SEC}s ..."
  sleep "$GAP_SEC"
done

echo "[DONE] chunks processed: $i"
