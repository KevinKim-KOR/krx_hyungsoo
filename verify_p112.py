import requests
import json
import sys

BASE_URL = 'http://localhost:8000/api'

def log(msg):
    print(f'[VERIFY] {msg}')

def get_export():
    try:
        res = requests.get(f'{BASE_URL}/order_plan_export/latest')
        if res.status_code != 200:
            log(f'GET Export failed: {res.status_code}')
            return None
        return res.json().get('data')
    except Exception as e:
        log(f'GET Export exc: {e}')
        return None

def prepare(token):
    try:
        res = requests.post(f'{BASE_URL}/execution_prep/prepare?confirm=true', json={'confirm_token': token})
        return res.json()
    except Exception as e:
        log(f'POST Prepare exc: {e}')
        return {}

def run():
    # 1. Get Token
    export = get_export()
    if not export or not export.get('human_confirm'):
        log('FAIL: No Export or Token found')
        sys.exit(1)
        
    valid_token = export['human_confirm']['confirm_token']
    log(f'Got Token: {valid_token}')
    
    # 2. Case B: Invalid Token
    res = prepare('INVALID_TOKEN')
    decision = res.get('decision')
    if decision == 'TOKEN_MISMATCH':
        log('PASS: Case B (Token Mismatch)')
    else:
        log(f'FAIL: Case B expected TOKEN_MISMATCH, got {decision}')
        
    # 3. Case A: Valid Token
    res = prepare(valid_token)
    decision = res.get('decision')
    if decision == 'READY':
        log('PASS: Case A (Ready)')
    else:
        log(f'FAIL: Case A expected READY, got {decision}')
        
    # 4. Check Resolver (Case C - Resolver)
    ref = 'reports/live/execution_prep/latest/execution_prep_latest.json'
    res = requests.get(f'{BASE_URL}/evidence/resolve?ref={ref}')
    if res.status_code == 200:
        log('PASS: Resolver (200 OK)')
    else:
        log(f'FAIL: Resolver expected 200, got {res.status_code}')

if __name__ == '__main__':
    run()
