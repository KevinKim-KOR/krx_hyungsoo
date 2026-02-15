#!/bin/bash
cd /home/ubuntu/krx_hyungsoo || exit 1

echo "=== 1. Sync & Recover ==="
git pull
bash deploy/oci/bundle_recover_check.sh

echo "=== 2. Daily Ops (Determine Day Type) ==="
bash deploy/oci/daily_ops.sh

echo "=== 3. Ops Summary Stage ==="
# Force regenerate to be sure
curl -s -X POST 'http://localhost:8000/api/ops/summary/regenerate?confirm=true' > /dev/null
python3 -c "import json; d=json.load(open('reports/ops/summary/ops_summary_latest.json')); row=d.get('rows',[{}])[0]; print(f'STAGE: {row.get(\"manual_loop\", {}).get(\"stage\")}')"

echo "=== 4. Artifact Check (Force Regen) ==="
# Export
curl -s -X POST 'http://localhost:8000/api/order_plan_export/regenerate?confirm=true' > /dev/null
python3 -c "import json; d=json.load(open('reports/live/order_plan_export/latest/order_plan_export_latest.json')); print(f'EXPORT_ROOT_ID: {d.get(\"plan_id\")}')"

# Ticket (Force Blocked Check)
curl -s -X POST 'http://localhost:8000/api/manual_execution_ticket/regenerate?confirm=true' > /dev/null
python3 -c "import json; d=json.load(open('reports/live/manual_execution_ticket/latest/manual_execution_ticket_latest.json')); print(f'TICKET_DEC: {d.get(\"decision\")}\nPLAN_ID: {d.get(\"source\",{}).get(\"plan_id\")}')"

echo "=== 5. Steady Gate ==="
bash deploy/oci/steady_gate_check.sh
