#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."

[ -f config/env.nas.sh ] && source config/env.nas.sh
PYTHONBIN="${PYTHONBIN:-python3}"

LOG="logs/watchlist_$(date +%F).log"
mkdir -p logs

{
  echo "[RUN] report-watchlist $(date '+%F %T')"

  # 외부요인(레이트리밋/HTTP오류 등)은 가드가 스킵 처리 (RC=0)
  bash scripts/linux/jobs/run_py_guarded.sh "$PYTHONBIN" report_watchlist_cli.py --date auto

  # (선택) 에러 패턴 감지 시 알림
  if grep -qE "Traceback|ERROR" "$LOG"; then
    "$PYTHONBIN" - <<'PY'
from reporting_eod import _load_cfg, _send_notify
_send_notify("❗️Watchlist 리포트 실패: 로그 확인 필요", _load_cfg())
PY
  fi

  echo "[DONE] report-watchlist $(date '+%F %T')"
} | tee -a "$LOG"
