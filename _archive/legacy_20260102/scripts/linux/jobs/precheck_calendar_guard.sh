#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"

# env / python 고정
# shellcheck disable=SC1091
source config/env.nas.sh
PY="${PYTHONBIN:-python3}"

LOG_PREFIX="[CALGUARD]"
TODAY_KST="$(TZ=Asia/Seoul date +%F)"
NOW_HM_KST="$(TZ=Asia/Seoul date +%H%M)"   # 예: 0930

CACHE="data/cache/kr/trading_days.pkl"

# python helper: read cache last day & contains today
read_cache() {
  "$PY" - <<'PY'
import pathlib, pickle, sys, datetime as dt, os
p = pathlib.Path("data/cache/kr/trading_days.pkl")
if not p.exists():
    print("exists=0 last= None contains_today=0")
    sys.exit(0)
try:
    days = pickle.load(open(p, "rb"))
    days = list(days)
except Exception:
    print("exists=0 last= None contains_today=0")
    sys.exit(0)
days_str = [str(d)[:10] for d in days if d is not None]
last = days_str[-1] if days_str else None
today = os.environ.get("CAL_TODAY")
print(f"exists=1 last={last} contains_today={int(today in days_str)}")
PY
}

is_weekday_kst() {
  # 1(월)..5(금) 범위면 영업일 가능성
  local dow
  dow="$(TZ=Asia/Seoul date +%u)"
  [[ "$dow" -ge 1 && "$dow" -le 5 ]]
}

is_trading_hours_kst() {
  # 09:00~15:30 사이면 영업시간(간단 가정)
  local hm="$NOW_HM_KST"
  [[ "$hm" -ge 0900 && "$hm" -le 1530 ]]
}

echo "[PRECHECK] $LOG_PREFIX today=$TODAY_KST hm=$NOW_HM_KST cache=$CACHE"

export CAL_TODAY="$TODAY_KST"
read1="$(read_cache)"
echo "$read1" | sed "s/^/[PRECHECK] $LOG_PREFIX cache1 /"

# parse
exists1="$(awk '{for(i=1;i<=NF;i++) if($i ~ /exists=/){split($i,a,"="); print a[2]}}' <<< "$read1")"
last1="$(awk '{for(i=1;i<=NF;i++) if($i ~ /last=/){split($i,a,"="); print a[2]}}' <<< "$read1")"
contains1="$(awk '{for(i=1;i<=NF;i++) if($i ~ /contains_today=/){split($i,a,"="); print a[2]}}' <<< "$read1")"

if [[ "$contains1" == "1" ]]; then
  echo "[PRECHECK] OK: cal contains=${TODAY_KST}, today=${TODAY_KST}"
  exit 0
fi

# not contains today -> try refresh
echo "[TRY] $LOG_PREFIX cal refresh start"
if [[ -x "scripts/linux/jobs/cal_refresh.sh" ]]; then
  bash scripts/linux/jobs/cal_refresh.sh || true
else
  # 레거시 이름 추정
  if [[ -x "scripts/linux/jobs/precache_benchmarks.sh" ]]; then
    bash scripts/linux/jobs/precache_benchmarks.sh || true
  fi
fi

# re-check
read2="$(read_cache)"
echo "$read2" | sed "s/^/[POST] $LOG_PREFIX cache2 /"
contains2="$(awk '{for(i=1;i<=NF;i++) if($i ~ /contains_today=/){split($i,a,"="); print a[2]}}' <<< "$read2")"
last2="$(awk '{for(i=1;i<=NF;i++) if($i ~ /last=/){split($i,a,"="); print a[2]}}' <<< "$read2")"

if [[ "$contains2" == "1" ]]; then
  echo "[DONE] $LOG_PREFIX refresh updated (last=${last2})"
  exit 0
fi

# 여전히 포함 안 됨
# 외부요인 케이스: 평일 아님 or 영업시간 아님 -> [SKIP] RC=0
if ! is_weekday_kst || ! is_trading_hours_kst; then
  echo "[SKIP] external-data-unavailable (non-trading window)  last=${last2}"
  exit 0
fi

# 영업일/영업시간이고 갱신 실패 -> 신선도 부족 (RC=2)
echo "[EXIT] RC=2 (stale calendar for trading day) last=${last2} today=${TODAY_KST}"
exit 2
