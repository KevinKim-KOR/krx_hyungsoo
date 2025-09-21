import pandas as pd
from datetime import date
from pykrx import stock as krx

def _to_krx_code(ticker:str)->str:
    # '069500.KS' -> '069500', '069500' -> '069500'
    digits = "".join(ch for ch in ticker if ch.isdigit())
    return digits[:6] if digits else ticker

def get_ohlcv_safe(ticker:str, start, end):
    """
    ticker: '069500.KS' 또는 '069500'
    start/end: datetime.date 또는 datetime-like
    return: DataFrame index=DatetimeIndex, cols=[Open,High,Low,Close,Volume]
    """
    if not isinstance(start, pd.Timestamp): start = pd.Timestamp(start)
    if not isinstance(end, pd.Timestamp):   end   = pd.Timestamp(end)
    code = _to_krx_code(ticker)
    df = krx.get_market_ohlcv_by_date(start.strftime("%Y%m%d"),
                                      (end + pd.Timedelta(days=1)).strftime("%Y%m%d"),
                                      code)
    # KRX 컬럼 -> 표준화
    df = df.rename(columns={"시가":"Open","고가":"High","저가":"Low","종가":"Close","거래량":"Volume"})
    df.index = pd.to_datetime(df.index)
    return df[["Open","High","Low","Close","Volume"]].sort_index()
