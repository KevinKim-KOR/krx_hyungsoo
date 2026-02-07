import json
import os
from pathlib import Path

def setup():
    Path('reports/ops/evidence/health').mkdir(parents=True, exist_ok=True)
    with open('reports/ops/evidence/health/health_latest.json', 'w') as f:
        json.dump({'schema': 'EVIDENCE_HEALTH_V1', 'decision': 'PASS', 'overall_health': 'PASS'}, f)

    Path('reports/live/reco/latest').mkdir(parents=True, exist_ok=True)
    with open('reports/live/reco/latest/reco_latest.json', 'w') as f:
        json.dump({'schema': 'OCI_RECO_V1', 'decision': 'PASS'}, f)

    Path('state/strategy_bundle/latest').mkdir(parents=True, exist_ok=True)
    with open('state/strategy_bundle/latest/strategy_bundle_latest.json', 'w') as f:
        json.dump({'schema': 'STRATEGY_BUNDLE_V1', 'bucket_url': 'test_bucket'}, f)

    # Missing Mocks
    Path('reports/live/order_plan/latest').mkdir(parents=True, exist_ok=True)
    with open('reports/live/order_plan/latest/order_plan_latest.json', 'w') as f:
         json.dump({'schema': 'ORDER_PLAN_V1', 'plan_id': 'test_plan_p126', 'decision': 'READY'}, f)

    Path('reports/live/order_plan_export/latest').mkdir(parents=True, exist_ok=True)
    with open('reports/live/order_plan_export/latest/order_plan_export_latest.json', 'w') as f:
         json.dump({'schema': 'ORDER_PLAN_EXPORT_V1', 'asof': '2026-02-08T12:00:00Z', 'plan_id': 'test_plan_p126', 'human_confirm': {'confirm_token': 'p126_token'}, 'orders': [], 'decision': 'READY'}, f)

    Path('reports/live/execution_prep/latest').mkdir(parents=True, exist_ok=True)
    # Prep Decision NOT READY/BLOCKED -> To trigger NEED_HUMAN_CONFIRM?
    # Ops Summary Logic: if not prep or prep != READY -> NEED_HUMAN_CONFIRM.
    # So if I make Prep "GENERATED" or just missing? 
    # Let's make it "WAITING" or just not ready.
    with open('reports/live/execution_prep/latest/execution_prep_latest.json', 'w') as f:
         json.dump({'schema': 'EXECUTION_PREP_V1', 'decision': 'WAITING', 'source': {'plan_id': 'test_plan_p126'}}, f)

    Path('reports/live/manual_execution_ticket/latest').mkdir(parents=True, exist_ok=True)
    with open('reports/live/manual_execution_ticket/latest/manual_execution_ticket_latest.json', 'w') as f:
         json.dump({'schema': 'MANUAL_EXECUTION_TICKET_V1', 'ticket_id': 'ticket_126', 'decision': 'PENDING', 'source': {'plan_id': 'test_plan_p126'}}, f)
         
    # Ops Summary needs to see this. generate_ops_summary.py needs to run.
    # I need to run generate_ops_summary.py on OCI after updating mocks.

    print("More Mocks setup complete.")

if __name__ == "__main__":
    setup()
