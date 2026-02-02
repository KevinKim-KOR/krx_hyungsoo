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
# Step 1: Repo Update (P83: GIT_PULL_* Enum)
# ============================================================================
echo ""
echo "$LOG_PREFIX [1/7] Updating repository..."

if [ "${DAILY_OPS_NO_GIT_PULL:-}" = "1" ]; then
    echo "$LOG_PREFIX [1/7] Repository update SKIPPED (Verification Mode)"
    GIT_PULL_RESULT="GIT_PULL_SKIPPED"
else
    # Normal Operation
    CURRENT_REV=$(git rev-parse --short HEAD)

    if ! git pull origin main > /dev/null 2>&1; then
        echo "$LOG_PREFIX ❌ Repository update failed"
        # P81-FIX: Critical Failure -> Incident
        GIT_PULL_RESULT="GIT_PULL_FAILED"
        send_incident "OPS_FAILED" "Step1" "git pull failed"
        exit 3
    fi

    # Check if changes were pulled
    REVISION=$(git rev-parse --short HEAD)
    if [ "$REVISION" = "$CURRENT_REV" ]; then
        echo "$LOG_PREFIX ✓ Repository: Already up to date ($REVISION)"
        GIT_PULL_RESULT="GIT_PULL_NO_CHANGES"
    else
        echo "$LOG_PREFIX ✓ Repository: Updated to $REVISION"
        GIT_PULL_RESULT="GIT_PULL_UPDATED"
    fi
fi

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

# ============================================================================
# Step 4: Reco Regenerate (P104)
# ============================================================================
echo ""
echo "$LOG_PREFIX [4/7] Regenerating Reco (RECO)..."
RECO_RESP=$(curl -s -X POST "${BASE_URL}/api/reco/regenerate?confirm=true")

if ! echo "$RECO_RESP" | grep -q '"decision"'; then
    echo "$LOG_PREFIX ❌ Reco regen failed: $RECO_RESP"
    send_incident "OPS_FAILED" "Step4" "Reco API failed"
    exit 3
fi

RECO_DECISION=$(echo "$RECO_RESP" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("decision","UNKNOWN"))' 2>/dev/null || echo "UNKNOWN")
RECO_REASON=$(echo "$RECO_RESP" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("reason",""))' 2>/dev/null || echo "")
echo "$LOG_PREFIX ✓ Reco: $RECO_DECISION ($RECO_REASON)"

# Fail-Closed Check for Reco
if [ "$RECO_DECISION" = "BLOCKED" ] || [ "$RECO_DECISION" = "MISSING_RECO" ]; then
    echo "$LOG_PREFIX ⚠️ Reco BLOCKED/MISSING"
    # Proceed to Order Plan (it handles fail-closed)
    EXIT_CODE=2
fi


# ============================================================================
# Step 5: Order Plan Regenerate (P104)
# ============================================================================
echo ""
echo "$LOG_PREFIX [5/7] Regenerating Order Plan (ORDER_PLAN)..."
ORDER_RESP=$(curl -s -X POST "${BASE_URL}/api/order_plan/regenerate?confirm=true")

if ! echo "$ORDER_RESP" | grep -q '"decision"'; then
    echo "$LOG_PREFIX ❌ Order Plan regen failed: $ORDER_RESP"
    send_incident "OPS_FAILED" "Step5" "Order Plan API failed"
    exit 3
fi

ORDER_DECISION=$(echo "$ORDER_RESP" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("decision","UNKNOWN"))' 2>/dev/null || echo "UNKNOWN")
ORDER_REASON=$(echo "$ORDER_RESP" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("reason",""))' 2>/dev/null || echo "")
ORDER_DETAIL=$(echo "$ORDER_RESP" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("reason_detail",""))' 2>/dev/null || echo "")

echo "$LOG_PREFIX ✓ Order Plan: $ORDER_DECISION ($ORDER_REASON)"

if [ "$ORDER_DECISION" = "BLOCKED" ]; then
    echo "$LOG_PREFIX ⚠️ Order Plan BLOCKED: $ORDER_REASON"
    EXIT_CODE=2
fi


# ============================================================================
# Step 6: Contract 5 Regenerate (P104)
# ============================================================================
echo ""
echo "$LOG_PREFIX [6/7] Regenerating Contract 5 (CONTRACT5)..."
C5_RESP=$(curl -s -X POST "${BASE_URL}/api/contract5/regenerate?confirm=true")

if ! echo "$C5_RESP" | grep -q '"decision"'; then
    echo "$LOG_PREFIX ❌ Contract 5 regen failed: $C5_RESP"
    send_incident "OPS_FAILED" "Step6" "Contract 5 API failed"
    exit 3
fi

C5_DECISION=$(echo "$C5_RESP" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("decision","UNKNOWN"))' 2>/dev/null || echo "UNKNOWN")
C5_REASON=$(echo "$C5_RESP" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("reason",""))' 2>/dev/null || echo "")

echo "$LOG_PREFIX ✓ Contract 5: $C5_DECISION ($C5_REASON)"

if [ "$C5_DECISION" = "BLOCKED" ]; then
    echo "$LOG_PREFIX ⚠️ Contract 5 BLOCKED: $C5_REASON"
    EXIT_CODE=2
elif [ "$C5_DECISION" = "EMPTY" ]; then
    echo "$LOG_PREFIX ℹ️ Contract 5 EMPTY: $C5_REASON"
fi


# ============================================================================
# Step 7: Daily Summary Log (P72 Standard + P104 Sealing)
# ============================================================================
echo ""
echo "$LOG_PREFIX [7/7] Generating Daily Summary (DAILY_SUMMARY)..."

# Fetch Risks (Same Logic)
RISKS_JSON="[]"
OPS_SUMMARY_JSON=$(curl -s "${BASE_URL}/api/ops/summary/latest" 2>/dev/null)
if [ -n "$OPS_SUMMARY_JSON" ]; then
    RISKS_JSON=$(echo "$OPS_SUMMARY_JSON" | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
    row = (d.get("rows") or [d])[0]
    risks = [r.get("code") for r in row.get("top_risks", [])]
    print(json.dumps(risks))
except:
    print("[]")
')
fi

# Construct JSON for Printer
SUMMARY_OUTPUT=$(cat <<EOF | python3 "${REPO_DIR}/app/utils/print_daily_summary.py"
{
  "overall_status": "$OPS_STATUS",
  "strategy_bundle": {
    "stale": $BUNDLE_STALE
  },
  "reco": {
    "decision": "$RECO_DECISION",
    "reason": "$RECO_REASON"
  },
  "order_plan": {
    "decision": "$ORDER_DECISION",
    "reason": "$ORDER_REASON",
    "reason_detail": "$ORDER_DETAIL"
  },
  "contract5": {
    "decision": "$C5_DECISION",
    "reason": "$C5_REASON"
  },
  "top_risks": $RISKS_JSON,
  "push": { "last_send_decision": "SKIPPED_P104" }
}
EOF
)

# Output handling (P77-FIX6: Dedicated Logs)
echo "$LOG_PREFIX $SUMMARY_OUTPUT"

# Logs (Ensure mtime update)
mkdir -p logs
# 'tee' updates file content and mtime
printf "[%s] %s\n" "$(date '+%Y-%m-%d %H:%M:%S')" "$SUMMARY_OUTPUT" | tee logs/daily_summary.latest >> logs/daily_summary.log

# ============================================================================
# Final Summary
# ============================================================================
echo ""
echo "$LOG_PREFIX ═══════════════════════════════════════════════════════════════"
echo "$LOG_PREFIX  DAILY OPS COMPLETE (P104 Sealing)"
echo "$LOG_PREFIX  Ops: $OPS_STATUS | Reco: $RECO_DECISION | Order: $ORDER_DECISION"
echo "$LOG_PREFIX  Contract5: $C5_DECISION"
echo "$LOG_PREFIX ═══════════════════════════════════════════════════════════════"

if [ "$EXIT_CODE" -eq 0 ]; then
    echo "$LOG_PREFIX ✅ All checks passed"
elif [ "$EXIT_CODE" -eq 2 ]; then
    echo "$LOG_PREFIX ⚠️ Ops Completed with Warnings (BLOCKED/EMPTY)"
else
    echo "$LOG_PREFIX ❌ Ops Failed (Exit Code: $EXIT_CODE)"
fi
exit $EXIT_CODE

