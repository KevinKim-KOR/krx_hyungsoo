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

# 2. Run Backend Holding Logic
mkdir -p "reports/ops/push/holding_watch/latest"
SSOT_FILE="reports/ops/push/holding_watch/latest/holding_watch_latest.json"
TMP_FILE="${SSOT_FILE}.tmp"
LOG_FILE="logs/holding_watch.log" # Ensure log file var definition if missing, but script usually has LOG_DIR logic?
# Original script check: Line 9-10... No LOG_FILE defined in original view?
# Ah, original script just echoed. I should define LOG_FILE or just redirect >> logs/holding_watch.log in usage.
# But spike_watch defined LOG_FILE.
# holding_watch.sh Usage says: bash ... >> logs/holding_watch.log
# So I can just echo to stdout and let the caller redirect.
# BUT spike_watch.sh redirected internally.
# I'll stick to echoing to stdout/stderr and let caller handle redirection as per usage comment, or match spike_watch.
# P91 3-B Command: bash ... >> logs/holding_watch.log. So stdout is fine.
# But spike_watch.sh implementation I did in prev step redirected to LOG_FILE internally.
# I should probably just echo.
# Wait, spike_watch.sh modification: I used `>> "$LOG_FILE"`.
# Let's check if LOG_FILE was defined in spike_watch.sh. Yes (line 10).
# In holding_watch.sh original, it's NOT defined.
# I'll add LOG_FILE definition for consistency or just echo.
# I'll define LOG_FILE="logs/holding_watch.log" to be safe and consistent with spike_watch upgrades.

mkdir -p logs
LOG_FILE="logs/holding_watch.log"

# Asof Timestamp for JSON
ASOF_ISO=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

RESPONSE=$(curl -s -X POST "http://localhost:8000/api/push/holding/run?confirm=true")
EXIT_CODE=$?

# Function to write SSOT (Atomic)
write_ssot() {
    local status="$1"
    local reason="$2"
    local alerts="$3"
    local sent="$4"
    # Source is always API for this script
    local source="API"
    
    # Minimal JSON writer
    echo "{" > "$TMP_FILE"
    echo "  \"schema\": \"WATCHER_STATUS_V1\"," >> "$TMP_FILE"
    echo "  \"asof\": \"$ASOF_ISO\"," >> "$TMP_FILE"
    echo "  \"status\": \"$status\"," >> "$TMP_FILE"
    echo "  \"reason\": \"$reason\"," >> "$TMP_FILE"
    echo "  \"alerts\": $alerts," >> "$TMP_FILE"
    echo "  \"sent\": \"$sent\"," >> "$TMP_FILE"
    echo "  \"source\": \"$source\"" >> "$TMP_FILE"
    echo "}" >> "$TMP_FILE"
    
    mv -f "$TMP_FILE" "$SSOT_FILE"
}

DATE_STR=$(date '+%Y-%m-%d %H:%M:%S')

# Curl itself failed
if [ $EXIT_CODE -ne 0 ]; then
    echo "[$DATE_STR] FAIL: API Unreachable" >> "$LOG_FILE"
    write_ssot "ERROR" "API_FAIL" 0 "NONE"
    exit 3
fi

# 3. Analyze Response
RESULT=$(echo "$RESPONSE" | grep -o '"result": *"[^"]*"' | cut -d'"' -f4)
REASON=$(echo "$RESPONSE" | grep -o '"reason": *"[^"]*"' | cut -d'"' -f4)
# Holding uses alerts_generated usually
ALERTS=$(echo "$RESPONSE" | grep -o '"alerts_generated": *[0-9]*' | cut -d':' -f2 | tr -d ' ')
if [ -z "$ALERTS" ]; then
    ALERTS=$(echo "$RESPONSE" | grep -o '"alerts": *[0-9]*' | cut -d':' -f2 | tr -d ' ')
fi
[ -z "$ALERTS" ] && ALERTS=0

if [ "$RESULT" == "OK" ]; then
    echo "[$DATE_STR] OK: Alerts=$ALERTS Reason=$REASON" >> "$LOG_FILE"
    
    # Determine Sent Status
    SENT="NONE"
    if [ "$ALERTS" -gt 0 ]; then SENT="TELEGRAM"; fi
    DELIV=$(echo "$RESPONSE" | grep -o '"delivery_actual": *"[^"]*"' | cut -d'"' -f4)
    if [ ! -z "$DELIV" ]; then SENT="$DELIV"; fi

    write_ssot "OK" "$REASON" "$ALERTS" "$SENT"
    exit 0

elif [ "$RESULT" == "SKIPPED" ]; then
    echo "[$DATE_STR] SKIP: $REASON" >> "$LOG_FILE"
    write_ssot "SKIPPED" "$REASON" 0 "NONE"
    exit 0

elif [ "$RESULT" == "BLOCKED" ]; then
    echo "[$DATE_STR] BLOCKED: $REASON" >> "$LOG_FILE"
    write_ssot "WARN" "$REASON" 0 "NONE"
    exit 2

else
    echo "[$DATE_STR] ERROR: $RESPONSE" >> "$LOG_FILE"
    write_ssot "ERROR" "RESPONSE_INVALID" 0 "NONE"
    exit 1
fi
