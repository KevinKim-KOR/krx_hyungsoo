#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."

[ -f config/env.nas.sh ] && source config/env.nas.sh
PYTHONBIN="${PYTHONBIN:-python3}"

# 엔트리포인트 선택
CMD=( "$PYTHONBIN" app.py scanner )
if ! "$PYTHONBIN" app.py -h 2>/dev/null | grep -qi scanner; then
  if [ -f ./scanner.py ]; then
    CMD=( "$PYTHONBIN" ./scanner.py )
  elif [ -f scripts/scanner.py ]; then
    CMD=( "$PYTHONBIN" scripts/scanner.py )
  fi
fi

bash scripts/linux/jobs/run_with_lock.sh \
  scripts/linux/jobs/_run_generic.sh \
    --log scanner \
    --guard th \
    -- \
    "${CMD[@]}"
