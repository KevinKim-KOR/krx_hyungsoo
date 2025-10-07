# calendar_kr.py  — KRX 거래일(휴장일) 가드 / 파일 캐시
from pathlib import Path
import pandas as pd
from datetime import date
#from krx_helpers import get_ohlcv_safe
from utils.datasources import calendar_symbol_priority
from fetchers import get_ohlcv_safe
import logging

_CACHE = Path("data/cache/kr/trading_days.pkl")
SYMS = calendar_symbol_priority()

def _ensure_cache_dir():
    _CACHE.parent.mkdir(parents=True, exist_ok=True)

def build_trading_days(start="2010-01-01", end=None) -> pd.DatetimeIndex:
    """069500.KS 일자를 기준으로 거래일 캘린더 구축 후 캐시 저장"""
    _ensure_cache_dir()
    end = pd.to_datetime(end or pd.Timestamp.today().date())
    #df = get_ohlcv_safe("069500.KS", pd.to_datetime(start).date(), end.date())
    df, _used = _first_available_ohlcv(start, end)
    if df is None or len(df) == 0:
        raise RuntimeError("calendar source unavailable (see logs)")
    idx = pd.DatetimeIndex(pd.to_datetime(df.index).normalize().unique()).sort_values()
    idx.to_series(index=idx).to_pickle(_CACHE)
    return idx

def load_trading_days(asof=None):
    """
    ETF(069500.KS) 일봉으로 거래일 인덱스를 만든다.
    - 연말 경계(1월 초/12월 말) 보완을 위해 이전 해 12월도 포함
    """
    d = _normalize_asof(asof)
    y = d.year
    # 이전 해 12월 1일부터 현재 연말까지 확보(경계일 prev_trading_day 대비)
    df, _used = _first_available_ohlcv(start, end)
    if df is None or len(df) == 0:
        raise RuntimeError("calendar source unavailable (see logs)")
    idx = pd.DatetimeIndex(df.index).tz_localize(None).normalize().sort_values().unique()
    return idx

def is_trading_day(d) -> bool:
    """주말 제외 + (오늘은 평일이면 거래일 취급) + 과거/미래는 일봉 존재일로 판정"""
    d = pd.to_datetime(d).tz_localize(None).normalize()
    # 주말 즉시 제외
    if d.weekday() >= 5:
        return False
    # 오늘(일중)은 평일이면 거래일로 간주 (일봉 미생성이라도 스킵 방지)
    if d.date() == pd.Timestamp.today().date():
        return True
    # 과거/미래: 실제 일봉이 존재하는 날만 거래일로 간주
    idx = load_trading_days(asof=d)
    return d in idx

def next_trading_day(d):
    """d 이후 다음 거래일 반환 (없으면 d 그대로)"""
    d = pd.to_datetime(d).normalize()
    idx = load_trading_days(asof=d + pd.Timedelta(days=10))
    pos = idx.searchsorted(d + pd.Timedelta(days=1))
    return (idx[pos] if pos < len(idx) else d)

def prev_trading_day(d):
    """d 이전 직전 거래일 반환 (없으면 d 그대로)"""
    d = pd.to_datetime(d).normalize()
    idx = load_trading_days(asof=d)
    pos = idx.searchsorted(d)
    return (idx[pos-1] if pos > 0 else d)

def _normalize_asof(asof):
    """
    - None / "" / NaT / 파싱 실패 → 오늘 날짜 normalize()
    - 문자열/Datetime 모두 허용
    """
    if asof in (None, "", pd.NaT):
        ts = pd.Timestamp.today()
    else:
        ts = pd.to_datetime(asof, errors="coerce")
        if pd.isna(ts):
            ts = pd.Timestamp.today()
    return ts.normalize()

def _first_available_ohlcv(start, end):
    """calendar_symbol_priority()에 정의된 심볼 우선순위로 OHLCV 조회, 성공한 첫 DF를 반환."""
    syms = calendar_symbol_priority()           # 예: ["069500.KS","069500"]
    start_d = pd.to_datetime(start).date()
    end_d   = pd.to_datetime(end).date()
    last_err = None

    for sym in syms:
        try:
            df = get_ohlcv_safe(sym, start_d, end_d)
            if df is not None and len(df) > 0:
                logging.getLogger(__name__).info("[CAL] calendar source = %s (n=%d)", sym, len(df))
                return df, sym
        except Exception as e:
            last_err = e

    # (옵션) 마지막 시도로 yfinance 직접 조회
    try:
        import yfinance as yf
        df = yf.download(syms[0], start=start_d, end=end_d, progress=False, auto_adjust=False, group_by="column", threads=False)
        if df is not None and len(df) > 0:
            logging.getLogger(__name__).info("[CAL] fallback yfinance source = %s (n=%d)", syms[0], len(df))
            return df, syms[0]
    except Exception as e:
        last_err = e

    logging.getLogger(__name__).warning("[CAL] all calendar sources failed: %s", last_err)
    return pd.DataFrame(), None
