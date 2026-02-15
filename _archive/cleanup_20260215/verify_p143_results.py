
import json
import os
import sys

# Add path for utils
sys.path.append(os.getcwd())
try:
    from app.utils.admin_utils import normalize_portfolio
except ImportError:
    print("WARN: admin_utils not found in path")

try:
    # Portfolio Check
    p_path = 'state/portfolio/latest/portfolio_latest.json'
    if os.path.exists(p_path):
        p = json.load(open(p_path))
        print(f"PORT_TOTAL={p.get('total_value')}")
        print(f"PORT_ASOF={p.get('asof')}")
    else:
        print("PORT_TOTAL=MISSING")

    # Ops Summary Check
    s_path = 'reports/ops/summary/ops_summary_latest.json'
    if os.path.exists(s_path):
        s = json.load(open(s_path))
        # Check Root first
        manual_loop = s.get("manual_loop")
        if not manual_loop and "rows" in s:
             manual_loop = s["rows"][0].get("manual_loop", {})
             
        stage = manual_loop.get("stage") if manual_loop else "UNKNOWN"
        print(f"STAGE={stage}")
    else:
        print("STAGE=MISSING")

    # Replay Check
    r_path = 'state/runtime/asof_override_latest.json'
    if os.path.exists(r_path):
        r = json.load(open(r_path))
        print(f"REPLAY={r.get('enabled')}")
        print(f"REPLAY_MODE={r.get('mode')}")
    else:
        print("REPLAY=MISSING")
        
except Exception as e:
    print(f"ERROR: {e}")
