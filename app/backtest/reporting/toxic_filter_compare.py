#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app/backtest/reporting/toxic_filter_compare.py — P209-STEP9B Track A sweep

Track A toxic filter 실험군(A0~A2, B0~B2)을 sweep 실행하고 비교 요약 산출물을
생성한다.

단일 책임: experiments list → rows (format_result + verdict) + 산출물 생성
패턴: holding_structure/sweep.py 와 동일한 아키텍처

P209-STEP9B realignment FIX (2026-04-11):
- except Exception swallow 제거 → 실패는 즉시 propagate (rule 7)
- silent .get(k, default) fallback 제거 → raw result REQUIRED 필드는 직접 subscript
- experiment 식별 meta (name/baseline_label/drop_mode) 를 runner 에 주입
- compare 산출물에 Baseline / Drop List Size / Avg Held 필드 추가 (지시문 요구)
- Q1~Q4 진단 요약 확장: Rule Set 채택 결론 (Q4) 명시적 문구 출력

주의:
- dynamic scanner / hybrid regime / safe asset / verdict 기준 수정 금지
- 실험군별 변경 허용값은 오직 drop_list, max_positions, allocation_mode
"""

from __future__ import annotations

import csv
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# ─── verdict (CAGR > 15, MDD < 10) — 기존 기준 그대로 ────────────────────
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
    raise ValueError(f"P209-STEP9B 허용되지 않은 allocation_mode: {allocation_mode!r}")


def _require_raw(raw: Dict[str, Any], key: str, variant: str) -> Any:
    """raw result 에서 REQUIRED 필드 직접 subscript (fail-loud).

    rule 6/7: silent .get(k, default) 금지. 누락 시 즉시 KeyError.
    """
    if key not in raw:
        raise KeyError(
            f"P209-STEP9B: {variant} raw result 에 '{key}' 누락."
            f" BacktestRunner.run 이 REQUIRED 필드를 반환하지 않았음."
        )
    return raw[key]


# ─── sweep ─────────────────────────────────────────────────────────────
def run_toxic_filter_sweep(
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
    """Track A 실험군을 sweep 실행.

    각 실험군의 baseline_label → holding_structure_experiments 에서
    max_positions / allocation_mode 해석. drop_list / experiment_name /
    baseline_label / drop_mode 를 runner 에 파라미터로 전달.

    실험 실패는 즉시 propagate (rule 7 fail-loud).
    """
    logger.info(f"[P209-STEP9B] toxic_filter_compare 실험군 {len(experiments)}개 실행")

    hs_by_name = {e["name"]: e for e in holding_experiments}

    out_dir = project_root / "reports" / "tuning"
    out_dir.mkdir(parents=True, exist_ok=True)

    rows: List[Dict[str, Any]] = []

    for exp in experiments:
        name = exp["name"]
        baseline_label = exp["baseline_label"]
        drop_mode = exp["drop_mode"]
        drop_list = exp["drop_list"]

        if baseline_label not in hs_by_name:
            raise KeyError(
                f"P209-STEP9B: baseline_label={baseline_label!r}"
                f" 가 holding_structure_experiments 에 없음"
            )
        hs_spec = hs_by_name[baseline_label]
        max_pos = hs_spec["max_positions"]
        alloc_mode = hs_spec["allocation_mode"]

        exp_params = dict(base_params)
        exp_params["max_positions"] = max_pos
        exp_params["allocation"] = _build_allocation_block(alloc_mode)
        exp_params["holding_structure_experiment_name"] = name
        # 하위 sweep 중첩 방지
        exp_params["holding_structure_experiments"] = None
        exp_params["allocation_experiments"] = None
        exp_params["tracka_toxic_filter_experiments"] = None

        raw = run_backtest_fn(
            price_data,
            exp_params,
            start,
            end,
            enable_regime=True,
            skip_baselines=True,
            toxic_drop_list=drop_list if drop_list else None,
            tracka_filter_experiment_name=name,
            tracka_baseline_label=baseline_label,
            tracka_drop_mode=drop_mode,
        )
        formatted = format_result_fn(
            raw,
            exp_params,
            start,
            end,
            price_data=price_data,
            run_mode="toxic_filter_experiment",
        )
        summary = formatted["summary"]
        meta = formatted["meta"]

        # rule 6/7: REQUIRED 필드 직접 subscript. summary 는 format_result 가
        # 항상 cagr/mdd/sharpe 3개를 설정한다 (값이 None 일 수는 있음).
        if "cagr" not in summary or "mdd" not in summary or "sharpe" not in summary:
            raise KeyError(f"P209-STEP9B: {name} summary 에 cagr/mdd/sharpe 누락")
        cagr = summary["cagr"]
        mdd = summary["mdd"]
        sharpe = summary["sharpe"]

        # raw result 에서 Track A 필드 직접 subscript
        hits_total = _require_raw(raw, "tracka_filter_hits_total", name)
        exhausted = _require_raw(raw, "tracka_filter_exhausted_count", name)
        promoted_total = _require_raw(raw, "tracka_promoted_total", name)
        avg_before = _require_raw(raw, "tracka_avg_candidates_before_filter", name)
        avg_after = _require_raw(raw, "tracka_avg_candidates_after_filter", name)
        avg_held = _require_raw(raw, "avg_held_positions", name)
        drop_list_used = _require_raw(raw, "tracka_drop_list_used", name)

        # meta.total_trades 는 format_result 가 항상 설정
        if "total_trades" not in meta:
            raise KeyError(f"P209-STEP9B: {name} meta 에 total_trades 누락")
        total_trades = meta["total_trades"]

        rows.append(
            {
                "variant": name,
                "baseline_label": baseline_label,
                "drop_mode": drop_mode,
                "drop_list": ",".join(drop_list_used) if drop_list_used else "",
                "drop_list_size": len(drop_list_used),
                "max_positions": max_pos,
                "allocation_mode": alloc_mode,
                "cagr": round(cagr, 4) if cagr is not None else None,
                "mdd": round(mdd, 4) if mdd is not None else None,
                "sharpe": round(sharpe, 4) if sharpe is not None else None,
                "total_trades": total_trades,
                "avg_held_positions": avg_held,
                "filter_hits_total": hits_total,
                "filter_exhausted_count": exhausted,
                "promoted_total": promoted_total,
                "avg_candidates_before_filter": avg_before,
                "avg_candidates_after_filter": avg_after,
                "verdict": _verdict(cagr, mdd),
            }
        )
        logger.info(
            f"[P209-STEP9B] {name}: baseline={baseline_label}"
            f" drop_mode={drop_mode} pos={max_pos}"
            f" CAGR={cagr} MDD={mdd} hits={hits_total}"
            f" exhausted={exhausted} promoted={promoted_total}"
        )

    # 정렬: 1차 MDD 오름차순, 2차 CAGR 내림차순
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


# ─── 산출물 생성 ──────────────────────────────────────────────────────
def _write_outputs(
    rows: List[Dict[str, Any]],
    out_dir: Path,
) -> None:
    """toxic_filter_compare.md / .json / .csv 생성."""
    generated_at = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+09:00")

    # JSON
    payload = {
        "generated_at": generated_at,
        "rows": rows,
    }
    json_path = out_dir / "toxic_filter_compare.json"
    json_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # CSV
    if rows:
        csv_path = out_dir / "toxic_filter_compare.csv"
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)

    # Markdown
    md_lines = _render_md(rows, generated_at)
    md_path = out_dir / "toxic_filter_compare.md"
    md_path.write_text("\n".join(md_lines), encoding="utf-8")
    logger.info(f"[P209-STEP9B] toxic_filter_compare 산출물 → {out_dir}")


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
    """Markdown 비교표 생성 (P209-STEP9B 지시문 완전 준수)."""
    lines = [
        "# P209-STEP9B Track A Toxic Filter Compare",
        "",
        f"- generated_at: {generated_at}",
        f"- experiments: {len(rows)}",
        "- verdict 기준 유지: `CAGR > 15` AND `MDD < 10`",
        "- 정렬: 1차 MDD 오름차순, 2차 CAGR 내림차순",
        "",
        "## 비교표",
        "",
        "| Rank | Variant | Baseline | Drop Mode | Drop List Size"
        " | Max Pos | CAGR | MDD | Sharpe | Avg Held"
        " | Filter Hits | Filter Exhausted | Promoted | Trades | Verdict |",
        "|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['rank']}"
            f" | {r['variant']}"
            f" | {r['baseline_label']}"
            f" | {r['drop_mode']}"
            f" | {r['drop_list_size']}"
            f" | {r['max_positions']}"
            f" | {_fmt_pct(r['cagr'])}"
            f" | {_fmt_pct(r['mdd'])}"
            f" | {_fmt_num(r['sharpe'])}"
            f" | {_fmt_num(r['avg_held_positions'], 3)}"
            f" | {r['filter_hits_total']}"
            f" | {r['filter_exhausted_count']}"
            f" | {r['promoted_total']}"
            f" | {r['total_trades']}"
            f" | {r['verdict']} |"
        )

    # 진단 요약 (Q1~Q4)
    lines += ["", "## 진단 요약"]

    # 실험군 조회 (fail-loud — 없으면 지시문 위반)
    by_variant = {r["variant"]: r for r in rows}
    expected = {
        "A0": "A0_pos2_raew_no_filter",
        "A1": "A1_pos2_raew_primary_drop",
        "A2": "A2_pos2_raew_extended_drop",
        "B0": "B0_pos3_raew_no_filter",
        "B1": "B1_pos3_raew_primary_drop",
        "B2": "B2_pos3_raew_extended_drop",
    }
    missing = [k for k, n in expected.items() if n not in by_variant]
    if missing:
        lines.append(f"- ⚠️ 누락 실험군: {missing} — 지시문 고정 6개 실험군 미준수")

    a0 = by_variant.get(expected["A0"])
    a1 = by_variant.get(expected["A1"])
    a2 = by_variant.get(expected["A2"])
    b0 = by_variant.get(expected["B0"])
    b1 = by_variant.get(expected["B1"])
    b2 = by_variant.get(expected["B2"])

    # Q1: primary drop 이 MDD 를 개선했는가?
    lines.append("")
    lines.append("### Q1. Primary drop 만으로 MDD 개선되는가")
    delta_a_primary: Optional[float] = None
    delta_b_primary: Optional[float] = None
    if a0 and a1 and a0["mdd"] is not None and a1["mdd"] is not None:
        delta_a_primary = round(a0["mdd"] - a1["mdd"], 4)
        lines.append(
            f"- **A baseline (`g2_pos2_raew`)**:"
            f" {a0['mdd']:.2f}% → {a1['mdd']:.2f}%"
            f" (Δ={delta_a_primary:+.2f}%p,"
            f" CAGR {a0['cagr']:.2f}% → {a1['cagr']:.2f}%)"
        )
    if b0 and b1 and b0["mdd"] is not None and b1["mdd"] is not None:
        delta_b_primary = round(b0["mdd"] - b1["mdd"], 4)
        lines.append(
            f"- **B baseline (`g4_pos3_raew`)**:"
            f" {b0['mdd']:.2f}% → {b1['mdd']:.2f}%"
            f" (Δ={delta_b_primary:+.2f}%p,"
            f" CAGR {b0['cagr']:.2f}% → {b1['cagr']:.2f}%)"
        )

    # Q2: extended drop 이 과도한 수익 훼손을 유발하는가?
    lines.append("")
    lines.append("### Q2. Extended drop 이 과도한 수익 훼손을 유발하는가")
    a_ext_cagr_loss: Optional[float] = None
    b_ext_cagr_loss: Optional[float] = None
    if a1 and a2 and a1["cagr"] is not None and a2["cagr"] is not None:
        a_ext_cagr_loss = round(a1["cagr"] - a2["cagr"], 4)
        a_ext_mdd_delta = round(a1["mdd"] - a2["mdd"], 4)
        lines.append(
            f"- **A baseline**:"
            f" CAGR {a1['cagr']:.2f}% → {a2['cagr']:.2f}%"
            f" (ΔCAGR={-a_ext_cagr_loss:+.2f}%p),"
            f" MDD {a1['mdd']:.2f}% → {a2['mdd']:.2f}%"
            f" (ΔMDD={a_ext_mdd_delta:+.2f}%p)"
        )
    if b1 and b2 and b1["cagr"] is not None and b2["cagr"] is not None:
        b_ext_cagr_loss = round(b1["cagr"] - b2["cagr"], 4)
        b_ext_mdd_delta = round(b1["mdd"] - b2["mdd"], 4)
        lines.append(
            f"- **B baseline**:"
            f" CAGR {b1['cagr']:.2f}% → {b2['cagr']:.2f}%"
            f" (ΔCAGR={-b_ext_cagr_loss:+.2f}%p),"
            f" MDD {b1['mdd']:.2f}% → {b2['mdd']:.2f}%"
            f" (ΔMDD={b_ext_mdd_delta:+.2f}%p)"
        )

    # Q3: 운영 vs 연구 baseline 중 어느 쪽이 필터 효과를 더 잘 흡수하는가
    lines.append("")
    lines.append(
        "### Q3. 운영 baseline vs 연구 baseline: 어느 쪽이 필터 효과를 더 잘 흡수하는가"
    )
    if delta_a_primary is not None and delta_b_primary is not None:
        if delta_b_primary > delta_a_primary:
            winner = "연구 baseline (`g4_pos3_raew`)"
            reason = (
                f"B primary drop MDD 개선폭 {delta_b_primary:+.2f}%p"
                f" > A primary drop MDD 개선폭 {delta_a_primary:+.2f}%p"
            )
        elif delta_a_primary > delta_b_primary:
            winner = "운영 baseline (`g2_pos2_raew`)"
            reason = (
                f"A primary drop MDD 개선폭 {delta_a_primary:+.2f}%p"
                f" > B primary drop MDD 개선폭 {delta_b_primary:+.2f}%p"
            )
        else:
            winner = "양쪽 유사"
            reason = f"A/B 개선폭 동일: {delta_a_primary:+.2f}%p"
        lines.append(f"- **우세**: {winner}")
        lines.append(f"- **근거**: {reason}")
    else:
        lines.append("- 데이터 부족 (A0/A1 또는 B0/B1 누락)")

    # Q4: Step9C 로 넘어가기 전 채택할 Rule Set 은 무엇인가 (지시문 핵심 질문)
    lines.append("")
    lines.append("### Q4. Step9C 로 넘어가기 전 채택할 Rule Set 결론")
    promoted = [r["variant"] for r in rows if r["verdict"] == "PROMOTE"]
    if promoted:
        # Promote 가 발생한 경우 — MDD 최저 + CAGR 최고 실험군
        top = rows[0]  # 이미 정렬됨 (MDD 오름차순, CAGR 내림차순)
        lines.append(
            f"- **채택**: `{top['variant']}` (baseline=`{top['baseline_label']}`,"
            f" drop_mode=`{top['drop_mode']}`,"
            f" drop_list={top['drop_list'] or '[]'})"
        )
        lines.append(
            f"- **근거**: MDD {top['mdd']:.2f}% < 10% AND"
            f" CAGR {top['cagr']:.2f}% > 15% — verdict 기준 동시 충족"
        )
        lines.append(f"- PROMOTE 실험군: {', '.join(promoted)}")
    else:
        # Promote 없음 — 차선 Rule Set 권고
        if rows:
            best = rows[0]  # MDD 최저
            lines.append(
                "- **채택 실패**: 6개 실험군 중 `CAGR > 15 AND MDD < 10`"
                " 동시 충족 없음"
            )
            lines.append(
                f"- **차선 권고**: `{best['variant']}`"
                f" (baseline=`{best['baseline_label']}`,"
                f" drop_mode=`{best['drop_mode']}`)"
                f" — MDD {_fmt_pct(best['mdd'])},"
                f" CAGR {_fmt_pct(best['cagr'])}"
            )
            lines.append(
                "- **다음 단계 분기 근거**: primary drop 만으로 MDD < 10 달성 불가"
                " 확인 → Step9C (tighter stop) 또는 Track B (ML classifier) 로"
                " 방향 전환 필요"
            )
        else:
            lines.append("- 실험군 rows 없음 — 완전 실패")

    # Filter exhausted 발생 여부 참고
    any_exhausted = any(r["filter_exhausted_count"] > 0 for r in rows)
    lines.append("")
    lines.append(
        f"- **참고 (Filter exhausted)**: {'발생' if any_exhausted else '없음'}"
        " — `on_exhausted_candidates = leave_unfilled_risky_sleeve_as_cash`"
        " 정책 적용 상태"
    )

    lines += [
        "",
        "## Notes",
        "- Step9B 는 selector_after_ranking_before_final_selection 단계에"
        " blacklist 기반 toxic drop 을 적용한 규칙기반 필터 실험 챕터",
        "- ML / 확률 예측 / trailing stop 미적용",
        "- dynamic scanner / hybrid regime / safe asset / allocation /"
        " holding structure 변경 없음",
    ]
    return lines
