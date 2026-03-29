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
from typing import Any, Dict, List, Optional

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


from app.utils.param_loader import load_params_strict


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
    )

    # Attach trigger evidence
    result["_trigger_source"] = trigger_source
    result["_effective_rebalance"] = effective_rebalance

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
        import numpy as np

        navs = pd.Series([e["equity"] for e in equity_curve])

        # MDD
        cummax = navs.cummax()
        drawdown = navs / cummax - 1.0
        mdd_val = abs(float(drawdown.min())) * 100
        if mdd_val == 0.0:
            mdd_reason = "no_drawdown_from_peak"

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
    summary = {
        "cagr": metrics.get("cagr", 0.0),
        "mdd": round(mdd_val, 4),
        "sharpe": round(sharpe_val, 4),
        "total_return": metrics.get("total_return", 0.0),
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
        "engine_version": "app.backtest.v2",
        "total_trades": metrics.get("order_count", 0),
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

    # 3. Load price data
    try:
        price_data = load_price_data(
            params["universe"], start, end, data_source=params["data_source"]
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
    try:
        atomic_write_result(formatted)
    except Exception as e:
        logger.error(f"Result write failed: {e}")
        return False

    # 6. Summary
    s = formatted["summary"]
    meta = formatted["meta"]
    logger.info("=" * 60)
    logger.info(
        f"[RESULT: OK] CAGR={s['cagr']:.4f}  MDD={s['mdd']:.4f}  "
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
