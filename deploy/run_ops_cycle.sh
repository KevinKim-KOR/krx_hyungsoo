#!/bin/bash
# deploy/run_ops_cycle.sh
# Ops Cycle 실행 스크립트 (Linux/Mac)
# Phase C-P.46: Preflight Hardening + 1-Line Summary + Exit Code Policy

set -e

API_BASE="${API_BASE:-http://127.0.0.1:8000}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "[OPS_CYCLE] Starting Ops Cycle Run..."
echo "[OPS_CYCLE] API Base: $API_BASE"
echo "[OPS_CYCLE] Project Root: $PROJECT_ROOT"

# ==============================================================================
# PREFLIGHT CHECKS (Phase C-P.46)
# ==============================================================================

# Preflight 1: .venv/bin/python 존재 확인
if [ ! -f "$PROJECT_ROOT/.venv/bin/python" ]; then
    echo "[OPS_CYCLE][PREFLIGHT] ERROR: .venv/bin/python not found"
    echo "[OPS_CYCLE] Refer: docs/ops/runbook_deploy_v1.md (Section 3: Bootstrap)"
    echo "[OPS_CYCLE] Run: ./deploy/bootstrap_linux.sh"
    exit 3
fi

# Preflight 2: Backend health check
HEALTH_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$API_BASE/api/ops/health" 2>/dev/null || echo "000")
if [ "$HEALTH_STATUS" != "200" ]; then
    echo "[OPS_CYCLE][PREFLIGHT] ERROR: Backend not running (health=$HEALTH_STATUS)"
    echo "[OPS_CYCLE] Check: tail -n 80 logs/backend.log"
    echo "[OPS_CYCLE] Start: cd $PROJECT_ROOT && uvicorn backend.main:app --host 0.0.0.0 --port 8000"
    exit 3
fi

echo "[OPS_CYCLE][PREFLIGHT] PASS: .venv OK, Backend health OK"

# ==============================================================================
# OPS CYCLE API CALL
# ==============================================================================

set +e  # Allow curl failure
response=$(curl -s -X POST "$API_BASE/api/ops/cycle/run" -H "Content-Type: application/json")
curl_exit=$?
set -e

if [ $curl_exit -ne 0 ]; then
    echo "[OPS_CYCLE] ERROR: Failed to call API (curl exit=$curl_exit)"
    exit 3
fi

# Check if response is empty
if [ -z "$response" ]; then
    echo "[OPS_CYCLE] ERROR: Empty response from API"
    exit 3
fi

# ==============================================================================
# PARSE JSON RESPONSE (Phase C-P.46: 1-Line Summary)
# ==============================================================================

# Parse all fields using Python (more portable than jq)
parse_result=$(echo "$response" | python3 -c "
import sys, json
try:
    obj = json.load(sys.stdin)
    data = obj.get('data') or obj or {}
    
    overall_status = data.get('overall_status') or obj.get('overall_status') or 'UNKNOWN'
    reason = data.get('reason') or 'N/A'
    
    counters = data.get('counters') or {}
    tickets_failed = counters.get('tickets_failed', 0)
    tickets_done = counters.get('tickets_done', 0)
    tickets_blocked = counters.get('tickets_blocked', 0)
    
    evidence_health = data.get('evidence_health') or {}
    evidence_decision = evidence_health.get('decision', 'N/A')
    
    # Output: overall_status|reason|tickets_failed|tickets_done|tickets_blocked|evidence_decision
    print(f'{overall_status}|{reason}|{tickets_failed}|{tickets_done}|{tickets_blocked}|{evidence_decision}')
except Exception as e:
    print(f'PARSE_ERROR|{str(e)}|0|0|0|N/A')
" 2>/dev/null)

# Split parsed result
IFS='|' read -r overall_status reason tickets_failed tickets_done tickets_blocked evidence_decision <<< "$parse_result"

# Handle parse error
if [ "$overall_status" = "PARSE_ERROR" ]; then
    echo "[OPS_CYCLE] ERROR: JSON parse failed - $reason"
    echo "[OPS_CYCLE] Raw response (first 500 chars):"
    echo "$response" | head -c 500
    exit 3
fi

# ==============================================================================
# OUTPUT: 1-Line Summary (Phase C-P.46)
# ==============================================================================

echo ""
echo "[OPS_CYCLE] $overall_status overall=$overall_status reason=$reason evidence=$evidence_decision tickets(f/d/b)=$tickets_failed/$tickets_done/$tickets_blocked"

# ==============================================================================
# EXIT CODE POLICY (Phase C-P.46)
# ==============================================================================
# DONE -> exit 0
# DONE_WITH_SKIPS -> exit 0 (skips already shown in summary)
# WARN -> exit 0 (warning but success)
# BLOCKED -> exit 2
# STOPPED/SKIPPED -> exit 0 (intentional stop)
# UNKNOWN/other -> exit 3 (error)

case "$overall_status" in
    DONE|DONE_WITH_SKIPS|WARN|STOPPED|SKIPPED)
        exit 0
        ;;
    BLOCKED)
        exit 2
        ;;
    *)
        echo "[OPS_CYCLE] ERROR: Unexpected status: $overall_status"
        exit 3
        ;;
esac
