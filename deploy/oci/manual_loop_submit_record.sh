#!/bin/bash
# P115: Daily Manual Loop Operator Runner - Submit Record
# Usage: bash deploy/oci/manual_loop_submit_record.sh <record_json_path>

source deploy/oci/env.sh
RECORD_FILE="$1"

if [ -z "$RECORD_FILE" ]; then
    echo "Usage: $0 <record_json_path>"
    exit 1
fi

if [ ! -f "$RECORD_FILE" ]; then
    echo "❌ File not found: $RECORD_FILE"
    exit 1
fi

echo "==================================================="
echo "   Daily Manual Loop: SUBMIT RECORD (Phase 2)"
echo "   Scope: Submit Record -> Done Today"
echo "==================================================="

# 1. Check SSOT Stage
SUMMARY_JSON=$(curl -s http://localhost:8000/api/ops/summary/latest)
STAGE=$(echo "$SUMMARY_JSON" | python3 -c "import sys, json; print((json.load(sys.stdin).get('rows') or [{}])[0].get('manual_loop', {}).get('stage', 'UNKNOWN'))")

echo "[Status] Current Stage: $STAGE"

if [ "$STAGE" != "AWAITING_HUMAN_EXECUTION" ] && [ "$STAGE" != "AWAITING_RECORD_SUBMIT" ]; then
    echo "❌ Wrong Stage for Submit. Expected: AWAITING_HUMAN_EXECUTION or AWAITING_RECORD_SUBMIT."
    exit 1
fi

# 2. Prompt for Token
echo -n "🔑 Enter Confirm Token (hidden): "
read -s CONFIRM_TOKEN
echo ""

if [ -z "$CONFIRM_TOKEN" ]; then
    echo "❌ Token empty. Aborting (Fail-Closed)."
    exit 2
fi

# 3. Construct Payload with Token
TEMP_PAYLOAD="/tmp/manual_record_payload_$$.json"

python3 -c "
import sys, json
try:
    data = json.load(open('$RECORD_FILE'))
    if isinstance(data, list):
        payload = {'confirm_token': '$CONFIRM_TOKEN', 'items': data}
    elif isinstance(data, dict):
        payload = data
        payload['confirm_token'] = '$CONFIRM_TOKEN'
    else:
        print('INVALID_JSON')
        sys.exit(1)
    
    print(json.dumps(payload))
except Exception as e:
    sys.exit(1)
" > "$TEMP_PAYLOAD"

if [ $? -ne 0 ]; then
    echo "❌ Failed to construct payload. Check JSON format."
    rm -f "$TEMP_PAYLOAD"
    exit 3
fi

# 4. Submit Record
echo ">> Submitting Record..."
SUBMIT_RESP=$(curl -s -X POST -H "Content-Type: application/json" -d @"$TEMP_PAYLOAD" "http://localhost:8000/api/manual_execution_record/submit?confirm=true")

rm -f "$TEMP_PAYLOAD"

if echo "$SUBMIT_RESP" | grep -q "\"result\": \"FAIL\""; then
    echo "❌ Submit Failed: $SUBMIT_RESP"
    exit 4
fi
if echo "$SUBMIT_RESP" | grep -q "\"result\": \"BLOCKED\""; then
    echo "❌ Submit Blocked: $SUBMIT_RESP"
    exit 4
fi

echo "✅ Record Submitted. Regenerating Summary..."

# 5. Final Status
curl -s -X POST "http://localhost:8000/api/ops/summary/regenerate?confirm=true" > /dev/null
SUMMARY_JSON=$(curl -s http://localhost:8000/api/ops/summary/latest)
NEW_STAGE=$(echo "$SUMMARY_JSON" | python3 -c "import sys, json; print((json.load(sys.stdin).get('rows') or [{}])[0].get('manual_loop', {}).get('stage', 'UNKNOWN'))")

echo "==================================================="
echo "✅ SUBMIT COMPLETED"
echo "   New Stage: $NEW_STAGE"
if [ "$NEW_STAGE" == "DONE_TODAY" ]; then
    echo "🎉 DAILY OPS COMPLETED SUCCESSFULLY!"
else
    echo "⚠️ Start is not DONE_TODAY. Check Plan ID match?"
fi
echo "==================================================="
