#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."

# 거래일 가드 (휴장 시 [SKIP] RC=0로 종료)
bash scripts/linux/jobs/precheck_calendar_guard.sh || exit 0

# 시간 윈도우: 기본 22:30~01:00 (KST)
WIN_START="${YF_WIN_START:-22:30}"
WIN_END="${YF_WIN_END:-01:00}"
now_hm=$(date +%H:%M)

# (추가) 강제 우회: YF_FORCE=1 이면 윈도우 체크 통과
if [ "${YF_FORCE:-0}" = "1" ]; then
  echo "[FORCE] yf_window override (YF_FORCE=1)"; exit 0
fi

# 단순 비교: 22:30~23:59 또는 00:00~01:00만 허용
if [[ "$now_hm" < "$WIN_START" && "$now_hm" > "$WIN_END" ]]; then
  echo "[SKIP] outside_yf_window now=$now_hm win=${WIN_START}-${WIN_END}"
  exit 100   # ← 윈도우 외는 100으로 반환(상위에서 즉시 종료)
fi

echo "[RUN] yf_window_ok now=$now_hm win=${WIN_START}-${WIN_END}"
exit 0
