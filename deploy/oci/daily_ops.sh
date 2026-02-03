#!/bin/bash
# daily_ops.sh - OCI Daily Operations Script (D-P.54 + D-P.57 + P105)
# Usage: bash deploy/oci/daily_ops.sh
# Cron: 5 8 * * * cd /home/ubuntu/krx_hyungsoo && bash deploy/oci/daily_ops.sh >> logs/daily_ops.log 2>&1
#
# P105: Cron Proof, Self-Heal Lite, Log Retention integration
# P104-FIX1: Exit Code Sealing (Gate Driven)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
BASE_URL="${KRX_API_URL:-http://127.0.0.1:8000}"
LOG_PREFIX="[$(date '+%Y-%m-%d %H:%M:%S')]"
SECRETS_FILE="$REPO_DIR/state/secrets/telegram.env"
PROOF_DIR="$REPO_DIR/reports/ops/cron_proof"
EXIT_CODE=0

cd "$REPO_DIR"

# Ensure directories
mkdir -p logs
mkdir -p "$PROOF_DIR"

# ============================================================================
# P105: 1. Start Proof
# ============================================================================
echo "$(date '+%Y-%m-%d %H:%M:%S KST')" > "$PROOF_DIR/last_start.txt"
git rev-parse --short HEAD >> "$PROOF_DIR/last_start.txt" 2>/dev/null || echo "nogit" >> "$PROOF_DIR/last_start.txt"

# ============================================================================
# Helpers
# ============================================================================
send_telegram_fallback() {
    local message="$1"
    if [ -f "$SECRETS_FILE" ]; then source "$SECRETS_FILE"; fi
    if [ -z "${TELEGRAM_BOT_TOKEN:-}" ] || [ -z "${TELEGRAM_CHAT_ID:-}" ]; then return 1; fi
    curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        -d "chat_id=${TELEGRAM_CHAT_ID}" -d "text=${message}" > /dev/null 2>&1 || true
}

send_incident() {
    local kind="$1"
    local step="$2"
    local reason="$3"
    
    local resp=$(curl -s -X POST "${BASE_URL}/api/push/incident/send?confirm=true&kind=${kind}&step=${step}&reason=$(echo "$reason" | head -c 100 | sed 's/ /%20/g')" 2>/dev/null || echo "")
    if echo "$resp" | grep -q '"result":"OK"'; then
        echo "$LOG_PREFIX ✓ Incident push sent via API: $kind"
        return 0
    fi
    echo "$LOG_PREFIX ⚠️ API incident failed, trying fallback..."
    send_telegram_fallback "🚨 INCIDENT: $kind ($step) - $reason"
}

check_fail_heal() {
    # P105: On API failure, check backend health.
    # If Healthy -> Exit 2 (WARN)
    # If Unhealthy -> Exit 1 (FAIL)
    local step="$1"
    local msg="$2"
    
    echo "$LOG_PREFIX ❌ $step failed: $msg"
    
    local health=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}/api/ops/health" 2>/dev/null || echo "000")
    if [ "$health" = "200" ]; then
        echo "$LOG_PREFIX ✓ Backend Healthy (200). Terminating with exit 2 (WARN)."
        send_incident "OPS_FAILED" "$step" "$msg (Backend Healthy)"
        # P105: Write exit stamp
        echo "2" > "$PROOF_DIR/last_exit_code.txt"
        date '+%Y-%m-%d %H:%M:%S KST' > "$PROOF_DIR/last_done.txt"
        exit 2
    else
        echo "$LOG_PREFIX ❌ Backend Unhealthy ($health). Terminating with exit 1 (FAIL)."
        send_telegram_fallback "🚨 INCIDENT: BACKEND_DOWN (Status $health) at $step. $msg"
        echo "1" > "$PROOF_DIR/last_exit_code.txt"
        date '+%Y-%m-%d %H:%M:%S KST' > "$PROOF_DIR/last_done.txt"
        exit 1
    fi
}

echo "$LOG_PREFIX ═══════════════════════════════════════════════════════════════"
echo "$LOG_PREFIX  OCI Daily Operations (P105 Stabilized)"
echo "$LOG_PREFIX ═══════════════════════════════════════════════════════════════"

# ============================================================================
# Step 1: Preflight & Repo Update
# ============================================================================
echo ""
echo "$LOG_PREFIX [1/8] Updating repository..."
if [ "${DAILY_OPS_NO_GIT_PULL:-}" != "1" ]; then
    if ! git pull origin main > /dev/null 2>&1; then
        check_fail_heal "Step1" "git pull failed"
    fi
    echo "$LOG_PREFIX ✓ Repository updated ($(git rev-parse --short HEAD))"
else
    echo "$LOG_PREFIX [1/8] Repository update SKIPPED"
fi

# ============================================================================
# P105: 2. Self-Heal Lite (Bundle Recover)
# ============================================================================
echo ""
echo "$LOG_PREFIX [2/8] Self-Heal Lite (Bundle Check)..."
if [ -f "deploy/oci/bundle_recover_check.sh" ]; then
    bash deploy/oci/bundle_recover_check.sh || echo "$LOG_PREFIX ⚠️ Bundle Check Warning (Non-fatal)"
else
    echo "$LOG_PREFIX ℹ️ bundle_recover_check.sh not found (Skipping)"
fi

# ============================================================================
# Step 3: Ops Summary Regenerate
# ============================================================================
echo ""
echo "$LOG_PREFIX [3/8] Regenerating Ops Summary..."
REGEN_RESP=$(curl -s -X POST "${BASE_URL}/api/ops/summary/regenerate?confirm=true")
if ! echo "$REGEN_RESP" | grep -q '"schema":"OPS_SUMMARY_V1"'; then
    check_fail_heal "Step3" "Ops Summary Regen failed"
fi
echo "$LOG_PREFIX ✓ Ops Summary regenerated"

# Status Check
OPS_STATUS=$(curl -s "${BASE_URL}/api/ops/summary/latest" | python3 -c 'import json,sys; d=json.load(sys.stdin); row=(d.get("rows") or [d])[0]; print(row.get("overall_status","UNKNOWN"))' 2>/dev/null || echo "UNKNOWN")
echo "$LOG_PREFIX ✓ Ops Summary status: $OPS_STATUS"
if [ "$OPS_STATUS" = "BLOCKED" ] || [ "$OPS_STATUS" = "STOPPED" ]; then
    echo "$LOG_PREFIX ⚠️ Ops Summary $OPS_STATUS"
    EXIT_CODE=2
fi
BUNDLE_STALE=$(curl -s "${BASE_URL}/api/strategy_bundle/latest" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(str(d.get("summary", d).get("stale", "false")).lower())' 2>/dev/null || echo "false")

# ============================================================================
# Step 4: Reco Regenerate
# ============================================================================
echo ""
echo "$LOG_PREFIX [4/8] Regenerating Reco (RECO)..."
RECO_RESP=$(curl -s -X POST "${BASE_URL}/api/reco/regenerate?confirm=true")
if ! echo "$RECO_RESP" | grep -q '"decision"'; then
    check_fail_heal "Step4" "Reco API failed"
fi

RECO_DECISION=$(echo "$RECO_RESP" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("decision","UNKNOWN"))' 2>/dev/null || echo "UNKNOWN")
RECO_REASON=$(echo "$RECO_RESP" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("reason",""))' 2>/dev/null || echo "")
echo "$LOG_PREFIX ✓ Reco: $RECO_DECISION ($RECO_REASON)"

if [ "$RECO_DECISION" = "BLOCKED" ] || [ "$RECO_DECISION" = "MISSING_RECO" ]; then
    echo "$LOG_PREFIX ⚠️ Reco BLOCKED/MISSING"
    EXIT_CODE=2
fi

# ============================================================================
# Step 5: Order Plan Regenerate
# ============================================================================
echo ""
echo "$LOG_PREFIX [5/8] Regenerating Order Plan..."
ORDER_RESP=$(curl -s -X POST "${BASE_URL}/api/order_plan/regenerate?confirm=true")
if ! echo "$ORDER_RESP" | grep -q '"decision"'; then
    check_fail_heal "Step5" "Order Plan API failed"
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
# Step 6: Contract 5 Regenerate
# ============================================================================
echo ""
echo "$LOG_PREFIX [6/8] Regenerating Contract 5..."
C5_RESP=$(curl -s -X POST "${BASE_URL}/api/contract5/regenerate?confirm=true")
if ! echo "$C5_RESP" | grep -q '"decision"'; then
    check_fail_heal "Step6" "Contract 5 API failed"
fi

C5_DECISION=$(echo "$C5_RESP" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("decision","UNKNOWN"))' 2>/dev/null || echo "UNKNOWN")
C5_REASON=$(echo "$C5_RESP" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("reason",""))' 2>/dev/null || echo "")
echo "$LOG_PREFIX ✓ Contract 5: $C5_DECISION ($C5_REASON)"

if [ "$C5_DECISION" = "BLOCKED" ]; then
    echo "$LOG_PREFIX ⚠️ Contract 5 BLOCKED: $C5_REASON"
    EXIT_CODE=2
fi

# ============================================================================
# Step 7: Daily Summary Log
# ============================================================================
# P106-FIX2: Daily Ops Summary SSOT Lock (Envelope-safe)
# Force regenerate to ensure Ups Summary reflects the latest Reco/Order Plan/C5 status from previous steps
echo "$LOG_PREFIX [7/8] Generating Daily Summary (Final SSOT Regen)..."
OPS_REGEN_RESP=$(curl -s -X POST "${BASE_URL}/api/ops/summary/regenerate?confirm=true")

# Pipe directly to print_daily_summary.py (SSOT Lock)
# This prevents discrepancies between variables/legacy paths and the actual Ops Summary
if [ -n "$OPS_REGEN_RESP" ]; then
    SUMMARY_OUTPUT=$(echo "$OPS_REGEN_RESP" | python3 "${REPO_DIR}/app/utils/print_daily_summary.py")
else
    SUMMARY_OUTPUT="DAILY_SUMMARY Reason=API_PUSH_FAILED detail=Ops_Summary_Regen_Empty"
fi
echo "$LOG_PREFIX $SUMMARY_OUTPUT"
mkdir -p logs
printf "[%s] %s\n" "$(date '+%Y-%m-%d %H:%M:%S')" "$SUMMARY_OUTPUT" | tee logs/daily_summary.latest >> logs/daily_summary.log

# ============================================================================
# Step 8: Gate Check & Finalize
# ============================================================================
echo ""
echo "$LOG_PREFIX [8/8] Final Gate Check..."
GATE_OUT_FILE=$(mktemp)
bash deploy/oci/steady_gate_check.sh | tee "$GATE_OUT_FILE"

FINAL_EXIT_CODE=1
if grep -q "OCI STEADY-STATE: PASS" "$GATE_OUT_FILE"; then
    FINAL_EXIT_CODE=0
    echo "$LOG_PREFIX ✅ Gate PASS -> Exit 0"
elif grep -q "OCI STEADY-STATE: WARN" "$GATE_OUT_FILE"; then
    FINAL_EXIT_CODE=2
    echo "$LOG_PREFIX ⚠️ Gate WARN -> Exit 2"
else
    FINAL_EXIT_CODE=1
    echo "$LOG_PREFIX ❌ Gate FAIL/UNKNOWN -> Exit 1"
fi
rm -f "$GATE_OUT_FILE"

# P105: End Proof
echo "$FINAL_EXIT_CODE" > "$PROOF_DIR/last_exit_code.txt"
date '+%Y-%m-%d %H:%M:%S KST' > "$PROOF_DIR/last_done.txt"

exit $FINAL_EXIT_CODE
