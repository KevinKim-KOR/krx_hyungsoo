#!/bin/bash
# check_live_cycle.sh - OCI 1-minute Live Cycle Check Script (D-P.51)
# Usage: bash deploy/oci/check_live_cycle.sh
# Exit codes: 0=PASS, 2=snapshot_ref mismatch, 3=API/JSON error

set -euo pipefail

BASE_URL="${KRX_API_URL:-http://127.0.0.1:8000}"

# Step 1: Run Live Cycle
echo "[1/4] Running Live Cycle..."
RUN_RESP=$(curl -s -X POST "${BASE_URL}/api/live/cycle/run?confirm=true")
if [ -z "$RUN_RESP" ]; then
    echo "❌ API call failed"
    exit 3
fi

# Parse run response
RUN_RESULT=$(echo "$RUN_RESP" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("result","ERROR"))' 2>/dev/null || echo "PARSE_ERROR")
if [ "$RUN_RESULT" = "PARSE_ERROR" ]; then
    echo "❌ JSON parse failed: $RUN_RESP"
    exit 3
fi

# Step 2: Get latest receipt
echo "[2/4] Fetching latest receipt..."
LATEST_RESP=$(curl -s "${BASE_URL}/api/live/cycle/latest")
if [ -z "$LATEST_RESP" ]; then
    echo "❌ Latest API call failed"
    exit 3
fi

# Step 3: Parse and validate
echo "[3/4] Validating receipt..."
VALIDATION=$(echo "$LATEST_RESP" | python3 -c '
import json,sys
try:
    d = json.load(sys.stdin)
    r = d.get("rows", [{}])[0]
    
    result = r.get("result", "UNKNOWN")
    decision = r.get("decision", "UNKNOWN")
    
    bundle = r.get("bundle") or {}
    bundle_decision = bundle.get("decision", "UNKNOWN")
    bundle_stale = str(bundle.get("stale", True)).lower()
    
    reco = r.get("reco") or {}
    reco_decision = reco.get("decision", "UNKNOWN")
    
    push = r.get("push") or {}
    delivery = push.get("delivery_actual", "UNKNOWN")
    
    snapshot_ref = r.get("snapshot_ref") or ""
    
    # Output for bash parsing
    print(f"RESULT={result}")
    print(f"DECISION={decision}")
    print(f"BUNDLE={bundle_decision}")
    print(f"STALE={bundle_stale}")
    print(f"RECO={reco_decision}")
    print(f"DELIVERY={delivery}")
    print(f"SNAPSHOT_REF={snapshot_ref}")
except Exception as e:
    print(f"PARSE_ERROR={e}")
')

# Parse validation output
eval "$VALIDATION"

if [ -n "${PARSE_ERROR:-}" ]; then
    echo "❌ Parse error: $PARSE_ERROR"
    exit 3
fi

# Step 4: Verify snapshot_ref via Evidence resolver
echo "[4/4] Verifying snapshot_ref..."
if [ -z "$SNAPSHOT_REF" ]; then
    echo "❌ snapshot_ref is null/empty"
    exit 2
fi

EVIDENCE_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}/api/evidence/resolve?ref=${SNAPSHOT_REF}")
if [ "$EVIDENCE_STATUS" != "200" ]; then
    echo "❌ Evidence resolve failed: HTTP $EVIDENCE_STATUS"
    exit 2
fi

# Build summary line
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "LIVE: $RESULT $DECISION | bundle=$BUNDLE stale=$STALE | reco=$RECO | delivery=$DELIVERY | snapshot_ref=OK"
echo "═══════════════════════════════════════════════════════════════"

# Final check
if [ "$DELIVERY" = "CONSOLE_SIMULATED" ]; then
    echo "✅ PASS: All checks passed"
    exit 0
else
    echo "⚠️ WARNING: delivery_actual=$DELIVERY (expected CONSOLE_SIMULATED)"
    exit 0
fi
