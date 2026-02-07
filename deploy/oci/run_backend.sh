#!/bin/bash
# deploy/oci/run_backend.sh

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$BASE_DIR" || exit 1

echo "Stopping existing backend..."
pkill -f "uvicorn backend.main:app" || true

echo "Starting backend..."
nohup python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 > backend.log 2>&1 &

echo "Backend started. Logs in backend.log"
