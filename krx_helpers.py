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

# 캐시 + 증분 통합: 기존 호출부에서 쓰던 이름 유지
# krx_helpers.py (상단 re-export 삭제하고 아래 함수로 대체)
def get_ohlcv_safe(*args, **kwargs):
    # 늦은 시점에 import하여 순환 임포트 방지
    from fetchers import get_ohlcv_safe as _impl
    return _impl(*args, **kwargs)
