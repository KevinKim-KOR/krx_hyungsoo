#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app/run_backtest.py — P164 CLI 백테스트 진입점

실행:
  python -m app.run_backtest --mode quick
  python -m app.run_backtest --mode full
  python -m app.run_backtest --start 2024-01-01 --end 2025-12-31

데이터 소스:
  state/strategy_bundle/latest/strategy_bundle_latest.json → 유니버스, 파라미터

출력:
  reports/backtest/latest/backtest_result.json (atomic write)
  reports/backtest/snapshots/backtest_result_YYYYMMDD_HHMMSS.json
"""

from __future__ import annotations
import argparse
import json
import logging
import shutil
import sys
import tempfile
import traceback
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional  # noqa: F401

import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("app.run_backtest")

# ─── Paths ────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
BUNDLE_PATH = (
    PROJECT_ROOT
    / "state"
    / "strategy_bundle"
    / "latest"
    / "strategy_bundle_latest.json"
)
RESULT_LATEST = (
    PROJECT_ROOT / "reports" / "backtest" / "latest" / "backtest_result.json"
)
RESULT_SNAPSHOTS = PROJECT_ROOT / "reports" / "backtest" / "snapshots"


# ─── 1. Strategy Bundle → Params ──────────────────────────────────────────
def load_strategy_bundle() -> Dict[str, Any]:
    """strategy_bundle_latest.json 읽기"""
    if not BUNDLE_PATH.exists():
        raise FileNotFoundError(f"Strategy bundle not found: {BUNDLE_PATH}")
    with open(BUNDLE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


from app.utils.param_loader import load_params_strict  # noqa: E402


# ─── 2. Data Loading ──────────────────────────────────────────────────────
def load_price_data(
    tickers: List[str], start: date, end: date, data_source: str = "fdr"
) -> pd.DataFrame:
    """
    종목별 OHLCV 다운로드 → MultiIndex(code, date) DataFrame.
    """
    try:
        from app.backtest.infra.data_loader import prefetch_ohlcv
    except ImportError as e:
        logger.error(f"data_loader import failed: {e}")
        raise

    combined = prefetch_ohlcv(tickers, start, end, data_source=data_source)
    logger.info(
        f"[DATA] Loaded {len(combined)} rows "
        f"({combined.index.get_level_values('date').min().date()} ~ "
        f"{combined.index.get_level_values('date').max().date()})"
    )
    return combined


# ─── 3. Run Backtest ──────────────────────────────────────────────────────
def run_backtest(
    price_data: pd.DataFrame,
    params: Dict[str, Any],
    start: date,
    end: date,
    enable_regime: bool = False,
    fear_threshold_override: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """BacktestRunner 실행"""
    from app.backtest.runners.backtest_runner import BacktestRunner

    runner = BacktestRunner(
        initial_capital=10_000_000,
        commission_rate=0.00015,
        slippage_rate=0.001,
        max_positions=params["max_positions"],
        rebalance_frequency="daily",
        instrument_type="etf",
        enable_defense=enable_regime,
        min_holding_days=0,
    )

    # target_weights = 유니버스 equal weight
    universe = params["universe"]
    target_weights = {t: 1.0 / len(universe) for t in universe}

    # P184-Fix: Priority Enforcement
    portfolio_mode = params["portfolio_mode"]
    if portfolio_mode == "bucket_portfolio":
        effective_rebalance = params["rebalance"]
        trigger_source = "params.rebalance"
    else:
        effective_rebalance = params.get("rebalance_rule", params["rebalance"])
        trigger_source = "params.rebalance_rule"

    # P205-STEP5E: dynamic schedule resolver
    _universe_resolver = None
    _schedule_meta = {}
    if params.get("universe_mode") == "dynamic_etf_market":
        try:
            from app.scanner.schedule_builder import (
                build_dynamic_schedule,
                make_universe_resolver,
            )

            # OHLCV를 ticker별 DataFrame으로 변환
            ohlcv_by_ticker = {}
            if isinstance(price_data.index, pd.MultiIndex):
                for code in price_data.index.get_level_values("code").unique():
                    ohlcv_by_ticker[code] = price_data.xs(code, level="code")

            schedule = build_dynamic_schedule(
                start=start,
                end=end,
                rebalance_rule=effective_rebalance,
                ohlcv_full=ohlcv_by_ticker,
                ticker_name_map={},
            )
            _universe_resolver = make_universe_resolver(schedule)
            _schedule_meta = {
                "dynamic_execution": True,
                "rebalance_universe_count": schedule.get("rebalance_count", 0),
                "schedule_precalculated": True,
                "schedule_cache_hit": schedule.get("cache_hit", False),
                "schedule_cache_key": schedule.get("cache_key"),
                "dynamic_schedule_path": schedule.get(
                    "schedule_snapshot_path",
                    "reports/tuning/dynamic_universe_schedule_latest.json",
                ),
            }
            if schedule.get("entries"):
                _schedule_meta["first_rebalance_snapshot_id"] = schedule["entries"][
                    0
                ].get("snapshot_id")
                _schedule_meta["last_rebalance_snapshot_id"] = schedule["entries"][
                    -1
                ].get("snapshot_id")
            logger.info(
                f"[DYNAMIC] schedule 준비 완료: "
                f"{schedule.get('rebalance_count', 0)}개 rebalance"
            )
        except Exception as exc:
            logger.warning(f"[DYNAMIC] schedule 실패, 고정 모드: {exc}")

    # P206-STEP6D: VIX fear regime schedule
    _exo_regime_result = None
    if params.get("universe_mode") == "dynamic_etf_market":
        try:
            from app.backtest.strategy.exo_regime_filter import (
                build_fear_regime_schedule,
                fetch_vix_cached,
            )

            _vix_ohlcv = fetch_vix_cached(start, end)

            _rebal_dates = []
            if _universe_resolver and hasattr(_universe_resolver, "_schedule"):
                _sched_entries = _universe_resolver._schedule.get("entries", [])
                _rebal_dates = [
                    date.fromisoformat(e["rebalance_date"])
                    for e in _sched_entries
                    if "rebalance_date" in e
                ]
            if not _rebal_dates:
                _rebal_dates = [d.date() for d in pd.date_range(start, end, freq="MS")]

            from app.backtest.strategy.exo_regime_filter import (
                get_active_providers as _gap,
            )

            _fp = next(
                (p for p in _gap() if p["key"] == "fear_index_regime"),
                {},
            )
            _ft = _fp.get("thresholds", {})
            if fear_threshold_override:
                _ft = {**_ft, **fear_threshold_override}
            _exo_regime_result = build_fear_regime_schedule(
                vix_ohlcv=_vix_ohlcv,
                rebalance_dates=_rebal_dates,
                risk_on_max=_ft.get("risk_on_max", 20.0),
                risk_off_min=_ft.get("risk_off_min", 30.0),
                spike_threshold=_ft.get("spike_threshold", 0.20),
            )
            if (
                fear_threshold_override
                and "neutral_cash_pct" in fear_threshold_override
            ):
                _exo_regime_result["neutral_cash_pct"] = fear_threshold_override[
                    "neutral_cash_pct"
                ]
            # P206-STEP6G: hybrid (VIX + domestic 069500)
            from app.backtest.strategy.exo_regime_filter import (
                build_hybrid_regime_schedule,
            )

            _dom_ohlcv = None
            if isinstance(price_data.index, pd.MultiIndex):
                _codes = price_data.index.get_level_values("code")
                if "069500" in _codes:
                    _dom_ohlcv = price_data.xs("069500", level="code")

            _hybrid = build_hybrid_regime_schedule(
                fear_schedule=_exo_regime_result,
                domestic_ohlcv=_dom_ohlcv,
                rebalance_dates=_rebal_dates,
            )
            # hybrid가 있으면 이것을 exo_regime으로 사용
            _exo_regime_result = _hybrid
            _hybrid["safe_asset_ticker"] = "261240"
            _schedule_meta["exo_regime_applied"] = True
            _schedule_meta["exo_regime_risk_off_count"] = _hybrid.get(
                "risk_off_count", 0
            )
            _schedule_meta["exo_regime_neutral_count"] = _hybrid.get("neutral_count", 0)
        except Exception as exc:
            logger.warning(f"[HYBRID-REGIME] schedule 실패: {exc}")

    result = runner.run(
        price_data=price_data,
        target_weights=target_weights,
        start_date=start,
        end_date=end,
        ma_period=params["momentum_period"],
        volatility_period=params["volatility_period"],
        entry_threshold=params["entry_threshold"],
        rsi_period=14,
        stop_loss=params["stop_loss"],
        adx_threshold=params["adx_filter_min"],
        portfolio_mode=portfolio_mode,
        sell_mode=params["sell_mode"],
        rebalance_rule=effective_rebalance,
        buckets=params["buckets"],
        universe_resolver=_universe_resolver,
        universe_mode=params.get("universe_mode", "fixed_current"),
        exo_regime_schedule=_exo_regime_result,
    )

    # Attach trigger evidence
    result["_trigger_source"] = trigger_source
    result["_effective_rebalance"] = effective_rebalance
    result.update(_schedule_meta)
    result["_exo_regime_result"] = _exo_regime_result

    # 비교군 동적 계산 (동일 기간)
    if params.get("universe_mode") == "dynamic_etf_market":
        _baselines = []

        def _run_var(sched):
            _tw = {t: 1.0 / len(params["universe"]) for t in params["universe"]}
            from app.backtest.runners.backtest_runner import (
                BacktestRunner as _BR2,
            )

            _r2 = _BR2(
                initial_capital=10_000_000,
                commission_rate=0.00015,
                slippage_rate=0.001,
                max_positions=params["max_positions"],
                rebalance_frequency="daily",
                instrument_type="etf",
                enable_defense=enable_regime,
                min_holding_days=0,
            )
            return _r2.run(
                price_data=price_data,
                target_weights=_tw,
                start_date=start,
                end_date=end,
                ma_period=params["momentum_period"],
                volatility_period=params["volatility_period"],
                entry_threshold=params["entry_threshold"],
                rsi_period=14,
                stop_loss=params["stop_loss"],
                adx_threshold=params["adx_filter_min"],
                portfolio_mode=portfolio_mode,
                sell_mode=params["sell_mode"],
                rebalance_rule=effective_rebalance,
                buckets=params["buckets"],
                universe_resolver=_universe_resolver,
                universe_mode=params.get("universe_mode", "fixed_current"),
                exo_regime_schedule=sched,
            )

        try:
            # no regime
            _nr = _run_var(None)
            _nrf = format_result(
                _nr,
                params,
                start,
                end,
                price_data=price_data,
                run_mode="compare",
            )
            _baselines.append(
                {
                    "variant": "no_regime",
                    "cagr": _nrf["summary"].get("cagr"),
                    "mdd": _nrf["summary"].get("mdd"),
                    "sharpe": _nrf["summary"].get("sharpe"),
                    "trades": _nrf["meta"].get("total_trades", 0),
                }
            )
        except Exception:
            pass
        try:
            # VIX baseline
            from app.backtest.strategy.exo_regime_filter import (
                build_fear_regime_schedule as _bfs2,
            )

            _vb = _bfs2(
                vix_ohlcv=_vix_ohlcv,
                rebalance_dates=_rebal_dates,
                risk_on_max=20.0,
                risk_off_min=30.0,
                spike_threshold=0.20,
            )
            _vr = _run_var(_vb)
            _vrf = format_result(
                _vr,
                params,
                start,
                end,
                price_data=price_data,
                run_mode="compare",
            )
            _baselines.append(
                {
                    "variant": "vix_baseline",
                    "cagr": _vrf["summary"].get("cagr"),
                    "mdd": _vrf["summary"].get("mdd"),
                    "sharpe": _vrf["summary"].get("sharpe"),
                    "trades": _vrf["meta"].get("total_trades", 0),
                    "n": _vb.get("neutral_count", 0),
                    "ro": _vb.get("risk_off_count", 0),
                }
            )
        except Exception:
            pass
        try:
            # hybrid cash-only
            from app.backtest.strategy.exo_regime_filter import (
                build_hybrid_regime_schedule as _bh2,
                build_fear_regime_schedule as _bfs3,
                get_active_providers as _gap3,
            )

            _fp3 = next(
                (p for p in _gap3() if p["key"] == "fear_index_regime"),
                {},
            )
            _ft3 = _fp3.get("thresholds", {})
            _vf3 = _bfs3(
                vix_ohlcv=_vix_ohlcv,
                rebalance_dates=_rebal_dates,
                risk_on_max=_ft3.get("risk_on_max", 20.0),
                risk_off_min=_ft3.get("risk_off_min", 30.0),
                spike_threshold=_ft3.get("spike_threshold", 0.20),
            )
            _dom3 = None
            if isinstance(price_data.index, pd.MultiIndex):
                _c3 = price_data.index.get_level_values("code")
                if "069500" in _c3:
                    _dom3 = price_data.xs("069500", level="code")
            _co = _bh2(
                fear_schedule=_vf3,
                domestic_ohlcv=_dom3,
                rebalance_dates=_rebal_dates,
            )
            # no safe asset ticker
            _cor = _run_var(_co)
            _corf = format_result(
                _cor,
                params,
                start,
                end,
                price_data=price_data,
                run_mode="compare",
            )
            _baselines.append(
                {
                    "variant": "hybrid_cash_only",
                    "cagr": _corf["summary"].get("cagr"),
                    "mdd": _corf["summary"].get("mdd"),
                    "sharpe": _corf["summary"].get("sharpe"),
                    "trades": _corf["meta"].get("total_trades", 0),
                    "n": _co.get("neutral_count", 0),
                    "ro": _co.get("risk_off_count", 0),
                }
            )
        except Exception:
            pass
        result["_compare_baselines"] = _baselines

    return result


# ─── 4. Per-Ticker Buy&Hold Metrics ────────────────────────────────────────
def compute_buyhold_metrics(
    closes: pd.Series, start: date, end: date
) -> Dict[str, Any]:
    """
    단일 종목 Buy&Hold 기준 cagr, mdd, win_rate 계산.
    closes: DatetimeIndex 종가 시리즈
    """
    if closes is None or len(closes) < 2:
        return {"cagr": 0.0, "mdd": 0.0, "win_rate": 0.0}

    closes = closes.sort_index().dropna()
    if len(closes) < 2:
        return {"cagr": 0.0, "mdd": 0.0, "win_rate": 0.0}

    first_val = float(closes.iloc[0])
    last_val = float(closes.iloc[-1])

    # CAGR
    total_days = (closes.index[-1] - closes.index[0]).days
    years = total_days / 365.25 if total_days > 0 else 1.0
    if first_val > 0 and years > 0:
        cagr = ((last_val / first_val) ** (1.0 / years) - 1.0) * 100
    else:
        cagr = 0.0

    # MDD
    cummax = closes.cummax()
    drawdown = closes / cummax - 1.0
    mdd = abs(float(drawdown.min())) * 100  # 양수 %

    # Win Rate (일별 양의 수익률 비율)
    daily_ret = closes.pct_change().dropna()
    if len(daily_ret) > 0:
        win_rate = float((daily_ret > 0).sum()) / len(daily_ret) * 100
    else:
        win_rate = 0.0

    return {
        "cagr": round(cagr, 4),
        "mdd": round(mdd, 4),
        "win_rate": round(win_rate, 2),
    }


# ─── 5. Format Output ─────────────────────────────────────────────────────
def format_result(
    result: Dict[str, Any],
    params: Dict[str, Any],
    start: date,
    end: date,
    price_data: pd.DataFrame = None,
    param_source: Dict[str, str] = None,
    run_mode: str = "quick",
) -> Dict[str, Any]:
    """
    결과를 현행 소비자 스키마로 포맷팅.
    P165: equity_curve/daily_returns 포함, ticker별 Buy&Hold 독립 계산.

    필수 최상위 키: summary, tickers, top_performers, meta
    """
    metrics = result.get("metrics", {})

    # ── Portfolio Equity Curve from nav_history ──
    nav_history = result.get("nav_history", [])
    equity_curve = []
    daily_returns = []

    if nav_history and len(nav_history) >= 2:
        for d, nav in nav_history:
            equity_curve.append(
                {
                    "date": str(d),
                    "equity": round(float(nav), 2),
                }
            )

        # daily returns from equity curve
        for i in range(1, len(nav_history)):
            prev_nav = nav_history[i - 1][1]
            curr_nav = nav_history[i][1]
            ret = (curr_nav / prev_nav - 1.0) if prev_nav > 0 else 0.0
            daily_returns.append(
                {
                    "date": str(nav_history[i][0]),
                    "ret": round(float(ret), 6),
                }
            )

    # ── Recompute MDD/Sharpe from equity curve ──
    sharpe_reason = None
    mdd_reason = None

    if len(equity_curve) >= 2:
        navs = pd.Series([e["equity"] for e in equity_curve]).dropna()

        # MDD (daily NAV 기준, NaN 제거 후)
        if len(navs) >= 2:
            cummax = navs.cummax()
            drawdown = navs / cummax - 1.0
            mdd_val = abs(float(drawdown.min())) * 100
            if mdd_val == 0.0:
                mdd_reason = "no_drawdown_from_peak"
        else:
            mdd_val = 0.0
            mdd_reason = "insufficient_valid_nav"

        # Sharpe
        rets = navs.pct_change().dropna()
        if len(rets) > 1 and float(rets.std()) > 0:
            sharpe_val = float(rets.mean() / rets.std()) * (252**0.5)
        else:
            sharpe_val = 0.0
            sharpe_reason = "std_zero" if len(rets) > 1 else "insufficient_data"
    else:
        mdd_val = 0.0
        sharpe_val = 0.0
        mdd_reason = "no_nav_history"
        sharpe_reason = "no_nav_history"

    # summary (override engine metrics with recomputed values)
    # CAGR/total_return: equity_curve 기반 재계산 (NaN-safe)
    import math

    cagr_val = metrics.get("cagr", 0.0)
    total_return_val = metrics.get("total_return", 0.0)
    cagr_reason = None
    total_return_reason = None
    if len(equity_curve) >= 2:
        nav_start = equity_curve[0]["equity"]
        # 마지막 유효 NAV 사용 (NaN 방어)
        nav_end = nav_start
        for e in reversed(equity_curve):
            if e["equity"] == e["equity"]:  # not NaN
                nav_end = e["equity"]
                break
        if nav_start > 0:
            total_return_val = (nav_end / nav_start - 1.0) * 100
            date_start = equity_curve[0]["date"]
            date_end = equity_curve[-1]["date"]
            cal_days = (
                date.fromisoformat(date_end) - date.fromisoformat(date_start)
            ).days
            yrs = cal_days / 365.25
            if yrs > 0:
                cagr_val = ((nav_end / nav_start) ** (1.0 / yrs) - 1.0) * 100
            else:
                cagr_val = None
                cagr_reason = "period_too_short"

    # fail-closed: NaN/inf 시 None으로 표기 (0.0으로 위장 금지)
    if cagr_val is not None and (math.isnan(cagr_val) or math.isinf(cagr_val)):
        cagr_reason = "cagr_not_computable"
        cagr_val = None
    if total_return_val is not None and (
        math.isnan(total_return_val) or math.isinf(total_return_val)
    ):
        total_return_reason = "total_return_not_computable"
        total_return_val = None

    summary = {
        "cagr": round(cagr_val, 4) if cagr_val is not None else None,
        "mdd": round(mdd_val, 4),
        "sharpe": round(sharpe_val, 4),
        "total_return": (
            round(total_return_val, 4) if total_return_val is not None else None
        ),
    }

    # ── Ticker-Level Buy&Hold Metrics ──
    tickers_out = {}
    if price_data is not None and isinstance(price_data.index, pd.MultiIndex):
        for t in params["universe"]:
            try:
                code_data = price_data.xs(t, level="code")
                if "close" in code_data.columns:
                    closes = code_data["close"]
                elif "Close" in code_data.columns:
                    closes = code_data["Close"]
                else:
                    closes = pd.Series(dtype=float)
                bh = compute_buyhold_metrics(closes, start, end)
                tickers_out[t] = {
                    "cagr": bh["cagr"],
                    "mdd": bh["mdd"],
                    "win_rate": bh["win_rate"],
                    "score": None,
                }
            except (KeyError, Exception) as e:
                logger.warning(f"[TICKER] {t} Buy&Hold calc failed: {e}")
                tickers_out[t] = {
                    "cagr": 0.0,
                    "mdd": 0.0,
                    "win_rate": 0.0,
                    "score": None,
                }
    else:
        # fallback: portfolio-level copy (should not happen)
        for t in params["universe"]:
            tickers_out[t] = {
                "cagr": metrics.get("cagr", 0.0),
                "mdd": round(mdd_val, 4),
                "win_rate": None,
                "score": None,
            }

    # top_performers (ticker cagr 내림차순, top 5)
    sorted_tickers = sorted(
        tickers_out.items(), key=lambda x: x[1]["cagr"], reverse=True
    )
    top_performers = [{"ticker": t, "cagr": v["cagr"]} for t, v in sorted_tickers[:5]]

    try:
        from app.backtest.infra.data_loader import get_telemetry

        telemetry = get_telemetry()
    except ImportError:
        telemetry = {}

    now_kst = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+09:00")

    meta = {
        "asof": now_kst,
        "start_date": str(start),
        "end_date": str(end),
        "mode": run_mode,
        "universe": params["universe"],
        "universe_mode": params.get("universe_mode", "fixed_current"),
        "universe_size": len(params["universe"]),
        "used_universe_snapshot_id": params.get("universe_snapshot_id"),
        "used_universe_snapshot_sha256": params.get("universe_snapshot_sha256"),
        "dynamic_execution": result.get("dynamic_execution", False),
        "rebalance_universe_count": result.get("rebalance_universe_count", 0),
        "schedule_precalculated": result.get("schedule_precalculated", False),
        "schedule_cache_hit": result.get("schedule_cache_hit"),
        "schedule_cache_key": result.get("schedule_cache_key"),
        "dynamic_schedule_path": result.get("dynamic_schedule_path"),
        "first_rebalance_snapshot_id": result.get("first_rebalance_snapshot_id"),
        "last_rebalance_snapshot_id": result.get("last_rebalance_snapshot_id"),
        "rebalance_universe_changes": result.get("rebalance_universe_changes", 0),
        "allocation_mode": result.get("allocation_mode", "bucket_portfolio"),
        "bucket_bypass_applied": result.get("bucket_bypass_applied", False),
        "exo_regime_applied": result.get("exo_regime_applied", False),
        "exo_regime_risk_off_count": result.get("exo_regime_risk_off_count", 0),
        "exo_regime_neutral_count": result.get("exo_regime_neutral_count", 0),
        "engine_version": "app.backtest.v2",
        "total_trades": metrics.get("order_count", 0),
        "buy_trade_count": sum(
            1 for t in result.get("trades", []) if t.action == "BUY"
        ),
        "sell_trade_count": sum(
            1 for t in result.get("trades", []) if t.action == "SELL"
        ),
        "trade_count_valid": result.get("trades") is not None,
        "signal_days": metrics.get("signal_days", 0),
        "param_source": param_source,
        "data_source_used": params["data_source"],
        "download_count": telemetry.get("download_count", 0),
        "cache_hit_count": telemetry.get("cache_hit_count", 0),
        "fallback_count": telemetry.get("fallback_count", 0),
        "used_params_5axes": {
            "momentum_period": params["momentum_period"],
            "volatility_period": params["volatility_period"],
            "entry_threshold": params["entry_threshold"],
            "exit_threshold": params["stop_loss"],
            "max_positions": params["max_positions"],
        },
        "params_used": {
            "momentum_period": params["momentum_period"],
            "volatility_period": params["volatility_period"],
            "entry_threshold": params["entry_threshold"],
            "stop_loss": params["stop_loss"],
            "max_positions": params["max_positions"],
            "portfolio_mode": params["portfolio_mode"],
            "sell_mode": params["sell_mode"],
            "rebalance": params["rebalance"],
            "buckets_used": [
                {
                    "name": b["name"],
                    "weight": b["weight"],
                    "universe_size": len(b["universe"]),
                }
                for b in params["buckets"]
            ],
        },
        "equity_curve": equity_curve,
        "daily_returns": daily_returns,
        # P183 Trade Evidence
        "trade_histogram_by_date": result.get("trade_histogram_by_date", {}),
        "trade_reason_counts": result.get("trade_reason_counts", {}),
        "trade_dates_top10": result.get("trade_dates_top10", []),
        "rebalance_cluster_check": result.get("rebalance_cluster_check", {}),
        # P184-Fix Evidence
        "rebalance_trigger_source": result.get("_trigger_source", "unknown"),
        "rebalance_effective": result.get("_effective_rebalance", {}),
    }

    # conditional reason fields
    if sharpe_reason:
        meta["sharpe_reason"] = sharpe_reason
    if mdd_reason:
        meta["mdd_reason"] = mdd_reason
    if cagr_reason:
        meta["cagr_reason"] = cagr_reason
    if total_return_reason:
        meta["total_return_reason"] = total_return_reason

    return {
        "summary": summary,
        "tickers": tickers_out,
        "top_performers": top_performers,
        "meta": meta,
    }


# ─── 6. Atomic Write ──────────────────────────────────────────────────────
def atomic_write_result(data: Dict[str, Any]) -> None:
    """Atomic write: tmp → rename → snapshot copy"""
    RESULT_LATEST.parent.mkdir(parents=True, exist_ok=True)
    RESULT_SNAPSHOTS.mkdir(parents=True, exist_ok=True)

    content = json.dumps(data, indent=2, ensure_ascii=False)

    # Atomic write to latest
    tmp_fd = tempfile.NamedTemporaryFile(
        mode="w",
        dir=RESULT_LATEST.parent,
        suffix=".tmp",
        delete=False,
        encoding="utf-8",
    )
    try:
        tmp_fd.write(content)
        tmp_fd.close()
        tmp_path = Path(tmp_fd.name)
        # On Windows, need to remove target first
        if RESULT_LATEST.exists():
            RESULT_LATEST.unlink()
        tmp_path.rename(RESULT_LATEST)
        logger.info(f"[WRITE] latest → {RESULT_LATEST}")
    except Exception:
        Path(tmp_fd.name).unlink(missing_ok=True)
        raise

    # Snapshot copy
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    snap_path = RESULT_SNAPSHOTS / f"backtest_result_{ts}.json"
    shutil.copy2(RESULT_LATEST, snap_path)
    logger.info(f"[WRITE] snapshot → {snap_path}")


# ─── 7. Main ──────────────────────────────────────────────────────────────
def run_cli_backtest(
    mode: str = "quick", start_str: str = None, end_str: str = None
) -> bool:
    """Run backtest programmatically. Returns True if successful."""
    logger.info("=" * 60)
    logger.info("P165 Backtest Engine — CLI")
    logger.info("=" * 60)

    # 1. Load strategy params via SSOT > Bundle
    try:
        params, param_source = load_params_strict()
    except Exception as e:
        logger.error(f"Strategy params load failed: {e}")
        return False

    logger.info(f"[PARAMS] src={param_source['path']}")
    logger.info(
        f"[PARAMS] universe={params['universe']}, ma={params['momentum_period']}, "
        f"vol={params['volatility_period']}, entry={params['entry_threshold']}, "
        f"max_pos={params['max_positions']}, stop_loss={params['stop_loss']}"
    )

    # 2. Determine date range
    today = date.today()
    if start_str and end_str:
        start = date.fromisoformat(start_str)
        end = date.fromisoformat(end_str)
    elif mode == "quick":
        start = today - timedelta(days=180)
        end = today - timedelta(days=1)
    else:  # full
        start = today - timedelta(days=365 * 3)
        end = today - timedelta(days=1)

    logger.info(f"[DATE] {start} → {end} (mode={mode})")

    # 3. Load price data (+ 069500 for domestic shock sensor)
    _fetch_tickers = list(params["universe"])
    if params.get("universe_mode") == "dynamic_etf_market":
        if "069500" not in _fetch_tickers:
            _fetch_tickers.append("069500")
        # 달러 ETF (안전자산)
        if "261240" not in _fetch_tickers:
            _fetch_tickers.append("261240")
    try:
        price_data = load_price_data(
            _fetch_tickers, start, end, data_source=params["data_source"]
        )
    except Exception as e:
        logger.error(f"Data loading failed: {e}")
        return False

    # 4. Run backtest
    enable_regime = mode == "full"
    try:
        result = run_backtest(
            price_data, params, start, end, enable_regime=enable_regime
        )
    except Exception as e:
        logger.error(f"Backtest execution failed: {e}")
        traceback.print_exc()
        return False

    # 5. Format and write (pass param_source)
    formatted = format_result(
        result,
        params,
        start,
        end,
        price_data=price_data,
        param_source=param_source,
        run_mode=mode,
    )
    # 5b. Dynamic execution trace + zero-trade diagnostic
    _trace = result.get("_rebalance_trace", [])
    if _trace and params.get("universe_mode") == "dynamic_etf_market":
        import csv as _csv

        trace_dir = RESULT_LATEST.parent
        trace_json = trace_dir / "dynamic_execution_trace_latest.json"
        trace_csv = trace_dir / "dynamic_execution_trace_latest.csv"
        trace_json.write_text(
            json.dumps(_trace, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        if _trace:
            with open(trace_csv, "w", encoding="utf-8", newline="") as f:
                w = _csv.DictWriter(f, fieldnames=_trace[0].keys())
                w.writeheader()
                w.writerows(_trace)

        # P205-STEP5E3: order_generation_trace 파일 생성
        _ogt_json = trace_dir / "order_generation_trace_latest.json"
        _ogt_csv = trace_dir / "order_generation_trace_latest.csv"
        _ogt_rows = []
        for t in _trace:
            _ogt_rows.append(
                {
                    "rebalance_date": t.get("rebalance_date"),
                    "snapshot_id": t.get("snapshot_id"),
                    "allocation_mode": t.get("allocation_mode", ""),
                    "allocation_path": t.get("allocation_mode", ""),
                    "bucket_bypass_applied": t.get("bucket_bypass_applied", False),
                    "selected_count": t.get("selected_count", 0),
                    "tradable_count": t.get("tradable_count", 0),
                    "entry_pass_count": t.get("entry_pass_count", 0),
                    "candidate_after_dedup_count": t.get(
                        "candidate_after_dedup_count", 0
                    ),
                    "candidate_after_hold_filter_count": t.get(
                        "candidate_after_hold_filter_count", 0
                    ),
                    "candidate_after_budget_filter_count": t.get(
                        "candidate_after_budget_filter_count", 0
                    ),
                    "candidate_after_position_limit_count": t.get(
                        "candidate_after_position_limit_count", 0
                    ),
                    "selected_pool_size_before_allocation": t.get(
                        "selected_pool_size_before_allocation", 0
                    ),
                    "candidate_after_allocation_filter_count": t.get(
                        "candidate_after_allocation_filter_count", 0
                    ),
                    "orders_created_count": t.get("orders_created_count", 0),
                    "buy_filled_count": t.get("buy_filled_count", 0),
                    "blocked_reason_counts": t.get("blocked_reason_counts", {}),
                    "dominant_block_reason": t.get("dominant_block_reason", ""),
                    "dominant_block_detail": t.get("dominant_block_detail", ""),
                    "regime": t.get("regime", ""),
                    "position_ratio": t.get("position_ratio", 1.0),
                }
            )
        _ogt_json.write_text(
            json.dumps(_ogt_rows, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        if _ogt_rows:
            # CSV: blocked_reason_counts를 문자열로 변환
            _csv_rows = []
            for r in _ogt_rows:
                row = dict(r)
                row["blocked_reason_counts"] = json.dumps(
                    row["blocked_reason_counts"], ensure_ascii=False
                )
                _csv_rows.append(row)
            with open(_ogt_csv, "w", encoding="utf-8", newline="") as f:
                w = _csv.DictWriter(f, fieldnames=_csv_rows[0].keys())
                w.writeheader()
                w.writerows(_csv_rows)
        logger.info(f"[WRITE] order_generation_trace → {_ogt_json}")

        # 집계 메타 (P205-STEP5E3: pipeline counters 포함)
        _totals = {
            "total_rebalance_points": result.get("total_rebalance_points", 0),
            "total_selected_tickers_seen": result.get("total_selected_tickers_seen", 0),
            "total_tradable_tickers_seen": result.get("total_tradable_tickers_seen", 0),
            "total_entry_pass_count": result.get("total_entry_pass_count", 0),
            "total_candidate_after_dedup": result.get("total_candidate_after_dedup", 0),
            "total_candidate_after_hold_filter": result.get(
                "total_candidate_after_hold_filter", 0
            ),
            "total_candidate_after_budget_filter": result.get(
                "total_candidate_after_budget_filter", 0
            ),
            "total_candidate_after_position_limit": result.get(
                "total_candidate_after_position_limit", 0
            ),
            "total_orders_created": result.get("total_orders_created", 0),
            "total_buy_filled": result.get("total_buy_filled", 0),
            "total_sell_filled": result.get("total_sell_filled", 0),
        }
        formatted["meta"].update(_totals)

        # P205-STEP5E3: zero-trade 진단 세분화
        _blocked_totals = result.get("blocked_reason_totals", {})
        if _totals["total_buy_filled"] == 0 and _totals["total_orders_created"] == 0:
            if _totals["total_entry_pass_count"] == 0:
                root = "entry_filter_blocked_all"
                root_detail = "entry 조건 통과 종목 0건"
            elif _totals["total_tradable_tickers_seen"] == 0:
                root = "all_selected_nontradable"
                root_detail = "선택 종목 전부 거래불가"
            elif _totals["total_selected_tickers_seen"] == 0:
                root = "schedule_not_applied"
                root_detail = "schedule에서 선택된 종목 0"
            elif _blocked_totals:
                # 지배적 차단 사유 결정
                root = max(_blocked_totals, key=_blocked_totals.get)
                root_detail = (
                    f"{root}={_blocked_totals[root]}"
                    f" (전체 entry_pass={_totals['total_entry_pass_count']})"
                )
            else:
                root = "order_generation_blocked"
                root_detail = "차단 사유 미상"
            formatted["meta"]["zero_trade_diagnostic"] = True
            formatted["meta"]["zero_trade_root_cause"] = root
            formatted["meta"]["zero_trade_root_detail"] = root_detail
            formatted["meta"]["blocked_reason_totals"] = _blocked_totals

            # 차단 단계 결정
            _block_stage = "unknown"
            if _totals["total_candidate_after_dedup"] == 0:
                _block_stage = "dedup"
            elif _totals["total_candidate_after_budget_filter"] == 0:
                _block_stage = "weight_scaling"
            elif _totals["total_candidate_after_position_limit"] == 0:
                _block_stage = "budget_filter"
            elif _totals["total_orders_created"] == 0:
                _block_stage = "position_limit"
            formatted["meta"]["zero_trade_block_stage"] = _block_stage
        else:
            formatted["meta"]["zero_trade_diagnostic"] = False

        # blocked_reason_totals를 항상 기록
        if _blocked_totals:
            formatted["meta"]["blocked_reason_totals"] = _blocked_totals
            formatted["meta"]["dominant_order_block_reason"] = max(
                _blocked_totals, key=_blocked_totals.get
            )

        # dynamic_execution_valid 검증
        dyn_valid = (
            formatted["meta"].get("dynamic_execution") is True
            and formatted["meta"].get("rebalance_universe_count", 0) >= 2
            and formatted["meta"].get("dynamic_schedule_path")
            and formatted["meta"].get("first_rebalance_snapshot_id")
            and formatted["meta"].get("last_rebalance_snapshot_id")
        )
        formatted["meta"]["dynamic_execution_valid"] = bool(dyn_valid)
        formatted["meta"]["resolver_mode"] = "schedule_lookup"

    # P206-STEP6G: hybrid regime 산출물 생성
    _exo_regime_result = result.get("_exo_regime_result")
    if _exo_regime_result and params.get("universe_mode") == "dynamic_etf_market":
        import csv as _csv2

        _regime_dir = PROJECT_ROOT / "reports" / "tuning"
        _regime_dir.mkdir(parents=True, exist_ok=True)

        _sched_data = _exo_regime_result.get("schedule", {})
        _prov_states = _exo_regime_result.get("provider_states", {})
        _prov_vals = _exo_regime_result.get("provider_values", {})
        _last_date = max(_sched_data.keys()) if _sched_data else None
        _latest_state = (
            _sched_data.get(_last_date, "risk_on") if _last_date else "risk_on"
        )
        _last_ps = _prov_states.get(_last_date, {}) if _last_date else {}
        _last_pv = _prov_vals.get(_last_date, {}) if _last_date else {}
        _verdict_asof = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+09:00")
        _n_count = _exo_regime_result.get("neutral_count", 0)
        _ro_count = _exo_regime_result.get("risk_off_count", 0)
        _ri_count = _exo_regime_result.get("risk_on_count", 0)

        # hybrid_regime_verdict_latest.json
        _verdict = {
            "asof": _verdict_asof,
            "global_state": _last_ps.get("global", "N/A"),
            "domestic_state": _last_ps.get("domestic", "N/A"),
            "aggregate_state": _latest_state,
            "policy_applied": (
                "hard_gate"
                if _latest_state == "risk_off"
                else "soft_gate" if _latest_state == "neutral" else "none"
            ),
            "target_cash_pct": (
                1.0
                if _latest_state == "risk_off"
                else 0.5 if _latest_state == "neutral" else 0.0
            ),
            "global_source_timestamp": _last_pv.get("global_source_date"),
            "domestic_source_timestamp": _last_pv.get("domestic_source_date"),
            "checkpoint_id": "K6",
            "regime_valid": _exo_regime_result.get("regime_valid", False),
            "error_code": _exo_regime_result.get("regime_error_code"),
            "risk_on_count": _ri_count,
            "neutral_count": _n_count,
            "risk_off_count": _ro_count,
        }
        (_regime_dir / "hybrid_regime_verdict_latest.json").write_text(
            json.dumps(_verdict, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        # hybrid_regime_schedule_latest.json/csv
        _sched_rows = []
        for rd, rs in _sched_data.items():
            _ps = _prov_states.get(rd, {})
            _pv = _prov_vals.get(rd, {})
            _tcp = 1.0 if rs == "risk_off" else 0.5 if rs == "neutral" else 0.0
            _sched_rows.append(
                {
                    "date": rd,
                    "checkpoint_id": "K6",
                    "global_state": _ps.get("global", ""),
                    "domestic_state": _ps.get("domestic", ""),
                    "aggregate_state": rs,
                    "gate_applied": rs in ("risk_off", "neutral"),
                    "target_cash_pct": _tcp,
                    "vix_value": _pv.get("vix_value"),
                    "preopen_return": _pv.get("preopen_return"),
                    "intraday_return": _pv.get("intraday_return"),
                    "domestic_eval_mode": _pv.get("domestic_eval_mode", ""),
                    "global_source_ts": _pv.get("global_source_date"),
                    "domestic_source_ts": _pv.get("domestic_source_date"),
                }
            )
        (_regime_dir / "hybrid_regime_schedule_latest.json").write_text(
            json.dumps(_sched_rows, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        if _sched_rows:
            _csv_p = _regime_dir / "hybrid_regime_schedule_latest.csv"
            with open(_csv_p, "w", encoding="utf-8", newline="") as f:
                w = _csv2.DictWriter(f, fieldnames=_sched_rows[0].keys())
                w.writeheader()
                w.writerows(_sched_rows)

        # hybrid_regime_reason_latest.md
        _g_state_last = _last_ps.get("global", "N/A")
        _d_state_last = _last_ps.get("domestic", "N/A")
        _trigger = "없음"
        if _latest_state == "risk_off":
            if _g_state_last == "risk_off" and _d_state_last == "risk_off":
                _trigger = "글로벌+국내 동시 risk_off"
            elif _g_state_last == "risk_off":
                _trigger = "글로벌(VIX) 단독 트리거"
            else:
                _trigger = "국내(069500) 단독 트리거"
        elif _latest_state == "neutral":
            if _g_state_last == "neutral":
                _trigger = "글로벌(VIX) neutral"
            else:
                _trigger = "국내(069500) neutral"
        _reason_md = [
            "# Hybrid Regime 판정 사유",
            "",
            "## 최신 판정",
            f"- 글로벌 상태: {_g_state_last}",
            f"- 국내 상태: {_d_state_last}",
            f"- 통합 상태: {_latest_state}",
            f"- 트리거 센서: {_trigger}",
            "- 판정 유형: 장전 기본 + 장중 일봉 근사",
            "",
            "## Sensor 구성",
            "1. Global: 미국 VIX (^VIX) — 미국 T종가 → 한국 T+1",
            "2. Domestic: 069500 전일 수익률 — 전일 확정 종가 기준",
            "",
            "## 통합 규칙",
            "- 한쪽이라도 risk_off → risk_off",
            "- 한쪽만 neutral → neutral",
            "- neutral+neutral → neutral (과도한 승격 금지)",
            "- 둘 다 risk_on → risk_on",
            "",
            "## 결과 요약",
            f"- Risk-On: {_ri_count}회",
            f"- Neutral: {_n_count}회",
            f"- Risk-Off: {_ro_count}회",
            "",
            "## 한계",
            "- 백테스트: 일봉 근사 (장중 체크포인트는 당일 종가로 근사)",
            "- 장중 대응: 하루 4~6회 체크포인트형 모델",
            "- 실시간 상시 추적 아님",
        ]
        (_regime_dir / "hybrid_regime_reason_latest.md").write_text(
            "\n".join(_reason_md), encoding="utf-8"
        )
        # hybrid_policy_compare.csv — 동일 기간 동적 비교
        _bd_cagr = round(formatted["summary"].get("cagr") or 0, 2)
        _bd_mdd = round(formatted["summary"].get("mdd") or 0, 2)
        _bd_sharpe = round(formatted["summary"].get("sharpe") or 0, 4)
        _bd_trades = formatted["meta"].get("total_trades", 0)
        _bd_safe_cnt = _n_count + _ro_count
        _bd_verdict = "PROMOTE" if _bd_cagr > 15 and _bd_mdd < 10 else "REJECT"
        _total_rebal = max(len(_sched_data), 1)

        # 비교군: run_backtest에서 동적 계산된 baselines 사용
        _baselines = result.get("_compare_baselines", [])

        _compare = []
        _dom_map = {
            "no_regime": "N/A",
            "vix_baseline": "N/A",
            "hybrid_cash_only": "hard_gate",
        }
        _safe_map = {
            "no_regime": "none",
            "vix_baseline": "none",
            "hybrid_cash_only": "none",
        }
        for _bl in _baselines:
            _v = _bl.get("variant", "?")
            _bc = round(_bl.get("cagr") or 0, 2)
            _bm = round(_bl.get("mdd") or 0, 2)
            _bs = round(_bl.get("sharpe") or 0, 4)
            _bn = _bl.get("n", 0)
            _bro = _bl.get("ro", 0)
            _compare.append(
                {
                    "policy_variant": _v,
                    "domestic_handling_mode": _dom_map.get(_v, "N/A"),
                    "safe_asset_mode": _safe_map.get(_v, "none"),
                    "CAGR": _bc,
                    "MDD": _bm,
                    "Sharpe": _bs,
                    "total_trades": _bl.get("trades", 0),
                    "neutral_count": _bn,
                    "risk_off_count": _bro,
                    "cash_drag_proxy": round((_bn + _bro) / _total_rebal, 4),
                    "safe_asset_switch_count": 0,
                    "verdict": ("PROMOTE" if _bc > 15 and _bm < 10 else "REJECT"),
                    "rank": 0,
                }
            )

        # B+D (current)
        _compare.append(
            {
                "policy_variant": "hybrid_B+D",
                "domestic_handling_mode": "neutral_only",
                "safe_asset_mode": "dollar_etf_20n_50r",
                "CAGR": _bd_cagr,
                "MDD": _bd_mdd,
                "Sharpe": _bd_sharpe,
                "total_trades": _bd_trades,
                "neutral_count": _n_count,
                "risk_off_count": _ro_count,
                "cash_drag_proxy": round((_n_count + _ro_count) / _total_rebal, 4),
                "safe_asset_switch_count": _bd_safe_cnt,
                "verdict": _bd_verdict,
                "rank": 0,
            }
        )
        # rank by MDD ascending
        _compare.sort(key=lambda x: x["MDD"])
        for _i, _c in enumerate(_compare):
            _c["rank"] = _i + 1
        _cmp_path = _regime_dir / "hybrid_policy_compare.csv"
        with open(_cmp_path, "w", encoding="utf-8", newline="") as f:
            w = _csv2.DictWriter(f, fieldnames=_compare[0].keys())
            w.writeheader()
            w.writerows(_compare)

        # hybrid_policy_summary.md
        _bd = next(
            (c for c in _compare if c["policy_variant"] == "hybrid_B+D"),
            _compare[-1],
        )
        _sum_lines = [
            "# Hybrid Policy Summary (B+D)",
            "",
            "## 추천안: B+D (domestic softening + safe asset)",
            "- 국내 단독 risk_off → neutral 격하",
            "- neutral: 50% 위험 + 30% 현금 + 20% 달러 ETF",
            "- risk_off: 50% 현금 + 50% 달러 ETF (글로벌만)",
            "",
            "## 비교",
            "| Variant | Dom | Safe | CAGR | MDD"
            " | Sharpe | N | RO | SafeCnt | Verdict |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ]
        for c in _compare:
            _sum_lines.append(
                f"| {c['policy_variant']}"
                f" | {c['domestic_handling_mode']}"
                f" | {c['safe_asset_mode']}"
                f" | {c['CAGR']}%"
                f" | {c['MDD']}%"
                f" | {c['Sharpe']}"
                f" | {c['neutral_count']}"
                f" | {c['risk_off_count']}"
                f" | {c['safe_asset_switch_count']}"
                f" | {c['verdict']} |"
            )
        _sum_lines += [
            "",
            "## 결론",
            f"B+D: CAGR {_bd['CAGR']}%,"
            f" MDD {_bd['MDD']}%,"
            f" Verdict={_bd['verdict']}",
            f"Safe Asset Switch: {_bd['safe_asset_switch_count']}회",
        ]
        (_regime_dir / "hybrid_policy_summary.md").write_text(
            "\n".join(_sum_lines), encoding="utf-8"
        )
        logger.info(f"[WRITE] hybrid regime outputs → {_regime_dir}")

    # P205-STEP5H: metric integrity audit
    _s = formatted["summary"]
    _m = formatted["meta"]
    # mdd_valid = 계산 자체가 성공했는지 (값이 0.0이어도 valid)
    _mdd_valid = _s.get("mdd") is not None and _m.get("mdd_reason") is None
    _tc_valid = _m.get("trade_count_valid", False)
    _audit = {
        "metric_source_nav_history": "engine.nav_history",
        "metric_source_return_series": "equity_curve.pct_change",
        "metric_source_trade_log": "engine.portfolio.trades",
        "nav_points": len(_m.get("equity_curve", [])),
        "return_points": len(_m.get("daily_returns", [])),
        "trade_event_count": _m.get("total_trades", 0),
        "buy_trade_count": _m.get("buy_trade_count", 0),
        "sell_trade_count": _m.get("sell_trade_count", 0),
        "mdd_valid": _mdd_valid,
        "mdd_value": _s.get("mdd"),
        "mdd_error_code": _m.get("mdd_reason"),
        "mdd_error_detail": (
            "drawdown 미발생"
            if not _mdd_valid and _m.get("mdd_reason") == "no_drawdown_from_peak"
            else None
        ),
        "trade_count_valid": _tc_valid,
        "trade_count_error_code": (None if _tc_valid else "trade_count_unavailable"),
        "trade_count_error_detail": None,
        "cagr_valid": _s.get("cagr") is not None,
        "cagr_error_code": _m.get("cagr_reason"),
        "sharpe_valid": _s.get("sharpe") is not None,
        "total_return_valid": _s.get("total_return") is not None,
        "ui_value_matches_json": (
            _s.get("mdd") is not None
            and _s.get("cagr") is not None
            and _s.get("total_return") is not None
            and _m.get("total_trades") is not None
        ),
        "ui_json_mismatches": [
            k
            for k, v in {
                "mdd": _s.get("mdd"),
                "cagr": _s.get("cagr"),
                "total_return": _s.get("total_return"),
                "total_trades": _m.get("total_trades"),
            }.items()
            if v is None
        ],
    }
    _audit_path = RESULT_LATEST.parent / "metric_integrity_audit_latest.json"
    _audit_path.write_text(
        json.dumps(_audit, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info(f"[WRITE] metric audit → {_audit_path}")

    try:
        atomic_write_result(formatted)
    except Exception as e:
        logger.error(f"Result write failed: {e}")
        return False

    # 6. Summary
    s = formatted["summary"]
    meta = formatted["meta"]
    logger.info("=" * 60)
    _cagr_str = f"{s['cagr']:.4f}" if s["cagr"] is not None else "N/A"
    logger.info(
        f"[RESULT: OK] CAGR={_cagr_str}  MDD={s['mdd']:.4f}  "
        f"Sharpe={s.get('sharpe', 0):.4f}  Trades={meta['total_trades']}"
    )
    logger.info(
        f"  equity_curve: {len(meta.get('equity_curve', []))} pts  "
        f"daily_returns: {len(meta.get('daily_returns', []))} pts"
    )
    if meta.get("sharpe_reason"):
        logger.info(f"  sharpe_reason: {meta['sharpe_reason']}")
    if meta.get("mdd_reason"):
        logger.info(f"  mdd_reason: {meta['mdd_reason']}")
    logger.info("=" * 60)

    # P206-STEP6B-PATCH1: Full Backtest 후 promotion_verdict 동기화
    try:
        from app.tuning.promotion_gate import refresh_promotion_verdict

        refresh_promotion_verdict(backtest_data_override=formatted)
        logger.info("[WRITE] promotion_verdict 동기화 완료")
    except Exception as exc:
        logger.warning(f"promotion_verdict 동기화 실패: {exc}")

    # P206-STEP6D-PATCH1: dynamic_evidence_latest.md 생성
    if params.get("universe_mode") == "dynamic_etf_market":
        try:
            _ev_dir = PROJECT_ROOT / "reports" / "tuning"
            _ev_path = _ev_dir / "dynamic_evidence_latest.md"

            # 소스 로드
            _bt = formatted
            _bt_s = _bt.get("summary", {})
            _bt_m = _bt.get("meta", {})

            _fv_p = _ev_dir / "hybrid_regime_verdict_latest.json"
            _fv = {}
            if _fv_p.exists():
                with open(_fv_p, encoding="utf-8") as _f:
                    _fv = json.load(_f)

            _pv_p = _ev_dir / "promotion_verdict.json"
            _pv = {}
            if _pv_p.exists():
                with open(_pv_p, encoding="utf-8") as _f:
                    _pv = json.load(_f)

            _gen_at = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+09:00")

            # verdict 판정
            _cagr_v = _bt_s.get("cagr")
            _mdd_v = _bt_s.get("mdd")
            _cagr_ok = "YES" if _cagr_v is not None and _cagr_v > 15 else "NO"
            _mdd_ok = "YES" if _mdd_v is not None and _mdd_v < 10 else "NO"
            _verdict_str = _pv.get("verdict", "N/A")

            # 한줄 결론
            if _cagr_ok == "YES" and _mdd_ok == "YES":
                _conclusion = "승격 가능. 정책 효과 확인됨."
            elif _cagr_ok == "YES":
                _conclusion = (
                    "구현 통과. MDD 미달로 정책 효과 실패." " 정책 재설계 필요."
                )
            else:
                _conclusion = "CAGR/MDD 모두 미달. 전략 재검토 필요."

            _cagr_s = f"{_cagr_v:.2f}%" if _cagr_v is not None else "N/A"
            _mdd_s = f"{_mdd_v:.2f}%" if _mdd_v is not None else "N/A"
            _sharpe_s = f"{_bt_s.get('sharpe', 0):.4f}"
            _tr_s = (
                f"{_bt_s.get('total_return', 0):.2f}%"
                if _bt_s.get("total_return") is not None
                else "N/A"
            )

            _lines = [
                "# Dynamic Evidence Latest",
                "",
                f"- generated_at: {_gen_at}",
                f"- universe_mode: {_bt_m.get('universe_mode', '?')}",
                f"- backtest_asof: {_bt_m.get('asof', '?')}",
                "",
                "## Performance",
                "| Metric | Value |",
                "|---|---:|",
                f"| CAGR | {_cagr_s} |",
                f"| MDD | {_mdd_s} |",
                f"| Sharpe | {_sharpe_s} |",
                f"| Total Return | {_tr_s} |",
                f"| Total Trades | {_bt_m.get('total_trades', 'N/A')} |",
                "",
                "## Hybrid Regime",
                "| Field | Value |",
                "|---|---|",
                f"| Global State | {_fv.get('global_state', 'N/A')} |",
                f"| Domestic State | {_fv.get('domestic_state', 'N/A')} |",
                f"| Aggregate | {_fv.get('aggregate_state', 'N/A')} |",
                f"| Policy | {_fv.get('policy_applied', 'N/A')} |",
                f"| Neutral Count | {_fv.get('neutral_count', 0)} |",
                f"| Risk-off Count | {_fv.get('risk_off_count', 0)} |",
                f"| Checkpoint | {_fv.get('checkpoint_id', 'K6')} |",
                f"| Global Source | {_fv.get('global_source_timestamp', 'N/A')} |",
                f"| Domestic Source | {_fv.get('domestic_source_timestamp', 'N/A')} |",
                "| Alignment | us_close_to_kr_next_open |",
                "| Policy Variant | B+D (domestic softening + safe asset) |",
                "| Domestic Handling | neutral_only (no domestic hard gate) |",
                "| Safe Asset Mode | dollar_etf 20% neutral / 50% risk_off |",
                "| Safe Asset | 261240 (달러 ETF) |",
                "| Checkpoint Summary | K1~K6 (백테스트: 일봉 근사) |",
                "",
                "## Promotion Verdict",
                "| Field | Value |",
                "|---|---|",
                f"| Verdict | {_verdict_str} |",
                f"| CAGR > 15 | {_cagr_ok} |",
                f"| MDD < 10 | {_mdd_ok} |",
                "",
                "## One-line Conclusion",
                _conclusion,
                "",
                "## Notes",
                "- 백테스트: 일봉 근사 (장중 K1~K6 체크포인트는 당일 종가로 근사)",
                "- 직장인형 저빈도 체크포인트 대응 모델 (상시 실시간 아님)",
            ]
            _ev_path.write_text("\n".join(_lines), encoding="utf-8")
            logger.info(f"[WRITE] dynamic_evidence → {_ev_path}")
        except Exception as ev_exc:
            logger.warning(f"dynamic_evidence 생성 실패: {ev_exc}")

    print(f"[RESULT: OK] backtest completed → {RESULT_LATEST}")
    return True


def main():
    parser = argparse.ArgumentParser(description="P165 Backtest CLI")
    parser.add_argument(
        "--mode",
        choices=["quick", "full"],
        default="quick",
        help="quick: 6개월, full: 3년",
    )
    parser.add_argument("--start", type=str, default=None, help="시작일 (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, default=None, help="종료일 (YYYY-MM-DD)")
    args = parser.parse_args()

    success = run_cli_backtest(mode=args.mode, start_str=args.start, end_str=args.end)
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
