#!/bin/bash
# P76: Ops Dashboard Wrapper
# Usage: bash deploy/oci/ops_dashboard.sh

# Ensure python path includes current dir
export PYTHONPATH=$PYTHONPATH:$(pwd)

# Run the python module
python3 -m app.utils.ops_dashboard "$@"
