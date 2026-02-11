import json
import os
import sys

def load_json(path):
    if os.path.exists(path):
        try:
            return json.load(open(path))
        except: return {}
    return {}

print('--- VERIFICATION START ---')

# 1. Check Export Plan ID
export = load_json('reports/live/order_plan_export/latest/order_plan_export_latest.json')
plan_id = export.get('source', {}).get('plan_id')
print(f"EXPORT_PLAN_ID: {plan_id}")

# 2. Check Prep (Simulate success check if run)
prep = load_json('reports/live/execution_prep/latest/execution_prep_latest.json')
decision = prep.get('decision')
print(f"PREP_DECISION: {decision}")
confirm_token = prep.get('source', {}).get('confirm_token')
print(f"PREP_TOKEN: {confirm_token}")

# 3. Check Ticket (Freshness)
ticket = load_json('reports/live/manual_execution_ticket/latest/manual_execution_ticket_latest.json')
t_decision = ticket.get('decision')
print(f"TICKET_DECISION: {t_decision}")
ticket_plan_id = ticket.get('source', {}).get('plan_id')
print(f"TICKET_PLAN_ID: {ticket_plan_id}")

# 4. Check Ops Summary Stage
summary = load_json('reports/ops/summary/ops_summary_latest.json')
rows = summary.get('rows') or [{}]
stage = rows[0].get('manual_loop', {}).get('stage', 'UNKNOWN')
print(f"STAGE: {stage}")

print('--- VERIFICATION END ---')
