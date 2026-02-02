#!/bin/bash
# deploy/oci/setup_cron.sh
# Safely adds rotation job to crontab

REPO_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
JOB_CMD="bash deploy/oci/rotate_logs.sh >> logs/rotate.log 2>&1"
FULL_JOB="10 1 * * 0 cd /home/ubuntu/krx_hyungsoo && $JOB_CMD"

if crontab -l 2>/dev/null | grep -F "rotate_logs.sh" > /dev/null; then
    echo "Cron already exists."
else
    (crontab -l 2>/dev/null; echo "$FULL_JOB") | crontab -
    echo "Cron added."
fi
