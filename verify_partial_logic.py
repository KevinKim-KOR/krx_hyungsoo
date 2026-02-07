import json
import os
import time
from pathlib import Path

# Setup Mocks (Ensure Prep/Ticket exist with 'test_plan_p123')
def setup_mocks():
    (Path('reports/live/order_plan_export/latest')).mkdir(parents=True, exist_ok=True)
    (Path('reports/live/order_plan/latest')).mkdir(parents=True, exist_ok=True)
    (Path('state/portfolio/latest')).mkdir(parents=True, exist_ok=True)
    (Path('reports/live/execution_prep/latest')).mkdir(parents=True, exist_ok=True)
    (Path('reports/live/manual_execution_ticket/latest')).mkdir(parents=True, exist_ok=True)

    with open('reports/live/order_plan/latest/order_plan_latest.json', 'w') as f:
        json.dump({'schema': 'ORDER_PLAN_V1', 'plan_id': 'test_plan_p123', 'decision': 'READY'}, f)

    # Export (Must match Plan ID for manual loop stage logic)
    with open('reports/live/order_plan_export/latest/order_plan_export_latest.json', 'w') as f:
        json.dump({
            'schema': 'ORDER_PLAN_EXPORT_V1',
            'asof': '2026-02-08T12:00:00Z',
            'plan_id': 'test_plan_p123', # Ops Summary checks this against Record
            'human_confirm': {'confirm_token': 'p123_token'},
            'orders': [{'ticker': '005930', 'side': 'BUY', 'qty': 10}], 
            'decision': 'READY'
        }, f)
        
    # Prep
    os.system('python3 app/generate_execution_prep.py p123_token > /dev/null 2>&1')
    # Ticket
    os.system('python3 app/generate_manual_execution_ticket.py > /dev/null 2>&1')

def run_submit(payload, outfile='res_p123.json'):
    with open('record_input.json', 'w') as f:
        json.dump(payload, f)
    
    cmd = f'echo p123_token | python3 app/generate_manual_execution_record.py record_input.json > {outfile}'
    os.system(cmd)
    
    if os.path.exists(outfile):
        try:
            return json.load(open(outfile))
        except: return {'decision': 'ERROR'}
    return {'decision': 'ERROR'}

setup_mocks()

print('--- Case A: Full Execution ---')
payload_a = {
    'source': {'plan_id': 'test_plan_p123'},
    'filled_at': '2026-02-08T12:00:00Z',
    'items': [{'ticker':'005930', 'side':'BUY', 'status':'EXECUTED', 'executed_qty':10}],
    'dedupe': {'idempotency_key': 'key_a'}
}
res = run_submit(payload_a, 'res_a.json')
print(f"Dec: {res.get('decision')}, Ver: {res.get('record_version')}")
os.system('python3 app/generate_ops_summary.py > /dev/null')
os.system('grep "DONE_TODAY" reports/ops/summary/latest/ops_summary_latest.json') # Expect DONE_TODAY

print('--- Case B: Partial Execution (New Version) ---')
payload_b = {
    'source': {'plan_id': 'test_plan_p123'},
    'filled_at': '2026-02-08T12:05:00Z',
    'items': [{'ticker':'005930', 'side':'BUY', 'status':'PARTIAL', 'executed_qty':5}],
    'dedupe': {'idempotency_key': 'key_b'} # Diff key -> New Version
}
res = run_submit(payload_b, 'res_b.json')
print(f"Dec: {res.get('decision')}, Ver: {res.get('record_version')}")
os.system('python3 app/generate_ops_summary.py > /dev/null')
os.system('grep "DONE_TODAY_PARTIAL" reports/ops/summary/latest/ops_summary_latest.json') # Expect DONE_TODAY_PARTIAL

print('--- Case C: Duplicate Replay (Blocking) ---')
# Re-submit payload_b (Key B)
res = run_submit(payload_b, 'res_c.json')
print(f"Dec: {res.get('decision')}, Reason: {res.get('reason')}")

