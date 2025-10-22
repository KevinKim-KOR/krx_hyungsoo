# providers/ohlcv_bridge.py
from __future__ import annotations
from pathlib import Path
from typing import Optional
import os
import pandas as pd
from providers.ohlcv import ingest_symbol  # 우리가 앞서 만든 라우터/인게스터

CACHE_DIR = Path("data/cache/ohlcv")

def _map_fetch_symbol(symbol: str) -> str:
    s = symbol.upper().strip()
    # 미국 벤치마크는 SPY로 대체(fetch 전용)
    if s == "^GSPC":
        return "SPY"
    return s

def _norm_cols(df: pd.DataFrame) -> pd.DataFrame:
    if df is None:
        return df
    if df.empty:
        return df
    # 표준 컬럼 네이밍
    df = df.rename(columns={
        "Adj_Close": "Adj Close",
        "AdjClose": "Adj Close",
        "open": "Open", "high": "High", "low": "Low", "close": "Close",
        "adj_close": "Adj Close", "volume": "Volume",
    })
    keep = [c for c in ["Open","High","Low","Close","Adj Close","Volume"] if c in df.columns]
    if keep:
        df = df[keep]
    # 인덱스 정리
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index, errors="coerce")
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    df = df.sort_index()
    df = df[~df.index.duplicated(keep="last")]
    return df

def _read_cache(symbol: str) -> Optional[pd.DataFrame]:
    p = CACHE_DIR / f"{symbol}.parquet"
    if not p.exists():
        return None
    try:
        df = pd.read_parquet(p)
        return _norm_cols(df)
    except Exception:
        return None

def get_ohlcv_df(symbol: str,
                 start: Optional[pd.Timestamp] = None,
                 end: Optional[pd.Timestamp] = None,
                 backfill_years: int = 2) -> pd.DataFrame:
    """
    Scanner가 호출할 OHLCV 진입점.
    - 캐시 우선
    - 부족 범위는 ingest_symbol로 채운 뒤 재로드
    - 반환: 인덱스=DatetimeIndex, 컬럼=Open,High,Low,Close,Adj Close,Volume (가능한 컬럼만)
    """
    orig = symbol.strip()
    fetch_sym = _map_fetch_symbol(orig)

    # 1) 캐시 1차 로드
    df = _read_cache(fetch_sym) or _read_cache(orig)

    # 기본 범위
    today = pd.Timestamp("today").normalize()
    if start is None:
        if df is not None and not df.empty:
            start = df.index.min().normalize()
        else:
            start = today - pd.DateOffset(years=backfill_years)
    if end is None:
        end = today

    need_fetch = False
    if df is None or df.empty:
        need_fetch = True
    else:
        have_min, have_max = df.index.min().normalize(), df.index.max().normalize()
        if start < have_min or end > have_max:
            need_fetch = True

    if need_fetch:
        # 캐시 확충 (부족 구간을 포함하도록 since 지정)
        since = start.strftime("%Y-%m-%d")
        ingest_symbol(fetch_sym, since=since)
        # 재로드
        df = _read_cache(fetch_sym) or _read_cache(orig)

    if df is None or df.empty:
        return pd.DataFrame()  # 빈 프레임 반환(스캐너는 스킵하도록)

    # 최종 슬라이스
    df = df.loc[(df.index >= pd.Timestamp(start)) & (df.index <= pd.Timestamp(end))]
    return _norm_cols(df)
