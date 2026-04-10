#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app/backtest/reporting/holding_structure_compare.py — P208-STEP8A

보유 구조 비교 실험(G1~G8) 전용 sweep/요약 생성기.

- max_positions × allocation_mode 조합을 동일 dynamic universe/hybrid B+D/
  safe asset 정책 하에서 실행하고, 보유 종목 수 구조의 순수 효과를 비교한다.
- 산출물: holding_structure_compare.md / .csv / .json

주의:
- dynamic scanner / hybrid regime / safe asset / verdict 기준 수정 금지
- 실험군별 변경 허용값은 오직 max_positions, allocation_mode
- inverse_volatility_v1 재도입 금지
"""

from __future__ import annotations

import csv as _csv
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List

logger = logging.getLogger(__name__)

_RAEW_DEFAULTS = {
    "mode": "risk_aware_equal_weight_v1",
    "volatility_lookback": 20,
    "volatility_floor": 0.05,
    "volatility_cap": 0.6,
    "weight_floor": 0.35,
    "weight_cap": 0.65,
    "fallback_mode": "dynamic_equal_weight",
}

_EQW_DEFAULTS = {
    "mode": "dynamic_equal_weight",
    "fallback_mode": "dynamic_equal_weight",
}


def _build_allocation_block(allocation_mode: str) -> Dict[str, Any]:
    """실험군 allocation_mode에 맞는 allocation 블록 반환.

    P208-STEP8A는 대표 2개 모드만 허용:
    - dynamic_equal_weight
    - risk_aware_equal_weight_v1 (P207 기본 floor/cap=0.35/0.65 유지)
    """
    if allocation_mode == "dynamic_equal_weight":
        return dict(_EQW_DEFAULTS)
    if allocation_mode == "risk_aware_equal_weight_v1":
        return dict(_RAEW_DEFAULTS)
    raise ValueError(f"P208-STEP8A 허용되지 않은 allocation_mode: {allocation_mode!r}")


def _verdict(cagr: float, mdd: float) -> str:
    """CAGR>15 & MDD<10 기준 (P206 verdict 기준 유지)."""
    if cagr is None or mdd is None:
        return "REJECT"
    return "PROMOTE" if (cagr > 15 and mdd < 10) else "REJECT"


def run_holding_structure_sweep(
    experiments: List[Dict[str, Any]],
    base_params: Dict[str, Any],
    price_data,
    start,
    end,
    run_backtest_fn: Callable,
    format_result_fn: Callable,
    project_root: Path,
) -> List[Dict[str, Any]]:
    """G1~G8 실험군을 동일 dynamic universe/hybrid regime/safe asset 하에서 실행.

    각 실험군당 max_positions와 allocation_mode만 변경되며 나머지 정책/시나리오는
    base_params 그대로 공유된다.
    """
    logger.info(f"[P208-SWEEP] holding_structure 실험군 {len(experiments)}개 실행")

    out_dir = project_root / "reports" / "tuning"
    out_dir.mkdir(parents=True, exist_ok=True)

    rows: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []

    for exp in experiments:
        name = exp["name"]
        max_pos = exp["max_positions"]
        mode = exp["allocation_mode"]

        try:
            exp_params = dict(base_params)
            exp_params["max_positions"] = max_pos
            exp_params["allocation"] = _build_allocation_block(mode)
            exp_params["holding_structure_experiment_name"] = name
            # 하위 sweep 중첩 방지
            exp_params["holding_structure_experiments"] = None
            exp_params["allocation_experiments"] = None

            raw = run_backtest_fn(
                price_data,
                exp_params,
                start,
                end,
                enable_regime=True,
                skip_baselines=True,
            )
            formatted = format_result_fn(
                raw,
                exp_params,
                start,
                end,
                price_data=price_data,
                run_mode="holding_structure_experiment",
            )
            summary = formatted["summary"]
            meta = formatted["meta"]

            cagr = summary.get("cagr")
            mdd = summary.get("mdd")
            sharpe = summary.get("sharpe")
            blocked_totals = meta.get("blocked_reason_totals") or {}
            blocked_max_pos = int(blocked_totals.get("BLOCKED_MAX_POSITIONS", 0))

            rows.append(
                {
                    "variant": name,
                    "max_positions": max_pos,
                    "allocation_mode": mode,
                    "cagr": round(cagr, 4) if cagr is not None else None,
                    "mdd": round(mdd, 4) if mdd is not None else None,
                    "sharpe": round(sharpe, 4) if sharpe is not None else None,
                    "total_trades": meta.get("total_trades", 0),
                    "avg_held_positions": meta.get("avg_held_positions", 0.0),
                    "max_held_positions_observed": meta.get(
                        "max_held_positions_observed", 0
                    ),
                    "rebalances_with_more_than_2_candidates": meta.get(
                        "rebalances_with_more_than_2_candidates", 0
                    ),
                    "blocked_max_positions": blocked_max_pos,
                    "blocked_reason_totals": blocked_totals,
                    "turnover_proxy": meta.get("turnover_proxy", 0.0),
                    "verdict": _verdict(cagr, mdd),
                }
            )
            logger.info(
                f"[P208-SWEEP] {name}: pos={max_pos} mode={mode}"
                f" CAGR={cagr} MDD={mdd} blocked_max_pos={blocked_max_pos}"
            )
        except Exception as exc:
            logger.warning(f"[P208-SWEEP] {name} 실패: {exc}")
            errors.append(
                {
                    "variant": name,
                    "max_positions": max_pos,
                    "allocation_mode": mode,
                    "error": str(exc),
                }
            )

    # 정렬: 1차 MDD 오름차순, 2차 CAGR 내림차순
    def _sort_key(r: Dict[str, Any]):
        mdd = r.get("mdd")
        cagr = r.get("cagr")
        return (
            mdd if mdd is not None else 9999.0,
            -(cagr if cagr is not None else -9999.0),
        )

    rows.sort(key=_sort_key)
    for i, r in enumerate(rows, start=1):
        r["rank"] = i

    _write_outputs(rows, errors, out_dir)
    return rows


def _write_outputs(
    rows: List[Dict[str, Any]],
    errors: List[Dict[str, Any]],
    out_dir: Path,
) -> None:
    """holding_structure_compare.md / .csv / .json 생성."""
    generated_at = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+09:00")

    # JSON
    json_path = out_dir / "holding_structure_compare.json"
    json_path.write_text(
        json.dumps(
            {
                "generated_at": generated_at,
                "experiments": rows,
                "errors": errors,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # CSV (flat)
    if rows:
        csv_path = out_dir / "holding_structure_compare.csv"
        _csv_rows = []
        for r in rows:
            rr = dict(r)
            rr["blocked_reason_totals"] = json.dumps(
                rr.get("blocked_reason_totals", {}),
                ensure_ascii=False,
            )
            _csv_rows.append(rr)
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            w = _csv.DictWriter(f, fieldnames=list(_csv_rows[0].keys()))
            w.writeheader()
            w.writerows(_csv_rows)

    # Markdown
    lines: List[str] = [
        "# Holding Structure Compare (P208-STEP8A)",
        "",
        f"- generated_at: {generated_at}",
        f"- experiments: {len(rows)}",
        "- scope: holding_structure_only (max_positions × allocation_mode)",
        "- shared: same dynamic scanner / hybrid B+D / safe asset / verdict",
        "- verdict: CAGR > 15 AND MDD < 10",
        "- 정렬: 1차 MDD 오름차순, 2차 CAGR 내림차순",
        "",
        "## 비교표",
        "",
        (
            "| Rank | Variant | Max Positions | Allocation"
            " | CAGR | MDD | Sharpe | Avg Held"
            " | Blocked MaxPos | Verdict |"
        ),
        "|---|---|---:|---|---:|---:|---:|---:|---:|---|",
    ]
    for r in rows:
        cagr = r.get("cagr")
        mdd = r.get("mdd")
        sharpe = r.get("sharpe")
        lines.append(
            f"| {r.get('rank', '-')}"
            f" | {r.get('variant', '-')}"
            f" | {r.get('max_positions', '-')}"
            f" | {r.get('allocation_mode', '-')}"
            f" | {cagr if cagr is not None else 'ERR'}%"
            f" | {mdd if mdd is not None else 'ERR'}%"
            f" | {sharpe if sharpe is not None else '-'}"
            f" | {r.get('avg_held_positions', '-')}"
            f" | {r.get('blocked_max_positions', 0)}"
            f" | {r.get('verdict', '-')} |"
        )

    if errors:
        lines += ["", "## 오류"]
        for e in errors:
            lines.append(
                f"- {e.get('variant')}"
                f" (pos={e.get('max_positions')}, mode={e.get('allocation_mode')})"
                f": {e.get('error')}"
            )

    # 진단 요약 (지시문의 4가지 질문)
    lines += _diagnostic_summary(rows)

    md_path = out_dir / "holding_structure_compare.md"
    md_path.write_text("\n".join(lines), encoding="utf-8-sig")
    logger.info(f"[P208-SWEEP] 비교 산출물 생성: {len(rows)} 실험군 → {md_path}")


def _diagnostic_summary(rows: List[Dict[str, Any]]) -> List[str]:
    """지시문이 요구한 4가지 질문에 답하는 요약 섹션."""
    if not rows:
        return ["", "## 진단 요약", "- 실험군 데이터가 없어 진단 불가"]

    pos2_rows = [r for r in rows if r.get("max_positions") == 2]
    pos3_rows = [r for r in rows if r.get("max_positions") == 3]
    pos4_rows = [r for r in rows if r.get("max_positions") == 4]
    pos5_rows = [r for r in rows if r.get("max_positions") == 5]

    def _avg(key: str, subset: List[Dict[str, Any]]):
        vals = [r.get(key) for r in subset if r.get(key) is not None]
        if not vals:
            return None
        return round(sum(vals) / len(vals), 4)

    def _sum(key: str, subset: List[Dict[str, Any]]):
        return sum(int(r.get(key, 0) or 0) for r in subset)

    pos2_blocked_sum = _sum("blocked_max_positions", pos2_rows)
    pos2_blocked_avg = _avg("blocked_max_positions", pos2_rows)
    pos2_pre_cap_max = max(
        (
            int(r.get("rebalances_with_more_than_2_candidates", 0) or 0)
            for r in pos2_rows
        ),
        default=0,
    )
    pos2_avg_mdd = _avg("mdd", pos2_rows)

    pos_blocks = [
        ("pos2", pos2_rows),
        ("pos3", pos3_rows),
        ("pos4", pos4_rows),
        ("pos5", pos5_rows),
    ]
    avg_mdd_by_pos = {
        label: _avg("mdd", subset) for label, subset in pos_blocks if subset
    }
    avg_cagr_by_pos = {
        label: _avg("cagr", subset) for label, subset in pos_blocks if subset
    }

    # Q1: max_positions=2가 병목이었는가
    # 진짜 병목 판정은 pre-cap 후보 풀이 2개 초과였던 리밸런스 수를 본다.
    # (pos2에서 BLOCKED_MAX_POSITIONS는 candidate 수가 실제로 많았음을 뜻한다)
    _q1_bottleneck = pos2_blocked_sum > 0 or pos2_pre_cap_max > 0
    q1 = (
        "pos2 실험군당 평균 Blocked MaxPos={}회"
        " (실험군 합계 {}회),"
        " pre-cap 후보>2 리밸런스={}회"
        " → 병목 {}"
    ).format(
        pos2_blocked_avg if pos2_blocked_avg is not None else 0,
        pos2_blocked_sum,
        pos2_pre_cap_max,
        "존재 (확대 필요 가능)" if _q1_bottleneck else "미확인",
    )

    # Q2: 보유 수 확대가 MDD를 줄였는가
    def _fmt(v):
        return f"{v:.2f}%" if v is not None else "N/A"

    mdd_str = ", ".join(f"{k}={_fmt(v)}" for k, v in avg_mdd_by_pos.items())
    if pos2_avg_mdd is not None and avg_mdd_by_pos:
        _min_label = min(
            avg_mdd_by_pos,
            key=lambda k: (
                avg_mdd_by_pos[k] if avg_mdd_by_pos[k] is not None else 9999.0
            ),
        )
        q2 = f"평균 MDD [{mdd_str}]" f" → 최저 MDD 구간: {_min_label}"
    else:
        q2 = f"평균 MDD [{mdd_str}]"

    # Q3: CAGR 훼손폭
    cagr_str = ", ".join(f"{k}={_fmt(v)}" for k, v in avg_cagr_by_pos.items())
    q3 = f"평균 CAGR [{cagr_str}]"

    # Q4: 다음 단계 기본 search space
    # MDD<10 만족하는 구간 우선, 없으면 MDD 최소 구간
    def _score(label, subset):
        avg_m = _avg("mdd", subset)
        avg_c = _avg("cagr", subset)
        if avg_m is None:
            return (1, 9999.0, 0.0)
        ok = 0 if (avg_m < 10 and (avg_c or 0) > 15) else 1
        return (ok, avg_m, -(avg_c or 0))

    ranked = sorted(
        [(label, subset) for label, subset in pos_blocks if subset],
        key=lambda x: _score(x[0], x[1]),
    )
    next_space = ranked[0][0] if ranked else "N/A"
    q4 = f"다음 단계 기본 search space 후보: {next_space}"

    return [
        "",
        "## 진단 요약",
        f"- Q1 (pos2가 실제 병목이었는가): {q1}",
        f"- Q2 (보유 수 확대가 MDD를 줄였는가): {q2}",
        f"- Q3 (CAGR 훼손폭): {q3}",
        f"- Q4 (다음 단계 기본 search space): {q4}",
    ]
