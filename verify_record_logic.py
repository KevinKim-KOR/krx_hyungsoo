import json
import os
import time
from pathlib import Path

# 1. Setup Prereqs (Mock Prep/Ticket)
# Ensure verify_ticket_ux.py exists or mock it manually here if needed.
# But assuming verify_ticket_ux.py is gone (I deleted it).
# So I need to recreate the mocked state: Prep, Ticket with 'test_plan_123'.

def setup_mocks():
    # Directories
    (Path('reports/live/order_plan_export/latest')).mkdir(parents=True, exist_ok=True)
    (Path('reports/live/order_plan/latest')).mkdir(parents=True, exist_ok=True)
    (Path('state/portfolio/latest')).mkdir(parents=True, exist_ok=True)
    (Path('reports/live/execution_prep/latest')).mkdir(parents=True, exist_ok=True)
    (Path('reports/live/manual_execution_ticket/latest')).mkdir(parents=True, exist_ok=True)

    # 1. Export
    with open('reports/live/order_plan_export/latest/order_plan_export_latest.json', 'w') as f:
        json.dump({
            'schema': 'ORDER_PLAN_EXPORT_V1',
            'asof': '2026-02-07T12:00:00Z',
            'human_confirm': {'confirm_token': 'test_token_123'},
            'orders': [{'ticker': '005930', 'side': 'BUY', 'qty': 10, 'price_ref': 60000}], 
            'decision': 'READY'
        }, f)

    # 2. Plan
    with open('reports/live/order_plan/latest/order_plan_latest.json', 'w') as f:
        json.dump({'schema': 'ORDER_PLAN_V1', 'plan_id': 'test_plan_123', 'decision': 'READY'}, f)

    # 3. Portfolio
    with open('state/portfolio/latest/portfolio_latest.json', 'w') as f:
        json.dump({'cash': 10000000, 'total_value': 20000000}, f)
        
    # 4. Prep (Manual gen to ensure it exists and matches)
    # Or just run generate_execution_prep.py
    os.system('python3 app/generate_execution_prep.py test_token_123 > /dev/null')
    
    # 5. Ticket
    os.system('python3 app/generate_manual_execution_ticket.py > /dev/null')

def run_submit(plan_id, token, outfile='res.json'):
    # Create Input JSON
    input_data = {
        'source': {'plan_id': plan_id},
        'filled_at': '2026-02-07T12:30:00Z',
        'items': [{'ticker':'005930', 'side':'BUY', 'status':'EXECUTED', 'executed_qty':10}]
    }
    with open('input_record.json', 'w') as f:
        json.dump(input_data, f)
    
    # Run
    # Pipeline input token
    cmd = f'echo {token} | python3 app/generate_manual_execution_record.py input_record.json > {outfile}'
    os.system(cmd)
    
    if not os.path.exists(outfile):
        return {'decision': 'ERROR', 'reason': 'Output file not found'}
        
    try:
        with open(outfile) as f:
            return json.load(f)
    except:
        return {'decision': 'ERROR', 'reason': 'Invalid JSON'}

# --- Execution ---
setup_mocks()

print('--- Test Case A: Success ---')
res = run_submit('test_plan_123', 'test_token_123', 'res_a.json')
print(f"Dec: {res.get('decision')}, Reason: {res.get('reason')}")

print('--- Test Case B: Duplicate ---')
res = run_submit('test_plan_123', 'test_token_123', 'res_b.json')
print(f"Dec: {res.get('decision')}, Reason: {res.get('reason')}")

print('--- Test Case C: Linkage Mismatch ---')
res = run_submit('WRONG_PLAN_ID', 'test_token_123', 'res_c.json')
print(f"Dec: {res.get('decision')}, Reason: {res.get('reason')}")
