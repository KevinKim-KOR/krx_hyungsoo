# calendar_kr.py  — KRX 거래일(휴장일) 가드 / 파일 캐시
from pathlib import Path
import pandas as pd
from datetime import date
from core.utils.datasources import calendar_symbol_priority
# fetchers import는 함수 내부에서 지연 import로 처리 (순환 import 방지)
import logging

PROJECT_ROOT = Path(__file__).resolve().parent
PKL = PROJECT_ROOT / "data" / "cache" / "kr" / "trading_days.pkl"
log = logging.getLogger(__name__)

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

def load_trading_days(asof=None, start=None, end=None):
    """
    1) 캐시(data/cache/kr/trading_days.pkl) 우선 사용
    2) 없거나 비어있으면 외부 소스로 빌드 후 캐시 저장
    """
    # 1) 캐시 먼저
    try:
        if PKL.exists():
            idx = pd.read_pickle(PKL)
            if isinstance(idx, pd.DatetimeIndex) and len(idx) > 0:
                globals()["_TRADING_DAYS"] = idx
                return idx
    except Exception:
        pass  # 손상 시 아래 빌드 시도

    # 2) 외부로 재빌드 (최근 2년 기준)
    _start = start or (pd.Timestamp.today() - pd.DateOffset(years=2)).normalize()
    _end   = end   or pd.Timestamp.today().normalize()

    df, used = _first_available_ohlcv(_start, _end)
    if df is None or len(df) == 0:
        # 프리체크 단계는 RC=2로 재시도되므로 메시지만 명확히
        raise RuntimeError("calendar source unavailable")

    # 인덱스 → 거래일 DatetimeIndex
    idx = pd.DatetimeIndex(
        pd.to_datetime(df.index).tz_localize(None).normalize().unique()
    ).sort_values()

    # 3) 캐시 저장
    PKL.parent.mkdir(parents=True, exist_ok=True)
    pd.to_pickle(idx, PKL)
    log.info("[CAL] wrote %s (n=%d, %s~%s)", PKL, len(idx), idx.min().date(), idx.max().date())

    globals()["_TRADING_DAYS"] = idx
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
    """calendar_symbol_priority() 우선순위로 일봉 조회. 성공하면 (df, symbol), 실패면 (빈DF, None)."""
    from core.data_loader import get_ohlcv_safe  # 지연 import
    syms = calendar_symbol_priority()  # 예: ["069500.KS", "069500"]
    sd   = pd.to_datetime(start).date()
    ed   = pd.to_datetime(end).date()

    last_err = None
    for sym in syms:
        try:
            df = get_ohlcv_safe(sym, sd, ed)
            if df is not None and len(df) > 0:
                log.info("[CAL] calendar source = %s (n=%d)", sym, len(df))
                return df, sym
        except Exception as e:
            last_err = e

    # 마지막 시도로 yfinance 직접(선택)
    try:
        import yfinance as yf
        df = yf.download(
            syms[0], start=sd, end=ed,
            progress=False, auto_adjust=False, group_by="column", threads=False
        )
        if df is not None and len(df) > 0:
            log.info("[CAL] fallback yfinance source = %s (n=%d)", syms[0], len(df))
            return df, syms[0]
    except Exception as e:
        last_err = e

    log.warning("[CAL] all calendar sources failed: %s", last_err)
    return pd.DataFrame(), None
