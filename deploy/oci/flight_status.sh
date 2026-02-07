#!/bin/bash
# P119: Daily Flight Status & Next Action Helper (Hardened)
# Usage: bash deploy/oci/flight_status.sh

source deploy/oci/env.sh

echo "==================================================="
echo "   ✈️  DAILY FLIGHT STATUS CHECK (OCI)"
echo "==================================================="

# 1. Fetch Summary with Timeout (Fail-Closed)
SUMMARY_JSON=$(curl -s --max-time 5 http://localhost:8000/api/ops/summary/latest)
CURL_EXIT=$?

if [ $CURL_EXIT -ne 0 ] || [ -z "$SUMMARY_JSON" ]; then
    echo "❌ API TIMEOUT or DOWN (curl exit $CURL_EXIT)"
    echo "👉 NEXT ACTION : CHECK_BACKEND (ssh -> tail logs/backend.log)"
    exit 2
fi

# 2. Parse Info (Python for reliability)
python3 -c "
import sys, json, datetime

try:
    d = json.load(sys.stdin)
    row = (d.get('rows') or [d])[0]
    
    # 1. Manual Loop Stage & Next
    ml = row.get('manual_loop') or {}
    stage = ml.get('stage', 'UNKNOWN')
    next_action = ml.get('next_action', 'UNKNOWN')
    
    # 2. Components
    bundle = row.get('strategy_bundle') or {}
    bundle_ts = bundle.get('created_at', 'N/A')
    
    reco = (row.get('reco') or {}).get('decision', 'N/A')
    reco_r = (row.get('reco') or {}).get('reason', '')
    
    op = (row.get('order_plan') or {}).get('decision', 'N/A')
    op_r = (row.get('order_plan') or {}).get('reason', '')
    
    export = (ml.get('export') or {}).get('decision', 'N/A')
    
    ticket = (ml.get('ticket') or {}).get('decision', 'N/A')
    ticket_ts = (ml.get('ticket') or {}).get('generated_at', 'N/A')
    
    record = (ml.get('record') or {}).get('decision', 'N/A')
    record_ts = (ml.get('record') or {}).get('submitted_at', 'N/A')
    
    print(f'➜ STAGE       : {stage}')
    print(f'➜ NEXT ACTION : {next_action}')
    print('---------------------------------------------------')
    print(f'📦 BUNDLE      : {bundle_ts}')
    print(f'🧠 RECO        : {reco} ({reco_r})')
    print(f'📋 ORDER_PLAN  : {op} ({op_r})')
    print(f'📤 EXPORT      : {export}')
    print(f'🎫 TICKET      : {ticket} ({ticket_ts})')
    print(f'📝 RECORD      : {record} ({record_ts})')
    print('---------------------------------------------------')
    print('📂 EVIDENCE_HINTS:')
    # Only hints, no dynamic check to keep it fast
    print('   - Export: reports/live/order_plan_export/latest/order_plan_export_latest.json')
    print('   - Ticket: reports/live/manual_execution_ticket/latest/manual_execution_ticket_latest.md')
    print('   - Record: reports/live/manual_execution_record/latest/manual_execution_record_latest.json')

except Exception as e:
    print(f'❌ ERROR Parsing Summary: {e}')
    print('👉 NEXT ACTION : CHECK_OPS_SUMMARY_LOG')
" <<< "$SUMMARY_JSON"

echo "==================================================="
