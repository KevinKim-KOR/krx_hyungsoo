#!/usr/bin/env python3
"""
Single-symbol EOD ingest with on-disk cache merge (yfinance).
- Reads/updates data/cache/ohlcv/{SYMBOL}.parquet
- Fetches only missing range since last cached date
- Dedup/sort/tz-naive; robust to empty frames
- Token-bucket throttle via .state/yf_last_call.ts
Usage:
  python -m scripts.ops.ingest_one_symbol --symbol 005930.KS [--since 2024-01-01]
Env:
  YF_MIN_INTERVAL_SEC (default 2.5)
"""
from __future__ import annotations
import argparse, os, sys, time, json
from pathlib import Path
from datetime import datetime, timedelta

import pandas as pd
try:
    import yfinance as yf
except Exception:
    yf = None

CACHE_DIR = Path("data/cache/ohlcv")
STATE_DIR = Path(".state"); STATE_DIR.mkdir(parents=True, exist_ok=True)
TOK_FILE = STATE_DIR / "yf_last_call.ts"

def _throttle():
    min_gap = float(os.environ.get("YF_MIN_INTERVAL_SEC", "2.5"))
    now = time.time()
    last = 0.0
    if TOK_FILE.exists():
        try:
            last = float(TOK_FILE.read_text().strip())
        except Exception:
            last = 0.0
    wait = (last + min_gap) - now
    if wait > 0:
        time.sleep(wait)
    TOK_FILE.write_text(str(time.time()))

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

def _fetch_yf(symbol: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame | None:
    if yf is None: return None
    # yfinance에 불필요한 옵션 최소화; progress False
    _throttle()
    df = yf.download(
        symbol,
        start=start.tz_localize(None),
        end=(end + pd.Timedelta(days=1)).tz_localize(None),
        auto_adjust=False,
        progress=False,
    )
    if df is None or df.empty: return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
        df = df.loc[:, ~df.columns.duplicated()]
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    df = df.sort_index()
    df = df[~df.index.duplicated(keep="first")]
    # 표준 컬럼만 유지 (없으면 패스)
    keep = [c for c in ["Open","High","Low","Close","Adj Close","Volume"] if c in df.columns]
    return df[keep]

def ingest_one(symbol: str, since: str | None) -> dict:
    symbol = symbol.strip()
    if not symbol:
        return {"symbol": symbol, "rows": 0, "status": "empty_symbol"}

    path = CACHE_DIR / f"{symbol}.parquet"
    cached = _read_parquet(path)
    today = pd.Timestamp(datetime.utcnow().date())

    # 결측 시작일 계산
    if since:
        start = pd.Timestamp(since)
    elif cached is not None and not cached.empty:
        start = cached.index.max() + pd.Timedelta(days=1)
    else:
        # 너무 과거까지 당기지 않도록 2년 제한 (필요시 조정)
        start = today - pd.DateOffset(years=2)
    end = today

    # 과거 범위면 스킵
    if cached is not None and not cached.empty and start > end:
        return {"symbol": symbol, "rows": 0, "status": "up_to_date"}

    fetched = _fetch_yf(symbol, start, end)
    if fetched is None or fetched.empty:
        # 캐시라도 있으면 그대로 성공 처리(아티팩트 유지)
        rows = 0 if cached is None else int(cached.shape[0])
        return {"symbol": symbol, "rows": rows, "status": "fetch_empty_or_failed"}

    merged = fetched if (cached is None or cached.empty) else pd.concat([cached, fetched])
    merged = merged.sort_index()
    merged = merged[~merged.index.duplicated(keep="last")]

    _write_parquet(path, merged)
    return {"symbol": symbol, "rows": int(merged.shape[0]), "status": "ok"}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--since", default=None)
    args = ap.parse_args()
    try:
        out = ingest_one(args.symbol, args.since)
        print(json.dumps(out, ensure_ascii=False))
        # 성공/부분성공을 0으로 두고, 완전 실패만 3으로 (상위 배치 재시도 트리거)
        if out["status"] in ("ok","up_to_date","fetch_empty_or_failed"):
            sys.exit(0)
        sys.exit(3)
    except KeyboardInterrupt:
        sys.exit(130)

if __name__ == "__main__":
    main()
