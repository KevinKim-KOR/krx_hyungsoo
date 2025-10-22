# providers/ohlcv.py
from __future__ import annotations
from pathlib import Path
from datetime import datetime
import os, time
import pandas as pd

# Optional deps
try: import yfinance as yf
except Exception: yf = None
try: import FinanceDataReader as fdr
except Exception: fdr = None
try:
    from pandas_datareader import data as pdr  # Stooq
except Exception:
    pdr = None

CACHE_DIR = Path("data/cache/ohlcv")
STATE_DIR = Path(".state"); STATE_DIR.mkdir(parents=True, exist_ok=True)

def _throttle(ts_name: str, env_key: str, default_gap: float):
    ts_file = STATE_DIR / ts_name
    min_gap = float(os.environ.get(env_key, str(default_gap)))
    now = time.time()
    last = 0.0
    if ts_file.exists():
        try: last = float(ts_file.read_text().strip())
        except Exception: pass
    wait = (last + min_gap) - now
    if wait > 0: time.sleep(wait)
    ts_file.write_text(str(time.time()))

def _read_parquet(path: Path) -> pd.DataFrame | None:
    if not path.exists(): return None
    try:
        df = pd.read_parquet(path)
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)
        df = df.sort_index()
        df = df[~df.index.duplicated(keep="first")]
        return df
    except Exception:
        return None

def _write_parquet(path: Path, df: pd.DataFrame):
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path)

def _norm(df: pd.DataFrame | None) -> pd.DataFrame | None:
    if df is None or df.empty: return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
        df = df.loc[:, ~df.columns.duplicated()]
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    df = df.sort_index()
    df = df[~df.index.duplicated(keep="last")]
    # unify columns if present
    col_alias = {"Adj_Close":"Adj Close","AdjClose":"Adj Close"}
    df = df.rename(columns=col_alias)
    keep = [c for c in ["Open","High","Low","Close","Adj Close","Volume"] if c in df.columns]
    return df[keep] if keep else df

def _is_kr(sym: str) -> bool:
    """한국 종목 판별: .KS 접미사 또는 6자리 숫자 코드"""
    if sym.endswith(".KS") or sym.startswith("^KS"):
        return True
    # 6자리 숫자 코드 (예: 069500, 005930)
    clean = sym.split(".")[0].strip()
    return clean.isdigit() and len(clean) == 6

def _to_fdr(sym: str) -> str:
    return sym.split(".")[0] if sym.endswith(".KS") else sym

def fetch_with_route(symbol: str, start: pd.Timestamp, end: pd.Timestamp) -> tuple[pd.DataFrame|None, str]:
    """Return (df, provider) using route: CacheRange->PyKRX/FDR->Stooq->YF."""
    # 1) PyKRX (KR)
    if _is_kr(symbol):
        try:
            from pykrx import stock as krx  # import on demand
            _throttle("pykrx_last.ts", "PYKRX_MIN_INTERVAL_SEC", 0.6)
            s = start.strftime("%Y%m%d"); e = end.strftime("%Y%m%d")
            # pykrx는 한국장 기준으로 일자 인덱스 반환
            df = krx.get_market_ohlcv_by_date(s, e, _to_fdr(symbol))
            if df is not None and not df.empty:
                df.index = pd.to_datetime(df.index)
                df = df.rename(columns={"시가":"Open","고가":"High","저가":"Low","종가":"Close","거래량":"Volume"})
                return _norm(df), "pykrx"
        except Exception:
            pass
        # 2) FDR (KR)
        if fdr is not None:
            try:
                _throttle("fdr_last.ts", "FDR_MIN_INTERVAL_SEC", 1.2)
                df = fdr.DataReader(_to_fdr(symbol), start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
                if df is not None and not df.empty:
                    return _norm(df), "fdr"
            except Exception:
                pass
    # 3) Stooq (글로벌 일부)
    if pdr is not None:
        try:
            _throttle("stooq_last.ts", "STOOQ_MIN_INTERVAL_SEC", 0.8)
            df = pdr.DataReader(symbol, "stooq", start, end)
            if df is not None and not df.empty:
                df = df.rename(columns=str.title)  # Open, High, Low, Close, Volume
                return _norm(df), "stooq"
        except Exception:
            pass
    # 4) YF (최후 폴백)
    if yf is not None:
        try:
            _throttle("yf_last.ts", "YF_MIN_INTERVAL_SEC", 3.5)
            df = yf.download(symbol, start=start.tz_localize(None), end=(end+pd.Timedelta(days=1)).tz_localize(None),
                             auto_adjust=False, progress=False)
            if df is not None and not df.empty:
                return _norm(df), "yfinance"
        except Exception:
            pass
    return None, "none"

def ingest_symbol(symbol: str, since: str | None = None) -> dict:
    symbol = symbol.strip()
    path = CACHE_DIR / f"{symbol}.parquet"
    cached = _read_parquet(path)
    today = pd.Timestamp(datetime.utcnow().date())
    if since:
        start = pd.Timestamp(since)
    elif cached is not None and not cached.empty:
        start = cached.index.max() + pd.Timedelta(days=1)
    else:
        start = today - pd.DateOffset(years=2)
    end = today
    if cached is not None and not cached.empty and start > end:
        return {"symbol": symbol, "provider":"cache", "rows": int(cached.shape[0]), "status":"up_to_date"}

    df, prov = fetch_with_route(symbol, start, end)
    if df is None or df.empty:
        rows = 0 if cached is None else int(cached.shape[0])
        return {"symbol": symbol, "provider":prov, "rows": rows, "status":"fetch_empty_or_failed"}

    merged = df if cached is None or cached.empty else pd.concat([cached, df]).sort_index().pipe(
        lambda x: x[~x.index.duplicated(keep="last")]
    )
    _write_parquet(path, merged)
    return {"symbol": symbol, "provider":prov, "rows": int(merged.shape[0]), "status":"ok"}
