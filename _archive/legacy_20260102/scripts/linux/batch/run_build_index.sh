#!/usr/bin/env bash
set -euo pipefail

# repo 루트 기준에서 실행된다고 가정
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"

# 환경 로드(없으면 안전 폴백)
if [[ -f "config/env.nas.sh" ]]; then
  # shellcheck disable=SC1091
  source "config/env.nas.sh"
fi
PYTHONBIN="${PYTHONBIN:-${ROOT}/venv/bin/python}"
LOGDIR="${ROOT}/logs"
mkdir -p "$LOGDIR"
LOG="${LOGDIR}/index_$(date +%F).log"

{
  echo "[PRECHECK] ROOT=$ROOT"
  if [[ ! -x "$PYTHONBIN" ]]; then
    echo "[PRECHECK] NG: PYTHONBIN not executable -> $PYTHONBIN" >&2
    echo "[EXIT] RC=2"
    exit 2
  fi
  # 어떤 파이썬/판다스인지 기록(진단용, 실패해도 계속)
  PYVER="$("$PYTHONBIN" - <<'PY'
import sys, importlib.util
print("python:", sys.version.split()[0])
print("pandas_installed:", importlib.util.find_spec("pandas") is not None)
PY
  )"
  echo "[PRECHECK] OK: ${PYVER//$'\n'/' | '}"

  echo "[RUN] build_index"
  "$PYTHONBIN" web/build_index.py
  RC=$?
  if [[ $RC -ne 0 ]]; then
    echo "[EXIT] RC=${RC}"
    exit "$RC"
  fi
  echo "[DONE] build_index"
  echo "[EXIT] RC=0"
} | tee -a "$LOG"
