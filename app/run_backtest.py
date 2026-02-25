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
BUNDLE_PATH = PROJECT_ROOT / "state" / "strategy_bundle" / "latest" / "strategy_bundle_latest.json"
PARAMS_SSOT_PATH = PROJECT_ROOT / "state" / "params" / "latest" / "strategy_params_latest.json"
RESULT_LATEST = PROJECT_ROOT / "reports" / "backtest" / "latest" / "backtest_result.json"
RESULT_SNAPSHOTS = PROJECT_ROOT / "reports" / "backtest" / "snapshots"


# ─── 1. Strategy Bundle → Params ──────────────────────────────────────────
def load_strategy_bundle() -> Dict[str, Any]:
    """strategy_bundle_latest.json 읽기"""
    if not BUNDLE_PATH.exists():
        raise FileNotFoundError(f"Strategy bundle not found: {BUNDLE_PATH}")
    with open(BUNDLE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_params(bundle: Dict[str, Any]) -> Dict[str, Any]:
    """번들에서 백테스트 파라미터 추출"""
    strategy = bundle.get("strategy", {})
    universe = strategy.get("universe", [])
    lookbacks = strategy.get("lookbacks", {})
    risk = strategy.get("risk_limits", {})
    pos_limits = strategy.get("position_limits", {})
    decision = strategy.get("decision_params", {})

    return {
        "universe": universe,
        "momentum_period": lookbacks.get("momentum_period", 60),
        "max_positions": pos_limits.get("max_positions", 4),
        "max_position_pct": risk.get("max_position_pct", 0.25),
        "min_cash_pct": pos_limits.get("min_cash_pct", 0.05),
        "stop_loss": decision.get("exit_threshold", -0.10),
        "adx_filter_min": decision.get("adx_filter_min", 20),
    }

def load_params_with_fallback() -> tuple[Dict[str, Any], Dict[str, str]]:
    """Load params from SSOT, fallback to bundle. Returns (params, param_source_meta)"""
    import hashlib
    
    def get_sha256(path: Path) -> str:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
            
    if PARAMS_SSOT_PATH.exists():
        try:
            with open(PARAMS_SSOT_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            p = data.get("params", {})
            params = {
                "universe": p.get("universe", []),
                "momentum_period": p.get("lookbacks", {}).get("momentum_period", 60),
                "max_positions": p.get("position_limits", {}).get("max_positions", 4),
                "max_position_pct": p.get("risk_limits", {}).get("max_position_pct", 0.25),
                "min_cash_pct": p.get("position_limits", {}).get("min_cash_pct", 0.05),
                "stop_loss": p.get("decision_params", {}).get("exit_threshold", -0.10),
                "adx_filter_min": p.get("decision_params", {}).get("adx_filter_min", 20),
            }
            if params["universe"]: # Only accept if universe is non-empty
                source = {
                    "path": "state/params/latest/strategy_params_latest.json",
                    "sha256": get_sha256(PARAMS_SSOT_PATH)
                }
                return params, source
        except Exception as e:
            logger.warning(f"Failed to load params SSOT: {e}")
            
    # Fallback to bundle
    if not BUNDLE_PATH.exists():
        raise FileNotFoundError(f"Nor SSOT nor Strategy bundle found.")
    with open(BUNDLE_PATH, "r", encoding="utf-8") as f:
        bundle = json.load(f)
    params = extract_params(bundle)
    source = {
        "path": "state/strategy_bundle/latest/strategy_bundle_latest.json",
        "sha256": get_sha256(BUNDLE_PATH)
    }
    return params, source

# ─── 2. Data Loading ──────────────────────────────────────────────────────
def load_price_data(
    tickers: List[str], start: date, end: date
) -> pd.DataFrame:
    """
    종목별 OHLCV 다운로드 → MultiIndex(code, date) DataFrame.

    Fallback: yfinance (.KS 우선, 실패 시 .KQ)
    """
    try:
        from app.backtest.infra.data_loader import get_ohlcv
    except ImportError:
        get_ohlcv = None

    frames = []
    for ticker in tickers:
        df = _fetch_single(ticker, start, end, get_ohlcv)
        if df is not None and not df.empty:
            frames.append(df)
        else:
            logger.warning(f"[DATA] No data for {ticker} — skipping")

    if not frames:
        raise RuntimeError(
            f"데이터 로딩 완전 실패. tickers={tickers}, "
            f"start={start}, end={end}. 네트워크 또는 yfinance 문제 확인 필요."
        )

    combined = pd.concat(frames).sort_index()
    logger.info(
        f"[DATA] Loaded {len(combined)} rows for {len(frames)} tickers "
        f"({combined.index.get_level_values('date').min().date()} ~ "
        f"{combined.index.get_level_values('date').max().date()})"
    )
    return combined


def _fetch_single(
    ticker: str, start: date, end: date, get_ohlcv_fn
) -> Optional[pd.DataFrame]:
    """단일 종목 OHLCV → MultiIndex(code, date) rows."""

    # yfinance 심볼 변환: 6자리 숫자 → .KS (실패 시 .KQ)
    if ticker.isdigit() and len(ticker) == 6:
        suffixes = [".KS", ".KQ"]
    elif ticker.isdigit():
        suffixes = [".KS"]
    else:
        suffixes = [""]  # 이미 완성된 심볼

    for suffix in suffixes:
        symbol = f"{ticker}{suffix}"
        try:
            if get_ohlcv_fn is not None:
                df = get_ohlcv_fn(symbol, start, end, use_cache=True)
            else:
                df = _yfinance_fallback(symbol, start, end)

            if df is not None and not df.empty:
                # 컬럼 소문자화
                df.columns = [c.lower() for c in df.columns]
                # 필수 컬럼 확인
                if "close" not in df.columns:
                    logger.warning(f"[DATA] {symbol}: 'close' column missing")
                    continue
                # MultiIndex 생성
                df["code"] = ticker  # 원본 6자리 코드 유지
                df.index.name = "date"
                df = df.reset_index().set_index(["code", "date"]).sort_index()
                logger.info(f"[DATA] {symbol}: {len(df)} rows loaded")
                return df
        except Exception as e:
            logger.warning(f"[DATA] {symbol} failed: {e}")
            continue

    return None


def _yfinance_fallback(symbol: str, start: date, end: date) -> Optional[pd.DataFrame]:
    """yfinance 직접 다운로드 (data_loader import 실패 시)."""
    try:
        import yfinance as yf
    except ImportError:
        raise ImportError(
            "yfinance 패키지 미설치. pip install yfinance 필요."
        )
    logger.info(f"[DATA] yfinance fallback: {symbol}")
    df = yf.download(
        symbol,
        start=str(start),
        end=str(end + timedelta(days=1)),
        progress=False,
        auto_adjust=False,
    )
    if df is not None and not df.empty:
        # yfinance 0.2.x returns MultiIndex columns with (Price, Ticker)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        # 타임존 제거
        if hasattr(df.index, 'tz') and df.index.tz is not None:
            df.index = df.index.tz_localize(None)
    return df


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

    result = runner.run(
        price_data=price_data,
        target_weights=target_weights,
        start_date=start,
        end_date=end,
        ma_period=params["momentum_period"],
        rsi_period=14,
        stop_loss=params["stop_loss"],
        adx_threshold=params["adx_filter_min"],
    )

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
    drawdown = (closes / cummax - 1.0)
    mdd = abs(float(drawdown.min())) * 100  # 양수 %

    # Win Rate (일별 양의 수익률 비율)
    daily_ret = closes.pct_change().dropna()
    if len(daily_ret) > 0:
        win_rate = float((daily_ret > 0).sum()) / len(daily_ret) * 100
    else:
        win_rate = 0.0

    return {"cagr": round(cagr, 4), "mdd": round(mdd, 4), "win_rate": round(win_rate, 2)}


# ─── 5. Format Output ─────────────────────────────────────────────────────
def format_result(
    result: Dict[str, Any],
    params: Dict[str, Any],
    start: date,
    end: date,
    price_data: pd.DataFrame = None,
    param_source: Dict[str, str] = None,
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
            equity_curve.append({
                "date": str(d),
                "equity": round(float(nav), 2),
            })

        # daily returns from equity curve
        for i in range(1, len(nav_history)):
            prev_nav = nav_history[i - 1][1]
            curr_nav = nav_history[i][1]
            ret = (curr_nav / prev_nav - 1.0) if prev_nav > 0 else 0.0
            daily_returns.append({
                "date": str(nav_history[i][0]),
                "ret": round(float(ret), 6),
            })

    # ── Recompute MDD/Sharpe from equity curve ──
    sharpe_reason = None
    mdd_reason = None

    if len(equity_curve) >= 2:
        import numpy as np
        navs = pd.Series([e["equity"] for e in equity_curve])

        # MDD
        cummax = navs.cummax()
        drawdown = (navs / cummax - 1.0)
        mdd_val = abs(float(drawdown.min())) * 100
        if mdd_val == 0.0:
            mdd_reason = "no_drawdown_from_peak"

        # Sharpe
        rets = navs.pct_change().dropna()
        if len(rets) > 1 and float(rets.std()) > 0:
            sharpe_val = float(rets.mean() / rets.std()) * (252 ** 0.5)
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
                tickers_out[t] = {"cagr": 0.0, "mdd": 0.0, "win_rate": 0.0, "score": None}
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
    sorted_tickers = sorted(tickers_out.items(), key=lambda x: x[1]["cagr"], reverse=True)
    top_performers = [{"ticker": t, "cagr": v["cagr"]} for t, v in sorted_tickers[:5]]

    # meta
    now_kst = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+09:00")

    meta = {
        "asof": now_kst,
        "start_date": str(start),
        "end_date": str(end),
        "mode": "P165_CLI",
        "universe": params["universe"],
        "engine_version": "app.backtest.v2",
        "total_trades": metrics.get("order_count", 0),
        "signal_days": metrics.get("signal_days", 0),
        "param_source": param_source,
        "params_used": {
            "momentum_period": params.get("momentum_period"),
            "stop_loss": params.get("stop_loss"),
            "max_positions": params.get("max_positions"),
        },
        "equity_curve": equity_curve,
        "daily_returns": daily_returns,
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
def run_cli_backtest(mode: str = "quick", start_str: str = None, end_str: str = None) -> bool:
    """Run backtest programmatically. Returns True if successful."""
    logger.info("=" * 60)
    logger.info("P165 Backtest Engine — CLI")
    logger.info("=" * 60)

    # 1. Load strategy params via SSOT > Bundle
    try:
        params, param_source = load_params_with_fallback()
    except Exception as e:
        logger.error(f"Strategy params load failed: {e}")
        return False

    logger.info(f"[PARAMS] src={param_source['path']}")
    logger.info(f"[PARAMS] universe={params['universe']}, ma={params['momentum_period']}, "
                f"max_pos={params['max_positions']}, stop_loss={params['stop_loss']}")

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
        price_data = load_price_data(params["universe"], start, end)
    except Exception as e:
        logger.error(f"Data loading failed: {e}")
        return False

    # 4. Run backtest
    enable_regime = (mode == "full")
    try:
        result = run_backtest(price_data, params, start, end, enable_regime=enable_regime)
    except Exception as e:
        logger.error(f"Backtest execution failed: {e}")
        traceback.print_exc()
        return False

    # 5. Format and write (pass param_source)
    formatted = format_result(result, params, start, end, price_data=price_data, param_source=param_source)
    try:
        atomic_write_result(formatted)
    except Exception as e:
        logger.error(f"Result write failed: {e}")
        return False

    # 6. Summary
    s = formatted["summary"]
    meta = formatted["meta"]
    logger.info("=" * 60)
    logger.info(f"[RESULT: OK] CAGR={s['cagr']:.4f}  MDD={s['mdd']:.4f}  "
                f"Sharpe={s.get('sharpe', 0):.4f}  Trades={meta['total_trades']}")
    logger.info(f"  equity_curve: {len(meta.get('equity_curve', []))} pts  "
                f"daily_returns: {len(meta.get('daily_returns', []))} pts")
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

