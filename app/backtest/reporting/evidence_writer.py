#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app/backtest/reporting/evidence_writer.py — dynamic_evidence_latest.md 렌더러

P206/P207/P208/P209 챕터의 evidence md 섹션을 통합 생성한다. 각 섹션은 순수
함수로 분리되어 있으며 입력 데이터만 받아 문자열 리스트를 반환한다. 최종
출력은 `\\n` 으로 join 하여 단일 markdown 파일로 저장된다.

R1 단계 원칙:
- run_backtest.py 의 inline f-string blob 을 순수 추출한다
- **byte-level 보존**: 생성 markdown 의 내용/순서/공백이 refactor 이전과 완전 일치
  (유일한 허용 차이는 `generated_at:` 타임스탬프)
- R1 은 fallback / 구조 개선이 아니라 '추출' 만 한다. 기존 silent fallback
  (`_fv = {}` 등) 동작은 그대로 유지. R5 에서 감사 예정.

호출:
    from app.backtest.reporting.evidence_writer import write_dynamic_evidence
    write_dynamic_evidence(
        formatted=formatted,
        raw_result=result,
        project_root=PROJECT_ROOT,
    )
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ─── 공개 진입점 ───────────────────────────────────────────────────────
def write_dynamic_evidence(
    *,
    formatted: Dict[str, Any],
    raw_result: Dict[str, Any],
    project_root: Path,
    output_path: Optional[Path] = None,
) -> Path:
    """dynamic_evidence_latest.md 를 생성하고 저장한다.

    Args:
        formatted: format_result 반환값 (summary, meta)
        raw_result: run_backtest 원본 반환값 (_exo_regime_result,
            _allocation_rebalance_trace, _drawdown_contribution_analyses)
        project_root: 프로젝트 루트 — reports/tuning 경로 해석용
        output_path: 미지정 시 project_root/reports/tuning/dynamic_evidence_latest.md

    Returns:
        생성된 파일 경로
    """
    ev_dir = project_root / "reports" / "tuning"
    if output_path is None:
        output_path = ev_dir / "dynamic_evidence_latest.md"

    bt_summary = formatted.get("summary", {})
    bt_meta = formatted.get("meta", {})

    # R1: byte-level 보존을 위해 기존 파일 로드 패턴 유지.
    # 이 silent fallback 들은 R5 fallback 감사 STEP 에서 재검토 대상.
    hybrid_verdict = _load_json_if_exists(ev_dir / "hybrid_regime_verdict_latest.json")
    promotion_verdict = _load_json_if_exists(ev_dir / "promotion_verdict.json")

    generated_at = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+09:00")

    cagr_v = bt_summary.get("cagr")
    mdd_v = bt_summary.get("mdd")
    cagr_ok = "YES" if cagr_v is not None and cagr_v > 15 else "NO"
    mdd_ok = "YES" if mdd_v is not None and mdd_v < 10 else "NO"
    verdict_str = promotion_verdict.get("verdict", "N/A")
    conclusion = _build_conclusion(cagr_ok, mdd_ok)

    exo_regime_result = raw_result.get("_exo_regime_result") or {}
    allocation_trace = raw_result.get("_allocation_rebalance_trace", [])
    dd_analyses = raw_result.get("_drawdown_contribution_analyses") or []

    cagr_str = f"{cagr_v:.2f}%" if cagr_v is not None else "N/A"
    mdd_str = f"{mdd_v:.2f}%" if mdd_v is not None else "N/A"
    sharpe_str = f"{bt_summary.get('sharpe', 0):.4f}"
    total_return_v = bt_summary.get("total_return")
    total_return_str = f"{total_return_v:.2f}%" if total_return_v is not None else "N/A"

    # 섹션 조립 — 각 renderer 가 빈 리스트를 반환하면 해당 섹션은 skip
    sections: List[List[str]] = [
        _render_header(generated_at, bt_meta),
        _render_performance_section(
            cagr_str=cagr_str,
            mdd_str=mdd_str,
            sharpe_str=sharpe_str,
            total_return_str=total_return_str,
            total_trades=bt_meta.get("total_trades", "N/A"),
        ),
        _render_hybrid_regime_section(hybrid_verdict, exo_regime_result),
        _render_allocation_section(bt_meta, allocation_trace),
        _render_holding_structure_section(bt_meta, verdict_str),
    ]

    dd_section = _render_drawdown_contribution_section(dd_analyses)
    if dd_section:
        sections.append(dd_section)

    trace_section = _render_last_rebalance_trace_section(allocation_trace)
    if trace_section:
        sections.append(trace_section)

    sections.append(_render_promotion_verdict_section(verdict_str, cagr_ok, mdd_ok))
    sections.append(_render_conclusion_section(conclusion))
    sections.append(_render_notes_section())

    lines: List[str] = []
    for i, section in enumerate(sections):
        if i > 0:
            lines.append("")
        lines.extend(section)

    output_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info(f"[WRITE] dynamic_evidence → {output_path}")
    return output_path


# ─── 보조 함수 ────────────────────────────────────────────────────────
def _load_json_if_exists(path: Path) -> Dict[str, Any]:
    """JSON 파일 로드. 없으면 빈 dict 반환.

    R1: 기존 run_backtest.py 의 silent fallback 패턴을 그대로 유지.
    R5 의 fallback 감사에서 재검토 예정.
    """
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _build_conclusion(cagr_ok: str, mdd_ok: str) -> str:
    if cagr_ok == "YES" and mdd_ok == "YES":
        return "승격 가능. 정책 효과 확인됨."
    if cagr_ok == "YES":
        return "구현 통과. MDD 미달로 정책 효과 실패. 정책 재설계 필요."
    return "CAGR/MDD 모두 미달. 전략 재검토 필요."


# ─── 섹션 렌더러 ──────────────────────────────────────────────────────
def _render_header(generated_at: str, bt_meta: Dict[str, Any]) -> List[str]:
    return [
        "# Dynamic Evidence Latest",
        "",
        f"- generated_at: {generated_at}",
        f"- universe_mode: {bt_meta.get('universe_mode', '?')}",
        f"- backtest_asof: {bt_meta.get('asof', '?')}",
    ]


def _render_performance_section(
    *,
    cagr_str: str,
    mdd_str: str,
    sharpe_str: str,
    total_return_str: str,
    total_trades: Any,
) -> List[str]:
    return [
        "## Performance",
        "| Metric | Value |",
        "|---|---:|",
        f"| CAGR | {cagr_str} |",
        f"| MDD | {mdd_str} |",
        f"| Sharpe | {sharpe_str} |",
        f"| Total Return | {total_return_str} |",
        f"| Total Trades | {total_trades} |",
    ]


def _render_hybrid_regime_section(
    hybrid_verdict: Dict[str, Any],
    exo_regime_result: Dict[str, Any],
) -> List[str]:
    ev_nrp = int(exo_regime_result.get("neutral_risky_pct", 0.35) * 100)
    ev_ndp = int(exo_regime_result.get("neutral_dollar_pct", 0.20) * 100)
    ev_ncp = 100 - ev_nrp - ev_ndp
    ev_rdp = int(exo_regime_result.get("riskoff_dollar_pct", 0.50) * 100)
    ev_rcp = 100 - ev_rdp
    return [
        "## Hybrid Regime",
        "| Field | Value |",
        "|---|---|",
        f"| Global State | {hybrid_verdict.get('global_state', 'N/A')} |",
        f"| Domestic State | {hybrid_verdict.get('domestic_state', 'N/A')} |",
        f"| Aggregate | {hybrid_verdict.get('aggregate_state', 'N/A')} |",
        f"| Policy | {hybrid_verdict.get('policy_applied', 'N/A')} |",
        f"| Neutral Count | {hybrid_verdict.get('neutral_count', 0)} |",
        f"| Risk-off Count | {hybrid_verdict.get('risk_off_count', 0)} |",
        f"| Checkpoint | {hybrid_verdict.get('checkpoint_id', 'K6')} |",
        f"| Global Source |"
        f" {hybrid_verdict.get('global_source_timestamp', 'N/A')} |",
        f"| Domestic Source |"
        f" {hybrid_verdict.get('domestic_source_timestamp', 'N/A')} |",
        "| Alignment | us_close_to_kr_next_open |",
        "| Policy Variant | B+D (domestic softening + safe asset) |",
        "| Domestic Handling | neutral_only (no domestic hard gate) |",
        "| Safe Asset Mode | dollar_etf neutral/risk_off |",
        "| Safe Asset | 261240 (달러 ETF) |",
        f"| Neutral Alloc | risky {ev_nrp}%"
        f" / cash {ev_ncp}%"
        f" / dollar {ev_ndp}% |",
        f"| Risk-off Alloc | cash {ev_rcp}% / dollar {ev_rdp}% |",
        "| Checkpoint Summary | K1~K6 (백테스트: 일봉 근사) |",
    ]


def _render_allocation_section(
    bt_meta: Dict[str, Any],
    allocation_trace: List[Dict[str, Any]],
) -> List[str]:
    alloc_params = bt_meta.get("allocation_params") or {}
    return [
        "## Allocation",
        "| Field | Value |",
        "|---|---|",
        f"| Mode | {bt_meta.get('allocation_mode', 'dynamic_equal_weight')} |",
        f"| Experiment Name |" f" {bt_meta.get('allocation_experiment_name', 'N/A')} |",
        f"| Fallback Used | {bt_meta.get('allocation_fallback_used', False)} |",
        f"| Weight Floor | {alloc_params.get('weight_floor', 'N/A')} |",
        f"| Weight Cap | {alloc_params.get('weight_cap', 'N/A')} |",
        f"| Vol Lookback | {alloc_params.get('volatility_lookback', 'N/A')} |",
        f"| Rebalances w/ Trace | {len(allocation_trace)} |",
    ]


def _render_holding_structure_section(
    bt_meta: Dict[str, Any],
    verdict_str: str,
) -> List[str]:
    blocked_totals = bt_meta.get("blocked_reason_totals") or {}
    blocked_max_pos = blocked_totals.get("BLOCKED_MAX_POSITIONS", 0)
    hs_name = bt_meta.get("holding_structure_experiment_name") or "N/A"
    return [
        "## Holding Structure (P208-STEP8A)",
        "| Field | Value |",
        "|---|---|",
        f"| Holding Structure Experiment | {hs_name} |",
        f"| Max Positions |"
        f" {bt_meta.get('holding_structure_max_positions', 'N/A')} |",
        f"| Allocation Mode | {bt_meta.get('allocation_mode', 'N/A')} |",
        f"| Avg Held Positions | {bt_meta.get('avg_held_positions', 0.0)} |",
        f"| Max Held Positions Observed |"
        f" {bt_meta.get('max_held_positions_observed', 0)} |",
        f"| Rebalances With >2 Candidates |"
        f" {bt_meta.get('rebalances_with_more_than_2_candidates', 0)} |",
        f"| Blocked By Max Positions | {blocked_max_pos} |",
        f"| Turnover Proxy | {bt_meta.get('turnover_proxy', 0.0)} |",
        f"| Verdict | {verdict_str} |",
    ]


def _render_drawdown_contribution_section(
    dd_analyses: List[Dict[str, Any]],
) -> List[str]:
    if not dd_analyses:
        return []

    a_an = dd_analyses[0] if len(dd_analyses) > 0 else {}
    b_an = dd_analyses[1] if len(dd_analyses) > 1 else {}
    a_w = a_an.get("mdd_window") or {}
    b_w = b_an.get("mdd_window") or {}
    a_qs = a_an.get("selection_quality_summary") or {}
    b_qs = b_an.get("selection_quality_summary") or {}
    a_top = a_an.get("top_ticker_contributors_to_mdd") or []
    b_top = b_an.get("top_ticker_contributors_to_mdd") or []
    a_worst = a_an.get("worst_selection_events") or []
    b_worst = b_an.get("worst_selection_events") or []

    a_toxic_set = {r.get("ticker") for r in a_top[:5]}
    b_toxic_set = {r.get("ticker") for r in b_top[:5]}
    common = sorted(t for t in (a_toxic_set & b_toxic_set) if t)
    common_str = ", ".join(common) if common else "(no common)"

    a_gap = a_qs.get("avg_selection_gap_pct")
    b_gap = b_qs.get("avg_selection_gap_pct")

    return [
        "## Drawdown Contribution (P209-STEP9A)",
        "| Field | A (Operational) | B (Compared) |",
        "|---|---|---|",
        f"| Baseline Label"
        f" | {a_an.get('label', 'N/A')}"
        f" | {b_an.get('label', 'N/A')} |",
        f"| Role" f" | {a_an.get('role', '-')}" f" | {b_an.get('role', '-')} |",
        f"| MDD %"
        f" | {a_w.get('mdd_pct', 'N/A')}%"
        f" | {b_w.get('mdd_pct', 'N/A')}% |",
        f"| MDD Peak Date"
        f" | {a_w.get('peak_date', 'N/A')}"
        f" | {b_w.get('peak_date', 'N/A')} |",
        f"| MDD Trough Date"
        f" | {a_w.get('trough_date', 'N/A')}"
        f" | {b_w.get('trough_date', 'N/A')} |",
        f"| Top Toxic (top 3)"
        f" | {_fmt_top_toxic(a_top)}"
        f" | {_fmt_top_toxic(b_top)} |",
        f"| Worst Selection Event"
        f" | {_fmt_worst_event(a_worst)}"
        f" | {_fmt_worst_event(b_worst)} |",
        f"| Positive Forward Ratio"
        f" | {a_qs.get('positive_forward_ratio', 0)}"
        f" | {b_qs.get('positive_forward_ratio', 0)} |",
        f"| Avg Forward Return"
        f" | {a_qs.get('avg_forward_return_pct', 0)}%"
        f" | {b_qs.get('avg_forward_return_pct', 0)}% |",
        f"| Avg Selection Gap (Unsel−Sel)"
        f" | {a_gap if a_gap is not None else 'N/A'}%p"
        f" | {b_gap if b_gap is not None else 'N/A'}%p |",
        f"| Selection Quality Verdict"
        f" | **{a_an.get('selection_quality_verdict', 'N/A')}**"
        f" | **{b_an.get('selection_quality_verdict', 'N/A')}** |",
        "",
        f"**A ∩ B 공통 Toxic Tickers**: {common_str}",
        "",
        "_Step9A = 분석 챕터. 필터/ML 실제 적용 없음._",
    ]


def _fmt_top_toxic(top_list: List[Dict[str, Any]]) -> str:
    if not top_list:
        return "N/A"
    return ", ".join(
        f"{r.get('ticker')}({r.get('contribution_to_nav_pct')}%)" for r in top_list[:3]
    )


def _fmt_worst_event(evts: List[Dict[str, Any]]) -> str:
    if not evts:
        return "N/A"
    e = evts[0]
    g = e.get("selection_gap_pct")
    g_str = f" gap={g}%p" if g is not None else ""
    return (
        f"{e.get('rebalance_date', 'N/A')}"
        f" worst={e.get('worst_ticker', 'N/A')}"
        f" ret={e.get('worst_return_pct', 'N/A')}%"
        f"{g_str}"
    )


def _render_last_rebalance_trace_section(
    allocation_trace: List[Dict[str, Any]],
) -> List[str]:
    if not allocation_trace:
        return []

    last_t = allocation_trace[-1]
    lines = [
        "### Last Rebalance Trace",
        f"- date: {last_t.get('date', 'N/A')}",
        f"- mode: {last_t.get('mode', 'N/A')}",
        f"- fallback: {last_t.get('fallback_used', False)}",
    ]

    raw_vols = last_t.get("raw_vols", {})
    pre_cap = last_t.get("pre_cap_weights", {})
    post_cap = last_t.get("post_cap_weights", {})
    final_w = last_t.get("final_weights", {})
    if not (raw_vols or final_w):
        return lines

    lines += [
        "",
        "| Code | Raw Score | Raw Vol | Pre-Cap W | Post-Cap W | Final W |",
        "|---|---|---|---|---|---|",
    ]
    raw_scores = last_t.get("raw_scores", {})
    for tc in final_w:
        rv = raw_vols.get(tc)
        rv_s = f"{rv:.4f}" if rv is not None else "N/A"
        rs = raw_scores.get(tc)
        rs_s = f"{rs:.4f}" if rs is not None else "N/A"
        lines.append(
            f"| {tc}"
            f" | {rs_s}"
            f" | {rv_s}"
            f" | {pre_cap.get(tc, 0):.4f}"
            f" | {post_cap.get(tc, 0):.4f}"
            f" | {final_w.get(tc, 0):.4f} |"
        )
    return lines


def _render_promotion_verdict_section(
    verdict_str: str,
    cagr_ok: str,
    mdd_ok: str,
) -> List[str]:
    return [
        "## Promotion Verdict",
        "| Field | Value |",
        "|---|---|",
        f"| Verdict | {verdict_str} |",
        f"| CAGR > 15 | {cagr_ok} |",
        f"| MDD < 10 | {mdd_ok} |",
    ]


def _render_conclusion_section(conclusion: str) -> List[str]:
    return [
        "## One-line Conclusion",
        conclusion,
    ]


def _render_notes_section() -> List[str]:
    return [
        "## Notes",
        "- 백테스트: 일봉 근사 (장중 K1~K6 체크포인트는 당일 종가로 근사)",
        "- 직장인형 저빈도 체크포인트 대응 모델 (상시 실시간 아님)",
    ]
