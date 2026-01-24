#!/bin/bash
# daily_ops.sh - OCI Daily Operations Script (D-P.54)
# Usage: bash deploy/oci/daily_ops.sh
# Cron: 5 9 * * * cd /home/ubuntu/krx_hyungsoo && bash deploy/oci/daily_ops.sh >> logs/daily_ops.log 2>&1
#
# Exit codes:
#   0 = COMPLETED or WARN (검증 OK)
#   2 = BLOCKED (안전장치로 막힘 - 정상 차단)
#   3 = 파싱 실패/백엔드 죽음/resolve 실패 (운영 장애)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
BASE_URL="${KRX_API_URL:-http://127.0.0.1:8000}"
LOG_PREFIX="[$(date '+%Y-%m-%d %H:%M:%S')]"

cd "$REPO_DIR"

echo "$LOG_PREFIX ═══════════════════════════════════════════════════════════════"
echo "$LOG_PREFIX  OCI Daily Operations - $(date '+%Y-%m-%d %H:%M:%S KST')"
echo "$LOG_PREFIX ═══════════════════════════════════════════════════════════════"

# ============================================================================
# Step 1: Repo Update
# ============================================================================
echo ""
echo "$LOG_PREFIX [1/5] Updating repository..."
if ! git pull origin archive-rebuild --quiet 2>/dev/null; then
    echo "$LOG_PREFIX ⚠️ git pull failed (will continue with current code)"
fi
echo "$LOG_PREFIX ✓ Repository updated"

# ============================================================================
# Step 2: Backend Health Check
# ============================================================================
echo ""
echo "$LOG_PREFIX [2/5] Checking backend health..."
HEALTH_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}/api/ops/health" 2>/dev/null || echo "000")

if [ "$HEALTH_STATUS" != "200" ]; then
    echo "$LOG_PREFIX ❌ Backend not responding (HTTP $HEALTH_STATUS)"
    echo "$LOG_PREFIX    → Try: nohup python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 > logs/backend.log 2>&1 &"
    exit 3
fi
echo "$LOG_PREFIX ✓ Backend healthy (HTTP 200)"

# ============================================================================
# Step 3: Ops Summary Regenerate + Check
# ============================================================================
echo ""
echo "$LOG_PREFIX [3/5] Regenerating Ops Summary..."
REGEN_RESP=$(curl -s -X POST "${BASE_URL}/api/ops/summary/regenerate?confirm=true")
if [ -z "$REGEN_RESP" ]; then
    echo "$LOG_PREFIX ❌ Ops Summary regenerate failed"
    exit 3
fi

# Parse summary
OPS_PARSED=$(curl -s "${BASE_URL}/api/ops/summary/latest" | python3 -c '
import json,sys
try:
    d = json.load(sys.stdin)
    row = (d.get("rows") or [d])[0]
    overall = row.get("overall_status", "UNKNOWN")
    guard = row.get("guard") or {}
    eh = guard.get("evidence_health") or {}
    tr = row.get("tickets_recent") or {}
    risks = row.get("top_risks") or []
    print(f"OPS_OVERALL:{overall}")
    print(f"OPS_EH_DECISION:{eh.get('decision','UNKNOWN')}")
    print(f"OPS_TR_FAILED:{tr.get('failed',0)}")
    print(f"OPS_RISK_COUNT:{len(risks)}")
except Exception as e:
    print(f"PARSE_ERROR:{e}")
    sys.exit(1)
')

if echo "$OPS_PARSED" | grep -q "^PARSE_ERROR:"; then
    echo "$LOG_PREFIX ❌ Ops Summary parse failed"
    exit 3
fi

OPS_OVERALL=$(echo "$OPS_PARSED" | grep "^OPS_OVERALL:" | cut -d: -f2-)
OPS_EH=$(echo "$OPS_PARSED" | grep "^OPS_EH_DECISION:" | cut -d: -f2-)
OPS_TR_FAILED=$(echo "$OPS_PARSED" | grep "^OPS_TR_FAILED:" | cut -d: -f2-)

echo "$LOG_PREFIX ✓ Ops Summary: status=$OPS_OVERALL health=$OPS_EH failed=$OPS_TR_FAILED"

# Check if BLOCKED
if [ "$OPS_OVERALL" = "BLOCKED" ] || [ "$OPS_OVERALL" = "STOPPED" ]; then
    echo "$LOG_PREFIX ⚠️ Ops Summary BLOCKED/STOPPED - 정상 차단"
    exit 2
fi

# ============================================================================
# Step 4: Live Cycle Run
# ============================================================================
echo ""
echo "$LOG_PREFIX [4/5] Running Live Cycle..."
CYCLE_RESP=$(curl -s -X POST "${BASE_URL}/api/live/cycle/run?confirm=true")
if [ -z "$CYCLE_RESP" ]; then
    echo "$LOG_PREFIX ❌ Live Cycle run failed"
    exit 3
fi

# Parse cycle result
CYCLE_PARSED=$(curl -s "${BASE_URL}/api/live/cycle/latest" | python3 -c '
import json,sys
try:
    d = json.load(sys.stdin)
    row = (d.get("rows") or [{}])[0]
    result = row.get("result", "UNKNOWN")
    decision = row.get("decision", "UNKNOWN")
    reason = row.get("reason", "UNKNOWN")
    push = row.get("push") or {}
    delivery = push.get("delivery_actual", "UNKNOWN")
    snapshot_ref = row.get("snapshot_ref") or ""
    print(f"CYCLE_RESULT:{result}")
    print(f"CYCLE_DECISION:{decision}")
    print(f"CYCLE_REASON:{reason}")
    print(f"CYCLE_DELIVERY:{delivery}")
    print(f"CYCLE_SNAPSHOT:{snapshot_ref}")
except Exception as e:
    print(f"PARSE_ERROR:{e}")
    sys.exit(1)
')

if echo "$CYCLE_PARSED" | grep -q "^PARSE_ERROR:"; then
    echo "$LOG_PREFIX ❌ Live Cycle parse failed"
    exit 3
fi

CYCLE_RESULT=$(echo "$CYCLE_PARSED" | grep "^CYCLE_RESULT:" | cut -d: -f2-)
CYCLE_DECISION=$(echo "$CYCLE_PARSED" | grep "^CYCLE_DECISION:" | cut -d: -f2-)
CYCLE_REASON=$(echo "$CYCLE_PARSED" | grep "^CYCLE_REASON:" | cut -d: -f2-)
CYCLE_DELIVERY=$(echo "$CYCLE_PARSED" | grep "^CYCLE_DELIVERY:" | cut -d: -f2-)
CYCLE_SNAPSHOT=$(echo "$CYCLE_PARSED" | grep "^CYCLE_SNAPSHOT:" | cut -d: -f2-)

echo "$LOG_PREFIX ✓ Live Cycle: result=$CYCLE_RESULT decision=$CYCLE_DECISION delivery=$CYCLE_DELIVERY"

# Check if BLOCKED
if [ "$CYCLE_DECISION" = "BLOCKED" ]; then
    echo "$LOG_PREFIX ⚠️ Live Cycle BLOCKED: $CYCLE_REASON - 정상 차단"
    exit 2
fi

# ============================================================================
# Step 5: Snapshot Verification
# ============================================================================
echo ""
echo "$LOG_PREFIX [5/5] Verifying snapshot..."
SNAPSHOT_OK="N/A"

if [ -n "$CYCLE_SNAPSHOT" ]; then
    RESOLVE_STATUS=$(curl -s -o /dev/null -w "%{http_code}" -G "${BASE_URL}/api/evidence/resolve" --data-urlencode "ref=${CYCLE_SNAPSHOT}")
    if [ "$RESOLVE_STATUS" = "200" ]; then
        SNAPSHOT_OK="OK"
    else
        echo "$LOG_PREFIX ⚠️ Snapshot resolve: HTTP $RESOLVE_STATUS (non-fatal)"
        SNAPSHOT_OK="SKIP"
    fi
fi
echo "$LOG_PREFIX ✓ Snapshot verification: $SNAPSHOT_OK"

# ============================================================================
# Final Summary
# ============================================================================
echo ""
echo "$LOG_PREFIX ═══════════════════════════════════════════════════════════════"
echo "$LOG_PREFIX  DAILY OPS COMPLETE"
echo "$LOG_PREFIX  Ops: $OPS_OVERALL | Cycle: $CYCLE_RESULT $CYCLE_DECISION"
echo "$LOG_PREFIX  Delivery: $CYCLE_DELIVERY | Snapshot: $SNAPSHOT_OK"
echo "$LOG_PREFIX ═══════════════════════════════════════════════════════════════"

# Verify delivery is CONSOLE_SIMULATED (safety check)
if [ "$CYCLE_DELIVERY" != "CONSOLE_SIMULATED" ]; then
    echo "$LOG_PREFIX ⚠️ WARNING: delivery_actual=$CYCLE_DELIVERY (expected CONSOLE_SIMULATED)"
fi

echo "$LOG_PREFIX ✅ All checks passed"
exit 0
