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
mkdir -p "reports/ops/push/spike_watch/latest"
SSOT_FILE="reports/ops/push/spike_watch/latest/spike_watch_latest.json"
TMP_FILE="${SSOT_FILE}.tmp"

# Asof Timestamp for JSON
ASOF_ISO=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

RESPONSE=$(curl -s -X POST "http://localhost:8000/api/push/spike/run?confirm=true")
EXIT_CODE=$?

# Function to write SSOT (Atomic)
write_ssot() {
    local status="$1"
    local reason="$2"
    local alerts="$3"
    local sent="$4"
    local detail="$5"
    # Source is always API for this script
    local source="API"
    
    # Sanitize detail (simple escape)
    local detail_safe=$(echo "$detail" | tr -d '"\n\r' | cut -c 1-100)
    
    # Minimal JSON writer (No jq dependency)
    echo "{" > "$TMP_FILE"
    echo "  \"schema\": \"WATCHER_STATUS_V1\"," >> "$TMP_FILE"
    echo "  \"asof\": \"$ASOF_ISO\"," >> "$TMP_FILE"
    echo "  \"status\": \"$status\"," >> "$TMP_FILE"
    echo "  \"reason\": \"$reason\"," >> "$TMP_FILE"
    echo "  \"alerts\": $alerts," >> "$TMP_FILE"
    echo "  \"sent\": \"$sent\"," >> "$TMP_FILE"
    echo "  \"reason_detail\": \"$detail_safe\"," >> "$TMP_FILE"
    echo "  \"source\": \"$source\"" >> "$TMP_FILE"
    echo "}" >> "$TMP_FILE"
    
    mv -f "$TMP_FILE" "$SSOT_FILE"
}

# Curl itself failed (Backend down)
if [ $EXIT_CODE -ne 0 ]; then
    echo "[$DATE_STR] FAIL: API Unreachable" >> "$LOG_FILE"
    write_ssot "ERROR" "API_FAIL" 0 "NONE" "ExitCode=$EXIT_CODE"
    
    # Trigger Incident Push
    curl -s -X POST "http://localhost:8000/api/push/incident/run" \
         -H "Content-Type: application/json" \
         -d '{"type": "MARKET_DATA_DOWN", "message": "Spike Watch API Unreachable"}' >> "$LOG_FILE" 2>&1
    exit 3
fi

# 3. Raw Response Classifier (P94)
# Check for known non-JSON signals first
if echo "$RESPONSE" | grep -q "OUTSIDE_SESSION"; then
    echo "[$DATE_STR] SKIP: Outside Session (Raw)" >> "$LOG_FILE"
    write_ssot "SKIPPED" "OUTSIDE_SESSION" 0 "NONE" "Raw signal"
    exit 0
fi

if echo "$RESPONSE" | grep -q "^SKIP:"; then
    echo "[$DATE_STR] SKIP: Generic (Raw)" >> "$LOG_FILE"
    write_ssot "SKIPPED" "OUTSIDE_SESSION" 0 "NONE" "Raw signal"
    exit 0
fi

# 4. JSON Parsing
RESULT=$(echo "$RESPONSE" | grep -o '"result": *"[^"]*"' | cut -d'"' -f4)
REASON=$(echo "$RESPONSE" | grep -o '"reason": *"[^"]*"' | cut -d'"' -f4)

# Validation: If RESULT is empty, parsing failed
if [ -z "$RESULT" ]; then
    echo "[$DATE_STR] ERROR: Parse Failed. Resp: $RESPONSE" >> "$LOG_FILE"
    write_ssot "ERROR" "RESPONSE_INVALID" 0 "NONE" "$RESPONSE"
    exit 1
fi

ALERTS=$(echo "$RESPONSE" | grep -o '"alerts": *[0-9]*' | cut -d':' -f2 | tr -d ' ')
[ -z "$ALERTS" ] && ALERTS=0

if [ "$RESULT" == "OK" ]; then
    echo "[$DATE_STR] OK: Alerts=$ALERTS Reason=$REASON" >> "$LOG_FILE"
    
    # Determine Sent Status
    SENT="NONE"
    # P93: If alerts>0, assume sent unless reason says otherwise or delivery_actual present
    if [ "$ALERTS" -gt 0 ]; then SENT="TELEGRAM"; fi 
    DELIV=$(echo "$RESPONSE" | grep -o '"delivery_actual": *"[^"]*"' | cut -d'"' -f4)
    if [ ! -z "$DELIV" ]; then SENT="$DELIV"; fi

    write_ssot "OK" "$REASON" "$ALERTS" "$SENT" ""
    exit 0

elif [ "$RESULT" == "SKIPPED" ]; then
    echo "[$DATE_STR] SKIP: $REASON" >> "$LOG_FILE"
    write_ssot "SKIPPED" "$REASON" 0 "NONE" ""
    exit 0

elif [ "$RESULT" == "BLOCKED" ]; then
    echo "[$DATE_STR] BLOCKED: $REASON" >> "$LOG_FILE"
    write_ssot "WARN" "$REASON" 0 "NONE" ""
    exit 2

else
    echo "[$DATE_STR] ERROR: $RESPONSE" >> "$LOG_FILE"
    write_ssot "ERROR" "RESPONSE_INVALID" 0 "NONE" "Result=$RESULT"
    exit 1
fi
