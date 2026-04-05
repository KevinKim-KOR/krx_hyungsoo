# -*- coding: utf-8 -*-
"""
app/tuning/fear_sensitivity_scan.py
P206-STEP6E: VIX Fear Regime 감도 스캔

run_backtest() + format_result() 공식 파이프라인을 재사용하여
threshold × neutral_cash 조합별 결과를 수집한다.
"""

from __future__ import annotations

import csv
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
REPORTS_DIR = PROJECT_ROOT / "reports" / "tuning"


def run_sensitivity_scan(
    price_data,
    params: Dict[str, Any],
    start: date,
    end: date,
) -> List[Dict[str, Any]]:
    """감도 스캔. run_backtest + format_result 공식 파이프라인 재사용."""
    from app.run_backtest import run_backtest, format_result

    risk_on_max_range = [14, 15, 16, 17, 18, 19, 20]
    risk_off_min_range = [18, 20, 22, 24, 26, 28, 30]
    spike_range = [0.05, 0.10, 0.15, 0.20]
    neutral_cash_range = [0.50, 0.65, 0.80]

    results = []
    combo_count = 0

    for rom in risk_on_max_range:
        for rfm in risk_off_min_range:
            if rfm <= rom or rfm - rom < 2:
                continue
            for spike in spike_range:
                for ncash in neutral_cash_range:
                    combo_count += 1
                    override = {
                        "risk_on_max": float(rom),
                        "risk_off_min": float(rfm),
                        "spike_threshold": spike,
                        "neutral_cash_pct": ncash,
                    }

                    try:
                        bt = run_backtest(
                            price_data,
                            params,
                            start,
                            end,
                            enable_regime=True,
                            fear_threshold_override=override,
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
                        logger.warning(f"[SCAN] #{combo_count}: {exc}")
                        continue

                    cagr_v = s.get("cagr") or 0.0
                    mdd_v = s.get("mdd") or 0.0
                    sharpe_v = s.get("sharpe", 0.0)
                    trades = m.get("total_trades", 0)

                    exo = bt.get("_exo_regime_result") or {}
                    n_cnt = exo.get("neutral_count", 0)
                    ro_cnt = exo.get("risk_off_count", 0)

                    cagr_ok = cagr_v > 15
                    mdd_ok = mdd_v < 10
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
                            "CAGR": round(cagr_v, 4),
                            "MDD": round(mdd_v, 4),
                            "Sharpe": round(sharpe_v, 4),
                            "total_trades": trades,
                            "neutral_count": n_cnt,
                            "risk_off_count": ro_cnt,
                            "verdict": verdict,
                        }
                    )

                    if combo_count % 20 == 0:
                        logger.info(f"[SCAN] {combo_count} combos")

    logger.info(f"[SCAN] 완료: {len(results)}/{combo_count}")
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


def write_grid_csv(ranked: List[Dict[str, Any]]) -> Path:
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
    no_regime: Dict[str, Any],
    baseline: Dict[str, Any],
) -> Path:
    """fear_sensitivity_summary.md 생성."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / "fear_sensitivity_summary.md"

    top5 = ranked[:5] if len(ranked) >= 5 else ranked
    promote = [r for r in ranked if r["verdict"] == "PROMOTE"]
    cagr_ok = [r for r in ranked if r["verdict"] == "CAGR_OK_MDD_FAIL"]
    best_mdd = min(ranked, key=lambda r: r["MDD"]) if ranked else None
    gen = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+09:00")

    lines = [
        "# Fear Sensitivity Scan Summary",
        "",
        f"- generated_at: {gen}",
        f"- total_combos: {len(ranked)}",
        f"- promote_candidates: {len(promote)}",
        "- metric_pipeline: run_backtest+format_result (Full 동일)",
        "",
        "## 비교군",
        "",
        "| 구성 | CAGR | MDD | Sharpe | Trades |",
        "|---|---|---|---|---|",
        f"| no regime | {no_regime.get('CAGR', 'N/A')}%"
        f" | {no_regime.get('MDD', 'N/A')}%"
        f" | {no_regime.get('Sharpe', 'N/A')}"
        f" | {no_regime.get('total_trades', 'N/A')} |",
        f"| baseline | {baseline.get('CAGR', 'N/A')}%"
        f" | {baseline.get('MDD', 'N/A')}%"
        f" | {baseline.get('Sharpe', 'N/A')}"
        f" | {baseline.get('total_trades', 'N/A')} |",
        "",
        "## 상위 5 후보",
        "",
        "| # | rom | rfm | spike | ncash"
        " | CAGR | MDD | Sharpe | Trades"
        " | N | RO | Verdict |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in top5:
        lines.append(
            f"| {r['rank']} | {r['risk_on_max']}"
            f" | {r['risk_off_min']}"
            f" | {r['spike_threshold']}"
            f" | {r['neutral_target_cash_pct']}"
            f" | {r['CAGR']}%"
            f" | {r['MDD']}%"
            f" | {r['Sharpe']}"
            f" | {r['total_trades']}"
            f" | {r['neutral_count']}"
            f" | {r['risk_off_count']}"
            f" | {r['verdict']} |"
        )

    lines += ["", "## 추천", ""]

    if promote:
        lines.append(f"MDD<10 + CAGR>15 달성: **{len(promote)}개**")
        for r in promote[:3]:
            lines.append(
                f"- {r['risk_on_max']}/{r['risk_off_min']}"
                f"/{r['spike_threshold']}"
                f"/{r['neutral_target_cash_pct']}"
                f" → CAGR {r['CAGR']}%"
                f" MDD {r['MDD']}%"
            )
    elif cagr_ok:
        lines.append("MDD<10 후보 없음. CAGR>15 중 MDD 최소:")
        b = min(cagr_ok, key=lambda r: r["MDD"])
        lines.append(
            f"- {b['risk_on_max']}/{b['risk_off_min']}"
            f"/{b['spike_threshold']}"
            f"/{b['neutral_target_cash_pct']}"
            f" → CAGR {b['CAGR']}% MDD {b['MDD']}%"
        )
    else:
        lines.append("CAGR>15 후보도 없음. 전체 MDD 최소:")
        if best_mdd:
            lines.append(
                f"- {best_mdd['risk_on_max']}"
                f"/{best_mdd['risk_off_min']}"
                f" → MDD {best_mdd['MDD']}%"
            )

    lines += [
        "",
        "## 보정 철학",
        "- VIX 임계치 하향 → 한국장 독자 변동성 간접 반영",
        "- neutral 빈도/강도 증가 → 독자 하락 방어",
        "- 장중 대응 미포함 (직장인형 EOD 모델)",
    ]

    path.write_text("\n".join(lines), encoding="utf-8")
    logger.info(f"[WRITE] summary → {path}")
    return path
