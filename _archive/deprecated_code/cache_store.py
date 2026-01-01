# cache_store.py - 간단한 OHLCV 파일 캐시
from pathlib import Path
import pandas as pd
from typing import Optional
import logging

log = logging.getLogger(__name__)

BASE = Path("data/cache/kr")  # 규칙: data/cache/{country}/*.pkl

def ensure_dir():
    BASE.mkdir(parents=True, exist_ok=True)

def cache_path(code: str) -> Path:
    ensure_dir()
    safe = code.replace("/", "_")
    return BASE / f"{safe}.pkl"

def load_cached(code: str) -> Optional[pd.DataFrame]:
    p = cache_path(code)
    if not p.exists():
        log.debug(f"[CACHE] miss: {code} (파일 없음)")
        return None
    try:
        df = pd.read_pickle(p)
        if df is None or df.empty:
            log.warning(f"[CACHE] miss: {code} (빈 데이터)")
            return None
        df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
        log.debug(f"[CACHE] hit: {code} ({len(df)} rows, {df.index.min().date()}~{df.index.max().date()})")
        return df.sort_index()
    except Exception as e:
        log.error(f"[CACHE] error loading {code}: {e}")
        return None

def save_cache(code: str, df: pd.DataFrame) -> None:
    if df is None or df.empty:
        log.debug(f"[CACHE] skip save: {code} (빈 데이터)")
        return
    try:
        df = df.copy()
        df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
        df = (df[["Open","High","Low","Close","Volume"]]
              .astype({"Open":float,"High":float,"Low":float,"Close":float,"Volume":"int64"}))
        p = cache_path(code)
        df.sort_index().to_pickle(p)
        log.info(f"[CACHE] saved: {code} ({len(df)} rows → {p})")
    except Exception as e:
        log.error(f"[CACHE] error saving {code}: {e}")
