#!/usr/bin/env bash
set -euo pipefail

# repo root 고정
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"

# env/venv
# shellcheck disable=SC1091
source "config/env.nas.sh"
PY="${PYTHONBIN:-python3}"

LOGDIR="$ROOT/logs"
mkdir -p "$LOGDIR"
LOG="$LOGDIR/build_index_$(date +%F).log"

{
  echo "[RUN] build-index $(date '+%F %T')"
  echo "[PRECHECK] ROOT=$ROOT"

  # 산출물 경로 보장
  mkdir -p "$ROOT/reports"

  # ENV로 루트 고정(경로 꼬임 방지)
  export WEB_REPO_ROOT="$ROOT"

  # 설정 파일 유무 안내(없어도 fallback)
  if [[ -f "$ROOT/config/web_index.yaml" ]]; then
    echo "[PRECHECK] OK: config=$ROOT/config/web_index.yaml (will be used)"
  else
    echo "[PRECHECK] OK: config=fallback(defaults)"
  fi

  # 실행
  set +e
  "$PY" "$ROOT/web/build_index.py"
  RC=$?
  set -e

  # (신규) UX 강화: 최근N/CSV/색상 주입
  if [[ -f "$ROOT/reports/index.html" ]]; then
    "$PY" "$ROOT/web/enhance_index.py" || true
  fi

  if [[ $RC -ne 0 ]]; then
    echo "[EXIT] RC=2 (build_index.py exited with $RC)"
    exit 2
  fi

  # 산출물 확인
  if [[ -f "$ROOT/reports/index.html" && -f "$ROOT/reports/index.json" ]]; then
    echo "[DONE] build-index"
    echo "[EXIT] RC=0"
    exit 0
  else
    # 외부요인으로 빈 인덱스일 수 있으나, 정책상 정상 종료
    echo "[SKIP] no index outputs found (treated as external/no-data)"
    echo "[EXIT] RC=0"
    exit 0
  fi
} | tee -a "$LOG"
