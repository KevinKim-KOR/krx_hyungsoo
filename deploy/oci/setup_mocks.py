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
         json.dump({'schema': 'ORDER_PLAN_V1', 'plan_id': 'test_plan_p123', 'decision': 'READY'}, f)

    Path('reports/live/order_plan_export/latest').mkdir(parents=True, exist_ok=True)
    with open('reports/live/order_plan_export/latest/order_plan_export_latest.json', 'w') as f:
         json.dump({'schema': 'ORDER_PLAN_EXPORT_V1', 'asof': '2026-02-08T12:00:00Z', 'plan_id': 'test_plan_p123', 'human_confirm': {'confirm_token': 'p123_token'}, 'orders': [], 'decision': 'READY'}, f)

    Path('reports/live/execution_prep/latest').mkdir(parents=True, exist_ok=True)
    with open('reports/live/execution_prep/latest/execution_prep_latest.json', 'w') as f:
         json.dump({'schema': 'EXECUTION_PREP_V1', 'decision': 'READY', 'source': {'plan_id': 'test_plan_p123', 'confirm_token': 'p123_token', 'export_ref': 'ref', 'order_plan_ref': 'ref'}, 'evidence_refs': []}, f)

    Path('reports/live/manual_execution_ticket/latest').mkdir(parents=True, exist_ok=True)
    with open('reports/live/manual_execution_ticket/latest/manual_execution_ticket_latest.json', 'w') as f:
         json.dump({'schema': 'MANUAL_EXECUTION_TICKET_V1', 'ticket_id': 'ticket_123', 'decision': 'GENERATED', 'source': {'plan_id': 'test_plan_p123'}}, f)

    print("More Mocks setup complete.")

if __name__ == "__main__":
    setup()
