import json
import os

try:
    e = json.load(open('reports/live/order_plan_export/latest/order_plan_export_latest.json'))
    try:
        s = json.load(open('reports/ops/summary/ops_summary_latest.json'))
        rows = s.get('rows', [{}])
        stage = rows[0].get('manual_loop', {}).get('stage') if rows else "UNKNOWN"
    except:
        stage = "UNKNOWN"
    
    try:
        t = json.load(open('reports/live/manual_execution_ticket/latest/manual_execution_ticket_latest.json'))
        ticket_dec = t.get('decision')
    except:
        ticket_dec = "MISSING"

    root_id = e.get('plan_id')
    src_id = e.get('source', {}).get('plan_id')
    orders_count = len(e.get('orders', []))
    
    print(f"ROOT_ID={root_id}")
    print(f"SRC_ID={src_id}")
    print(f"STAGE={stage}")
    print(f"TICKET_DEC={ticket_dec}")
    print(f"ORDERS={orders_count}")
    
except Exception as e:
    print(f"ERROR: {e}")
