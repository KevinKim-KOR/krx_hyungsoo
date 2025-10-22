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

# 캐시 + 증분 통합: 순환 참조 방지를 위해 직접 구현
def get_ohlcv_safe(ticker: str, start, end):
    """
    순환 참조 방지 버전 - providers.ohlcv_bridge 직접 사용
    """
    try:
        from providers.ohlcv_bridge import get_ohlcv_df
        return get_ohlcv_df(ticker, start, end)
    except Exception as e:
        log.warning(f"get_ohlcv_safe failed for {ticker}: {e}")
        return pd.DataFrame(columns=["Open","High","Low","Close","Volume"])
