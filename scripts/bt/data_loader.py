from __future__ import annotations
from pathlib import Path
from datetime import datetime
import pandas as pd

def _bdate_range(start: str, end: str) -> pd.DatetimeIndex:
    return pd.bdate_range(start=pd.to_datetime(start), end=pd.to_datetime(end), freq="B")

def _to_yyyymmdd(s: str) -> str:
    return pd.to_datetime(s).strftime("%Y%m%d")

def _load_yf_index_close_ret(ticker: str, start: str, end: str) -> pd.DataFrame:
    """Yahoo Finance로 인덱스 티커를 받아 close/ret 생성 (단일/멀티컬럼 안전)."""
    import yfinance as yf
    df = yf.download(
        ticker, start=start, end=end,
        progress=False, auto_adjust=False,
        group_by="column", threads=False
    )
    if df is None or len(df) == 0:
        raise ValueError(f"yfinance empty for {ticker}")

    # 단일/멀티컬럼 모두 대응
    if not isinstance(df.columns, pd.MultiIndex):
        if   "Adj Close" in df.columns: close = df["Adj Close"]
        elif "Close"     in df.columns: close = df["Close"]
        else:
            # 'Adj' 또는 'Close'가 들어간 첫 컬럼 사용
            cand = [c for c in df.columns if "Adj" in c or "Close" in c]
            if not cand: raise KeyError(f"Close not found: {df.columns.tolist()}")
            close = df[cand[0]]
    else:
        flat_cols = [" | ".join(map(str, c)) for c in df.columns]
        df = df.copy(); df.columns = flat_cols
        cand = [c for c in df.columns if "Adj Close" in c] or [c for c in df.columns if "Close" in c]
        if not cand: raise KeyError(f"Close not found in MultiIndex: {flat_cols}")
        close = df[cand[0]]

    close.name = "close"
    close.index = pd.to_datetime(close.index)
    close = close.sort_index()
    idx = _bdate_range(start, end)
    out = pd.DataFrame({"close": close.reindex(idx).ffill()})
    out["ret"] = out["close"].pct_change().fillna(0.0)
    return out

def load_kospi(start: str, end: str) -> pd.DataFrame:
    """KOSPI: 우선 pykrx, 실패 시 yfinance(^KS11)로 폴백."""
    try:
        from pykrx import stock
        s, e = _to_yyyymmdd(start), _to_yyyymmdd(end)
        df = stock.get_index_ohlcv_by_date(s, e, "1001")[["종가"]].rename(columns={"종가": "close"})
        df.index = pd.to_datetime(df.index)
        idx = _bdate_range(start, end)
        df = df.reindex(idx).ffill()
        df["ret"] = df["close"].pct_change().fillna(0.0)
        return df
    except Exception as ex:
        # pykrx 이슈(지수명/사이트응답) 시 안전 폴백
        return _load_yf_index_close_ret("^KS11", start, end)

def load_kosdaq(start: str, end: str) -> pd.DataFrame:
    """KOSDAQ: 우선 pykrx, 실패 시 yfinance(^KQ11)로 폴백."""
    try:
        from pykrx import stock
        s, e = _to_yyyymmdd(start), _to_yyyymmdd(end)
        df = stock.get_index_ohlcv_by_date(s, e, "2001")[["종가"]].rename(columns={"종가": "close"})
        df.index = pd.to_datetime(df.index)
        idx = _bdate_range(start, end)
        df = df.reindex(idx).ffill()
        df["ret"] = df["close"].pct_change().fillna(0.0)
        return df
    except Exception as ex:
        return _load_yf_index_close_ret("^KQ11", start, end)


def load_sp500(start: str, end: str) -> pd.DataFrame:
    """S&P500: yfinance ^GSPC (견고 모드)."""
    return _load_yf_index_close_ret("^GSPC", start, end)


def load_benchmark(name: str, start: str, end: str) -> pd.DataFrame:
    name = name.upper()
    if name == "KOSPI":
        return load_kospi(start, end)
    if name == "KOSDAQ":
        return load_kosdaq(start, end)
    if name in {"S&P500", "SP500", "GSPC"}:
        return load_sp500(start, end)
    raise ValueError(f"Unsupported benchmark: {name}")
