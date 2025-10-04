#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."

LOGDIR="logs"; mkdir -p "$LOGDIR"
LOG="$LOGDIR/update_$(date +%F).log"

{
  echo "[RUN] update_from_git $(date '+%F %T')"

  # 1) Git 업데이트
  git fetch --all --prune
  echo "[BRANCH]" $(git rev-parse --abbrev-ref HEAD)
  git pull --ff-only
  echo "[HEAD]" $(git rev-parse --short HEAD)

  # 2) (선택) 환경 설정
  #    - NAS 전용 환경변수/파이썬 경로가 config/env.nas.sh 에 있다면 로드
  if [ -f "config/env.nas.sh" ]; then
    # ENV=nas, PYTHONBIN=python3 등
    source config/env.nas.sh
  fi

  # 3) (선택) venv 활성화
  #    - 기존 방식 유지 (있으면 사용, 없으면 스킵)
  if [ -d "venv" ] && [ -f "venv/bin/activate" ]; then
    echo "[VENV] activate"
    # shellcheck disable=SC1091
    source venv/bin/activate
  fi

  # 4) (선택) 의존성 설치
  #    - requirements-nas.txt 가 있으면 그것부터
  if [ -f "requirements-nas.txt" ]; then
    echo "[PIP] install from requirements-nas.txt"
    pip install -r requirements-nas.txt -q || true
  else
    echo "[PIP] install base packages"
    pip install "SQLAlchemy>=2.0,<2.1" pandas==1.5.3 numpy==1.24.4 \
                yfinance==0.2.52 pykrx==1.0.45 tabulate==0.9.0 \
                "PyYAML>=6.0" "requests>=2.31" "tqdm>=4.66" "rich>=13" -q || true
  fi

  echo "[DONE] update_from_git $(date '+%F %T')"
} | tee -a "$LOG"
