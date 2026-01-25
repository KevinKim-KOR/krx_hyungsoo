#!/bin/bash
# ============================================================================
# Spike Push (D-P.61)
# ============================================================================
# Cron: 09:10 ~ 15:20, every 5-10 min
# Usage: bash deploy/oci/spike_watch.sh

REPO_DIR="/home/ubuntu/krx_hyungsoo"
LOG_DIR="$REPO_DIR/logs"
LOG_FILE="$LOG_DIR/spike_watch.log"
DATE_STR=$(date "+%Y-%m-%d %H:%M:%S")

mkdir -p "$LOG_DIR"

cd "$REPO_DIR" || exit 1

echo "[$DATE_STR] Spike Watch Started" >> "$LOG_FILE"

# 1. Pull Latest Watchlist (from PC)
git pull origin archive-rebuild >> "$LOG_FILE" 2>&1

# 2. Run Backend Spike Logic
# If backend is down, this will fail. We log it.
RESPONSE=$(curl -s -X POST "http://localhost:8000/api/push/spike/run?confirm=true")
echo "[$DATE_STR] Response: $RESPONSE" >> "$LOG_FILE"

# 3. Simple Check
if echo "$RESPONSE" | grep -q "FAILED"; then
    echo "[$DATE_STR] FAIL: Backend reported error" >> "$LOG_FILE"
    exit 1
fi
if echo "$RESPONSE" | grep -q "BLOCKED"; then
    # This acts as info logging (e.g. no watchlist)
    echo "[$DATE_STR] BLOCKED: Logic block" >> "$LOG_FILE"
    exit 2
fi

echo "[$DATE_STR] SUCCESS" >> "$LOG_FILE"
exit 0
