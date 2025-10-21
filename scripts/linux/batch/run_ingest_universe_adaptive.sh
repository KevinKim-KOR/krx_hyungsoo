#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."

[ -f "config/env.nas.sh" ] && source config/env.nas.sh
PY="${PYTHONBIN:-python3}"

SRC="${SRC:-data/universe/yf_universe.txt}"
TMP="data/universe/.adaptive_$(date +%s)"
mkdir -p data/universe

# 0) 유니버스 정리 + 벤치마크 보강
if [ ! -f "$SRC" ]; then
  echo "[ERR] universe file not found: $SRC" >&2
  exit 2
fi
# 정리(LF/트림/주석제거/대문자)
sed -e 's/\r$//' "$SRC" \
| sed -e 's/^[ \t]*//;s/[ \t]*$//' \
| grep -Ev '^(#|$|EOF)' \
| tr '[:lower:]' '[:upper:]' > "$TMP"

# 벤치마크 강제 포함: ^KS11, SPY
grep -q '^\^KS11$' "$TMP" || echo "^KS11" >> "$TMP"
grep -q '^SPY$'     "$TMP" || echo "SPY"   >> "$TMP"

# 1) 단건 인게스트(레이트리밋 친화)
echo "[RUN] one-by-one ingest"
SRC="$TMP" \
YF_MIN_INTERVAL_SEC="${YF_MIN_INTERVAL_SEC:-4}" \
DELAY_SEC="${DELAY_SEC:-2}" \
JITTER_MAX_SEC="${JITTER_MAX_SEC:-5}" \
RETRY_MAX="${RETRY_MAX:-3}" \
bash scripts/linux/batch/run_ingest_one_symbol.sh

# 2) 캐시 -> DB 싱크
echo "[RUN] cache -> DB sync"
bash scripts/linux/batch/run_sync_cache_to_db.sh || true

# 3) 리포트 (프리체크 OK면 재시도 없이 1회)
echo "[RUN] EOD report"
bash scripts/linux/batch/run_report_eod.sh || true

echo "[DONE] adaptive ingest + sync + report"
