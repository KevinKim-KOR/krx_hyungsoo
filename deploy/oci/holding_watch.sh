#!/bin/bash
# holding_watch.sh - Holding Watch Automation (Phase D-P.66)
# Usage: bash deploy/oci/holding_watch.sh
# Cron: */10 09-15 * * 1-5 ...

cd "$(dirname "$0")/../../" || exit 1
source .venv/bin/activate 2>/dev/null || true

export PYTHONPATH=$PYTHONPATH:.

# Run Holding Watch
# Exit codes:
# 0: OK (Sent or Skipped)
# 2: BLOCKED (No Portfolio/Settings)
# 3: FAILED (Market Data Down, etc)

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting Holding Watch..."
python3 app/run_holding_watch.py
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ Holding Watch Completed (OK/SKIP)"
elif [ $EXIT_CODE -eq 2 ]; then
    echo "⛔ Holding Watch BLOCKED (Check Portfolio/Settings)"
elif [ $EXIT_CODE -eq 3 ]; then
    echo "❌ Holding Watch FAILED (Incident)"
else
    echo "⚠️ Holding Watch Unknown Exit: $EXIT_CODE"
fi

exit $EXIT_CODE
