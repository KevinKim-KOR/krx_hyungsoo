# calendar_kr.py  — KRX 거래일(휴장일) 가드 / 파일 캐시
from pathlib import Path
import pandas as pd
from datetime import date
from krx_helpers import get_ohlcv_safe

_CACHE = Path("data/cache/kr/trading_days.pkl")

def _ensure_cache_dir():
    _CACHE.parent.mkdir(parents=True, exist_ok=True)

def build_trading_days(start="2010-01-01", end=None) -> pd.DatetimeIndex:
    """069500.KS 일자를 기준으로 거래일 캘린더 구축 후 캐시 저장"""
    _ensure_cache_dir()
    end = pd.to_datetime(end or pd.Timestamp.today().date())
    df = get_ohlcv_safe("069500.KS", pd.to_datetime(start).date(), end.date())
    if df is None or df.empty:
        return pd.DatetimeIndex([])
    idx = pd.DatetimeIndex(pd.to_datetime(df.index).normalize().unique()).sort_values()
    idx.to_series(index=idx).to_pickle(_CACHE)
    return idx

def load_trading_days(asof=None) -> pd.DatetimeIndex:
    """캐시가 없거나 asof를 포함하지 못하면 재빌드"""
    _ensure_cache_dir()
    asof = pd.to_datetime(asof or pd.Timestamp.today().date())
    if _CACHE.exists():
        try:
            s = pd.read_pickle(_CACHE)
            idx = pd.DatetimeIndex(s.index) if hasattr(s, "index") else pd.DatetimeIndex(s)
            if len(idx) and idx[-1] >= asof - pd.Timedelta(days=5):
                return idx
        except Exception:
            pass
    return build_trading_days(end=asof)

def is_trading_day(d) -> bool:
    d = pd.to_datetime(d).normalize()
    idx = load_trading_days(asof=d)
    return d in idx

def next_trading_day(d):
    """d 이후 다음 거래일 반환 (없으면 d 그대로)"""
    d = pd.to_datetime(d).normalize()
    idx = load_trading_days(asof=d + pd.Timedelta(days=10))
    pos = idx.searchsorted(d + pd.Timedelta(days=1))
    return (idx[pos] if pos < len(idx) else d)
