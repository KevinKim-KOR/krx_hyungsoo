import requests
import json
import sys
import os

BASE_URL = 'http://localhost:8000/api'

def log(msg):
    print(f'[VERIFY] {msg}')

def get_token():
    try:
        res = requests.get(f'{BASE_URL}/execution_prep/latest')
        if res.status_code != 200:
            return None
        return res.json().get('data', {}).get('source', {}).get('confirm_token')
    except:
        return None

def verify():
    # 1. Generate Ticket
    log('1. Generating Ticket...')
    res = requests.post(f'{BASE_URL}/manual_execution_ticket/regenerate?confirm=true')
    if res.status_code != 200:
        log(f'FAIL: Ticket Regen code {res.status_code}')
        sys.exit(1)
        
    ticket = res.json()
    if ticket.get('decision') != 'GENERATED':
        log(f'FAIL: Ticket Decision {ticket.get("decision")}')
        print(json.dumps(ticket, indent=2))
        sys.exit(1)
        
    log('PASS: Ticket GENERATED')
    
    # 2. Check Files
    csv_path = "krx_hyungsoo/" + ticket['output_files']['csv_path']
    md_path = "krx_hyungsoo/" + ticket['output_files']['md_path']
    
    if os.path.exists(csv_path):
        log('PASS: CSV File Exists')
    else:
        log('FAIL: CSV File Missing')
        
    if os.path.exists(md_path):
        log('PASS: MD File Exists')
    else:
        log('FAIL: MD File Missing')

    # 3. Submit Record
    token = get_token()
    if not token:
        log('FAIL: Could not get token from Prep')
        sys.exit(1)
        
    log(f'Token: {token}')
    
    # Create dummy items from ticket orders
    orders = ticket.get('orders', [])
    items = []
    for o in orders:
        items.append({
            "ticker": o.get("ticker"),
            "side": o.get("side"),
            "status": "EXECUTED",
            "executed_qty": o.get("qty", 0),
            "note": "Verified by Script"
        })
        
    payload = {
        "confirm_token": token,
        "items": items
    }
    
    log('3. Submitting Record...')
    res = requests.post(f'{BASE_URL}/manual_execution_record/submit?confirm=true', json=payload)
    if res.status_code != 200:
        log(f'FAIL: Record Submit code {res.status_code}')
        print(res.text)
        sys.exit(1)
        
    record = res.json()
    if record.get('decision') != 'EXECUTED' and record.get('decision') != 'NO_ITEMS':
        log(f'FAIL: Record Decision {record.get("decision")}')
        print(json.dumps(record, indent=2))
        sys.exit(1)
    
    if record.get('decision') == 'NO_ITEMS':
        log('PASS: Record NO_ITEMS (Empty plan tested)')
    else:
        log('PASS: Record EXECUTED')

    # 4. Resolver Check
    ref = 'reports/live/manual_execution_ticket/latest/manual_execution_ticket_latest.json'
    res = requests.get(f'{BASE_URL}/evidence/resolve?ref={ref}')
    if res.status_code == 200:
        log('PASS: Resolver (Ticket)')
    else:
        log(f'FAIL: Resolver Ticket {res.status_code}')

if __name__ == '__main__':
    verify()
