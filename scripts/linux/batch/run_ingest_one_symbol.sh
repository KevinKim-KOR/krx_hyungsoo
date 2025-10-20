#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."

[ -f "config/env.nas.sh" ] && source config/env.nas.sh
PY="${PYTHONBIN:-python3}"

SRC="${SRC:-data/universe/yf_universe.txt}"
DELAY="${DELAY_SEC:-2}"
JITTER_MAX="${JITTER_MAX_SEC:-5}"
RETRY_MAX="${RETRY_MAX:-3}"

[ -f "$SRC" ] || { echo "[ERR] SRC not found: $SRC" >&2; exit 2; }

echo "[RUN] ingest one-by-one src=$SRC delay=$DELAY jitter<=$JITTER_MAX retry=$RETRY_MAX"

i=0
while IFS= read -r sym; do
  sym="$(echo "$sym" | tr -d '[:space:]')"
  [[ -z "$sym" || "$sym" =~ ^# ]] && continue

  ((i++))
  # 지터
  if [ "$JITTER_MAX" -gt 0 ] 2>/dev/null; then
    j=$(( RANDOM % (JITTER_MAX + 1) ))
    sleep "$j"
  fi

  attempt=0
  while [ $attempt -le "$RETRY_MAX" ]; do
    attempt=$((attempt+1))
    echo "[RUN] ($i) $sym attempt=$attempt"
    out="$($PY -m scripts.ops.ingest_one_symbol --symbol "$sym" 2>&1 || true)"
    echo "$out"

    if echo "$out" | grep -qiE 'Too Many Requests|Rate limited'; then
      # 강한 백오프
      sleep $(( 20 + attempt*15 ))
      continue
    fi

    # 성공/유지/부분실패도 다음 심볼로
    break
  done

  sleep "$DELAY"
done < "$SRC"

echo "[DONE] ingest one-by-one count=$i"
