#!/bin/bash
# P116: Daily Flight Status & Next Action Helper
# Usage: bash deploy/oci/flight_status.sh

source deploy/oci/env.sh

echo "==================================================="
echo "   ✈️  DAILY FLIGHT STATUS CHECK"
echo "==================================================="

# 1. Fetch Summary
SUMMARY_JSON=$(curl -s http://localhost:8000/api/ops/summary/latest)

# 2. Parse Info (Python for reliability)
python3 -c "
import sys, json, datetime

try:
    d = json.load(sys.stdin)
    row = (d.get('rows') or [d])[0]
    
    # 1. Manual Loop Stage
    ml = row.get('manual_loop') or {}
    stage = ml.get('stage', 'UNKNOWN')
    next_action = ml.get('next_action', 'UNKNOWN')
    
    # 2. Top Risk
    risks = row.get('top_risks') or []
    top_risk = risks[0].get('code') if risks else 'NONE'
    
    # 3. Bundle Info
    bundle = row.get('strategy_bundle') or {}
    bundle_stale = bundle.get('stale', False)
    bundle_ts = bundle.get('created_at', 'N/A')
    
    # 4. Decisions
    reco = (row.get('reco') or {}).get('decision', 'N/A')
    op = (row.get('order_plan') or {}).get('decision', 'N/A')
    export = (ml.get('export') or {}).get('decision', 'N/A')
    
    print(f'➜ STAGE       : {stage}')
    print(f'➜ TOP RISK    : {top_risk}')
    print(f'➜ BUNDLE      : {bundle_ts} (Stale={bundle_stale})')
    print(f'➜ PIPELINE    : Reco[{reco}] -> Plan[{op}] -> Export[{export}]')
    print('---------------------------------------------------')
    print(f'👉 NEXT ACTION : {next_action}')
    print('---------------------------------------------------')
    
    # 5. Evidence Paths (Exist Check)
    print('📂 Latest Evidence Paths:')
    
    # Helper to check file existence? No, just print paths from Summary or Defaults.
    # Actually, we can just print the refs if they exist in the summary data.
    pass

except Exception as e:
    print(f'❌ ERROR Parsing Summary: {e}')
" <<< "$SUMMARY_JSON"

# 3. Print Key Evidence Paths (Hardcoded standard paths)
echo "   - Order Plan Export: reports/live/order_plan_export/latest/order_plan_export_latest.json"
echo "   - Execution Prep:    reports/live/execution_prep/latest/execution_prep_latest.json"
echo "   - Manual Ticket:     reports/live/manual_execution_ticket/latest/manual_execution_ticket_latest.md"
echo "   - Manual Record:     reports/live/manual_execution_record/latest/manual_execution_record_latest.json"

echo "==================================================="
