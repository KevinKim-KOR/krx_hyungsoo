#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."

LOGDIR="logs"; mkdir -p "$LOGDIR"
LOG="$LOGDIR/update_$(date +%F).log"

{
  echo "[RUN] update_from_git $(date '+%F %T')"

  # 1) Git 업데이트
  git fetch --all --prune
  echo "[BRANCH] $(git rev-parse --abbrev-ref HEAD)"
  git pull --ff-only
  echo "[HEAD]   $(git rev-parse --short HEAD)"

  # 2) 환경 로드(있으면)
  export PYTHONPATH="${PYTHONPATH:-}"
  [ -f "config/env.nas.sh" ] && source config/env.nas.sh

  # 3) venv 준비
  if [ ! -d "venv" ]; then
    python3 -m venv venv
  fi
  # shellcheck disable=SC1091
  source venv/bin/activate

  # 4) 의존성
  python -m pip install -q --upgrade pip || true
  if [ -f "requirements-nas.txt" ]; then
    python -m pip install -q -r requirements-nas.txt || true
  else
    python -m pip install -q \
      "SQLAlchemy>=2.0,<2.1" pandas==1.5.3 numpy==1.24.4 \
      yfinance==0.2.52 pykrx==1.0.45 tabulate==0.9.0 \
      "PyYAML>=6.0" "requests>=2.31" "tqdm>=4.66" "rich>=13" || true
  fi

  echo "[DONE] update_from_git $(date '+%F %T')"
} | tee -a "$LOG"
