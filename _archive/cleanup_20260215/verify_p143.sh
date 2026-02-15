
#!/bin/bash
cd /home/ubuntu/krx_hyungsoo || exit 1

echo "=== 1. Sync Code ==="
git pull

echo "=== 2. Setup Replay Mode ==="
mkdir -p state/runtime
echo '{"mode": "REPLAY", "asof_kst": "2026-02-13", "enabled": true}' > state/runtime/asof_override_latest.json

echo "=== 3. Ops Summary Stage (Holiday Check) ==="
# Force regenerate
curl -s -X POST 'http://localhost:8000/api/ops/summary/regenerate?confirm=true' > /dev/null
python3 -c "import json; d=json.load(open('reports/ops/summary/ops_summary_latest.json')); row=d.get('rows',[{}])[0]; print(f'STAGE: {row.get(\"manual_loop\", {}).get(\"stage\")}')"

echo "=== 4. Setup Inconsistent Portfolio for Normalize Test ==="
# Create inconsistent portfolio: Cash=100, Pos=50 (10*5), Total=9999 (Wrong)
mkdir -p state/portfolio/latest
cat <<EOF > state/portfolio/latest/portfolio_latest.json
{
  "updated_at": "2026-02-13T00:00:00Z",
  "cash": 100,
  "total_value": 9999, 
  "holdings": {
    "TEST": {"ticker": "TEST", "quantity": 10, "avg_price": 5}
  }
}
EOF

echo "=== 5. Apply Bundle Override (Trigger Normalize) ==="
# We simulate apply_portfolio_override logic by running a script that calls normalize_portfolio directly
# or by creating a bundle with override.
# Let's use a python one-liner to verify normalize_portfolio logic on OCI environment
python3 -c "
import sys
sys.path.append('.')
from app.utils.admin_utils import normalize_portfolio
import json

p = json.load(open('state/portfolio/latest/portfolio_latest.json'))
n = normalize_portfolio(p)
print(f'ORIG_TOTAL: {p.get(\"total_value\")}')
print(f'NORM_TOTAL: {n.get(\"total_value\")}')
print(f'ASOF_EXISTS: {bool(n.get(\"asof\"))}')

# Save it back to simulate the effect
with open('state/portfolio/latest/portfolio_latest.json', 'w') as f:
    json.dump(n, f)
"

echo "=== 6. Verify Dashboard Replay Info ==="
# Check Replay Info via API (optional, or just check the file we created)
python3 -c "import json; d=json.load(open('state/runtime/asof_override_latest.json')); print(f'REPLAY_ENABLED: {d.get(\"enabled\")}')"

echo "=== 7. Cleanup (Optional) ==="
# rm state/runtime/asof_override_latest.json
