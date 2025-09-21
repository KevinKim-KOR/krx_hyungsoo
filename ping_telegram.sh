#!/bin/bash
set -e
cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular
source venv/bin/activate
python - <<'PY'
from scanner import load_config_yaml
from notifications import send_notify
cfg=load_config_yaml("config.yaml")
send_notify("☀️ KRX 스캐너 헬스체크: OK", cfg)
PY
