#!/bin/bash
# Daily Ops Cycle Runner (Linux/NAS)
# Phase C-P.17

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# Activate venv if exists
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

# Run ops cycle
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting Daily Ops Cycle..."
python -m app.run_ops_cycle
EXIT_CODE=$?

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Ops Cycle finished with exit code: $EXIT_CODE"
exit $EXIT_CODE
