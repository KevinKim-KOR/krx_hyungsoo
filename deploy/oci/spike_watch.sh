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
    local source="$5"
    
    # Minimal JSON writer (No jq dependency)
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

# Curl itself failed (Backend down)
if [ $EXIT_CODE -ne 0 ]; then
    echo "[$DATE_STR] FAIL: API Unreachable" >> "$LOG_FILE"
    write_ssot "ERROR" "API_FAIL" 0 "NONE" "LOCAL_FALLBACK"
    
    # Trigger Incident Push
    curl -s -X POST "http://localhost:8000/api/push/incident/run" \
         -H "Content-Type: application/json" \
         -d '{"type": "MARKET_DATA_DOWN", "message": "Spike Watch API Unreachable"}' >> "$LOG_FILE" 2>&1
    exit 3
fi

# 3. Analyze Response
RESULT=$(echo "$RESPONSE" | grep -o '"result": *"[^"]*"' | cut -d'"' -f4)
REASON=$(echo "$RESPONSE" | grep -o '"reason": *"[^"]*"' | cut -d'"' -f4)
ALERTS=$(echo "$RESPONSE" | grep -o '"alerts": *[0-9]*' | cut -d':' -f2 | tr -d ' ')
[ -z "$ALERTS" ] && ALERTS=0

if [ "$RESULT" == "OK" ]; then
    echo "[$DATE_STR] OK: Alerts=$ALERTS Reason=$REASON" >> "$LOG_FILE"
    
    # Determine Sent Status (Approximation based on alerts)
    SENT="NONE"
    if [ "$ALERTS" -gt 0 ]; then SENT="TELEGRAM"; fi # Assumption for P91. Real sent info needs deeper parse but this satisfies "alerts>0 -> sent" logic mapping for now. User said "sent: TELEGRAM if sent".
    # Actually, check if response contains "delivery_actual"
    DELIV=$(echo "$RESPONSE" | grep -o '"delivery_actual": *"[^"]*"' | cut -d'"' -f4)
    if [ ! -z "$DELIV" ]; then SENT="$DELIV"; fi

    write_ssot "OK" "$REASON" "$ALERTS" "$SENT" "API"
    exit 0

elif [ "$RESULT" == "SKIPPED" ]; then
    echo "[$DATE_STR] SKIP: $REASON" >> "$LOG_FILE"
    write_ssot "SKIPPED" "$REASON" 0 "NONE" "API"
    exit 0

elif [ "$RESULT" == "BLOCKED" ]; then
    echo "[$DATE_STR] BLOCKED: $REASON" >> "$LOG_FILE"
    write_ssot "WARN" "$REASON" 0 "NONE" "API"
    exit 2

else
    echo "[$DATE_STR] ERROR: $RESPONSE" >> "$LOG_FILE"
    write_ssot "ERROR" "UNKNOWN_RESPONSE" 0 "NONE" "API"
    exit 1
fi
