set -e
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular
source venv/bin/activate
python app.py scanner-slack --date $(date +%F) >> logs/scanner_$(date +%F).log 2>&1
