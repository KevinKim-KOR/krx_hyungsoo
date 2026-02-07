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

    print("Mocks setup complete.")

if __name__ == "__main__":
    setup()
