import pandas as pd
from datetime import date
from pykrx import stock as krx
# krx_helpers.py  상단에 추가
import logging, pandas as pd
from datetime import timedelta
from cache_store import load_cached, save_cache
log = logging.getLogger(__name__)


def _to_krx_code(ticker:str)->str:
    # '069500.KS' -> '069500', '069500' -> '069500'
    digits = "".join(ch for ch in ticker if ch.isdigit())
    return digits[:6] if digits else ticker

# def get_ohlcv_safe(ticker:str, start, end):
#     """
#     ticker: '069500.KS' 또는 '069500'
#     start/end: datetime.date 또는 datetime-like
#     return: DataFrame index=DatetimeIndex, cols=[Open,High,Low,Close,Volume]
#     """
#     if not isinstance(start, pd.Timestamp): start = pd.Timestamp(start)
#     if not isinstance(end, pd.Timestamp):   end   = pd.Timestamp(end)
#     code = _to_krx_code(ticker)
#     df = krx.get_market_ohlcv_by_date(start.strftime("%Y%m%d"),
#                                       (end + pd.Timedelta(days=1)).strftime("%Y%m%d"),
#                                       code)
#     # KRX 컬럼 -> 표준화
#     df = df.rename(columns={"시가":"Open","고가":"High","저가":"Low","종가":"Close","거래량":"Volume"})
#     df.index = pd.to_datetime(df.index)
#     return df[["Open","High","Low","Close","Volume"]].sort_index()

# pykrx로 일일 OHLCV 수집 (ETF/주식)
def _fetch_ohlcv_krx(code: str, start, end) -> pd.DataFrame:
    from pykrx import stock as krx
    s = pd.to_datetime(start).date()
    e = pd.to_datetime(end).date()
    raw_code = code.split(".")[0]  # '069500.KS' -> '069500'
    df = krx.get_market_ohlcv_by_date(s.strftime("%Y%m%d"), e.strftime("%Y%m%d"), raw_code)
    if df is None or df.empty:
        return pd.DataFrame(columns=["Open","High","Low","Close","Volume"])
    # pykrx 컬럼 매핑
    colmap = {"시가":"Open","고가":"High","저가":"Low","종가":"Close","거래량":"Volume"}
    df = df.rename(columns={k:v for k,v in colmap.items() if k in df.columns})
    df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
    df = df[["Open","High","Low","Close","Volume"]].astype({"Open":float,"High":float,"Low":float,"Close":float,"Volume":"int64"})
    return df.sort_index()

# 캐시 + 증분 통합: 기존 호출부에서 쓰던 이름 유지
def get_ohlcv_safe(code: str, start, end) -> pd.DataFrame:
    start = pd.to_datetime(start).tz_localize(None).normalize()
    end   = pd.to_datetime(end).tz_localize(None).normalize()
    cached = load_cached(code)

    need_before = None
    need_after  = None

    if cached is None or cached.empty:
        # 캐시 없음 → 전기간 수집
        fetched = _fetch_ohlcv_krx(code, start, end)
        save_cache(code, fetched)
        log.info(f"[CACHE] seed {code}: {len(fetched)} rows")
        return fetched.loc[(fetched.index>=start) & (fetched.index<=end)]
    else:
        c0, c1 = cached.index.min(), cached.index.max()
        # 앞쪽 부족
        if start < c0:
            need_before = (start, min(c0 - timedelta(days=1), end))
        # 뒤쪽 부족
        if end > c1:
            need_after = (max(c1 + timedelta(days=1), start), end)

        parts = []
        if need_before and need_before[0] <= need_before[1]:
            fb = _fetch_ohlcv_krx(code, *need_before)
            parts.append(fb)
        parts.append(cached)
        if need_after and need_after[0] <= need_after[1]:
            fa = _fetch_ohlcv_krx(code, *need_after)
            parts.append(fa)

        merged = pd.concat([p for p in parts if p is not None and not p.empty]).sort_index()
        merged = merged[~merged.index.duplicated(keep="last")]
        # 캐시 갱신
        save_cache(code, merged)
        got = merged.loc[(merged.index>=start) & (merged.index<=end)]
        log.info(f"[CACHE] {code}: hit {len(cached)} rows, +before {0 if need_before is None else len(parts[0]) if parts and not parts[0].empty else 0}, +after {0 if need_after is None else len(parts[-1]) if parts and not parts[-1].empty else 0} → use {len(got)}")
        return got
