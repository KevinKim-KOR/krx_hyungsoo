#!/usr/bin/env python3
from __future__ import annotations
import glob, os, sys, json
from pathlib import Path
from datetime import datetime
import pandas as pd

def _cache_latest(glob_pat="data/cache/ohlcv/*.parquet"):
    paths = sorted(glob.glob(glob_pat))
    latest = None
    for p in paths:
        try:
            df = pd.read_parquet(p)
            if df.empty: continue
            mx = pd.to_datetime(df.index).max().tz_localize(None)
            latest = mx if latest is None or mx > latest else latest
        except Exception:
            continue
    return latest

def _load_ticker(p):
    try:
        df = pd.read_parquet(p)
        df.index = pd.to_datetime(df.index).tz_localize(None)
        return df.sort_index()
    except Exception:
        return None

def build_cache_report(out_dir="logs/reports"):
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    latest = _cache_latest()
    if latest is None:
        print(json.dumps({"status":"empty"}))
        return 2

    files = sorted(glob.glob("data/cache/ohlcv/*.parquet"))
    rows = []
    for p in files:
        sym = Path(p).stem
        df = _load_ticker(p)
        if df is None or df.empty: continue
        # 당일(또는 최신일) 종가/전일 대비
        last = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else None
        close = float(last.get("Adj Close", last.get("Close", float("nan"))))
        chg = None
        if prev is not None:
            prev_close = float(prev.get("Adj Close", prev.get("Close", float("nan"))))
            if pd.notna(close) and pd.notna(prev_close) and prev_close != 0:
                chg = (close/prev_close - 1.0) * 100.0
        rows.append({"symbol": sym, "close": close, "chg_pct": chg})

    dfsum = pd.DataFrame(rows).dropna(subset=["close"])
    dfsum = dfsum.sort_values(by="chg_pct", ascending=False)

    ts = latest.strftime("%Y%m%d")
    md = [f"# EOD Report (Cache) — {latest.date()}",
          "",
          "## Top 10 Up",
          ""
          ]
    for _, r in dfsum.head(10).iterrows():
        s = f"- {r['symbol']}: close={r['close']:.4f}" + (f", chg={r['chg_pct']:.2f}%" if pd.notna(r['chg_pct']) else "")
        md.append(s)
    md += ["", "## Top 10 Down", ""]
    for _, r in dfsum.tail(10).iloc[::-1].iterrows():
        s = f"- {r['symbol']}: close={r['close']:.4f}" + (f", chg={r['chg_pct']:.2f}%" if pd.notna(r['chg_pct']) else "")
        md.append(s)

    out_md = Path(out_dir) / f"eod_cache_{ts}.md"
    out_csv = Path(out_dir) / f"eod_cache_{ts}.csv"
    out_md.write_text("\n".join(md), encoding="utf-8")
    dfsum.to_csv(out_csv, index=False)
    print(json.dumps({"status":"ok","latest":str(latest.date()),"md":str(out_md),"csv":str(out_csv)}))
    return 0

if __name__ == "__main__":
    sys.exit(build_cache_report())
