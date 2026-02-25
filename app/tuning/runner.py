# -*- coding: utf-8 -*-
"""
app/tuning/runner.py — P167-R 단일 trial 백테스트 실행기

Option A 강제: BacktestRunner.run()을 파이썬 내부에서 직접 호출.
subprocess, 파일 I/O 왕복 절대 금지.

레거시 참조: _archive/legacy_20260102/extensions/tuning/runner.py
"""
from __future__ import annotations
import logging
from datetime import date
from typing import Any, Dict, List

import numpy as np
import pandas as pd

from app.backtest.runners.backtest_runner import BacktestRunner

logger = logging.getLogger(__name__)


def run_single_trial(
    params: Dict[str, Any],
    price_data: pd.DataFrame,
    universe: List[str],
    start: date,
    end: date,
) -> Dict[str, Any]:
    """
    단일 trial 백테스트 실행 (Option A: 직접 호출).

    Args:
        params: 튜닝 파라미터 (momentum_period, stop_loss, max_positions)
        price_data: 프리페치된 OHLCV 데이터 (MultiIndex: code, date)
        universe: 종목 코드 리스트
        start: 시작일
        end: 종료일

    Returns:
        메트릭 딕셔너리: sharpe, mdd_pct, cagr, total_return, total_trades, ...
    """
    runner = BacktestRunner(
        initial_capital=10_000_000,
        commission_rate=0.00015,
        slippage_rate=0.001,
        max_positions=params["max_positions"],
        rebalance_frequency="daily",
        instrument_type="etf",
        enable_defense=False,
        min_holding_days=0,
    )

    target_weights = {t: 1.0 / len(universe) for t in universe}

    result = runner.run(
        price_data=price_data,
        target_weights=target_weights,
        start_date=start,
        end_date=end,
        ma_period=params["momentum_period"],
        rsi_period=14,
        stop_loss=params["stop_loss"],
        adx_threshold=20,
    )

    # ── Extract metrics from engine result ──
    engine_metrics = result.get("metrics", {})
    nav_history = result.get("nav_history", [])

    # Recompute Sharpe/MDD from nav_history (same logic as run_backtest.py)
    sharpe = 0.0
    mdd_pct = 0.0
    cagr = engine_metrics.get("cagr", 0.0)
    total_return = engine_metrics.get("total_return", 0.0)
    total_trades = engine_metrics.get("order_count", 0)

    if nav_history and len(nav_history) >= 2:
        navs = pd.Series([nav for _, nav in nav_history])

        # MDD
        cummax = navs.cummax()
        drawdown = navs / cummax - 1.0
        mdd_pct = abs(float(drawdown.min())) * 100

        # Sharpe
        rets = navs.pct_change().dropna()
        if len(rets) > 1 and float(rets.std()) > 0:
            sharpe = float(rets.mean() / rets.std()) * (252 ** 0.5)

    return {
        "sharpe": round(sharpe, 4),
        "mdd_pct": round(mdd_pct, 4),
        "cagr": round(cagr, 4),
        "total_return": round(total_return, 4),
        "total_trades": total_trades,
        "signal_days": engine_metrics.get("signal_days", 0),
    }
