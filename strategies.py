import pandas as pd
from typing import Dict, List, Sequence
from sqlalchemy import select
from db import SessionLocal, Security
from config import EXCLUDE_KEYWORDS, TOP_N, MOM_LOOKBACK_D, TREND_SMA_D, REGIME_TICKER_YF, REGIME_SMA_D
import yfinance as yf
from krx_helpers import get_ohlcv_safe

# --- 유틸 ---

def _name_excluded(name: str, excludes: Sequence[str]) -> bool:
    n = (name or "").lower()
    return any(kw.lower() in n for kw in excludes)

def load_etf_universe(session: SessionLocal, excludes: Sequence[str]=EXCLUDE_KEYWORDS) -> List[str]:
    """ETF만 선택 + 이름에 제외 키워드 포함되면 제외 → code 리스트 반환"""
    q = select(Security).where(Security.type=="ETF")
    secs = session.execute(q).scalars().all()
    codes = []
    for s in secs:
        if _name_excluded(s.name, excludes):
            continue
        codes.append(s.code)
    return sorted(list(set(codes)))

def market_regime_ok(end_date: pd.Timestamp) -> bool:
    """S&P500(야후 069500.KS)의 200일 단순이평 위인지 체크"""
    start = (end_date - pd.Timedelta(days=REGIME_SMA_D * 3)).date()
    df = get_ohlcv_safe(REGIME_TICKER_YF, start, end_date.date())+pd.Timedelta(days=1), interval="1d", progress=False)
    if df is None or df.empty:
        # 데이터 없으면 보수적으로 '중단' 판단
        return False
    close = df["Close"].dropna()
    if close.shape[0] < REGIME_SMA_D:
        return False
    sma = close.rolling(REGIME_SMA_D).mean()
    return float(close.iloc[-1]) >= float(sma.iloc[-1])

# --- 전략 본체 ---

def trend_following_etf(prices: pd.DataFrame,
                        end_date: pd.Timestamp,
                        top_n: int = TOP_N,
                        mom_lookback: int = MOM_LOOKBACK_D,
                        trend_sma: int = TREND_SMA_D) -> Dict[str, float]:
    """
    입력:
      prices: [code,date,close] (end_date까지 포함된 DB 추출 데이터)
      end_date: 신호 생성 기준일(리밸런스 시점)
    규칙:
      1) 개별 ETF close > 200일 SMA (추세 필터)
      2) 최근 126일(6개월) 모멘텀 상위 TOP_N
      3) 시장 레짐: 069500.KS close > 200SMA 아닐 경우 현금(빈 dict)
    반환: {code: weight} (균등비중)
    """
    # 시장 레짐 점검
    if not market_regime_ok(end_date):
        return {}  # 현금

    df = prices.copy()
    df = df[df["date"] <= end_date].copy()
    if df.empty:
        return {}

    # 피벗 (날짜 x 종목)
    wide = df.pivot(index="date", columns="code", values="close").sort_index().ffill()
    if wide.index.max() < end_date.normalize():
        # end_date 거래일이 아닐 수 있으니 직전 값으로 ffill된 상태면 OK
        pass

    # 추세 필터: close > SMA(200)
    sma = wide.rolling(trend_sma, min_periods=trend_sma).mean()
    trend_ok = (wide.iloc[-1] > sma.iloc[-1])  # 마지막 행 기준

    # 모멘텀: (종가 / n일전 종가) - 1
    if wide.shape[0] <= mom_lookback:
        return {}
    mom = (wide.iloc[-1] / wide.iloc[-1-mom_lookback]) - 1.0

    # 후보: 추세 통과 종목만
    candidates = mom[trend_ok.fillna(False)]
    if candidates.empty:
        return {}

    picks = candidates.sort_values(ascending=False).head(top_n).index.tolist()
    if not picks:
        return {}

    w = 1.0 / len(picks)
    return {c: w for c in picks}
