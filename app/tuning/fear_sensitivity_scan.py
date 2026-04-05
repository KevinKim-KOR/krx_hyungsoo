# -*- coding: utf-8 -*-
"""
app/tuning/fear_sensitivity_scan.py
P206-STEP6E: VIX Fear Regime 감도 스캔

threshold × neutral_cash 조합별 Full Backtest를 돌려
최적 방어 임계치 후보군을 찾는다.
"""

from __future__ import annotations

import csv
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
REPORTS_DIR = PROJECT_ROOT / "reports" / "tuning"


def run_sensitivity_scan(
    price_data: pd.DataFrame,
    params: Dict[str, Any],
    start: date,
    end: date,
    vix_ohlcv: pd.DataFrame,
    rebalance_dates: List[date],
    universe_resolver=None,
) -> List[Dict[str, Any]]:
    """감도 스캔 실행. 각 조합별 backtest 결과를 반환."""
    from app.backtest.runners.backtest_runner import BacktestRunner
    from app.backtest.strategy.exo_regime_filter import (
        build_fear_regime_schedule,
    )

    risk_on_max_range = [14, 15, 16, 17, 18, 19, 20]
    risk_off_min_range = [18, 20, 22, 24, 26, 28, 30]
    spike_range = [0.05, 0.10, 0.15, 0.20]
    neutral_cash_range = [0.50, 0.65, 0.80]

    results = []
    combo_count = 0

    for rom in risk_on_max_range:
        for rfm in risk_off_min_range:
            if rfm <= rom:
                continue  # 불합리 조합 제외
            if rfm - rom < 2:
                continue  # neutral 구간 너무 좁음
            for spike in spike_range:
                for ncash in neutral_cash_range:
                    combo_count += 1

                    # fear schedule 생성
                    sched = build_fear_regime_schedule(
                        vix_ohlcv=vix_ohlcv,
                        rebalance_dates=rebalance_dates,
                        risk_on_max=float(rom),
                        risk_off_min=float(rfm),
                        spike_threshold=spike,
                    )
                    sched["neutral_cash_pct"] = ncash

                    # backtest 실행
                    runner = BacktestRunner(
                        initial_capital=10_000_000,
                        commission_rate=0.00015,
                        slippage_rate=0.001,
                        max_positions=params["max_positions"],
                        rebalance_frequency="daily",
                        instrument_type="etf",
                        enable_defense=True,
                        min_holding_days=0,
                    )
                    target_w = {
                        t: 1.0 / len(params["universe"]) for t in params["universe"]
                    }

                    portfolio_mode = params["portfolio_mode"]
                    rebalance_rule = params.get("rebalance_rule", params["rebalance"])
                    if portfolio_mode == "bucket_portfolio":
                        rebalance_rule = params["rebalance"]

                    try:
                        result = runner.run(
                            price_data=price_data,
                            target_weights=target_w,
                            start_date=start,
                            end_date=end,
                            ma_period=params["momentum_period"],
                            volatility_period=params["volatility_period"],
                            entry_threshold=params["entry_threshold"],
                            rsi_period=14,
                            stop_loss=params["stop_loss"],
                            adx_threshold=params.get("adx_filter_min", 20),
                            portfolio_mode=portfolio_mode,
                            sell_mode=params["sell_mode"],
                            rebalance_rule=rebalance_rule,
                            buckets=params["buckets"],
                            universe_resolver=universe_resolver,
                            universe_mode=params.get("universe_mode", "fixed_current"),
                            exo_regime_schedule=sched,
                        )
                    except Exception as exc:
                        logger.warning(f"[SCAN] combo #{combo_count} 실패: {exc}")
                        continue

                    metrics = result.get("metrics", {})
                    nav_hist = result.get("nav_history", [])

                    # MDD from nav
                    mdd_val = 0.0
                    if len(nav_hist) >= 2:
                        navs = pd.Series([n for _, n in nav_hist]).dropna()
                        if len(navs) >= 2:
                            cum = navs.cummax()
                            dd = navs / cum - 1.0
                            mdd_val = abs(float(dd.min())) * 100

                    # CAGR from nav
                    cagr_val = 0.0
                    if len(nav_hist) >= 2:
                        nav_s = nav_hist[0][1]
                        nav_e_list = [n for _, n in reversed(nav_hist) if n == n]
                        nav_e = nav_e_list[0] if nav_e_list else nav_s
                        days = (nav_hist[-1][0] - nav_hist[0][0]).days
                        yrs = days / 365.25
                        if yrs > 0 and nav_s > 0:
                            cagr_val = ((nav_e / nav_s) ** (1.0 / yrs) - 1.0) * 100

                    # Sharpe from nav
                    sharpe_val = 0.0
                    if len(nav_hist) >= 3:
                        nav_ser = pd.Series([n for _, n in nav_hist]).dropna()
                        rets = nav_ser.pct_change().dropna()
                        if len(rets) > 1 and float(rets.std()) > 0:
                            sharpe_val = float(rets.mean() / rets.std()) * (252**0.5)

                    trades = metrics.get(
                        "order_count",
                        len(result.get("trades", [])),
                    )
                    n_cnt = sched.get("neutral_count", 0)
                    ro_cnt = sched.get("risk_off_count", 0)

                    cagr_ok = cagr_val > 15
                    mdd_ok = mdd_val < 10
                    if cagr_ok and mdd_ok:
                        verdict = "PROMOTE"
                    elif cagr_ok:
                        verdict = "CAGR_OK_MDD_FAIL"
                    else:
                        verdict = "REJECT"

                    results.append(
                        {
                            "risk_on_max": rom,
                            "risk_off_min": rfm,
                            "spike_threshold": spike,
                            "neutral_target_cash_pct": ncash,
                            "CAGR": round(cagr_val, 4),
                            "MDD": round(mdd_val, 4),
                            "Sharpe": round(sharpe_val, 4),
                            "total_trades": trades,
                            "neutral_count": n_cnt,
                            "risk_off_count": ro_cnt,
                            "verdict": verdict,
                        }
                    )

                    if combo_count % 20 == 0:
                        logger.info(f"[SCAN] {combo_count} combos done")

    logger.info(f"[SCAN] 완료: {len(results)}/{combo_count} combos")
    return results


def rank_results(
    results: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """추천 기준에 따라 순위 매기기."""

    def sort_key(r):
        mdd_ok = 1 if r["MDD"] < 10 else 0
        cagr_ok = 1 if r["CAGR"] > 15 else 0
        return (
            -mdd_ok,
            -cagr_ok,
            r["MDD"],
            -r["Sharpe"],
            r["risk_off_count"],
            r["neutral_count"],
        )

    ranked = sorted(results, key=sort_key)
    for i, r in enumerate(ranked):
        r["rank"] = i + 1
    return ranked


def write_grid_csv(
    ranked: List[Dict[str, Any]],
) -> Path:
    """fear_sensitivity_grid.csv 생성."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / "fear_sensitivity_grid.csv"
    if not ranked:
        return path
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=ranked[0].keys())
        w.writeheader()
        w.writerows(ranked)
    logger.info(f"[WRITE] grid → {path}")
    return path


def write_summary_md(
    ranked: List[Dict[str, Any]],
    no_regime_metrics: Dict[str, Any],
    baseline_metrics: Dict[str, Any],
) -> Path:
    """fear_sensitivity_summary.md 생성."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / "fear_sensitivity_summary.md"

    top5 = ranked[:5] if len(ranked) >= 5 else ranked
    promote = [r for r in ranked if r["verdict"] == "PROMOTE"]
    cagr_ok = [r for r in ranked if r["verdict"] == "CAGR_OK_MDD_FAIL"]
    best_mdd = min(ranked, key=lambda r: r["MDD"]) if ranked else None

    lines = [
        "# Fear Sensitivity Scan Summary",
        "",
        f"- generated_at: {datetime.now().strftime('%Y-%m-%dT%H:%M:%S+09:00')}",
        f"- total_combos: {len(ranked)}",
        f"- promote_candidates: {len(promote)}",
        "",
        "## 비교군",
        "",
        "| 구성 | CAGR | MDD | Sharpe | Trades |",
        "|---|---|---|---|---|",
        f"| no regime | {no_regime_metrics.get('CAGR', 'N/A')}% "
        f"| {no_regime_metrics.get('MDD', 'N/A')}% "
        f"| {no_regime_metrics.get('Sharpe', 'N/A')} "
        f"| {no_regime_metrics.get('total_trades', 'N/A')} |",
        f"| baseline (20/30/0.20/0.50) "
        f"| {baseline_metrics.get('CAGR', 'N/A')}% "
        f"| {baseline_metrics.get('MDD', 'N/A')}% "
        f"| {baseline_metrics.get('Sharpe', 'N/A')} "
        f"| {baseline_metrics.get('total_trades', 'N/A')} |",
        "",
        "## 상위 5 후보",
        "",
        "| Rank | rom | rfm | spike | ncash "
        "| CAGR | MDD | Sharpe | Trades | N | RO | Verdict |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in top5:
        lines.append(
            f"| {r['rank']} | {r['risk_on_max']} "
            f"| {r['risk_off_min']} "
            f"| {r['spike_threshold']} "
            f"| {r['neutral_target_cash_pct']} "
            f"| {r['CAGR']}% "
            f"| {r['MDD']}% "
            f"| {r['Sharpe']} "
            f"| {r['total_trades']} "
            f"| {r['neutral_count']} "
            f"| {r['risk_off_count']} "
            f"| {r['verdict']} |"
        )

    lines += [
        "",
        "## 추천",
        "",
    ]

    if promote:
        lines.append(f"MDD<10 + CAGR>15 달성 후보: **{len(promote)}개**")
        for r in promote[:3]:
            lines.append(
                f"- rom={r['risk_on_max']} rfm={r['risk_off_min']}"
                f" spike={r['spike_threshold']}"
                f" ncash={r['neutral_target_cash_pct']}"
                f" → CAGR {r['CAGR']}% MDD {r['MDD']}%"
                f" Sharpe {r['Sharpe']}"
            )
    elif cagr_ok:
        lines.append("MDD<10 달성 후보 없음. CAGR>15 유지 중 MDD 최소:")
        best_cagr_mdd = min(cagr_ok, key=lambda r: r["MDD"])
        lines.append(
            f"- rom={best_cagr_mdd['risk_on_max']}"
            f" rfm={best_cagr_mdd['risk_off_min']}"
            f" spike={best_cagr_mdd['spike_threshold']}"
            f" ncash={best_cagr_mdd['neutral_target_cash_pct']}"
            f" → CAGR {best_cagr_mdd['CAGR']}%"
            f" MDD {best_cagr_mdd['MDD']}%"
        )
    else:
        lines.append("CAGR>15 유지 후보도 없음. 전체 MDD 최소:")
        if best_mdd:
            lines.append(
                f"- rom={best_mdd['risk_on_max']}"
                f" rfm={best_mdd['risk_off_min']}"
                f" → MDD {best_mdd['MDD']}%"
            )

    lines += [
        "",
        "## 보정 철학",
        "- 미국 VIX 임계치를 낮추어 한국장 독자 변동성을 간접 반영",
        "- neutral을 더 자주, 더 강하게 발동 → 한국장 독자 하락 방어",
        "- 장중 대응은 미포함 (직장인형 EOD/개장 전 방어 모델)",
    ]

    path.write_text("\n".join(lines), encoding="utf-8")
    logger.info(f"[WRITE] summary → {path}")
    return path
