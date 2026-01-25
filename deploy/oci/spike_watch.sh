#!/bin/bash
# ============================================================================
# Spike Push (D-P.62) - Operational Hardened
# ============================================================================
# Cron: */10 09-15 * * 1-5 (Weekdays 09:10-15:20)
# Usage: bash deploy/oci/spike_watch.sh

REPO_DIR="/home/ubuntu/krx_hyungsoo"
LOG_DIR="$REPO_DIR/logs"
LOG_FILE="$LOG_DIR/spike_watch.log"
DATE_STR=$(date "+%Y-%m-%d %H:%M:%S")

mkdir -p "$LOG_DIR"

cd "$REPO_DIR" || exit 1

# 1. Pull Latest Settings/Watchlist (from PC)
git pull origin archive-rebuild >> "$LOG_FILE" 2>&1

# 2. Run Backend Spike Logic
# If backend is down, this will fail. We need to catch that.
RESPONSE=$(curl -s -X POST "http://localhost:8000/api/push/spike/run?confirm=true")
EXIT_CODE=$?

# Curl itself failed (Backend down)
if [ $EXIT_CODE -ne 0 ]; then
    echo "[$DATE_STR] FAIL: API Unreachable" >> "$LOG_FILE"
    # Trigger Incident Push (Idempotent)
    curl -s -X POST "http://localhost:8000/api/push/incident/run" \
         -H "Content-Type: application/json" \
         -d '{"type": "MARKET_DATA_DOWN", "message": "Spike Watch API Unreachable"}' >> "$LOG_FILE" 2>&1
    exit 3
fi

# 3. Analyze Response
# Normal: {"result": "OK", ...}
# Skipped: {"result": "SKIPPED", "reason": "OUTSIDE_SESSION"} or "DISABLED_BY_SETTINGS"
# Blocked: {"result": "BLOCKED", ...}

RESULT=$(echo "$RESPONSE" | grep -o '"result": *"[^"]*"' | cut -d'"' -f4)
REASON=$(echo "$RESPONSE" | grep -o '"reason": *"[^"]*"' | cut -d'"' -f4)

if [ "$RESULT" == "OK" ]; then
    ALERTS=$(echo "$RESPONSE" | grep -o '"alerts": *[0-9]*' | cut -d':' -f2)
    echo "[$DATE_STR] OK: Alerts=$ALERTS" >> "$LOG_FILE"
    exit 0

elif [ "$RESULT" == "SKIPPED" ]; then
    # Operational Noise Reduction: Just Log
    echo "[$DATE_STR] SKIP: $REASON" >> "$LOG_FILE"
    exit 0

elif [ "$RESULT" == "BLOCKED" ]; then
    # Configuration Missing -> Warn
    echo "[$DATE_STR] BLOCKED: $REASON" >> "$LOG_FILE"
    exit 2

else
    # Unknown Error or Exception
    echo "[$DATE_STR] ERROR: $RESPONSE" >> "$LOG_FILE"
    exit 1
fi
