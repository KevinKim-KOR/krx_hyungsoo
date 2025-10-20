#!/usr/bin/env python3
from __future__ import annotations
import argparse, os, sys, time
from pathlib import Path
from datetime import datetime
import pandas as pd

# Optional deps
try:
    import yfinance as yf
except Exception:
    yf = None

try:
    import FinanceDataReader as fdr
except Exception:
    fdr = None

CACHE_DIR = Path("data/cache/ohlcv")
STATE_DIR = Path(".state"); STATE_DIR.mkdir(parents=True, exist_ok=True)
TOK_FILE = STATE_DIR / "yf_last_call.ts"
TOK_FDR = STATE_DIR / "fdr_last_call.ts"

def _throttle(ts_file: Path, env_key: str, default_gap: float):
    """Token-bucket style throttle using timestamp file."""
    min_gap = float(os.environ.get(env_key, str(default_gap)))
    now = time.time()
    last = 0.0
    if ts_file.exists():
        try: last = float(ts_file.read_text().strip())
        except Exception: last = 0.0
    wait = (last + min_gap) - now
    if wait > 0:
        time.sleep(wait)
    ts_file.write_text(str(time.time()))

def _read_parquet(p: Path) -> pd.DataFrame | None:
    if not p.exists(): return None
    try:
        df = pd.read_parquet(p)
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)
        df = df.sort_index()
        df = df[~df.index.duplicated(keep="first")]
        return df
    except Exception:
        return None

def _write_parquet(p: Path, df: pd.DataFrame):
    p.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(p)

def _norm_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    """Standardize columns to [Open,High,Low,Close,Adj Close,Volume] subset if present."""
    if df is None or df.empty:
        return df
    # Normalize MultiIndex columns (yfinance)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
        df = df.loc[:, ~df.columns.duplicated()]
    # Common FDR column mapping
    colmap = {
        'Open':'Open', 'High':'High', 'Low':'Low', 'Close':'Close',
        'Adj Close':'Adj Close', 'Volume':'Volume',
        'Adj_Close':'Adj Close', 'AdjClose':'Adj Close',
    }
    # If FDR style columns exist, align
    for c in list(df.columns):
        if c in colmap: continue
        if c.replace(' ', '_') in colmap:
            df.rename(columns={c: colmap[c.replace(' ','_')]}, inplace=True)
    keep = [c for c in ["Open","High","Low","Close","Adj Close","Volume"] if c in df.columns]
    if keep:
        df = df[keep]
    # Index tz-naive, sorted, dedup
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    df = df.sort_index()
    df = df[~df.index.duplicated(keep="last")]
    return df

def _fetch_yf(symbol: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame | None:
    if yf is None: return None
    _throttle(TOK_FILE, "YF_MIN_INTERVAL_SEC", 2.5)
    df = yf.download(
        symbol,
        start=start.tz_localize(None),
        end=(end + pd.Timedelta(days=1)).tz_localize(None),
        auto_adjust=False,
        progress=False,
    )
    if df is None or df.empty: return None
    return _norm_ohlcv(df)

def _to_fdr_symbol(symbol: str) -> str:
    # '005930.KS' -> '005930'; '^KS11' -> '^KS11'(FDR 지원 안 되면 None 반환)
    if symbol.endswith(".KS") and len(symbol) >= 3:
        return symbol.split(".")[0]
    # 미국 심볼(AAPL 등)은 FDR로도 일부 가능하지만 여기서는 YF 우선
    return symbol

def _fetch_fdr(symbol: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame | None:
    if fdr is None: return None
    # FDR는 한국 심볼에서 비교적 우수. 과도 호출 방지 스로틀
    _throttle(TOK_FDR, "FDR_MIN_INTERVAL_SEC", 1.5)
    sym = _to_fdr_symbol(symbol)
    try:
        df = fdr.DataReader(sym, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
    except Exception:
        return None
    if df is None or df.empty: return None
    # FDR 인덱스/컬럼 정리
    if not isinstance(df.index, pd.DatetimeIndex):
        if 'Date' in df.columns:
            df.index = pd.to_datetime(df['Date'])
            df = df.drop(columns=['Date'])
        else:
            df.index = pd.to_datetime(df.index)
    return _norm_ohlcv(df)

def ingest_one(symbol: str, since: str | None) -> dict:
    symbol = symbol.strip()
    if not symbol:
        return {"symbol": symbol, "rows": 0, "status": "empty_symbol"}

    path = CACHE_DIR / f"{symbol}.parquet"
    cached = _read_parquet(path)
    today = pd.Timestamp(datetime.utcnow().date())

    # Missing range calc
    if since:
        start = pd.Timestamp(since)
    elif cached is not None and not cached.empty:
        start = cached.index.max() + pd.Timedelta(days=1)
    else:
        # Limit initial backfill to 2y (adjustable)
        start = today - pd.DateOffset(years=2)
    end = today

    # Up-to-date shortcut
    if cached is not None and not cached.empty and start > end:
        return {"symbol": symbol, "rows": int(cached.shape[0]), "status": "up_to_date"}

    # Try yfinance first
    fetched = _fetch_yf(symbol, start, end)

    # If YF failed/empty and KR ticker -> fallback to FDR
    if (fetched is None or fetched.empty) and (symbol.endswith(".KS") or symbol.startswith("^KS")):
        fetched = _fetch_fdr(symbol, start, end)
        if fetched is not None and not fetched.empty:
            status = "ok_fdr"
        else:
            status = "fetch_empty_or_failed"
    else:
        status = "ok" if (fetched is not None and not fetched.empty) else "fetch_empty_or_failed"

    # If still nothing but have cache, keep cache
    if (fetched is None or fetched.empty):
        rows = 0 if cached is None else int(cached.shape[0])
        return {"symbol": symbol, "rows": rows, "status": status}

    merged = fetched if (cached is None or cached.empty) else pd.concat([cached, fetched])
    merged = merged.sort_index()
    merged = merged[~merged.index.duplicated(keep="last")]
    _write_parquet(path, merged)
    return {"symbol": symbol, "rows": int(merged.shape[0]), "status": status}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--since", default=None)
    args = ap.parse_args()
    try:
        out = ingest_one(args.symbol, args.since)
        print(out)
        # Treat ok/up_to_date/ok_fdr as success (exit 0). Others -> 3 to trigger retry upstream
        if out["status"] in ("ok","up_to_date","ok_fdr","fetch_empty_or_failed"):
            sys.exit(0)
        sys.exit(3)
    except KeyboardInterrupt:
        sys.exit(130)

if __name__ == "__main__":
    main()
