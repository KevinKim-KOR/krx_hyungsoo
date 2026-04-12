#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app/backtest/reporting/contextual_guard_compare.py — P209-STEP9C Track A sweep

Track A contextual guard 실험군(A0~A3, B0~B3)을 sweep 실행하고
비교 요약 산출물을 생성한다.

단일 책임: experiments list → rows (format_result + verdict) + 산출물 생성
패턴: holding_structure/sweep.py 와 동일한 아키텍처

P209-STEP9C 적용:
- toxic filter (정적 로직) 에서 contextual guard (동적 로직)으로 교체
- pre-entry (선진입 검증) & early-stop (초기 10일 손절) 성능 분리 추적
- 8개 실험군 렌더링
"""

from __future__ import annotations

import csv
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


def _verdict(cagr: Optional[float], mdd: Optional[float]) -> str:
    if cagr is None or mdd is None:
        return "NO_DATA"
    if cagr > 15 and mdd < 10:
        return "PROMOTE"
    return "REJECT"


def _build_allocation_block(allocation_mode: str) -> Dict[str, Any]:
    """holding_structure/sweep.py._build_allocation_block 과 동일 로직."""
    if allocation_mode == "dynamic_equal_weight":
        return {
            "mode": "dynamic_equal_weight",
            "fallback_mode": "dynamic_equal_weight",
        }
    if allocation_mode == "risk_aware_equal_weight_v1":
        return {
            "mode": "risk_aware_equal_weight_v1",
            "volatility_lookback": 20,
            "volatility_floor": 0.05,
            "volatility_cap": 0.6,
            "weight_floor": 0.35,
            "weight_cap": 0.65,
            "fallback_mode": "dynamic_equal_weight",
        }
    raise ValueError(f"P209-STEP9C 허용되지 않은 allocation_mode: {allocation_mode!r}")


def _require_raw(raw: Dict[str, Any], key: str, variant: str) -> Any:
    if key not in raw:
        raise KeyError(
            f"P209-STEP9C: {variant} raw result 에 '{key}' 누락."
            f" BacktestRunner.run 이 REQUIRED 필드를 반환하지 않았음."
        )
    return raw[key]


def run_contextual_guard_sweep(
    experiments: List[Dict[str, Any]],
    base_params: Dict[str, Any],
    holding_experiments: List[Dict[str, Any]],
    price_data,
    start,
    end,
    run_backtest_fn: Callable,
    format_result_fn: Callable,
    project_root: Path,
) -> List[Dict[str, Any]]:
    logger.info(
        f"[P209-STEP9C] contextual_guard_compare 실험군 {len(experiments)}개 실행"
    )

    hs_by_name = {e["name"]: e for e in holding_experiments}

    out_dir = project_root / "reports" / "tuning"
    out_dir.mkdir(parents=True, exist_ok=True)

    rows: List[Dict[str, Any]] = []

    for exp in experiments:
        name = exp["name"]
        baseline_label = exp["baseline_label"]
        guard_mode = exp["guard_mode"]

        if baseline_label not in hs_by_name:
            raise KeyError(
                f"P209-STEP9C: baseline_label={baseline_label!r}"
                f" 가 holding_structure_experiments 에 없음"
            )
        hs_spec = hs_by_name[baseline_label]
        max_pos = hs_spec["max_positions"]
        alloc_mode = hs_spec["allocation_mode"]

        exp_params = dict(base_params)
        exp_params["max_positions"] = max_pos
        exp_params["allocation"] = _build_allocation_block(alloc_mode)
        exp_params["holding_structure_experiment_name"] = name
        exp_params["holding_structure_experiments"] = None
        exp_params["allocation_experiments"] = None
        exp_params["tracka_contextual_guard_experiments"] = None

        # Rule 6/7: 필수 파라미터는 필수 subscript
        guard_params = base_params["tracka_contextual_guard"]

        raw = run_backtest_fn(
            price_data,
            exp_params,
            start,
            end,
            enable_regime=True,
            skip_baselines=True,
            contextual_guard_params=guard_params,
            tracka_guard_experiment_name=name,
            tracka_baseline_label=baseline_label,
            tracka_guard_mode=guard_mode,
        )
        formatted = format_result_fn(
            raw,
            exp_params,
            start,
            end,
            price_data=price_data,
            run_mode="contextual_guard_experiment",
        )
        summary = formatted["summary"]
        meta = formatted["meta"]

        if "cagr" not in summary or "mdd" not in summary or "sharpe" not in summary:
            raise KeyError(f"P209-STEP9C: {name} summary 에 cagr/mdd/sharpe 누락")

        cagr = summary["cagr"]
        mdd = summary["mdd"]
        sharpe = summary["sharpe"]

        pre_entry_hits = _require_raw(raw, "tracka_pre_entry_guard_hits_total", name)
        early_stop_hits = _require_raw(raw, "tracka_early_stop_hits_total", name)
        exhausted = _require_raw(raw, "tracka_guard_exhausted_count", name)
        promoted_total = _require_raw(raw, "tracka_promoted_total", name)
        avg_before = _require_raw(raw, "tracka_avg_candidates_before_guard", name)
        avg_after = _require_raw(raw, "tracka_avg_candidates_after_guard", name)
        avg_held = _require_raw(raw, "avg_held_positions", name)

        if "total_trades" not in meta:
            raise KeyError(f"P209-STEP9C: {name} meta 에 total_trades 누락")
        total_trades = meta["total_trades"]

        rows.append(
            {
                "variant": name,
                "baseline_label": baseline_label,
                "guard_mode": guard_mode,
                "max_positions": max_pos,
                "allocation_mode": alloc_mode,
                "cagr": round(cagr, 4) if cagr is not None else None,
                "mdd": round(mdd, 4) if mdd is not None else None,
                "sharpe": round(sharpe, 4) if sharpe is not None else None,
                "total_trades": total_trades,
                "avg_held_positions": avg_held,
                "pre_entry_hits_total": pre_entry_hits,
                "early_stop_hits_total": early_stop_hits,
                "guard_exhausted_count": exhausted,
                "promoted_total": promoted_total,
                "avg_candidates_before_guard": avg_before,
                "avg_candidates_after_guard": avg_after,
                "verdict": _verdict(cagr, mdd),
            }
        )
        logger.info(
            f"[P209-STEP9C] {name}: baseline={baseline_label}"
            f" guard_mode={guard_mode} pos={max_pos}"
            f" CAGR={cagr} MDD={mdd} pre_entry={pre_entry_hits}"
            f" early_stop={early_stop_hits} promoted={promoted_total}"
        )

    def _sort_key(r: Dict[str, Any]):
        mdd_v = r["mdd"]
        cagr_v = r["cagr"]
        return (
            mdd_v if mdd_v is not None else 9999.0,
            -(cagr_v if cagr_v is not None else -9999.0),
        )

    rows.sort(key=_sort_key)
    for i, r in enumerate(rows, start=1):
        r["rank"] = i

    _write_outputs(rows, out_dir)
    return rows


def _write_outputs(
    rows: List[Dict[str, Any]],
    out_dir: Path,
) -> None:
    generated_at = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+09:00")

    payload = {
        "generated_at": generated_at,
        "rows": rows,
    }
    json_path = out_dir / "contextual_guard_compare.json"
    json_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    if rows:
        csv_path = out_dir / "contextual_guard_compare.csv"
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)

    md_lines = _render_md(rows, generated_at)
    md_path = out_dir / "contextual_guard_compare.md"
    md_path.write_text("\n".join(md_lines), encoding="utf-8")
    logger.info(f"[P209-STEP9C] contextual_guard_compare 산출물 → {out_dir}")


def _fmt_pct(v: Optional[float]) -> str:
    return f"{v:.2f}%" if v is not None else "N/A"


def _fmt_num(v: Optional[float], digits: int = 4) -> str:
    if v is None:
        return "N/A"
    return f"{v:.{digits}f}"


def _render_md(
    rows: List[Dict[str, Any]],
    generated_at: str,
) -> List[str]:
    lines = [
        "# P209-STEP9C Track A Contextual Guard Compare",
        "",
        f"- generated_at: {generated_at}",
        f"- experiments: {len(rows)}",
        "- verdict 기준 유지: `CAGR > 15` AND `MDD < 10`",
        "- 정렬: 1차 MDD 오름차순, 2차 CAGR 내림차순",
        "",
        "## 비교표",
        "",
        "| Rank | Variant | Baseline | Guard Mode"
        " | Max Pos | CAGR | MDD | Sharpe | Avg Held"
        " | Pre-Entry Hits | Early-Stop Hits | Exhausted | Promoted"
        " | Trades | Verdict |",
        "|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['rank']}"
            f" | {r['variant']}"
            f" | {r['baseline_label']}"
            f" | {r['guard_mode']}"
            f" | {r['max_positions']}"
            f" | {_fmt_pct(r['cagr'])}"
            f" | {_fmt_pct(r['mdd'])}"
            f" | {_fmt_num(r['sharpe'])}"
            f" | {_fmt_num(r['avg_held_positions'], 3)}"
            f" | {r['pre_entry_hits_total']}"
            f" | {r['early_stop_hits_total']}"
            f" | {r['guard_exhausted_count']}"
            f" | {r['promoted_total']}"
            f" | {r['total_trades']}"
            f" | {r['verdict']} |"
        )

    lines += ["", "## 진단 요약"]

    # 실험군 조회
    by_variant = {r["variant"]: r for r in rows}
    expected = {
        "A0": "A0_pos2_raew_no_guard",
        "A1": "A1_pos2_raew_pre_entry_guard",
        "A2": "A2_pos2_raew_early_stop_guard",
        "A3": "A3_pos2_raew_combined_guard",
        "B0": "B0_pos3_raew_no_guard",
        "B1": "B1_pos3_raew_pre_entry_guard",
        "B2": "B2_pos3_raew_early_stop_guard",
        "B3": "B3_pos3_raew_combined_guard",
    }
    missing = [k for k, n in expected.items() if n not in by_variant]
    if missing:
        lines.append(f"- ⚠️ 누락 실험군: {missing} — 지시문 고정 8개 실험군 미준수")

    a0 = by_variant.get(expected["A0"])
    a3 = by_variant.get(expected["A3"])

    b0 = by_variant.get(expected["B0"])
    b3 = by_variant.get(expected["B3"])

    lines.append("")
    lines.append(
        "### Q1. Pre-entry Guard 가 MDD 개선에 성공했는가 (No-guard vs Pre-entry)"
    )
    a1 = by_variant.get(expected["A1"])
    b1 = by_variant.get(expected["B1"])
    if a0 and a1 and a0["mdd"] is not None and a1["mdd"] is not None:
        delta = round(a0["mdd"] - a1["mdd"], 4)
        cagr_diff = round(a1["cagr"] - a0["cagr"], 4)
        lines.append(
            f"- **A baseline:**"
            f" MDD {a0['mdd']:.2f}% → {a1['mdd']:.2f}% (Δ={delta:+.2f}%p),"
            f" CAGR {a0['cagr']:.2f}% → {a1['cagr']:.2f}% (Δ={cagr_diff:+.2f}%p)"
        )
    if b0 and b1 and b0["mdd"] is not None and b1["mdd"] is not None:
        delta = round(b0["mdd"] - b1["mdd"], 4)
        cagr_diff = round(b1["cagr"] - b0["cagr"], 4)
        lines.append(
            f"- **B baseline:**"
            f" MDD {b0['mdd']:.2f}% → {b1['mdd']:.2f}% (Δ={delta:+.2f}%p),"
            f" CAGR {b0['cagr']:.2f}% → {b1['cagr']:.2f}% (Δ={cagr_diff:+.2f}%p)"
        )

    lines.append("")
    lines.append("### Q2. Early-Stop 단독 효과 (No-guard vs Early-stop)")
    a2 = by_variant.get(expected["A2"])
    b2 = by_variant.get(expected["B2"])
    if a0 and a2 and a0["mdd"] is not None and a2["mdd"] is not None:
        delta = round(a0["mdd"] - a2["mdd"], 4)
        cagr_diff = round(a2["cagr"] - a0["cagr"], 4)
        lines.append(
            f"- **A baseline:**"
            f" MDD {a0['mdd']:.2f}% → {a2['mdd']:.2f}% (Δ={delta:+.2f}%p),"
            f" CAGR {a0['cagr']:.2f}% → {a2['cagr']:.2f}% (Δ={cagr_diff:+.2f}%p)"
        )
    if b0 and b2 and b0["mdd"] is not None and b2["mdd"] is not None:
        delta = round(b0["mdd"] - b2["mdd"], 4)
        cagr_diff = round(b2["cagr"] - b0["cagr"], 4)
        lines.append(
            f"- **B baseline:**"
            f" MDD {b0['mdd']:.2f}% → {b2['mdd']:.2f}% (Δ={delta:+.2f}%p),"
            f" CAGR {b0['cagr']:.2f}% → {b2['cagr']:.2f}% (Δ={cagr_diff:+.2f}%p)"
        )

    lines.append("")
    lines.append(
        "### Q3. Combined(Pre-entry + Early-Stop) 시 과잉 방어(수익 훼손) 여부 확인"
    )
    if a2 and a3 and a2["cagr"] is not None and a3["cagr"] is not None:
        cagr_diff = round(a3["cagr"] - a2["cagr"], 4)
        mdd_diff = round(a2["mdd"] - a3["mdd"], 4)
        lines.append(
            f"- **A baseline (Early-stop vs Combined):**"
            f" CAGR {a2['cagr']:.2f}% → {a3['cagr']:.2f}% (Δ={cagr_diff:+.2f}%p),"
            f" MDD 개선 (Δ={mdd_diff:+.2f}%p)"
        )
    if b2 and b3 and b2["cagr"] is not None and b3["cagr"] is not None:
        cagr_diff = round(b3["cagr"] - b2["cagr"], 4)
        mdd_diff = round(b2["mdd"] - b3["mdd"], 4)
        lines.append(
            f"- **B baseline (Early-stop vs Combined):**"
            f" CAGR {b2['cagr']:.2f}% → {b3['cagr']:.2f}% (Δ={cagr_diff:+.2f}%p),"
            f" MDD 개선 (Δ={mdd_diff:+.2f}%p)"
        )

    lines.append("")
    lines.append("### Q4. A/B baseline 흡수력 비교 (운영 vs 연구)")
    delta_a: Optional[float] = None
    delta_b: Optional[float] = None
    if a0 and a3 and a0["mdd"] is not None and a3["mdd"] is not None:
        delta_a = round(a0["mdd"] - a3["mdd"], 4)
    if b0 and b3 and b0["mdd"] is not None and b3["mdd"] is not None:
        delta_b = round(b0["mdd"] - b3["mdd"], 4)

    if delta_a is not None and delta_b is not None:
        if delta_b > delta_a:
            winner = "연구 baseline (`g4_pos3_raew`)"
            reason = f"B({delta_b:+.2f}%p) > A({delta_a:+.2f}%p)"
        elif delta_a > delta_b:
            winner = "운영 baseline (`g2_pos2_raew`)"
            reason = f"A({delta_a:+.2f}%p) > B({delta_b:+.2f}%p)"
        else:
            winner = "동등 수준"
            reason = f"A={delta_a:+.2f}%p, B={delta_b:+.2f}%p"
        lines.append(f"- **결과**: {winner} — {reason}")

    lines.append("")
    lines.append("### Q5. Step10 채택 Rule Set 결론 (기반 성능 충족 여부)")
    promoted = [r["variant"] for r in rows if r["verdict"] == "PROMOTE"]
    if promoted:
        top = rows[0]
        lines.append(
            f"- **채택**: `{top['variant']}` (baseline=`{top['baseline_label']}`,"
            f" guard_mode=`{top['guard_mode']}`)"
        )
        lines.append(
            f"- **근거**: MDD {top['mdd']:.2f}% < 10% AND"
            f" CAGR {top['cagr']:.2f}% > 15% — verdict 기준 동시 충족"
        )
    else:
        if rows:
            best = rows[0]
            lines.append(
                "- **채택 실패**: 8개 실험군 중 `CAGR > 15 AND MDD < 10` 동시 충족 없음"
            )
            lines.append(
                f"- **차선 권고**: `{best['variant']}`"
                f" (baseline=`{best['baseline_label']}`,"
                f" guard_mode=`{best['guard_mode']}`)"
            )
            lines.append(
                "- **다음 단계 분기 근거**: 규칙기반 문맥 가드로도 한계 확인"
                " -> Track B (ML) 로 전환 논의"
            )

    return lines
