#!/bin/bash
cd /home/ubuntu/krx_hyungsoo || exit 1

echo "--- 1. Regenerate Export (Force Plan ID) ---"
curl -s -X POST 'http://localhost:8000/api/order_plan_export/regenerate?confirm=true' > /dev/null

echo "--- 2. Run Prep (Token: TEST_TOKEN_VIA_SCRIPT) ---"
# Pipe token to stdin for read -s
printf "TEST_TOKEN_VIA_SCRIPT\n" | bash deploy/oci/manual_loop_prepare.sh

echo "--- 3. Run Verify Script ---"
python3 verify_p140.py
