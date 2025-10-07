#!/usr/bin/env python3
from pathlib import Path
from datetime import date, timedelta
import sys
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATADIR = ROOT / "data" / "cache" / "kr"
DATADIR.mkdir(parents=True, exist_ok=True)
OUTP = DATADIR / "trading_days.pkl"

def _pick_symbols():
    # 최소 의존: 우선순위(캐시키/ETF)
    return ["069500.KS", "069500"]

def _fetch_ohlcv(symbol: str, start: str, end: str) -> pd.DataFrame:
    """
    가능한 최소 의존으로 가져오기:
    - fetchers.get_ohlcv_safe가 있으면 우선 사용(내부에서 pykrx/yf 폴백)
    - 없으면 yfinance 단독 시도 (없으면 빈 DF)
    """
    try:
        import fetchers
        return fetchers.get_ohlcv_safe(symbol, start, end)
    except Exception:
        pass
    try:
        import yfinance as yf
        df = yf.download(symbol, start=start, end=end, progress=False, auto_adjust=False, group_by="column", threads=False)
        if df is None or len(df)==0:
            return pd.DataFrame()
        if "Close" in df.columns:
            df = df[["Close"]]
        elif "Adj Close" in df.columns:
            df = df[["Adj Close"]].rename(columns={"Adj Close":"Close"})
        return df
    except Exception:
        return pd.DataFrame()

def build_calendar(start: str, end: str) -> pd.DatetimeIndex:
    for sym in _pick_symbols():
        df = _fetch_ohlcv(sym, start, end)
        if df is not None and len(df) > 0:
            idx = pd.to_datetime(df.index).tz_localize(None)
            idx = pd.DatetimeIndex(sorted(pd.unique(idx)))
            if len(idx) > 0:
                return idx
    return pd.DatetimeIndex([])

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default=(date.today().replace(month=1, day=1) - timedelta(days=365)).isoformat())
    ap.add_argument("--end",   default=date.today().isoformat())
    args = ap.parse_args()

    idx = build_calendar(args.start, args.end)
    if len(idx) == 0:
        print("[CAL] no data -> exit 2 (retry)")
        return 2

    # 기존과 호환되게 저장(Series/Index 상관 없이 읽기 가능)
    pd.to_pickle(idx, OUTP)
    print(f"[CAL] wrote {OUTP} (n={len(idx)}, {idx.min().date()}~{idx.max().date()})")
    return 0

if __name__ == "__main__":
    sys.exit(main())
