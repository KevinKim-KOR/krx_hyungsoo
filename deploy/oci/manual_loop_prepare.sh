#!/bin/bash
# P115: Daily Manual Loop Operator Runner - Prepare Phase
# Usage: bash deploy/oci/manual_loop_prepare.sh

source deploy/oci/env.sh

echo "==================================================="
echo "   Daily Manual Loop: PREPARE (Phase 1)"
echo "   Scope: Execution Prep -> Manual Ticket"
echo "==================================================="

# 1. Check SSOT Stage
SUMMARY_JSON=$(curl -s http://localhost:8000/api/ops/summary/latest)
STAGE=$(echo "$SUMMARY_JSON" | python3 -c "import sys, json; print((json.load(sys.stdin).get('rows') or [{}])[0].get('manual_loop', {}).get('stage', 'UNKNOWN'))")

echo "[Status] Current Stage: $STAGE"

if [ "$STAGE" != "NEED_HUMAN_CONFIRM" ] && [ "$STAGE" != "PREP_READY" ]; then
    echo "❌ Wrong Stage for Prepare. Expected: NEED_HUMAN_CONFIRM or PREP_READY."
    exit 1
fi

# 2. Prompt for Token
echo -n "🔑 Enter Execution Prep Token (hidden): "
read -s CONFIRM_TOKEN
echo ""

if [ -z "$CONFIRM_TOKEN" ]; then
    echo "❌ Token empty. Aborting (Fail-Closed)."
    exit 2
fi

# 3. Call Execution Prep (If needed)
if [ "$STAGE" == "NEED_HUMAN_CONFIRM" ]; then
    echo ">> Requesting Execution Prep..."
    PREP_RESP=$(curl -s -X POST -H "Content-Type: application/json" -d "{\"confirm_token\": \"$CONFIRM_TOKEN\"}" "http://localhost:8000/api/execution_prep/prepare?confirm=true")
    
    # Check Result
    if echo "$PREP_RESP" | grep -q "\"result\": \"FAIL\""; then
        echo "❌ Prep Failed: $PREP_RESP"
        exit 3
    fi
    if echo "$PREP_RESP" | grep -q "\"result\": \"BLOCKED\""; then
         echo "❌ Prep Blocked: $PREP_RESP"
         exit 3
    fi
    echo "✅ Prep Success."
fi

# 4. Generate Ticket
echo ">> Generating Manual Execution Ticket..."
TICKET_RESP=$(curl -s -X POST "http://localhost:8000/api/manual_execution_ticket/regenerate?confirm=true")

if echo "$TICKET_RESP" | grep -q "\"result\": \"FAIL\""; then
    echo "❌ Ticket Gen Failed: $TICKET_RESP"
    exit 4
fi

# 5. Final Status
# Regenerate Summary to get fresh state
curl -s -X POST "http://localhost:8000/api/ops/summary/regenerate?confirm=true" > /dev/null
SUMMARY_JSON=$(curl -s http://localhost:8000/api/ops/summary/latest)
NEW_STAGE=$(echo "$SUMMARY_JSON" | python3 -c "import sys, json; print((json.load(sys.stdin).get('rows') or [{}])[0].get('manual_loop', {}).get('stage', 'UNKNOWN'))")

echo "==================================================="
echo "✅ PREPARE COMPLETED"
echo "   New Stage: $NEW_STAGE"
echo "   Ticket: reports/live/manual_execution_ticket/latest/manual_execution_ticket_latest.md"
echo "   Next: EXECUTE trades manually, then run 'manual_loop_submit_record.sh'"
echo "==================================================="
