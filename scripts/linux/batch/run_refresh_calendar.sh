#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."

[ -f "config/env.nas.sh" ] && source config/env.nas.sh
PYTHONBIN="${PYTHONBIN:-python3}"
JITTER_MAX_SEC="${JITTER_MAX_SEC:-300}"

# 0) 지터 (선택)
if [ "${JITTER_MAX_SEC}" -gt 0 ] 2>/dev/null; then
  S=$(( RANDOM % JITTER_MAX_SEC ))
  echo "[JITTER] sleep ${S}s"
  sleep "${S}"
fi

# 1) 실제 리프레시 실행 (RC=2 재시도)
bash scripts/linux/jobs/_run_generic.sh \
  --log cal_refresh \
  --retry-rc 2 --retry-max 2 --retry-sleep 300 \
  -- \
  "$PYTHONBIN" -m scripts.ops.refresh_calendar_cache \
    --start "$(date -d '2 years ago' +%F 2>/dev/null || date -v-2y +%F)" \
    --end   "$(date +%F)"
