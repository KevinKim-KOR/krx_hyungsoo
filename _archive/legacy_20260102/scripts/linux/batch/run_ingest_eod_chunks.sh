#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."

SRC="${SRC:-data/universe/yf_universe.txt}"
CHUNK_SIZE="${CHUNK_SIZE:-1}"
GAP_SEC="${GAP_SEC:-60}"
RETRY_MAX="${RETRY_MAX:-3}"
RETRY_SLEEP="${RETRY_SLEEP:-45}"
JITTER_MAX="${JITTER_MAX:-7}"
STOP_ON_FIRST_SUCCESS="${STOP_ON_FIRST_SUCCESS:-1}"  # ✅ 성공 1건이면 즉시 종료
MAX_CHUNKS="${MAX_CHUNKS:-0}"                        # ✅ 0이면 모두, >0이면 그 개수만

[ -f "$SRC" ] || { echo "[ERR] SRC not found: $SRC" >&2; exit 2; }

# 야후 윈도우(강제시 precheck 내부에서 YF_FORCE=1이면 통과)
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
success_count=0
for f in "$CHUNKDIR"/*.txt; do
  [ -f "$f" ] || continue
  i=$((i+1))
  if [ "$MAX_CHUNKS" -gt 0 ] && [ "$i" -gt "$MAX_CHUNKS" ]; then
    echo "[STOP] reached MAX_CHUNKS=${MAX_CHUNKS}"; break
  fi
  echo "[SWAP] chunk#$i -> $TARGET ($(wc -l < "$f") lines)"
  cp -f "$f" "$TARGET"

  # 지터
  if [ "$JITTER_MAX" -gt 0 ] 2>/dev/null; then
    J=$(( RANDOM % (JITTER_MAX + 1) )); echo "[JITTER] +${J}s"; sleep "$J"
  fi

  # 실행 + 재시도
  attempt=0
  ok=0
  while [ $attempt -le "$RETRY_MAX" ]; do
    attempt=$((attempt+1))
    echo "[RUN] chunk#$i attempt=$attempt"
    if bash scripts/linux/batch/run_ingest_eod.sh; then
      # 성공판정: parquet/csv 행수>0
      rows_parq=$( (python3 - <<'PY'
import glob
try:
    import pyarrow.parquet as pq
    f=sorted(glob.glob('data/tmp/ingest_last.parquet'))[-1:] or []
    print(pq.read_table(f[0]).num_rows if f else 0)
except Exception:
    print(0)
PY
) 2>/dev/null || echo 0 )
      rows_csv=$( ( [ -f data/tmp/ingest_last.csv ] && tail -n +2 data/tmp/ingest_last.csv | wc -l ) || echo 0 )
      if [ "${rows_parq:-0}" -gt 0 ] || [ "${rows_csv:-0}" -gt 0 ]; then
        echo "[OK] chunk#$i rows(parq=${rows_parq:-0}, csv=${rows_csv:-0})"
        ok=1; success_count=$((success_count+1)); break
      fi
    fi
    if [ $attempt -le "$RETRY_MAX" ]; then
      echo "[RETRY] chunk#$i sleep ${RETRY_SLEEP}s"; sleep "$RETRY_SLEEP"
    fi
  done

  # ✅ 성공 시 즉시 종료 옵션
  if [ "$ok" -eq 1 ] && [ "$STOP_ON_FIRST_SUCCESS" = "1" ]; then
    echo "[STOP] first success achieved (success_count=${success_count})"; break
  fi

  echo "[SLEEP] gap ${GAP_SEC}s ..."; sleep "$GAP_SEC"
done

echo "[DONE] chunks processed: $i, success=${success_count}"
