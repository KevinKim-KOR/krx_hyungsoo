#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."

# 거래일 가드 (기존 캘린더 가드 활용)
bash scripts/linux/jobs/precheck_calendar_guard.sh || exit 0  # 휴장 등은 [SKIP]로 RC=0

# 시간 윈도우: 기본 22:30~01:00 (KST)
WIN_START="${YF_WIN_START:-22:30}"
WIN_END="${YF_WIN_END:-01:00}"

now_hm=$(date +%H:%M)
# 단순 비교: 22:30~23:59 또는 00:00~01:00
if [[ "$now_hm" < "$WIN_START" && "$now_hm" > "$WIN_END" ]]; then
  echo "[SKIP] outside_yf_window now=$now_hm win=${WIN_START}-${WIN_END}"
  exit 0
fi

echo "[RUN] yf_window_ok now=$now_hm win=${WIN_START}-${WIN_END}"
exit 0

