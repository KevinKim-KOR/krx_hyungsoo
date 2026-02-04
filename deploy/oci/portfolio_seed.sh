#!/bin/bash
# deploy/oci/portfolio_seed.sh
# P109: Portfolio SSOT Seeding (Manual Injection)
# Usage: bash deploy/oci/portfolio_seed.sh

set -e

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PORTFOLIO_DIR="$BASE_DIR/state/portfolio/latest"
SNAPSHOT_DIR="$BASE_DIR/state/portfolio/snapshots"

mkdir -p "$PORTFOLIO_DIR"
mkdir -p "$SNAPSHOT_DIR"

TARGET_FILE="$PORTFOLIO_DIR/portfolio_latest.json"

# DEFAULT VALUES (Can be overridden by env vars)
# 10M KRW Cash, No Holdings
CASH=${PORTFOLIO_CASH:-10000000}
TOTAL_VALUE=$CASH

# Current Timestamp ISO8601
NOW=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Create JSON content (Atomic Write)
cat <<EOF > "${TARGET_FILE}.tmp"
{
  "schema": "PORTFOLIO_SNAPSHOT_V1",
  "asof": "${NOW}",
  "portfolio_id": "seed-$(date +%s)",
  "cash": ${CASH},
  "holdings": [],
  "total_value": ${TOTAL_VALUE},
  "cash_ratio_pct": 100.0,
  "updated_at": "${NOW}",
  "updated_by": "manual_seed_script",
  "snapshot_ref": "state/portfolio/snapshots/seed_${NOW}.json",
  "evidence_refs": [],
  "integrity": {
    "payload_sha256": "seed-integrity-signature"
  }
}
EOF

# Move to final location
mv "${TARGET_FILE}.tmp" "$TARGET_FILE"

# Copy to snapshot
cp "$TARGET_FILE" "$SNAPSHOT_DIR/portfolio_seed_$(date +%Y%m%d_%H%M%S).json"

echo "✅ Portfolio Seeded: $TARGET_FILE"
cat "$TARGET_FILE" | python3 -m json.tool
