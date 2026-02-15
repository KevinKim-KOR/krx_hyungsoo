import requests
import json
import sys
import os

BASE_URL = 'http://localhost:8000/api'

def log(msg):
    print(f'[VERIFY] {msg}')

def check_ops_summary():
    try:
        res = requests.get(f'{BASE_URL}/ops/summary/latest')
        if res.status_code != 200:
            log(f'FAIL: Ops Summary GET {res.status_code}')
            return None
        return res.json()
    except Exception as e:
        log(f'FAIL: Ops Summary Exception {e}')
        return None

def verify():
    # 1. Check Ops Summary Stage
    summary = check_ops_summary()
    if not summary:
        sys.exit(1)
        
    manual_loop = summary.get('manual_loop', {})
    stage = manual_loop.get('stage')
    log(f'Current Stage: {stage}')
    
    # Check Risks
    risks = summary.get('top_risks', [])
    risk_codes = [r['code'] for r in risks]
    log(f'Risks: {risk_codes}')
    
    # 2. Case A logic
    if stage == 'NEED_HUMAN_CONFIRM':
        log('PASS: Stage is NEED_HUMAN_CONFIRM')
        if 'NEED_HUMAN_CONFIRM' in risk_codes:
            log('PASS: Risk NEED_HUMAN_CONFIRM present')
        else:
            log('FAIL: Risk NEED_HUMAN_CONFIRM missing')
    else:
        log(f'INFO: Stage is {stage}, expecting NEED_HUMAN_CONFIRM for Case A (unless confirmed)')

    # 3. Simulate Human Confirm (Prepare)
    if stage == 'NEED_HUMAN_CONFIRM':
        log('3. Simulating Human Confirm...')
        # We need a token?
        # Export should be ready.
        export = manual_loop.get('export')
        if not export:
            log('FAIL: Export missing in manual_loop')
            sys.exit(1)
            
        token = export.get('human_confirm', {}).get('confirm_token')
        if not token:
            log('FAIL: Token missing in Export')
            # Maybe Export is blocked?
            log(f'Export Decision: {export.get("decision")}')
            sys.exit(1)
            
        log(f'Token: {token}')
        
        # Call Prepare
        res = requests.post(f'{BASE_URL}/execution_prep/prepare?confirm=true', json={'confirm_token': token})
        if res.status_code != 200:
            log(f'FAIL: Prepare POST {res.status_code}')
            print(res.text)
        else:
            log('PASS: Prepare Successful')
            
            # Regen Ops Summary to see update
            requests.post(f'{BASE_URL}/ops/summary/regenerate?confirm=true')
            summary = check_ops_summary()
            new_stage = summary.get('manual_loop', {}).get('stage')
            log(f'New Stage: {new_stage}')
            if new_stage == 'PREP_READY' or new_stage == 'NEED_TICKET':
                 log('PASS: Stage advanced to PREP_READY')
            else:
                 log(f'WARN: Stage is {new_stage}')

    # 4. Simulate Ticket
    # If Prepped, generate ticket
    # ... (similar logic as P113-A verification)

if __name__ == '__main__':
    # Print last 20 lines of daily_ops.log
    if os.path.exists('logs/daily_ops.log'):
        print('--- daily_ops.log tail ---')
        os.system('tail -n 20 logs/daily_ops.log')
        print('--------------------------')
        
    verify()
