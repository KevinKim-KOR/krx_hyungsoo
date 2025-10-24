# -*- coding: utf-8 -*-
"""
지표/스코어 계산 유틸 모듈

- 단일 종목 지표: SMA, EMA, RSI, ATR/ADX, MFI, Z-Score, Slope, N일 수익률, 변동성, MDD
- 거래대금 유동성 지표: 평균/표준편차, Z-Score
- 섹터 스코어: 섹터별 20/60일 수익률 기반 점수

입출력 규칙
- 단일 시리즈 입력: pandas.Series index=Date, values=float
- 멀티(OHLCV) 입력: pandas.Series(high/low/close/volume) 또는
  DataFrame[date, code, close, (high, low, volume 선택)]
"""

from __future__ import annotations
from typing import Dict, Iterable, Optional, Tuple
import numpy as np
import pandas as pd


# ---------- 기본 보조 함수 ----------

def _to_series(x) -> pd.Series:
    if isinstance(x, pd.Series):
        return x
    raise TypeError("pandas.Series를 입력하세요.")


# ---------- 단일 시계열 지표 ----------

def sma(series: pd.Series, n: int) -> pd.Series:
    s = _to_series(series).astype(float)
    return s.rolling(n, min_periods=n).mean()

def ema(series: pd.Series, n: int) -> pd.Series:
    s = _to_series(series).astype(float)
    return s.ewm(span=n, adjust=False, min_periods=n).mean()

def pct_change_n(series: pd.Series, n: int) -> pd.Series:
    s = _to_series(series).astype(float)
    return s.pct_change(n)

def zscore(series: pd.Series, n: int = 20) -> pd.Series:
    s = _to_series(series).astype(float)
    roll = s.rolling(n, min_periods=n)
    return (s - roll.mean()) / (roll.std(ddof=0) + 1e-12)

def slope(series: pd.Series, n: int = 20) -> pd.Series:
    """
    단순 선형회귀 기울기(정규화). +면 상승, -면 하락.
    """
    s = _to_series(series).astype(float)
    idx = np.arange(len(s))
    def _sl(x):
        y = x.values
        x_ = np.arange(len(y))
        if len(y) < 2:
            return np.nan
        # 표준화된 기울기
        denom = (x_.std() * (y.std() + 1e-12)) + 1e-12
        return np.cov(x_, y)[0, 1] / denom
    return s.rolling(n, min_periods=n).apply(_sl, raw=False)

def volatility(series: pd.Series, n: int = 20) -> pd.Series:
    """로그수익률 표준편차(연율화X)"""
    s = _to_series(series).astype(float)
    logret = np.log(s / s.shift(1))
    return logret.rolling(n, min_periods=n).std(ddof=0)

def rolling_max_drawdown(series: pd.Series) -> pd.Series:
    """
    시점별 MDD (0 또는 음수). series는 NAV 혹은 가격.
    """
    s = _to_series(series).astype(float)
    roll_max = s.cummax()
    dd = s / (roll_max + 1e-12) - 1.0
    return dd

# ---------- RSI / ATR / ADX / MFI ----------

def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    c = _to_series(close).astype(float)
    delta = c.diff()
    up = delta.clip(lower=0.0)
    down = (-delta).clip(lower=0.0)
    rs = up.ewm(alpha=1/n, adjust=False).mean() / (down.ewm(alpha=1/n, adjust=False).mean() + 1e-12)
    return 100 - (100 / (1 + rs))

def _true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    h, l, c = map(lambda x: _to_series(x).astype(float), (high, low, close))
    prev_close = c.shift(1)
    tr = pd.concat([(h - l).abs(), (h - prev_close).abs(), (l - prev_close).abs()], axis=1).max(axis=1)
    return tr

def atr(high: pd.Series, low: pd.Series, close: pd.Series, n: int = 14) -> pd.Series:
    tr = _true_range(high, low, close)
    return tr.ewm(alpha=1/n, adjust=False, min_periods=n).mean()

def adx(high: pd.Series, low: pd.Series, close: pd.Series, n: int = 14) -> pd.Series:
    """
    Welles Wilder ADX 구현(일반적 근사).
    """
    h, l, c = map(lambda x: _to_series(x).astype(float), (high, low, close))
    up = h.diff()
    dn = -l.diff()

    plus_dm = np.where((up > dn) & (up > 0), up, 0.0)
    minus_dm = np.where((dn > up) & (dn > 0), dn, 0.0)

    tr = _true_range(h, l, c)
    atr_ = tr.ewm(alpha=1/n, adjust=False, min_periods=n).mean() + 1e-12

    plus_di = pd.Series(100 * (pd.Series(plus_dm, index=h.index).ewm(alpha=1/n, adjust=False).mean() / atr_), index=h.index)
    minus_di = pd.Series(100 * (pd.Series(minus_dm, index=h.index).ewm(alpha=1/n, adjust=False).mean() / atr_), index=h.index)

    dx = ( (plus_di - minus_di).abs() / ((plus_di + minus_di).abs() + 1e-12) ) * 100
    adx_ = dx.ewm(alpha=1/n, adjust=False, min_periods=n).mean()
    return adx_

def mfi(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series, n: int = 14) -> pd.Series:
    """
    Money Flow Index
    """
    h, l, c, v = map(lambda x: _to_series(x).astype(float), (high, low, close, volume))
    tp = (h + l + c) / 3.0
    mf = tp * v
    sign = np.sign(tp.diff())
    pos_mf = mf.where(sign >= 0, 0.0)
    neg_mf = mf.where(sign < 0, 0.0)
    pos_roll = pos_mf.rolling(n, min_periods=n).sum()
    neg_roll = neg_mf.rolling(n, min_periods=n).sum() + 1e-12
    mfr = pos_roll / neg_roll
    return 100 - (100 / (1 + mfr))


# ---------- 유동성(거래대금) 관련 ----------

def turnover(close: pd.Series, volume: pd.Series) -> pd.Series:
    """거래대금 = 종가 * 거래량 (원화 기준이면 그대로, 달러면 환산 별도)"""
    c, v = _to_series(close).astype(float), _to_series(volume).astype(float)
    return c * v

def turnover_stats(close: pd.Series, volume: pd.Series, n: int = 20) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    최근 n일 평균/표준편차/ Z-Score (오늘 대비)
    """
    t = turnover(close, volume)
    roll = t.rolling(n, min_periods=n)
    mean = roll.mean()
    std = roll.std(ddof=0)
    z = (t - mean) / (std + 1e-12)
    return mean, std, z


# ---------- 섹터 스코어 ----------

def sector_score(
    prices_df: pd.DataFrame,
    sectors_map: Dict[str, str],
    win_short: int = 20,
    win_long: int = 60,
    weights: Tuple[float, float] = (0.5, 0.5),
) -> pd.DataFrame:
    """
    섹터별 모멘텀 스코어 계산
    입력:
      prices_df: DataFrame[date, code, close] (여러 종목)
      sectors_map: {code: sector}
    출력:
      DataFrame[sector, ret_short, ret_long, score] (마지막 날짜 기준)
    """
    if prices_df.empty:
        return pd.DataFrame(columns=["sector", "ret_short", "ret_long", "score"])

    df = prices_df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df["sector"] = df["code"].map(sectors_map).fillna("Unknown")

    last_date = df["date"].max()
    ref_short = last_date - pd.Timedelta(days=win_short)
    ref_long = last_date - pd.Timedelta(days=win_long)

    # 각 섹터의 대표가격: 섹터 내 종목 균등 평균
    wide = df.pivot(index="date", columns="code", values="close").sort_index().ffill()
    sec_cols = {}
    for code, sec in sectors_map.items():
        if code in wide.columns:
            sec_cols.setdefault(sec, []).append(code)

    sec_price = {}
    for sec, cols in sec_cols.items():
        if not cols:
            continue
        sec_price[sec] = wide[cols].mean(axis=1)
    if not sec_price:
        return pd.DataFrame(columns=["sector", "ret_short", "ret_long", "score"])

    sec_df = pd.DataFrame(sec_price)

    def _ret(series: pd.Series, d: pd.Timestamp) -> float:
        s = series.reindex(sec_df.index).ffill()
        if d not in s.index:
            # 직전 거래일로 대체
            s = s.dropna()
            if s.empty: 
                return np.nan
            return float(s.iloc[-1] / s.iloc[max(len(s)-win_short-1, 0)] - 1.0)
        idx = s.index.get_loc(d)
        base_idx = max(idx - win_short, 0)
        long_base_idx = max(idx - win_long, 0)
        return float(s.iloc[idx] / s.iloc[base_idx] - 1.0)

    rows = []
    for sec in sec_df.columns:
        s = sec_df[sec]
        # 실제 수익률 계산 (직전 n일 대비)
        short_ret = (s.iloc[-1] / s.iloc[max(len(s)-win_short-1, 0)]) - 1.0 if len(s) > win_short else np.nan
        long_ret  = (s.iloc[-1] / s.iloc[max(len(s)-win_long-1, 0)]) - 1.0 if len(s) > win_long  else np.nan
        score = weights[0]*(short_ret if pd.notna(short_ret) else 0.0) + \
                weights[1]*(long_ret  if pd.notna(long_ret)  else 0.0)
        rows.append({"sector": sec, "ret_short": short_ret, "ret_long": long_ret, "score": score})

    out = pd.DataFrame(rows).sort_values("score", ascending=False).reset_index(drop=True)
    return out
