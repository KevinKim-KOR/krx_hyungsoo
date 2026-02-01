#!/bin/bash
# =============================================================================
# steady_gate_check.sh - P97 OCI Steady-State 1-Command Gate
# =============================================================================
# Usage: bash deploy/oci/steady_gate_check.sh
# =============================================================================

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_DIR" || exit 1
source .venv/bin/activate 2>/dev/null || true

echo ""
echo "╔════════════════════════════════════════════════════════════════════╗"
echo "║             KRX ALERTOR OCI STEADY-STATE GATE CHECK               ║"
echo "╚════════════════════════════════════════════════════════════════════╝"
echo ""
DATE_NOW=$(date '+%Y-%m-%d %H:%M:%S %Z')
echo "🕐 Checked at: $DATE_NOW"
echo ""

# =============================================================================
# 1. Ops Dashboard Summary
# =============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 OPS DASHBOARD OUTPUT"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
python3 -m app.utils.ops_dashboard 2>&1 || true
echo ""

# =============================================================================
# 2. Clean Check (MISSING/UNKNOWN/UNMAPPED)
# =============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔍 CLEAN CHECK (MISSING/UNKNOWN/UNMAPPED)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
CLEAN_CHECK=$(python3 -m app.utils.ops_dashboard 2>&1 | grep -E "MISSING|UNKNOWN|UNMAPPED" || echo "")
if [ -z "$CLEAN_CHECK" ]; then
    echo "✅ CLEAN CHECK: PASS (No MISSING/UNKNOWN/UNMAPPED)"
    CLEAN_PASS=1
else
    echo "❌ CLEAN CHECK: FAIL"
    echo "$CLEAN_CHECK"
    CLEAN_PASS=0
fi
echo ""

# =============================================================================
# 3. Watcher Freshness (age check)
# =============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "⏱️  WATCHER FRESHNESS CHECK"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

check_watcher_age() {
    local name="$1"
    local file="$2"
    
    if [ ! -f "$file" ]; then
        echo "   $name: ❌ FILE NOT FOUND"
        return 1
    fi
    
    # Get asof from JSON
    ASOF=$(grep -o '"asof": *"[^"]*"' "$file" | cut -d'"' -f4 2>/dev/null || echo "")
    if [ -z "$ASOF" ]; then
        echo "   $name: ⚠️  NO ASOF FIELD"
        return 1
    fi
    
    # Get file mtime as fallback
    MTIME=$(stat -c %Y "$file" 2>/dev/null || stat -f %m "$file" 2>/dev/null || echo "0")
    NOW=$(date +%s)
    AGE_SEC=$((NOW - MTIME))
    
    if [ "$AGE_SEC" -lt 60 ]; then
        AGE_STR="${AGE_SEC}s"
    elif [ "$AGE_SEC" -lt 3600 ]; then
        AGE_STR="$((AGE_SEC / 60))m"
    elif [ "$AGE_SEC" -lt 86400 ]; then
        AGE_STR="$((AGE_SEC / 3600))h"
    else
        AGE_STR="$((AGE_SEC / 86400))d"
    fi
    
    # Check for stale (> 2 hours = 7200 sec)
    if [ "$AGE_SEC" -gt 7200 ]; then
        echo "   $name: ⚠️  STALE (mtime age=$AGE_STR, asof=$ASOF)"
        return 1
    else
        echo "   $name: ✅ FRESH (mtime age=$AGE_STR, asof=$ASOF)"
        return 0
    fi
}

SPIKE_PATH="reports/ops/push/spike_watch/latest/spike_watch_latest.json"
HOLDING_PATH="reports/ops/push/holding_watch/latest/holding_watch_latest.json"

WATCHER_OK=1
check_watcher_age "Spike Watch  " "$SPIKE_PATH" || WATCHER_OK=0
check_watcher_age "Holding Watch" "$HOLDING_PATH" || WATCHER_OK=0

if [ "$WATCHER_OK" -eq 1 ]; then
    echo "   → All watchers FRESH"
else
    echo "   → Some watchers STALE or MISSING"
fi
echo ""

# =============================================================================
# 4. Daily Summary Freshness
# =============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📅 DAILY SUMMARY FRESHNESS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
DAILY_PATH="logs/daily_summary.latest"
if [ -f "$DAILY_PATH" ]; then
    DAILY_MTIME=$(stat -c %Y "$DAILY_PATH" 2>/dev/null || stat -f %m "$DAILY_PATH" 2>/dev/null || echo "0")
    NOW=$(date +%s)
    DAILY_AGE_SEC=$((NOW - DAILY_MTIME))
    DAILY_AGE_HR=$((DAILY_AGE_SEC / 3600))
    
    if [ "$DAILY_AGE_HR" -lt 24 ]; then
        echo "   Daily Summary: ✅ FRESH (age=${DAILY_AGE_HR}h)"
    else
        echo "   Daily Summary: ⚠️  STALE (age=${DAILY_AGE_HR}h, >24h)"
    fi
    
    # Show last line
    LAST_LINE=$(tail -n1 "$DAILY_PATH" 2>/dev/null || echo "")
    echo "   Last Entry: $LAST_LINE"
else
    echo "   Daily Summary: ❌ FILE NOT FOUND"
fi
echo ""

# =============================================================================
# 5. Backend Health
# =============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔧 BACKEND HEALTH"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
HEALTH=$(curl -s --connect-timeout 2 http://localhost:8000/api/ops/health 2>/dev/null || echo "")
if [ -n "$HEALTH" ] && echo "$HEALTH" | grep -q "ok\|OK\|healthy"; then
    echo "   Backend: ✅ HEALTHY"
else
    echo "   Backend: ❌ NOT REACHABLE or UNHEALTHY"
fi
echo ""

# =============================================================================
# 6. Final Verdict
# =============================================================================
echo "╔════════════════════════════════════════════════════════════════════╗"
if [ "$CLEAN_PASS" -eq 1 ] && [ "$WATCHER_OK" -eq 1 ]; then
    echo "║  🟢 OCI STEADY-STATE: PASS                                        ║"
else
    echo "║  🟡 OCI STEADY-STATE: WARN (Check items above)                    ║"
fi
echo "╚════════════════════════════════════════════════════════════════════╝"
echo ""
