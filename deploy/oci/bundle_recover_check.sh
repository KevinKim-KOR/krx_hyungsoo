#!/bin/bash
# ============================================================================
# Bundle Recovery Check (P84)
# 
# Purpose: 운영자 1-Command로 bundle stale 상태 확인 + 복구 유도
# 
# 실행: bash deploy/oci/bundle_recover_check.sh
# ============================================================================

set -euo pipefail

# Load environment
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/../.."

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo ""
echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}  Bundle Recovery Check (P84) - $(date '+%Y-%m-%d %H:%M:%S KST')${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
echo ""

# Step A: Git Pull
echo -e "${YELLOW}[A] Git Pull (최신 번들 확인)${NC}"
GIT_OUTPUT=$(git pull origin main 2>&1)
if echo "$GIT_OUTPUT" | grep -q "Already up to date"; then
    echo -e "   ${GREEN}✓${NC} Already up to date (변경 없음)"
else
    echo -e "   ${GREEN}✓${NC} Updated: $GIT_OUTPUT"
fi
echo ""

# Step B: Ops Summary Regenerate (P84-FIX: HTTP code/body logging + fallback)
echo -e "${YELLOW}[B] Ops Summary Regenerate${NC}"
BASE_URL="${KRX_API_URL:-http://localhost:8000}"

# Use temp file for body, capture HTTP code separately
REGEN_TMP="/tmp/ops_regen_$$.json"
HTTP_CODE=$(curl -sS -o "$REGEN_TMP" -w "%{http_code}" -X POST "${BASE_URL}/api/ops/summary/regenerate?confirm=true" 2>/dev/null || echo "000")
REGEN_BODY=$(cat "$REGEN_TMP" 2>/dev/null | head -c 500 || echo "")
rm -f "$REGEN_TMP"

REGEN_STATUS=$(echo "$REGEN_BODY" | python3 -c 'import json,sys; d=json.load(sys.stdin); print("OK" if d.get("result")=="OK" or d.get("schema") else "ERROR")' 2>/dev/null || echo "PARSE_ERROR")

if [ "$HTTP_CODE" = "200" ] && [ "$REGEN_STATUS" = "OK" ]; then
    echo -e "   ${GREEN}✓${NC} Ops Summary regenerated (HTTP $HTTP_CODE)"
else
    echo -e "   ${RED}✗${NC} Ops Summary regenerate failed"
    echo -e "   ${YELLOW}→${NC} HTTP_CODE=$HTTP_CODE"
    echo -e "   ${YELLOW}→${NC} BODY=${REGEN_BODY:0:300}"
    
    # Fallback: Show current ops_summary/latest status
    echo ""
    echo -e "   ${CYAN}[Fallback] Current Ops Summary Latest:${NC}"
    FALLBACK=$(curl -s "${BASE_URL}/api/ops/summary/latest" 2>/dev/null || echo '{"error":"unreachable"}')
    FALLBACK_STATUS=$(echo "$FALLBACK" | python3 -c 'import json,sys; d=json.load(sys.stdin); r=(d.get("rows") or [d])[0]; print(f"status={r.get(\"overall_status\",\"?\")}, asof={r.get(\"asof\",\"?\")[:19] if r.get(\"asof\") else \"?\"}") ' 2>/dev/null || echo "parse_error")
    echo -e "   ${CYAN}→${NC} $FALLBACK_STATUS"
fi
echo ""

# Step C: Bundle Status
echo -e "${YELLOW}[C] Strategy Bundle 상태${NC}"
BUNDLE_DATA=$(curl -s "${BASE_URL}/api/strategy_bundle/latest" 2>/dev/null || echo '{}')
BUNDLE_STALE=$(echo "$BUNDLE_DATA" | python3 -c 'import json,sys; d=json.load(sys.stdin); s=d.get("summary",d); print(str(s.get("stale","unknown")).lower())' 2>/dev/null || echo "unknown")
BUNDLE_AGE=$(echo "$BUNDLE_DATA" | python3 -c 'import json,sys; d=json.load(sys.stdin); s=d.get("summary",d); print(s.get("stale_reason","N/A"))' 2>/dev/null || echo "N/A")

if [ "$BUNDLE_STALE" = "true" ]; then
    echo -e "   ${RED}●${NC} bundle_stale = ${RED}true${NC}"
    echo -e "   ${YELLOW}→${NC} Age: $BUNDLE_AGE"
    echo ""
    echo -e "${RED}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║  ⚠️  ACTION REQUIRED: PC에서 번들 갱신 필요                    ║${NC}"
    echo -e "${RED}╠══════════════════════════════════════════════════════════════╣${NC}"
    echo -e "${RED}║  PC에서:                                                       ║${NC}"
    echo -e "${RED}║  1. 전략 번들 생성/갱신                                        ║${NC}"
    echo -e "${RED}║  2. git add . && git commit -m 'update bundle' && git push   ║${NC}"
    echo -e "${RED}║                                                               ║${NC}"
    echo -e "${RED}║  OCI에서 다시 실행:                                           ║${NC}"
    echo -e "${RED}║  bash deploy/oci/bundle_recover_check.sh                      ║${NC}"
    echo -e "${RED}╚══════════════════════════════════════════════════════════════╝${NC}"
elif [ "$BUNDLE_STALE" = "false" ]; then
    echo -e "   ${GREEN}●${NC} bundle_stale = ${GREEN}false${NC} (✓ Fresh)"
else
    echo -e "   ${YELLOW}?${NC} bundle_stale = $BUNDLE_STALE"
fi
echo ""

# Step D: Daily Summary Latest
echo -e "${YELLOW}[D] Daily Summary 최신 상태${NC}"
if [ -f "logs/daily_summary.latest" ]; then
    cat logs/daily_summary.latest | head -1
else
    echo "   (logs/daily_summary.latest 없음)"
fi
echo ""

# Summary
echo -e "${CYAN}───────────────────────────────────────────────────────────────${NC}"
if [ "$BUNDLE_STALE" = "false" ]; then
    echo -e "${GREEN}✅ Bundle is FRESH - 정상 상태${NC}"
else
    echo -e "${YELLOW}⚠️  Bundle is STALE - PC에서 갱신 후 다시 확인${NC}"
fi
echo ""
