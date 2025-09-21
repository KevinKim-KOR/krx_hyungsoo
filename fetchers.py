# fetchers.py

import datetime as dt
from typing import Optional, List, Union
import pandas as pd
import pytz
import requests
import yfinance as yf
from pykrx import stock as krx
from db import SessionLocal, Security, PriceDaily, PriceRealtime
from sqlalchemy import select, exists
from config import TIMEZONE
import time

SEOUL = pytz.timezone(TIMEZONE)

# ---------------------------
# Date normalization helpers
# ---------------------------

DateLike = Union[str, dt.date, dt.datetime, None]

def _to_date(d: DateLike) -> dt.date:
    """입력값을 datetime.date로 정규화.
       허용: 'auto' | 'yesterday' | 'today' | 'YYYY-MM-DD' | 'YYYYMMDD' | date | datetime | None
    """
    if d is None:
        return (dt.datetime.now(SEOUL) - dt.timedelta(days=1)).date()

    if isinstance(d, dt.datetime):
        return d.date()

    if isinstance(d, dt.date):
        return d

    if isinstance(d, str):
        s = d.strip().lower()
        if s in ("auto", "yesterday"):
            return (dt.datetime.now(SEOUL) - dt.timedelta(days=1)).date()
        if s == "today":
            return dt.datetime.now(SEOUL).date()

        # Try common formats
        for fmt in ("%Y-%m-%d", "%Y%m%d"):
            try:
                return dt.datetime.strptime(d, fmt).date()
            except ValueError:
                pass

    raise ValueError(f"Unsupported date input: {d!r}")

def _yyyymmdd(d: DateLike) -> str:
    """입력값을 YYYYMMDD 문자열로 변환."""
    return _to_date(d).strftime("%Y%m%d")

# ---------------------------
# Business logic
# ---------------------------

def ensure_yahoo_ticker(code: str, market: str) -> str:
    # KRX code -> Yahoo suffix
    suffix = ".KS" if market.upper() == "KS" else ".KQ"
    return f"{code}{suffix}"

def fetch_eod_krx(code: str, start: DateLike, end: DateLike) -> pd.DataFrame:
    """pykrx로 OHLCV 일별 수집 (양식: date, open, high, low, close, volume)"""
    df = krx.get_market_ohlcv_by_date(_yyyymmdd(start), _yyyymmdd(end), code)
    if df is None or df.empty:
        return pd.DataFrame(columns=["date","open","high","low","close","volume"])
    df = df.rename(columns={"시가":"open","고가":"high","저가":"low","종가":"close","거래량":"volume"})
    df = df.reset_index().rename(columns={"날짜":"date"})
    df["date"] = pd.to_datetime(df["date"]).dt.date
    return df[["date","open","high","low","close","volume"]]

def fetch_eod_yf(ticker: str, start: DateLike, end: DateLike) -> pd.DataFrame:
    time.sleep(1)  # 필요시 1~2초로 늘리세요
    start_d = _to_date(start)
    end_d = _to_date(end)
    data = yf.download(
        tickers=ticker,
        start=start_d,
        end=end_d + dt.timedelta(days=1),
        interval="1d",
        progress=False
    )
    if data is None or data.empty:
        return pd.DataFrame(columns=["date","open","high","low","close","volume"])
    df = data.reset_index()[["Date","Open","High","Low","Close","Volume"]]
    df.columns = ["date","open","high","low","close","volume"]
    df["date"] = pd.to_datetime(df["date"]).dt.date
    return df

def ingest_eod(date: DateLike = None):
    # 기존: date_norm = _to_date(date)
    # 변경: 최근 거래일로 보정
    date_norm = _last_trading_date_on_or_before(date if date is not None else "auto")
    session = SessionLocal()
    try:
        secs = session.execute(select(Security)).scalars().all()
        for s in secs:
            exists_q = session.query(
                exists().where((PriceDaily.code == s.code) & (PriceDaily.date == date_norm))
            ).scalar()
            if exists_q:
                continue

            # 1) KRX 시세 우선
            df = fetch_eod_krx(s.code, date_norm, date_norm)

            # 2) 보조: 야후
            if df.empty:
                ticker = s.yahoo_ticker or ensure_yahoo_ticker(s.code, s.market)
                df = fetch_eod_yf(ticker, date_norm, date_norm)

            if df.empty:
                continue

            row = df.iloc[0]
            session.add(PriceDaily(
                code=s.code, date=row["date"],
                open=float(row["open"]), high=float(row["high"]),
                low=float(row["low"]), close=float(row["close"]),
                volume=float(row.get("volume", 0) or 0)
            ))
        session.commit()
    finally:
        session.close()

def fetch_realtime_price(code: str) -> Optional[float]:
    """
    근실시간 단일 호가 (네이버 비공식 API, 변경될 수 있음).
    """
    try:
        url = f"https://polling.finance.naver.com/api/realtime?query=SERVICE_ITEM:{code}"
        r = requests.get(url, timeout=5)
        js = r.json()
        items = js.get("result", {}).get("areas", [])[0].get("datas", [])
        if not items:
            return None
        price = items[0].get("nv")  # 현재가
        return float(price) if price is not None else None
    except Exception:
        return None

def ingest_realtime_once(codes: Optional[List[str]] = None, ts: Optional[pd.Timestamp] = None):
    if ts is None:
        ts = pd.Timestamp.now(tz=SEOUL)
    session = SessionLocal()
    try:
        if codes is None:
            secs = session.execute(select(Security.code)).scalars().all()
            codes = list(secs)
        for code in codes:
            p = fetch_realtime_price(code)
            if p is None:
                continue
            session.add(PriceRealtime(code=code, ts=ts.to_pydatetime(), price=float(p)))
        session.commit()
    finally:
        session.close()


# fetchers.py 상단 부근
def _last_trading_date_on_or_before(d: DateLike) -> dt.date:
    """입력일이 휴일이면 과거로 내려가며 첫 거래일을 반환 (최대 10일 탐색)."""
    target = _to_date(d)
    for _ in range(10):
        # KRX 단일 종목으로 가볍게 조회(대표 코드: 005930)
        try:
            df = krx.get_market_ohlcv_by_date(
                target.strftime("%Y%m%d"), target.strftime("%Y%m%d"), "005930"
            )
            if df is not None and not df.empty:
                return target
        except Exception:
            pass
        target -= dt.timedelta(days=1)
    # 그래도 못 찾으면 그냥 입력일의 전 평일 반환
    while target.weekday() >= 5:  # 5,6 = 토,일
        target -= dt.timedelta(days=1)
    return target
