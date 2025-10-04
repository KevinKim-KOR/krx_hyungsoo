from __future__ import annotations
from pathlib import Path
from datetime import datetime
import pandas as pd

def _bdate_range(start: str, end: str) -> pd.DatetimeIndex:
    return pd.bdate_range(start=pd.to_datetime(start), end=pd.to_datetime(end), freq="B")

def _to_yyyymmdd(s: str) -> str:
    return pd.to_datetime(s).strftime("%Y%m%d")

def load_kospi(start: str, end: str) -> pd.DataFrame:
    """KOSPI index close/ret via pykrx (index code '1001')."""
    from pykrx import stock
    s, e = _to_yyyymmdd(start), _to_yyyymmdd(end)
    df = stock.get_index_ohlcv_by_date(s, e, "1001")[["종가"]].rename(columns={"종가": "close"})
    df.index = pd.to_datetime(df.index)
    idx = _bdate_range(start, end)
    df = df.reindex(idx).ffill()
    df["ret"] = df["close"].pct_change().fillna(0.0)
    return df

def load_kosdaq(start: str, end: str) -> pd.DataFrame:
    """KOSDAQ index via pykrx (index code '2001')."""
    from pykrx import stock
    s, e = _to_yyyymmdd(start), _to_yyyymmdd(end)
    df = stock.get_index_ohlcv_by_date(s, e, "2001")[["종가"]].rename(columns={"종가": "close"})
    df.index = pd.to_datetime(df.index)
    idx = _bdate_range(start, end)
    df = df.reindex(idx).ffill()
    df["ret"] = df["close"].pct_change().fillna(0.0)
    return df

def load_sp500(start: str, end: str) -> pd.DataFrame:
    """S&P 500 via yfinance (^GSPC)."""
    import yfinance as yf
    df = yf.download("^GSPC", start=start, end=end, progress=False)[["Adj Close"]].rename(columns={"Adj Close": "close"})
    df.index = pd.to_datetime(df.index)
    idx = _bdate_range(start, end)
    df = df.reindex(idx).ffill()
    df["ret"] = df["close"].pct_change().fillna(0.0)
    return df

def load_benchmark(name: str, start: str, end: str) -> pd.DataFrame:
    name = name.upper()
    if name == "KOSPI":
        return load_kospi(start, end)
    if name == "KOSDAQ":
        return load_kosdaq(start, end)
    if name in {"S&P500", "SP500", "GSPC"}:
        return load_sp500(start, end)
    raise ValueError(f"Unsupported benchmark: {name}")
