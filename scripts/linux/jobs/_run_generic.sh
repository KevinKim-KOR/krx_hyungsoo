#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."

JOB_NAME="${1:-}"             # 예: watchlist, signals, ingest-eod
shift || true

[ -z "$JOB_NAME" ] && { echo "Usage: $0 <job-name> [-- <legacy-cmd> ...]"; exit 2; }

TODAY=$(date +%F)
LOG="logs/${JOB_NAME}_${TODAY}.log"
mkdir -p logs

{
  echo "[RUN] ${JOB_NAME} $(date '+%F %T')"

  # ---- 레거시 스크립트 호출 (두 가지 방식 중 택1) ----
  # 1) 레거시 파일 직접 지정
  if [ "${1:-}" = "--" ]; then
    shift
    # 예: -- scripts/linux/jobs/legacy/run_watchlist_legacy.sh --arg1
    bash "$@"
  else
    # 2) 이름 규칙으로 찾기 (예: scripts/linux/jobs/run_${JOB_NAME}.sh 가 있으면 실행)
    if [ -f "scripts/linux/jobs/run_${JOB_NAME}.sh" ]; then
      bash "scripts/linux/jobs/run_${JOB_NAME}.sh"
    else
      echo "[ERROR] No legacy script for job: ${JOB_NAME}"
      exit 1
    fi
  fi
  # ------------------------------------------------------

  echo "[DONE] ${JOB_NAME} $(date '+%F %T')"
} | tee -a "$LOG"
