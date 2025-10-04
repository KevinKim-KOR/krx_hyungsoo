#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."

# PC에서는 ALLOW_NET_FETCH=1
export ALLOW_NET_FETCH=1

# 범위를 적절히 조절하세요
START="2000-01-03"
END="$(date +%F)"

python - <<'PY'
from pathlib import Path
from scripts.bt.data_loader import _load_yf_index_close_ret
import pandas as pd

pairs = [
  ("KOSPI","^KS11"), ("KOSDAQ","^KQ11"), ("S&P500","^GSPC"),
  ("KOSPI_ETF","069500.KS"), ("KOSDAQ_ETF","229200.KS"), ("SPY","SPY")
]
outdir = Path("data/benchmarks"); outdir.mkdir(parents=True, exist_ok=True)
for name,tkr in pairs:
    df = _load_yf_index_close_ret(tkr, START, END)
    df.to_parquet(outdir / f"{name}.parquet")
    print("[PRECACHE]", name, "rows:", len(df))
PY
