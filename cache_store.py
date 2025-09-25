# cache_store.py - 간단한 OHLCV 파일 캐시
from pathlib import Path
import pandas as pd

BASE = Path("data/cache/kr")  # 규칙: data/cache/{country}/*.pkl

def ensure_dir():
    BASE.mkdir(parents=True, exist_ok=True)

def cache_path(code: str) -> Path:
    ensure_dir()
    safe = code.replace("/", "_")
    return BASE / f"{safe}.pkl"

def load_cached(code: str) -> pd.DataFrame | None:
    p = cache_path(code)
    if not p.exists():
        return None
    try:
        df = pd.read_pickle(p)
        if df is None or df.empty:
            return None
        df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
        return df.sort_index()
    except Exception:
        return None

def save_cache(code: str, df: pd.DataFrame) -> None:
    if df is None or df.empty:
        return
    df = df.copy()
    df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
    df = (df[["Open","High","Low","Close","Volume"]]
          .astype({"Open":float,"High":float,"Low":float,"Close":float,"Volume":"int64"}))
    df.sort_index().to_pickle(cache_path(code))
