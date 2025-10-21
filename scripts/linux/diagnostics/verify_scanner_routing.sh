#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."

[ -f "config/env.nas.sh" ] && source config/env.nas.sh
PY="${PYTHONBIN:-python3}"

echo "[CHECK] providers bridge"
$PY - <<'PY'
import pandas as pd
from providers.ohlcv_bridge import get_ohlcv_df
for s in ["^KS11", "005930.KS", "SPY", "AAPL"]:
    df = get_ohlcv_df(s)
    print(s, "rows=", 0 if df is None else len(df.index))
PY
