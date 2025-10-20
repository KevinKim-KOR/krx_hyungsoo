#!/usr/bin/env bash
# scripts/linux/maintenance/warm_cache_universe.sh
# 목적: 유니버스 티커에 대해 EOD 인게스트를 간격을 두고 순차 수행(레이트리밋 회피)
set -euo pipefail
cd "$(dirname "$0")/../../.."

UF="data/universe/yf_universe.txt"
[ -f "$UF" ] || { echo "[ERR] $UF not found"; exit 2; }

# 환경 로딩(있을 경우)
[ -f "config/env.nas.sh" ] && source config/env.nas.sh

DELAY="${YF_DELAY_SEC:-1.5}"   # 심볼당 대기(초). 필요 시 env로 조정.
COUNT=0
while IFS= read -r sym; do
  sym="$(echo "$sym" | tr -d '[:space:]')"
  [ -z "$sym" ] && continue
  echo "[RUN] ingest EOD -> $sym"
  # 표준 배치 훅 사용(없다면 기존 jobs/run_ingest_eod.sh 로 교체)
  if [ -x "scripts/linux/batch/run_ingest_eod.sh" ]; then
    bash scripts/linux/batch/run_ingest_eod.sh "$sym" || true
  elif [ -x "scripts/linux/jobs/run_ingest_eod.sh" ]; then
    bash scripts/linux/jobs/run_ingest_eod.sh "$sym" || true
  else
    echo "[ERR] ingest runner not found (scripts/linux/batch|jobs/run_ingest_eod.sh)"; exit 2
  fi
  COUNT=$((COUNT+1))
  sleep "$DELAY"
done < "$UF"

echo "[DONE] warmed EOD cache for $COUNT symbols (delay=${DELAY}s)"
