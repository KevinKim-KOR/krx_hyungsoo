#!/bin/bash
# deploy/oci/restart_backend.sh
# Safe restart: kills any stale process on port 8000, then restarts via systemd.
set -e

echo "=== Killing any process on port 8000 ==="
fuser -k 8000/tcp 2>/dev/null || true
sleep 1

echo "=== Restarting via systemd ==="
sudo systemctl restart krx-backend.service
sleep 2

echo "=== Status ==="
sudo systemctl --no-pager -l status krx-backend.service
