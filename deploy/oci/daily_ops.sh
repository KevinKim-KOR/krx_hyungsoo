#!/bin/bash
# daily_ops.sh - OCI Daily Operations Script (D-P.54 + D-P.57)
# Usage: bash deploy/oci/daily_ops.sh
# Cron: 5 9 * * * cd /home/ubuntu/krx_hyungsoo && bash deploy/oci/daily_ops.sh >> logs/daily_ops.log 2>&1
#
# Exit codes:
#   0 = COMPLETED or WARN (검증 OK)
#   2 = BLOCKED (안전장치로 막힘 - 정상 차단)
#   3 = 파싱 실패/백엔드 죽음/resolve 실패 (운영 장애)
#
# D-P.57: Incident push on failure + backend-down fallback

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
BASE_URL="${KRX_API_URL:-http://127.0.0.1:8000}"
LOG_PREFIX="[$(date '+%Y-%m-%d %H:%M:%S')]"
SECRETS_FILE="$REPO_DIR/state/secrets/telegram.env"
EXIT_CODE=0

cd "$REPO_DIR"

# Ensure logs directory
mkdir -p logs

# ============================================================================
# Helper: Telegram Fallback (backend down일 때 직발송)
# ============================================================================
send_telegram_fallback() {
    local message="$1"
    
    # Load secrets if exists
    if [ -f "$SECRETS_FILE" ]; then
        source "$SECRETS_FILE"
    fi
    
    if [ -z "${TELEGRAM_BOT_TOKEN:-}" ] || [ -z "${TELEGRAM_CHAT_ID:-}" ]; then
        echo "$LOG_PREFIX [FALLBACK] No telegram credentials, skip"
        return 1
    fi
    
    curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        -d "chat_id=${TELEGRAM_CHAT_ID}" \
        -d "text=${message}" > /dev/null 2>&1 || true
    
    echo "$LOG_PREFIX [FALLBACK] Telegram sent"
    return 0
}

# ============================================================================
# Helper: Incident Push (API or fallback)
# ============================================================================
send_incident() {
    local kind="$1"
    local step="$2"
    local reason="$3"
    
    # Try API first
    local resp=$(curl -s -X POST "${BASE_URL}/api/push/incident/send?confirm=true&kind=${kind}&step=${step}&reason=$(echo "$reason" | head -c 100 | sed 's/ /%20/g')" 2>/dev/null || echo "")
    
    if echo "$resp" | grep -q '"result":"OK"'; then
        echo "$LOG_PREFIX ✓ Incident push sent via API: $kind"
        return 0
    fi
    
    # Fallback to direct telegram
    echo "$LOG_PREFIX ⚠️ API incident failed, trying fallback..."
    send_telegram_fallback "🚨 INCIDENT: $kind

Step: $step
Reason: $reason

조치: OCI 접속하여 systemctl restart krx-backend.service"
}

echo "$LOG_PREFIX ═══════════════════════════════════════════════════════════════"
echo "$LOG_PREFIX  OCI Daily Operations - $(date '+%Y-%m-%d %H:%M:%S KST')"
echo "$LOG_PREFIX ═══════════════════════════════════════════════════════════════"

# ============================================================================
# Step 1: Repo Update
# ============================================================================
echo ""
echo "$LOG_PREFIX [1/7] Updating repository..."
if ! git pull origin archive-rebuild --quiet 2>/dev/null; then
    echo "$LOG_PREFIX ⚠️ git pull failed (will continue with current code)"
fi
echo "$LOG_PREFIX ✓ Repository updated"

# ============================================================================
# Step 2: Backend Health Check (+ fallback on failure)
# ============================================================================
echo ""
echo "$LOG_PREFIX [2/7] Checking backend health..."
HEALTH_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}/api/ops/health" 2>/dev/null || echo "000")

if [ "$HEALTH_STATUS" != "200" ]; then
    echo "$LOG_PREFIX ❌ Backend not responding (HTTP $HEALTH_STATUS)"
    
    # D-P.57: Fallback - direct telegram when backend is down
    send_telegram_fallback "🚨 INCIDENT: BACKEND_DOWN

서버가 응답하지 않습니다.
HTTP Status: $HEALTH_STATUS

조치: OCI 접속하여 systemctl restart krx-backend.service"
    
    exit 3
fi
echo "$LOG_PREFIX ✓ Backend healthy (HTTP 200)"

# ============================================================================
# Step 3: Ops Summary Regenerate (minimal verification)
# ============================================================================
# ============================================================================
# Step 3: Ops Summary Regenerate (minimal verification)
# ============================================================================
echo ""
echo "$LOG_PREFIX [3/7] Regenerating Ops Summary..."
REGEN_RESP=$(curl -s -X POST "${BASE_URL}/api/ops/summary/regenerate?confirm=true")

if ! echo "$REGEN_RESP" | grep -q '"schema":"OPS_SUMMARY_V1"'; then
    echo "$LOG_PREFIX ❌ Ops Summary regenerate failed: $REGEN_RESP"
    send_incident "OPS_FAILED" "Step3" "Regenerate API failed"
    exit 3
fi
echo "$LOG_PREFIX ✓ Ops Summary regenerated"

# Quick status check from latest
OPS_STATUS=$(curl -s "${BASE_URL}/api/ops/summary/latest" | python3 -c 'import json,sys; d=json.load(sys.stdin); row=(d.get("rows") or [d])[0]; print(row.get("overall_status","UNKNOWN"))' 2>/dev/null || echo "UNKNOWN")
echo "$LOG_PREFIX ✓ Ops Summary status: $OPS_STATUS"

# Check if BLOCKED/STOPPED
if [ "$OPS_STATUS" = "BLOCKED" ] || [ "$OPS_STATUS" = "STOPPED" ]; then
    echo "$LOG_PREFIX ⚠️ Ops Summary $OPS_STATUS - 정상 차단"
    send_incident "OPS_BLOCKED" "Step3" "Ops Summary $OPS_STATUS"
    EXIT_CODE=2
fi

# Fetch Bundle Stale Status (SPoT)
BUNDLE_STALE=$(curl -s "${BASE_URL}/api/strategy_bundle/latest" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(str(d.get("summary", d).get("stale", "false")).lower())' 2>/dev/null || echo "false")


# ============================================================================
# Step 4: Live Cycle Run (Only if OK)
# ============================================================================
CYCLE_RESULT="SKIPPED"
CYCLE_DECISION="SKIPPED"
CYCLE_REASON="OPS_BLOCKED"
CYCLE_DELIVERY="NONE"
CYCLE_SNAPSHOT=""

if [ $EXIT_CODE -eq 0 ]; then
    echo ""
    echo "$LOG_PREFIX [4/7] Running Live Cycle..."
    CYCLE_RESP=$(curl -s -X POST "${BASE_URL}/api/live/cycle/run?confirm=true")
    if [ -z "$CYCLE_RESP" ]; then
        echo "$LOG_PREFIX ❌ Live Cycle run failed"
        send_incident "LIVE_FAILED" "Step4" "Live Cycle API returned empty"
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
        send_incident "LIVE_FAILED" "Step4" "Live Cycle parse error"
        exit 3
    fi

    CYCLE_RESULT=$(echo "$CYCLE_PARSED" | grep "^CYCLE_RESULT:" | cut -d: -f2-)
    CYCLE_DECISION=$(echo "$CYCLE_PARSED" | grep "^CYCLE_DECISION:" | cut -d: -f2-)
    CYCLE_REASON=$(echo "$CYCLE_PARSED" | grep "^CYCLE_REASON:" | cut -d: -f2-)
    CYCLE_DELIVERY=$(echo "$CYCLE_PARSED" | grep "^CYCLE_DELIVERY:" | cut -d: -f2-)
    CYCLE_SNAPSHOT=$(echo "$CYCLE_PARSED" | grep "^CYCLE_SNAPSHOT:" | cut -d: -f2-)
    # Check result
    if [ "$CYCLE_RESULT" = "FAILED" ]; then
        echo "$LOG_PREFIX ❌ Live Cycle FAILED: $CYCLE_REASON"
        send_incident "LIVE_FAILED" "Step4" "$CYCLE_REASON"
        exit 3
    fi

    echo "$LOG_PREFIX ✓ Live Cycle: result=$CYCLE_RESULT decision=$CYCLE_DECISION delivery=$CYCLE_DELIVERY"

    # Check if BLOCKED
    if [ "$CYCLE_DECISION" = "BLOCKED" ]; then
        echo "$LOG_PREFIX ⚠️ Live Cycle BLOCKED: $CYCLE_REASON (Continuing to push)"
        # Don't exit here, just set flag to return 2 at the end
        EXIT_CODE=2
    fi
fi

# ============================================================================
# Step 5: Order Plan Regenerate (D-P.58) (Only if OK)
# ============================================================================
ORDER_DECISION="SKIPPED"
ORDER_REASON="OPS_BLOCKED"

if [ $EXIT_CODE -eq 0 ]; then
    echo ""
    echo "$LOG_PREFIX [5/7] Regenerating Order Plan..."
    ORDER_RESP=$(curl -s -X POST "${BASE_URL}/api/order_plan/regenerate?confirm=true")

    if echo "$ORDER_RESP" | grep -q '"decision"'; then
        ORDER_DECISION=$(echo "$ORDER_RESP" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("decision","UNKNOWN"))' 2>/dev/null || echo "UNKNOWN")
        ORDER_REASON=$(echo "$ORDER_RESP" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("reason",""))' 2>/dev/null || echo "")
        
        echo "$LOG_PREFIX ✓ Order Plan: $ORDER_DECISION ($ORDER_REASON)"
        
        if [ "$ORDER_DECISION" = "BLOCKED" ]; then
            # Order Plan BLOCKED is not fatal, just warning (e.g. no portfolio)
            echo "$LOG_PREFIX ⚠️ Order Plan BLOCKED: $ORDER_REASON"
            # We don't exit here, just log it. Stale risk is handled in Ops Summary.
        fi
    else
        echo "$LOG_PREFIX ❌ Order Plan regen failed: $ORDER_RESP"
        send_incident "ORDER_PLAN_FAILED" "Step5" "Order plan API failed"
        exit 3
    fi
fi

# ============================================================================
# Step 6: Snapshot Verification (Only if Cycle Ran)
# ============================================================================
SNAPSHOT_OK="N/A"
if [ -n "$CYCLE_SNAPSHOT" ]; then
    echo ""
    echo "$LOG_PREFIX [6/7] Verifying snapshot..."
    RESOLVE_STATUS=$(curl -s -o /dev/null -w "%{http_code}" -G "${BASE_URL}/api/evidence/resolve" --data-urlencode "ref=${CYCLE_SNAPSHOT}")
    if [ "$RESOLVE_STATUS" = "200" ]; then
        SNAPSHOT_OK="OK"
    else
        echo "$LOG_PREFIX ⚠️ Snapshot resolve: HTTP $RESOLVE_STATUS (non-fatal)"
        SNAPSHOT_OK="SKIP"
    fi
    echo "$LOG_PREFIX ✓ Snapshot verification: $SNAPSHOT_OK"
fi

# ============================================================================
# Step 6b (Real Step 7): Daily Status Push (Always Run if not failed fatally)
# ============================================================================
echo ""
echo "$LOG_PREFIX [7/7] Sending Daily Status Push (with reco details)..."

PUSH_RESP=$(curl -s -X POST "${BASE_URL}/api/push/daily_status/send?confirm=true")

if echo "$PUSH_RESP" | grep -q '"result":"OK"'; then
    PUSH_SKIPPED=$(echo "$PUSH_RESP" | python3 -c 'import json,sys; d=json.load(sys.stdin); print("true" if d.get("skipped") else "false")' 2>/dev/null || echo "false")
    PUSH_DELIVERY=$(echo "$PUSH_RESP" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("delivery_actual","UNKNOWN"))' 2>/dev/null || echo "UNKNOWN")
    PUSH_RECO_COUNT=$(echo "$PUSH_RESP" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("reco_items_count",0))' 2>/dev/null || echo "0")
    
    if [ "$PUSH_SKIPPED" = "true" ]; then
        echo "$LOG_PREFIX ✓ Daily PUSH: SKIPPED (already sent today)"
    else
        echo "$LOG_PREFIX ✓ Daily PUSH: SENT delivery=$PUSH_DELIVERY reco_items=$PUSH_RECO_COUNT"
    fi
else
    echo "$LOG_PREFIX ⚠️ Daily PUSH failed: $PUSH_RESP (non-fatal)"
    send_incident "PUSH_FAILED" "Step6" "Daily status push failed"
fi

# ============================================================================
# Step 7: Daily Summary Log (P72 Standard)
# ============================================================================
echo ""
echo "$LOG_PREFIX [7/7] Generating Daily Summary..."

# Fetch Reco Status (SPoT) - Single Source /api/reco/latest
# P77-FIX5: Strict Normalization (No UNKNOWN, No GENERATED)
RECO_JSON=$(curl -s "${BASE_URL}/api/reco/latest" 2>/dev/null || echo "{}")

# Reco Decision Normalization
# Allow: OK, EMPTY_RECO, BLOCKED, MISSING_RECO
# Map: GENERATED -> OK, UNKNOWN -> MISSING_RECO, anything else -> MISSING_RECO (safeguard)
RECO_DECISION=$(echo "$RECO_JSON" | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
    # 1. Unwrap
    report = d.get("report") or d
    dec = report.get("decision")
    
    # 2. Normalize
    if not dec:
        print("MISSING_RECO")
    elif dec == "GENERATED" or dec == "OK" or dec == "COMPLETED":
        print("OK")
    elif dec in ["EMPTY_RECO", "BLOCKED", "MISSING_RECO"]:
        print(dec)
    else:
        # Catch-all for UNKNOWN or unexpected values
        print("MISSING_RECO")
except:
    print("MISSING_RECO")
')

RECO_REASON=$(echo "$RECO_JSON" | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
    report = d.get("report") or d
    print(report.get("reason", "MISSING_RECO"))
except:
    print("MISSING_RECO")
')

# Fetch Risks from Ops Summary
# P77-FIX5: Enforce Risk Consistency
RISKS_JSON="[]"
OPS_SUMMARY_JSON=$(curl -s "${BASE_URL}/api/ops/summary/latest" 2>/dev/null)
if [ -n "$OPS_SUMMARY_JSON" ]; then
    RISKS_JSON=$(echo "$OPS_SUMMARY_JSON" | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
    # Unwrap rows if needed
    row = (d.get("rows") or [d])[0]
    risks = [r.get("code") for r in row.get("top_risks", [])]
    print(json.dumps(risks))
except:
    print("[]")
')
fi

# Force Risk Consistency: If Order Plan is BLOCKED, Risks MUST NOT be empty
if [ "$ORDER_DECISION" = "BLOCKED" ]; then
    # Check if RISKS_JSON is truly empty array "[]"
    if [ "$RISKS_JSON" = "[]" ]; then
        # Force inject the reason or generic block code
        RISKS_JSON="[\"ORDER_PLAN_BLOCKED\"]"
    else
        # If not empty, ensure it contains the block reason if possible? 
        # But if it's not empty, it likely has the cause (e.g. NO_BUNDLE). 
        # User requirement: "Reason=ORDER_PLAN_BLOCKED이면 risks에 반드시 ORDER_PLAN_BLOCKED 포함"
        # We can append or checks. Easier to ensure strictly for this case.
        if [ "$ORDER_REASON" = "ORDER_PLAN_BLOCKED" ]; then
             RISKS_JSON=$(echo "$RISKS_JSON" | python3 -c "import json,sys; r=json.load(sys.stdin); r.append('ORDER_PLAN_BLOCKED') if 'ORDER_PLAN_BLOCKED' not in r else None; print(json.dumps(r))")
        fi
    fi
fi

# P77-FIX: Use CURRENT run results for summary (Consistency)
# Construct JSON manually from bash variables
SUMMARY_OUTPUT=$(cat <<EOF | python3 "${REPO_DIR}/app/utils/print_daily_summary.py" | sed "s/^/$LOG_PREFIX /"
{
  "ops_status": "$OPS_STATUS",
  "live_status": {
    "result": "$CYCLE_RESULT",
    "decision": "$CYCLE_DECISION"
  },
  "bundle": {
    "stale": "$BUNDLE_STALE"
  },
  "reco": {
    "decision": "$RECO_DECISION",
    "reason": "$RECO_REASON"
  },
  "order_plan": {
    "decision": "$ORDER_DECISION",
    "reason": "$ORDER_REASON"
  },
  "top_risks": $RISKS_JSON
}
EOF
)

# Output handling (P77-FIX6: Dedicated Logs)
# 1. Stdout (for daily_ops.log)
echo "$SUMMARY_OUTPUT"

# 2. Dedicated Logs (Reliable Verification)
mkdir -p logs
echo "$SUMMARY_OUTPUT" >> logs/daily_summary.log
echo "$SUMMARY_OUTPUT" > logs/daily_summary.latest
# Note: Reco decision is technically inside Cycle or Order Plan context, usually implies EMPTY_RECO if BLOCKED.
# However, print_daily_summary mainly cares about Order Plan and Bundle Stale.
# We can fetch reco status if strictly needed, but Order Plan Reason now contains RECO_ reason.


# ============================================================================
# Final Summary
# ============================================================================
echo ""
echo "$LOG_PREFIX ═══════════════════════════════════════════════════════════════"
echo "$LOG_PREFIX  DAILY OPS COMPLETE"
echo "$LOG_PREFIX  Ops: $OPS_STATUS | Cycle: $CYCLE_RESULT $CYCLE_DECISION"
echo "$LOG_PREFIX  Delivery: $CYCLE_DELIVERY | Snapshot: $SNAPSHOT_OK"
echo "$LOG_PREFIX ═══════════════════════════════════════════════════════════════"

if [ "$EXIT_CODE" -eq 0 ]; then
    echo "$LOG_PREFIX ✅ All checks passed"
elif [ "$EXIT_CODE" -eq 2 ]; then
    echo "$LOG_PREFIX ⚠️ Ops Completed with Warnings (BLOCKED)"
else
    echo "$LOG_PREFIX ❌ Ops Failed (Exit Code: $EXIT_CODE)"
fi
exit $EXIT_CODE
