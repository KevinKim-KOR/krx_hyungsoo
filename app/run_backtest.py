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


# ─── 4. Format Output ─────────────────────────────────────────────────────
def format_result(
    result: Dict[str, Any],
    params: Dict[str, Any],
    start: date,
    end: date,
) -> Dict[str, Any]:
    """
    결과를 현행 소비자 스키마로 포맷팅.

    필수 최상위 키: summary, tickers, top_performers
    """
    metrics = result.get("metrics", {})

    # summary
    summary = {
        "cagr": metrics.get("cagr", 0.0),
        "mdd": metrics.get("mdd", 0.0),
        "sharpe": metrics.get("sharpe", 0.0),
        "total_return": metrics.get("total_return", 0.0),
    }

    # tickers — 종목별 성과 (메인 엔진은 포트폴리오 레벨만 제공하므로 동일값 배분)
    tickers_out = {}
    for t in params["universe"]:
        tickers_out[t] = {
            "cagr": metrics.get("cagr", 0.0),
            "mdd": metrics.get("mdd", 0.0),
            "win_rate": metrics.get("win_rate_daily", None),
            "score": None,
        }

    # top_performers (cagr 내림차순)
    sorted_tickers = sorted(tickers_out.items(), key=lambda x: x[1]["cagr"], reverse=True)
    top_performers = [{"ticker": t, "cagr": v["cagr"]} for t, v in sorted_tickers]

    # meta (추가 정보)
    now_kst = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+09:00")

    return {
        "summary": summary,
        "tickers": tickers_out,
        "top_performers": top_performers,
        "meta": {
            "asof": now_kst,
            "start_date": str(start),
            "end_date": str(end),
            "mode": "P164_CLI",
            "universe": params["universe"],
            "engine_version": "app.backtest.v1",
            "total_trades": metrics.get("order_count", 0),
            "signal_days": metrics.get("signal_days", 0),
        },
    }


# ─── 5. Atomic Write ──────────────────────────────────────────────────────
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


# ─── 6. Main ──────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="P164 Backtest CLI")
    parser.add_argument(
        "--mode",
        choices=["quick", "full"],
        default="quick",
        help="quick: 6개월, full: 3년",
    )
    parser.add_argument("--start", type=str, default=None, help="시작일 (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, default=None, help="종료일 (YYYY-MM-DD)")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("P164 Backtest Engine — CLI")
    logger.info("=" * 60)

    # 1. Load strategy bundle
    try:
        bundle = load_strategy_bundle()
        params = extract_params(bundle)
    except Exception as e:
        logger.error(f"Strategy bundle load failed: {e}")
        print(f"[RESULT: FAIL] Strategy bundle error: {e}", file=sys.stderr)
        sys.exit(1)

    logger.info(f"[PARAMS] universe={params['universe']}, ma={params['momentum_period']}, "
                f"max_pos={params['max_positions']}, stop_loss={params['stop_loss']}")

    # 2. Determine date range
    today = date.today()
    if args.start and args.end:
        start = date.fromisoformat(args.start)
        end = date.fromisoformat(args.end)
    elif args.mode == "quick":
        start = today - timedelta(days=180)
        end = today - timedelta(days=1)
    else:  # full
        start = today - timedelta(days=365 * 3)
        end = today - timedelta(days=1)

    logger.info(f"[DATE] {start} → {end} (mode={args.mode})")

    # 3. Load price data
    try:
        price_data = load_price_data(params["universe"], start, end)
    except Exception as e:
        logger.error(f"Data loading failed: {e}")
        print(f"[RESULT: FAIL] Data loading error: {e}", file=sys.stderr)
        sys.exit(1)

    # 4. Run backtest
    enable_regime = args.mode == "full"
    try:
        result = run_backtest(price_data, params, start, end, enable_regime=enable_regime)
    except Exception as e:
        logger.error(f"Backtest execution failed: {e}")
        traceback.print_exc()
        print(f"[RESULT: FAIL] Backtest error: {e}", file=sys.stderr)
        sys.exit(1)

    # 5. Format and write
    formatted = format_result(result, params, start, end)

    try:
        atomic_write_result(formatted)
    except Exception as e:
        logger.error(f"Result write failed: {e}")
        print(f"[RESULT: FAIL] Write error: {e}", file=sys.stderr)
        sys.exit(1)

    # 6. Summary
    s = formatted["summary"]
    logger.info("=" * 60)
    logger.info(f"[RESULT: OK] CAGR={s['cagr']:.4f}  MDD={s['mdd']:.4f}  "
                f"Sharpe={s.get('sharpe', 0):.4f}  Trades={formatted['meta']['total_trades']}")
    logger.info("=" * 60)
    print(f"[RESULT: OK] backtest completed → {RESULT_LATEST}")


if __name__ == "__main__":
    main()
