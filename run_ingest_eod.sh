#!/bin/bash
set -e
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular
source venv/bin/activate
python app.py ingest-eod --date auto >> logs/ingest_$(date +%F).log 2>&1
