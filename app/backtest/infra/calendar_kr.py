# calendar_kr.py — KRX 거래일 가드 (P164 간소화 버전)
# 원본: legacy core/calendar_kr.py
# 변경: core.utils.datasources 의존성 제거, yfinance 직접 사용
from pathlib import Path
import pandas as pd
from datetime import date
import logging

log = logging.getLogger(__name__)

_CACHE = Path("data/cache/kr/trading_days.pkl")
_CALENDAR_SYMBOLS = ["069500.KS", "069500"]


def _ensure_cache_dir():
    _CACHE.parent.mkdir(parents=True, exist_ok=True)


def _first_available_ohlcv(start, end):
    """yfinance로 일봉 조회. 성공하면 (df, symbol), 실패면 (빈DF, None)."""
    from app.backtest.infra.data_loader import get_ohlcv_safe
    sd = pd.to_datetime(start).date() if not isinstance(start, date) else start
    ed = pd.to_datetime(end).date() if not isinstance(end, date) else end

    for sym in _CALENDAR_SYMBOLS:
        try:
            df = get_ohlcv_safe(sym, sd, ed)
            if df is not None and len(df) > 0:
                log.info("[CAL] calendar source = %s (n=%d)", sym, len(df))
                return df, sym
        except Exception as e:
            log.warning("[CAL] %s failed: %s", sym, e)

    log.warning("[CAL] all calendar sources failed")
    return pd.DataFrame(), None


def build_trading_days(start="2010-01-01", end=None) -> pd.DatetimeIndex:
    """069500.KS 일자를 기준으로 거래일 캘린더 구축 후 캐시 저장"""
    _ensure_cache_dir()
    end = pd.to_datetime(end or pd.Timestamp.today().date())
    df, _used = _first_available_ohlcv(start, end)
    if df is None or len(df) == 0:
        raise RuntimeError("calendar source unavailable (see logs)")
    idx = pd.DatetimeIndex(pd.to_datetime(df.index).normalize().unique()).sort_values()
    idx.to_series(index=idx).to_pickle(_CACHE)
    return idx


def load_trading_days(asof=None, start=None, end=None):
    """
    1) 캐시(data/cache/kr/trading_days.pkl) 우선 사용
    2) 없거나 비어있으면 외부 소스로 빌드 후 캐시 저장
    """
    try:
        if _CACHE.exists():
            idx = pd.read_pickle(_CACHE)
            if isinstance(idx, pd.DatetimeIndex) and len(idx) > 0:
                return idx
    except Exception:
        pass

    _start = start or (pd.Timestamp.today() - pd.DateOffset(years=2)).normalize()
    _end = end or pd.Timestamp.today().normalize()

    df, used = _first_available_ohlcv(_start, _end)
    if df is None or len(df) == 0:
        raise RuntimeError("calendar source unavailable")

    idx = pd.DatetimeIndex(
        pd.to_datetime(df.index).tz_localize(None).normalize().unique()
    ).sort_values()

    _CACHE.parent.mkdir(parents=True, exist_ok=True)
    pd.to_pickle(idx, _CACHE)
    log.info("[CAL] wrote %s (n=%d, %s~%s)", _CACHE, len(idx), idx.min().date(), idx.max().date())
    return idx


def is_trading_day(d) -> bool:
    d = pd.to_datetime(d).tz_localize(None).normalize()
    if d.weekday() >= 5:
        return False
    if d.date() == pd.Timestamp.today().date():
        return True
    idx = load_trading_days(asof=d)
    return d in idx


def next_trading_day(d):
    d = pd.to_datetime(d).normalize()
    idx = load_trading_days(asof=d + pd.Timedelta(days=10))
    pos = idx.searchsorted(d + pd.Timedelta(days=1))
    return (idx[pos] if pos < len(idx) else d)


def prev_trading_day(d):
    d = pd.to_datetime(d).normalize()
    idx = load_trading_days(asof=d)
    pos = idx.searchsorted(d)
    return (idx[pos-1] if pos > 0 else d)
