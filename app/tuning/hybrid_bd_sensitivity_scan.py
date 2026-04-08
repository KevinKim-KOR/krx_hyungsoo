# -*- coding: utf-8 -*-
"""
app/tuning/hybrid_bd_sensitivity_scan.py
P206-STEP6J: Hybrid B+D 정책 감도 스캔

run_backtest() 공식 파이프라인 재사용.
neutral_risky_pct, neutral_dollar_pct, riskoff_dollar_pct,
domestic_neutral_threshold, domestic_riskoff_threshold 5축 그리드 탐색.
"""

from __future__ import annotations

import csv
import logging
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
REPORTS_DIR = PROJECT_ROOT / "reports" / "tuning"

# ── 탐색 범위 ────────────────────────────────────────────────
NEUTRAL_RISKY_PCT_RANGE = [0.35, 0.50, 0.65, 0.80, 0.95]
NEUTRAL_DOLLAR_PCT_RANGE = [0.0, 0.10, 0.20, 0.30]
RISKOFF_DOLLAR_PCT_RANGE = [0.30, 0.50, 0.70]
DOMESTIC_NEUTRAL_THRESHOLD_RANGE = [-0.005, -0.01, -0.015, -0.02, -0.03]
DOMESTIC_RISKOFF_THRESHOLD_RANGE = [-0.03, -0.05]


def _build_combos() -> List[Dict[str, float]]:
    """유효한 파라미터 조합 생성.

    제약:
    - neutral_risky_pct + neutral_dollar_pct <= 0.95 (최소 5% cash)
    - domestic_riskoff_threshold < domestic_neutral_threshold
    """
    combos: List[Dict[str, float]] = []
    for nrp in NEUTRAL_RISKY_PCT_RANGE:
        for ndp in NEUTRAL_DOLLAR_PCT_RANGE:
            if nrp + ndp > 0.95:
                continue
            ncp = round(1.0 - nrp - ndp, 4)
            for rdp in RISKOFF_DOLLAR_PCT_RANGE:
                rcp = round(1.0 - rdp, 4)
                for dnt in DOMESTIC_NEUTRAL_THRESHOLD_RANGE:
                    for drt in DOMESTIC_RISKOFF_THRESHOLD_RANGE:
                        if drt >= dnt:
                            continue
                        combos.append(
                            {
                                "neutral_risky_pct": nrp,
                                "neutral_cash_pct": ncp,
                                "neutral_dollar_pct": ndp,
                                "riskoff_cash_pct": rcp,
                                "riskoff_dollar_pct": rdp,
                                "domestic_neutral_threshold": dnt,
                                "domestic_riskoff_threshold": drt,
                            }
                        )
    return combos


def run_hybrid_bd_scan(
    price_data,
    params: Dict[str, Any],
    start: date,
    end: date,
) -> List[Dict[str, Any]]:
    """감도 스캔. run_backtest(skip_baselines=True) 파이프라인 재사용."""
    from app.run_backtest import format_result, run_backtest

    combos = _build_combos()
    logger.info(f"[HYBRID-BD-SCAN] 조합 수: {len(combos)}")

    results: List[Dict[str, Any]] = []
    t_start = time.time()

    for i, combo in enumerate(combos):
        override = {
            "neutral_risky_pct": combo["neutral_risky_pct"],
            "neutral_dollar_pct": combo["neutral_dollar_pct"],
            "riskoff_dollar_pct": combo["riskoff_dollar_pct"],
            "domestic_neutral_threshold": combo["domestic_neutral_threshold"],
            "domestic_riskoff_threshold": combo["domestic_riskoff_threshold"],
        }

        try:
            bt = run_backtest(
                price_data,
                params,
                start,
                end,
                enable_regime=True,
                fear_threshold_override=override,
                skip_baselines=True,
            )
            fmt = format_result(
                bt,
                params,
                start,
                end,
                price_data=price_data,
                run_mode="scan",
            )
            s = fmt["summary"]
            m = fmt["meta"]
        except Exception as exc:
            logger.warning(f"[SCAN] #{i + 1}: {exc}")
            continue

        cagr_v = s.get("cagr") or 0.0
        mdd_v = s.get("mdd") or 0.0
        sharpe_v = s.get("sharpe", 0.0)
        trades = m.get("total_trades", 0)

        exo = bt.get("_exo_regime_result") or {}
        n_cnt = exo.get("neutral_count", 0)
        ro_cnt = exo.get("risk_off_count", 0)

        # safe asset switch count
        sched = exo.get("schedule", {})
        sa_cnt = sum(1 for st in sched.values() if st != "risk_on")

        cagr_ok = cagr_v > 15
        mdd_ok = mdd_v < 10
        if cagr_ok and mdd_ok:
            verdict = "PROMOTE"
        elif cagr_ok:
            verdict = "CAGR_OK"
        else:
            verdict = "REJECT"

        results.append(
            {
                "neutral_risky_pct": combo["neutral_risky_pct"],
                "neutral_cash_pct": combo["neutral_cash_pct"],
                "neutral_dollar_pct": combo["neutral_dollar_pct"],
                "riskoff_cash_pct": combo["riskoff_cash_pct"],
                "riskoff_dollar_pct": combo["riskoff_dollar_pct"],
                "domestic_neutral_threshold": combo["domestic_neutral_threshold"],
                "domestic_riskoff_threshold": combo["domestic_riskoff_threshold"],
                "CAGR": round(cagr_v, 4),
                "MDD": round(mdd_v, 4),
                "Sharpe": round(sharpe_v, 4),
                "total_trades": trades,
                "neutral_count": n_cnt,
                "risk_off_count": ro_cnt,
                "safe_asset_switch_count": sa_cnt,
                "verdict": verdict,
            }
        )

        if (i + 1) % 50 == 0:
            elapsed = time.time() - t_start
            per = elapsed / (i + 1)
            remaining = per * (len(combos) - i - 1)
            logger.info(
                f"[SCAN] {i + 1}/{len(combos)}"
                f" ({elapsed:.0f}s, ~{remaining:.0f}s left)"
            )

    elapsed = time.time() - t_start
    logger.info(f"[SCAN] 완료: {len(results)}/{len(combos)}" f" ({elapsed:.0f}s)")
    return results


def rank_results(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """순위 매기기: MDD<10 우선, CAGR>15 다음, Sharpe 순."""

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


def write_grid_csv(ranked: List[Dict[str, Any]]) -> Path:
    """hybrid_bd_sensitivity_grid.csv 생성."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / "hybrid_bd_sensitivity_grid.csv"
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
) -> Path:
    """hybrid_bd_sensitivity_summary.md 생성."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / "hybrid_bd_sensitivity_summary.md"

    top10 = ranked[:10] if len(ranked) >= 10 else ranked
    promote = [r for r in ranked if r["verdict"] == "PROMOTE"]
    cagr_ok = [r for r in ranked if r["verdict"] == "CAGR_OK"]
    best_mdd = min(ranked, key=lambda r: r["MDD"]) if ranked else None
    gen = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+09:00")

    lines = [
        "# Hybrid B+D Sensitivity Scan Summary",
        "",
        f"- generated_at: {gen}",
        f"- total_combos: {len(ranked)}",
        f"- promote_candidates: {len(promote)}",
        f"- cagr_ok_candidates: {len(cagr_ok)}",
        "- pipeline: run_backtest(skip_baselines=True)",
        "- date_fix: P206-STEP6J-FIX (calendar→trading day snap)",
        "",
        "## 상위 10 후보",
        "",
        "| # | nrp | ndp | rdp | dnt | drt"
        " | CAGR | MDD | Sharpe | Trades"
        " | N | RO | SA | Verdict |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in top10:
        lines.append(
            f"| {r['rank']}"
            f" | {r['neutral_risky_pct']}"
            f" | {r['neutral_dollar_pct']}"
            f" | {r['riskoff_dollar_pct']}"
            f" | {r['domestic_neutral_threshold']}"
            f" | {r['domestic_riskoff_threshold']}"
            f" | {r['CAGR']}%"
            f" | {r['MDD']}%"
            f" | {r['Sharpe']}"
            f" | {r['total_trades']}"
            f" | {r['neutral_count']}"
            f" | {r['risk_off_count']}"
            f" | {r['safe_asset_switch_count']}"
            f" | {r['verdict']} |"
        )

    lines += ["", "## 추천", ""]

    if promote:
        lines.append(f"CAGR>15 + MDD<10 달성: **{len(promote)}개**")
        for r in promote[:5]:
            lines.append(
                f"- nrp={r['neutral_risky_pct']}"
                f" ndp={r['neutral_dollar_pct']}"
                f" rdp={r['riskoff_dollar_pct']}"
                f" dnt={r['domestic_neutral_threshold']}"
                f" → CAGR {r['CAGR']}%"
                f" MDD {r['MDD']}%"
                f" Sharpe {r['Sharpe']}"
            )
    elif cagr_ok:
        lines.append("MDD<10 후보 없음. CAGR>15 중 MDD 최소:")
        b = min(cagr_ok, key=lambda r: r["MDD"])
        lines.append(
            f"- nrp={b['neutral_risky_pct']}"
            f" dnt={b['domestic_neutral_threshold']}"
            f" → CAGR {b['CAGR']}% MDD {b['MDD']}%"
        )
    else:
        lines.append("CAGR>15 후보 없음. 전체 최고 Sharpe:")
        if best_mdd:
            lines.append(
                f"- nrp={best_mdd['neutral_risky_pct']}"
                f" dnt={best_mdd['domestic_neutral_threshold']}"
                f" → CAGR {best_mdd['CAGR']}% MDD {best_mdd['MDD']}%"
            )

    lines += [
        "",
        "## 버그 수정 (P206-STEP6J-FIX)",
        "- 원인: regime schedule 날짜(캘린더 1일) ≠ runner 리밸런스 날짜(실제 거래일)",
        "- 영향: 47%의 regime state가 risk_on 기본값으로 무시됨",
        "- 수정: _rebal_dates를 실제 거래일로 snap",
        "",
        "## 스캔 축",
        f"- neutral_risky_pct: {NEUTRAL_RISKY_PCT_RANGE}",
        f"- neutral_dollar_pct: {NEUTRAL_DOLLAR_PCT_RANGE}",
        f"- riskoff_dollar_pct: {RISKOFF_DOLLAR_PCT_RANGE}",
        f"- domestic_neutral_threshold: {DOMESTIC_NEUTRAL_THRESHOLD_RANGE}",
        f"- domestic_riskoff_threshold: {DOMESTIC_RISKOFF_THRESHOLD_RANGE}",
    ]

    path.write_text("\n".join(lines), encoding="utf-8")
    logger.info(f"[WRITE] summary → {path}")
    return path
