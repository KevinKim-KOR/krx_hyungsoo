#!/bin/bash
set -e
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular
git pull --ff-only
source venv/bin/activate
if [ -f requirements-nas.txt ]; then
  pip install -r requirements-nas.txt -q || true
else
  pip install "SQLAlchemy>=2.0,<2.1" pandas==1.5.3 numpy==1.24.4 yfinance==0.2.52 pykrx==1.0.45 tabulate==0.9.0 PyYAML>=6.0 requests>=2.31 tqdm>=4.66 rich>=13 -q || true
fi
echo "Updated ✓"
