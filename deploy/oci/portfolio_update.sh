#!/bin/bash
# deploy/oci/portfolio_update.sh
# P110: Portfolio Update (Positions Injection)
# Usage: bash deploy/oci/portfolio_update.sh

set -e

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PORTFOLIO_DIR="$BASE_DIR/state/portfolio/latest"
SNAPSHOT_DIR="$BASE_DIR/state/portfolio/snapshots"

mkdir -p "$PORTFOLIO_DIR"
mkdir -p "$SNAPSHOT_DIR"

TARGET_FILE="$PORTFOLIO_DIR/portfolio_latest.json"

# SAMPLE UPDATE VALUES
# Cash: 5M
# Holdings: KODEX 200 (100 shares @ 35000) = 3.5M
# Total Value: 8.5M

CASH=5000000
QTY=100
PRICE=35000
HOLDING_VAL=$((QTY * PRICE))
TOTAL_VALUE=$((CASH + HOLDING_VAL))

# Current Timestamp ISO8601
NOW=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Create JSON content (Atomic Write)
cat <<EOF > "${TARGET_FILE}.tmp"
{
  "schema": "PORTFOLIO_SNAPSHOT_V1",
  "asof": "${NOW}",
  "portfolio_id": "update-$(date +%s)",
  "cash": ${CASH},
  "holdings": [
      {
          "ticker": "069500",
          "name": "KODEX 200",
          "quantity": ${QTY},
          "avg_price": ${PRICE},
          "current_price": ${PRICE},
          "value": ${HOLDING_VAL},
          "market_value": ${HOLDING_VAL}
      }
  ],
  "total_value": ${TOTAL_VALUE},
  "cash_ratio_pct": $((CASH * 100 / TOTAL_VALUE)).0,
  "updated_at": "${NOW}",
  "updated_by": "manual_update_script",
  "snapshot_ref": "state/portfolio/snapshots/update_${NOW}.json",
  "evidence_refs": [],
  "integrity": {
    "payload_sha256": "update-integrity-signature"
  }
}
EOF

# Move to final location
mv "${TARGET_FILE}.tmp" "$TARGET_FILE"

# Copy to snapshot
cp "$TARGET_FILE" "$SNAPSHOT_DIR/portfolio_update_$(date +%Y%m%d_%H%M%S).json"

echo "✅ Portfolio Updated: $TARGET_FILE"
cat "$TARGET_FILE" | python3 -m json.tool
