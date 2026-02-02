#!/bin/bash
# deploy/oci/rotate_logs.sh
# Retention Policy Enforcer (P105)
# - Logs: Keep last 50,000 lines
# - Snapshots: Keep last 200 files per directory

set -e

REPO_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_DIR" || exit 1

LOG_DIR="logs"
SNAPSHOT_DIRS=(
  "reports/live/reco/snapshots"
  "reports/live/order_plan/snapshots"
  "reports/ops/contract5/snapshots"
  "reports/ops/summary/snapshots"
)

MAX_LINES=50000
KEEP_SNAPSHOTS=200

echo "[Rotate] Starting log rotation & pruning..."

# 1. Rotate Logs
if [ -d "$LOG_DIR" ]; then
    for log in "$LOG_DIR"/*.log; do
        if [ -f "$log" ]; then
            LINES=$(wc -l < "$log")
            if [ "$LINES" -gt "$MAX_LINES" ]; then
                echo "   Pruning log: $log ($LINES lines -> $MAX_LINES)"
                tail -n "$MAX_LINES" "$log" > "$log.tmp" && mv "$log.tmp" "$log"
            fi
        fi
    done
fi

# 2. Prune Snapshots
for dir in "${SNAPSHOT_DIRS[@]}"; do
    if [ -d "$dir" ]; then
        COUNT=$(ls -1 "$dir" | wc -l)
        if [ "$COUNT" -gt "$KEEP_SNAPSHOTS" ]; then
            PRUNE_COUNT=$((COUNT - KEEP_SNAPSHOTS))
            echo "   Pruning $dir: Removing $PRUNE_COUNT old snapshots..."
            # List by time (oldest first), take top N
            ls -1tr "$dir" | head -n "$PRUNE_COUNT" | while read f; do
                rm "$dir/$f"
            done
        fi
    fi
done

echo "[Rotate] Done."
