#!/bin/bash
# check_ops_summary.sh - OCI Ops Summary Check Script (D-P.53)
# Usage: bash deploy/oci/check_ops_summary.sh
# Exit codes: 0=OK (even if WARN), 3=API/JSON/resolve error

set -euo pipefail

BASE_URL="${KRX_API_URL:-http://127.0.0.1:8000}"

# Step 1: Regenerate Ops Summary
echo "[1/3] Regenerating Ops Summary..."
REGEN_RESP=$(curl -s -X POST "${BASE_URL}/api/ops/summary/regenerate?confirm=true")
if [ -z "$REGEN_RESP" ]; then
    echo "❌ Regenerate API call failed"
    exit 3
fi

# Step 2: Get latest summary
echo "[2/3] Fetching latest summary..."
LATEST_RESP=$(curl -s "${BASE_URL}/api/ops/summary/latest")
if [ -z "$LATEST_RESP" ]; then
    echo "❌ Latest API call failed"
    exit 3
fi

# Step 3: Parse and validate
echo "[3/3] Validating summary..."
VALIDATION=$(echo "$LATEST_RESP" | python3 -c '
import json,sys
try:
    d = json.load(sys.stdin)
    row = (d.get("rows") or [d])[0]
    
    overall = row.get("overall_status", "UNKNOWN")
    
    guard = row.get("guard") or {}
    eh = guard.get("evidence_health") or {}
    eh_decision = eh.get("decision", "UNKNOWN")
    eh_snapshot_ref = eh.get("snapshot_ref") or ""
    
    tr = row.get("tickets_recent") or {}
    tr_failed = tr.get("failed", 0)
    tr_excluded = tr.get("excluded_cleanup_failed", 0)
    
    risks = row.get("top_risks") or []
    risk_codes = [r.get("code") for r in risks]
    
    # Find health risk evidence_refs
    health_risk_refs = []
    for r in risks:
        if r.get("code") in ("EVIDENCE_HEALTH_WARN", "EVIDENCE_HEALTH_FAIL"):
            health_risk_refs = r.get("evidence_refs", [])
            break
    
    print(f"OVERALL={overall}")
    print(f"EH_DECISION={eh_decision}")
    print(f"EH_SNAPSHOT_REF={eh_snapshot_ref}")
    print(f"TR_FAILED={tr_failed}")
    print(f"TR_EXCLUDED={tr_excluded}")
    print(f"RISK_CODES={risk_codes}")
    print(f"HEALTH_RISK_REFS={health_risk_refs}")
except Exception as e:
    print(f"PARSE_ERROR={e}")
')

# Parse output
eval "$VALIDATION"

if [ -n "${PARSE_ERROR:-}" ]; then
    echo "❌ Parse error: $PARSE_ERROR"
    exit 3
fi

# Step 4: Verify snapshot_ref via Evidence resolver (if exists)
if [ -n "$EH_SNAPSHOT_REF" ]; then
    echo "[4/4] Verifying evidence_health.snapshot_ref..."
    EVIDENCE_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}/api/evidence/resolve?ref=${EH_SNAPSHOT_REF}")
    if [ "$EVIDENCE_STATUS" != "200" ]; then
        echo "❌ Evidence resolve failed: HTTP $EVIDENCE_STATUS for $EH_SNAPSHOT_REF"
        exit 3
    fi
    EH_RESOLVE="OK"
else
    EH_RESOLVE="N/A"
fi

# Summary
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "OPS: $OVERALL | health=$EH_DECISION | snapshot=$EH_RESOLVE"
echo "tickets_recent: failed=$TR_FAILED excluded=$TR_EXCLUDED"
echo "top_risks: $RISK_CODES"
echo "═══════════════════════════════════════════════════════════════"

echo "✅ PASS: All checks passed"
exit 0
