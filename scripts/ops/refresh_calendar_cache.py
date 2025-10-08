#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from datetime import date, timedelta
import pandas as pd

import sys
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
    
from utils.datasources import calendar_symbol_priority

from fetchers import get_ohlcv_safe

DATADIR = ROOT / "data" / "cache" / "kr"
DATADIR.mkdir(parents=True, exist_ok=True)
OUTP = DATADIR / "trading_days.pkl"

def _try_first_available(syms, start, end):
    """심볼 우선순위대로 첫 성공하는 일봉 DataFrame 반환."""
    for s in syms:
        try:
            df = get_ohlcv_safe(s, start, end)
            if df is not None and len(df):
                return s, df
        except Exception:
            pass
    return None, None

def calendar_symbols_priority():
    return calendar_symbol_priority()  # YAML → 기본값까지 포함

def _build_calendar_index(start=None, end=None):
    end   = pd.to_datetime(end or pd.Timestamp.today()).normalize()
    start = pd.to_datetime(start or (end - pd.DateOffset(years=2))).normalize()

    syms = calendar_symbol_priority()  # YAML → 기본값 ["069500.KS","069500"]
    _, df = _try_first_available(syms, start.date(), end.date())
    if df is None or df.empty:
        # 배치 프리체크에서 이 문구를 그대로 기대하고 있으니 유지
        raise RuntimeError("No objects to concatenate")

    idx = pd.to_datetime(df.index).normalize().unique()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    pd.to_pickle(idx, PICKLE)
    print(f"[CAL] wrote {PICKLE} (n={len(idx)}, {idx.min().date()}~{idx.max().date()})")
    return idx

def trading_days_cached_or_build(asof=None):
    """
    1) 캐시가 적절하면 그대로 반환
    2) 없거나 손상/빈값이면 새로 빌드 → 저장 → 반환
    """
    try:
        idx = pd.read_pickle(PICKLE)
        if isinstance(idx, pd.DatetimeIndex) and len(idx) > 0:
            return idx
    except Exception:
        pass
    return _build_calendar_index()

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
    for sym in calendar_symbols_priority():
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
    _build_calendar_index()
    sys.exit(main())
