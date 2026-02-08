#!/bin/bash
# deploy/oci/manual_loop_submit_dry_run.sh
# P131: Dry Run Submission (No Broker Execution)

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$BASE_DIR" || exit 1

echo "==================================================="
echo "   🛡️  DRY RUN SUBMISSION (NO TRADES)"
echo "==================================================="

# 0. Check Status
# Must be AWAITING_HUMAN_EXECUTION (or close to it)
# We won't block strictly here, relying on backend/generator to validate ticket presence.

# 1. Token Prompt
echo -n "Enter OCI Token to confirm DRY RUN: "
read -s TOKEN
echo ""

if [ -z "$TOKEN" ]; then
    echo "Error: Token cannot be empty."
    exit 1
fi

# 2. Call API
# Requires API running on localhost:8000
echo "Submitting Dry Run Record..."
RESPONSE=$(curl -s -X POST "http://localhost:8000/api/dry_run_record/submit?confirm=true" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json")

# 3. Validation
echo "Response: $RESPONSE"

if echo "$RESPONSE" | grep -q '"result":"OK"'; then
    echo "✅ Dry Run Submitted Successfully."
    echo "   Stage should now be DONE_TODAY (Mode: DRY_RUN)"
else
    echo "❌ Submission Failed."
    exit 1
fi
