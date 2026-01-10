#!/bin/bash
# deploy/run_ops_cycle.sh
# Ops Cycle 실행 스크립트 (Linux/Mac)
# Phase C-P.27

API_BASE="${API_BASE:-http://127.0.0.1:8000}"

echo "[OPS_CYCLE] Starting Ops Cycle Run..."
echo "[OPS_CYCLE] API Base: $API_BASE"

response=$(curl -s -X POST "$API_BASE/api/ops/cycle/run" -H "Content-Type: application/json")

if [ $? -ne 0 ]; then
    echo "[OPS_CYCLE] Error: Failed to call API"
    exit 1
fi

echo "[OPS_CYCLE] Response:"
echo "$response" | python3 -m json.tool 2>/dev/null || echo "$response"

overall_status=$(echo "$response" | python3 -c "import sys,json; print(json.load(sys.stdin).get('overall_status','UNKNOWN'))" 2>/dev/null)

case "$overall_status" in
    DONE|STOPPED|SKIPPED)
        echo "[OPS_CYCLE] Completed with status: $overall_status"
        exit 0
        ;;
    *)
        echo "[OPS_CYCLE] Completed with status: $overall_status"
        exit 1
        ;;
esac
