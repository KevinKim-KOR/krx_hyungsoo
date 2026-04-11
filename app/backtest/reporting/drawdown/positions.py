#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app/backtest/reporting/drawdown/positions.py — daily per-ticker position 복원

P209-STEP9A drawdown 분석의 포지션 복원 단계. trades 를 replay 하여 각
영업일별 ticker 별 수량/시가총액/현금흐름을 복원한다.

단일 책임: trade log + close series → daily per-ticker value + cash_flow
R2 단계에서 drawdown_contribution.py god module 에서 분리된 모듈.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Tuple

import pandas as pd


def _build_close_series(price_data) -> Dict[str, pd.Series]:
    """MultiIndex(code, date) price_data에서 ticker별 close 시리즈 추출."""
    out: Dict[str, pd.Series] = {}
    if not isinstance(price_data.index, pd.MultiIndex):
        return out
    for code in price_data.index.get_level_values("code").unique():
        df = price_data.xs(code, level="code")
        col = None
        if "close" in df.columns:
            col = "close"
        elif "Close" in df.columns:
            col = "Close"
        if col is None:
            continue
        s = df[col].astype(float)
        if not isinstance(s.index, pd.DatetimeIndex):
            s.index = pd.to_datetime(s.index)
        out[code] = s.sort_index()
    return out


def reconstruct_daily_positions(
    trades: List[Any],
    nav_history: List[Tuple[Any, float]],
    close_by_code: Dict[str, pd.Series],
) -> List[Dict[str, Any]]:
    """trades를 replay하여 각 영업일별 per-ticker 수량/시가총액/현금흐름을 복원.

    반환: [{"date": str, "value": {code: float}, "cash_flow": {code: float}}, ...]
    - value: end-of-day mark-to-market (기존 + 신규 포지션 모두 포함)
    - cash_flow: 당일 매매로 인한 ticker별 현금 유출입
        (양수=순매수 cost, 음수=순매도 proceeds).
        return attribution 시 이 값을 P&L에서 차감해야 순수 mark-to-market
        수익 기여만 남는다.
    """
    if not nav_history:
        return []

    events_by_date: Dict[str, List[Any]] = defaultdict(list)
    for t in trades:
        events_by_date[str(t.date)].append(t)

    qtys: Dict[str, int] = defaultdict(int)
    daily: List[Dict[str, Any]] = []

    for d, _nav in nav_history:
        d_str = str(d)
        ts = pd.Timestamp(d_str)

        cash_flow: Dict[str, float] = defaultdict(float)
        # 거래 적용 (BUY 가산, SELL 차감) + ticker별 cash flow 누적
        for t in events_by_date.get(d_str, []):
            q = int(getattr(t, "quantity", 0))
            p = float(getattr(t, "price", 0.0))
            if t.action == "BUY":
                qtys[t.symbol] += q
                cash_flow[t.symbol] += q * p  # 순매수 cost (양수)
            elif t.action == "SELL":
                qtys[t.symbol] -= q
                if qtys[t.symbol] < 0:
                    qtys[t.symbol] = 0
                cash_flow[t.symbol] -= q * p  # 매도 proceeds (음수)

        # Mark-to-market
        vals: Dict[str, float] = {}
        for code, q in qtys.items():
            if q <= 0:
                continue
            s = close_by_code.get(code)
            if s is None or s.empty:
                continue
            try:
                idx = s.index.asof(ts)
            except (KeyError, TypeError):
                idx = None
            if idx is None or (hasattr(pd, "NaT") and idx is pd.NaT):
                continue
            try:
                price = float(s.loc[idx])
            except (KeyError, TypeError, ValueError):
                continue
            if price > 0:
                vals[code] = q * price

        daily.append(
            {
                "date": d_str,
                "value": vals,
                "cash_flow": dict(cash_flow),
            }
        )

    return daily
