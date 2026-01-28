#!/bin/bash
# holding_watch.sh - Holding Watch Automation (Phase D-P.66)
# Usage: bash deploy/oci/holding_watch.sh
# Cron: */10 09-15 * * 1-5 ...

REPO_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_DIR" || exit 1
source .venv/bin/activate 2>/dev/null || true

export PYTHONPATH=$PYTHONPATH:.

# Secrets Load (Telegram) - use set -a to export vars automatically
SECRETS_FILE="$REPO_DIR/state/secrets/telegram.env"
if [ -f "$SECRETS_FILE" ]; then
    set -a
    source "$SECRETS_FILE"
    set +a
fi

# Run Holding Watch
# Exit codes:
# 0: OK (Sent or Skipped)
# 2: BLOCKED (No Portfolio/Settings)
# 3: FAILED (Market Data Down, etc)

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting Holding Watch..."
RESPONSE=$(python3 app/run_holding_watch.py)
EXIT_CODE=$?

# Parse Response (JSON)
# Expected: {"result": "...", "reason": "...", "alerts": N} or empty/error text
RESULT=$(echo "$RESPONSE" | grep -o '"result": *"[^"]*"' | cut -d'"' -f4)
REASON=$(echo "$RESPONSE" | grep -o '"reason": *"[^"]*"' | cut -d'"' -f4)
ALERTS=$(echo "$RESPONSE" | grep -o '"alerts": *[0-9]*' | cut -d':' -f2)

DATE_STR=$(date '+%Y-%m-%d %H:%M:%S')

if [ $EXIT_CODE -eq 0 ]; then
    # OK or SKIP
    if [ "$RESULT" == "SKIPPED" ]; then
        echo "[$DATE_STR] SKIP: $REASON"
    else
        # OK
        ALERTS=${ALERTS:-0}
        REASON=${REASON:-UNKNOWN}
        echo "[$DATE_STR] OK: Alerts=$ALERTS Reason=$REASON"
    fi

elif [ $EXIT_CODE -eq 2 ]; then
    # BLOCKED
    REASON=${REASON:-UNKNOWN}
    echo "[$DATE_STR] BLOCKED: $REASON"

elif [ $EXIT_CODE -eq 3 ]; then
    # FAILED
    echo "[$DATE_STR] FAILED: Incident (Exit 3)"
    # Log raw output for debugging
    echo "$RESPONSE"

else
    echo "[$DATE_STR] ERROR: Unknown Exit $EXIT_CODE"
    echo "$RESPONSE"
fi

exit $EXIT_CODE
