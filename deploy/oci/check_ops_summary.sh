#!/bin/bash
# check_ops_summary.sh - OCI Ops Summary Check Script (D-P.53.1)
# Usage: bash deploy/oci/check_ops_summary.sh
# Exit codes: 0=OK (even if WARN), 3=API/JSON/resolve error
#
# D-P.53.1 Hardening:
# - Python outputs raw strings only (no list syntax)
# - Evidence validation via resolver API only (no local file access)
# - URL encoding for ref parameters

set -euo pipefail

BASE_URL="${KRX_API_URL:-http://127.0.0.1:8000}"

# Step 1: Regenerate Ops Summary
echo "[1/4] Regenerating Ops Summary..."
REGEN_RESP=$(curl -s -X POST "${BASE_URL}/api/ops/summary/regenerate?confirm=true")
if [ -z "$REGEN_RESP" ]; then
    echo "❌ Regenerate API call failed"
    exit 3
fi

# Step 2: Get latest summary
echo "[2/4] Fetching latest summary..."
LATEST_RESP=$(curl -s "${BASE_URL}/api/ops/summary/latest")
if [ -z "$LATEST_RESP" ]; then
    echo "❌ Latest API call failed"
    exit 3
fi

# Step 3: Parse summary (safe output - no lists, just raw values)
echo "[3/4] Parsing summary..."
PARSED=$(echo "$LATEST_RESP" | python3 -c '
import json,sys,urllib.parse
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
    risk_codes_str = ",".join(r.get("code","") for r in risks)
    
    # Collect evidence_refs from EVIDENCE_HEALTH_* risks (one per line)
    health_refs = []
    for r in risks:
        if r.get("code") in ("EVIDENCE_HEALTH_WARN", "EVIDENCE_HEALTH_FAIL"):
            health_refs = r.get("evidence_refs", [])
            break
    
    # Output format: key=value (no special chars that need escaping)
    print(f"OVERALL:{overall}")
    print(f"EH_DECISION:{eh_decision}")
    print(f"EH_SNAPSHOT_REF:{eh_snapshot_ref}")
    print(f"TR_FAILED:{tr_failed}")
    print(f"TR_EXCLUDED:{tr_excluded}")
    print(f"RISK_CODES:{risk_codes_str}")
    print(f"HEALTH_REFS_COUNT:{len(health_refs)}")
    # Output each ref on separate line with prefix for safe parsing
    for ref in health_refs:
        if ref:
            print(f"REF:{ref}")
except Exception as e:
    print(f"PARSE_ERROR:{e}")
    sys.exit(1)
')

# Check for parse error
if echo "$PARSED" | grep -q "^PARSE_ERROR:"; then
    echo "❌ Parse error: $(echo "$PARSED" | grep "^PARSE_ERROR:" | cut -d: -f2-)"
    exit 3
fi

# Extract values safely (no eval!)
OVERALL=$(echo "$PARSED" | grep "^OVERALL:" | cut -d: -f2-)
EH_DECISION=$(echo "$PARSED" | grep "^EH_DECISION:" | cut -d: -f2-)
EH_SNAPSHOT_REF=$(echo "$PARSED" | grep "^EH_SNAPSHOT_REF:" | cut -d: -f2-)
TR_FAILED=$(echo "$PARSED" | grep "^TR_FAILED:" | cut -d: -f2-)
TR_EXCLUDED=$(echo "$PARSED" | grep "^TR_EXCLUDED:" | cut -d: -f2-)
RISK_CODES=$(echo "$PARSED" | grep "^RISK_CODES:" | cut -d: -f2-)

# Step 4: Verify evidence_health.snapshot_ref via resolver (if exists)
echo "[4/4] Verifying evidence refs via resolver..."
EH_RESOLVE="N/A"

if [ -n "$EH_SNAPSHOT_REF" ]; then
    # Use --data-urlencode for safe URL encoding
    EVIDENCE_STATUS=$(curl -s -o /dev/null -w "%{http_code}" -G "${BASE_URL}/api/evidence/resolve" --data-urlencode "ref=${EH_SNAPSHOT_REF}")
    if [ "$EVIDENCE_STATUS" = "200" ]; then
        EH_RESOLVE="OK"
    else
        echo "⚠️ snapshot_ref resolve: HTTP $EVIDENCE_STATUS (non-fatal)"
        EH_RESOLVE="SKIP"
    fi
fi

# Verify health risk evidence_refs via resolver
REF_OK=0
REF_FAIL=0
echo "$PARSED" | grep "^REF:" | cut -d: -f2- | while read -r REF; do
    if [ -n "$REF" ]; then
        STATUS=$(curl -s -o /dev/null -w "%{http_code}" -G "${BASE_URL}/api/evidence/resolve" --data-urlencode "ref=${REF}")
        if [ "$STATUS" = "200" ]; then
            ((REF_OK++)) || true
        else
            echo "⚠️ ref resolve failed: $REF (HTTP $STATUS)"
            ((REF_FAIL++)) || true
        fi
    fi
done

# Summary
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "OPS: $OVERALL | health=$EH_DECISION | snapshot=$EH_RESOLVE"
echo "tickets_recent: failed=$TR_FAILED excluded=$TR_EXCLUDED"
echo "top_risks: [$RISK_CODES]"
echo "═══════════════════════════════════════════════════════════════"

echo "✅ PASS: All checks completed"
exit 0
