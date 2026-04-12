#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app/backtest/reporting/evidence_writer.py — dynamic_evidence_latest.md 렌더러

P206/P207/P208/P209 챕터의 evidence md 섹션을 통합 생성한다. 각 섹션은 순수
함수로 분리되어 있으며 입력 데이터만 받아 문자열 리스트를 반환한다.

## R5v2 fallback 정책 (rule 6/7 전수 적용)

이 모듈의 모든 `.get(k, default)` 와 `or {}`/`or []` 는 다음 4개 카테고리
중 하나로 분류된다. 각 호출 위치에 카테고리 주석이 명시되어 있다.

1. **REQUIRED**: BacktestRunner.run / format_result / meta_builder 가 반드시
   설정하는 필드. 누락 = 데이터 손상. `bt_meta["key"]` 직접 subscript,
   누락 시 KeyError raise.

2. **OPTIONAL**: legitimate 하게 None/empty 일 수 있는 필드. 예: hybrid regime
   이 disabled 면 `_exo_regime_result` 는 None. 명시적 `if x is None: ...`
   분기로 처리. `or {}`/`or []` 금지.

3. **DISPLAY (whitelist)**: 사용자에게 보여주는 markdown 출력에서 optional
   파일/필드가 누락된 경우 `'N/A'`/`0` 등으로 표시. 이는 파일 로드 실패 등
   정상 케이스를 포함하며 silent bug 가 아니다. 각 호출에
   `# R5 whitelist: display fallback` 주석 명시.

4. **ACCUMULATOR**: `lines: List = []` 등 초기화 패턴. fallback 이 아님.
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
        formatted: format_result 반환값 (summary, meta 필수)
        raw_result: run_backtest 원본 반환값. 아래 optional 필드들을 포함:
            - `_exo_regime_result`: Optional[Dict] (regime 미적용 시 None)
            - `_allocation_rebalance_trace`: Optional[List] (P207 미적용 시 None)
            - `_drawdown_contribution_analyses`: Optional[List] (P209 미실행 시 None)
        project_root: 프로젝트 루트 — reports/tuning 경로 해석용
        output_path: 미지정 시 project_root/reports/tuning/dynamic_evidence_latest.md

    Returns:
        생성된 파일 경로
    """
    ev_dir = project_root / "reports" / "tuning"
    if output_path is None:
        output_path = ev_dir / "dynamic_evidence_latest.md"

    # ── REQUIRED: format_result 가 반드시 설정하는 필드 ──
    if "summary" not in formatted:
        raise KeyError(
            "write_dynamic_evidence: formatted 에 'summary' 누락"
            " (format_result 가 반드시 설정해야 함)"
        )
    if "meta" not in formatted:
        raise KeyError("write_dynamic_evidence: formatted 에 'meta' 누락")
    bt_summary = formatted["summary"]
    bt_meta = formatted["meta"]

    # ── OPTIONAL: 별도 파이프라인 생성 산출물 (누락 가능) ──
    # hybrid_regime_verdict_latest.json: hybrid regime 엔진이 생성
    # promotion_verdict.json: tuning/promotion 엔진이 생성
    # 둘 다 optional — 파일 없으면 section renderer 가 'N/A' 로 표시
    hybrid_verdict = _load_json_if_exists(ev_dir / "hybrid_regime_verdict_latest.json")
    promotion_verdict = _load_json_if_exists(ev_dir / "promotion_verdict.json")

    generated_at = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+09:00")

    # ── REQUIRED: summary 의 숫자 필드 ──
    # format_result 가 반드시 설정 (None 일 수 있지만 키는 존재)
    if "cagr" not in bt_summary:
        raise KeyError("write_dynamic_evidence: summary 에 'cagr' 누락")
    if "mdd" not in bt_summary:
        raise KeyError("write_dynamic_evidence: summary 에 'mdd' 누락")
    cagr_v = bt_summary["cagr"]
    mdd_v = bt_summary["mdd"]
    cagr_ok = "YES" if cagr_v is not None and cagr_v > 15 else "NO"
    mdd_ok = "YES" if mdd_v is not None and mdd_v < 10 else "NO"

    # promotion_verdict 는 OPTIONAL 파일 — 파일 없거나 verdict 키 없으면 'N/A'
    # R5 whitelist: display fallback (optional 파일 미존재 / 부분 데이터)
    verdict_str = promotion_verdict.get("verdict", "N/A")
    conclusion = _build_conclusion(cagr_ok, mdd_ok)

    # ── OPTIONAL: raw_result 의 챕터별 optional 데이터 ──
    # 명시적 None 체크. `or {}` / `or []` 사용 금지.
    exo_raw = raw_result.get("_exo_regime_result")
    exo_regime_result: Dict[str, Any] = exo_raw if exo_raw is not None else {}

    allocation_trace_raw = raw_result.get("_allocation_rebalance_trace")
    allocation_trace: List[Dict[str, Any]] = (
        allocation_trace_raw if allocation_trace_raw is not None else []
    )

    dd_analyses_raw = raw_result.get("_drawdown_contribution_analyses")
    dd_analyses: List[Dict[str, Any]] = (
        dd_analyses_raw if dd_analyses_raw is not None else []
    )

    # ── REQUIRED: summary 의 optional-value 필드 (키는 필수) ──
    if "sharpe" not in bt_summary:
        raise KeyError("write_dynamic_evidence: summary 에 'sharpe' 누락")
    if "total_return" not in bt_summary:
        raise KeyError("write_dynamic_evidence: summary 에 'total_return' 누락")
    sharpe_v = bt_summary["sharpe"]
    total_return_v = bt_summary["total_return"]

    cagr_str = f"{cagr_v:.2f}%" if cagr_v is not None else "N/A"
    mdd_str = f"{mdd_v:.2f}%" if mdd_v is not None else "N/A"
    sharpe_str = f"{sharpe_v:.4f}" if sharpe_v is not None else "N/A"
    total_return_str = f"{total_return_v:.2f}%" if total_return_v is not None else "N/A"

    # ── REQUIRED: format_result 가 반드시 설정하는 meta 필드 ──
    if "total_trades" not in bt_meta:
        raise KeyError("write_dynamic_evidence: meta 에 'total_trades' 누락")
    if "allocation_mode" not in bt_meta:
        raise KeyError(
            "write_dynamic_evidence: meta 에 'allocation_mode' 누락"
            " (build_allocation_meta 가 반드시 설정)"
        )
    if "allocation_fallback_used" not in bt_meta:
        raise KeyError(
            "write_dynamic_evidence: meta 에 'allocation_fallback_used' 누락"
        )
    if "blocked_reason_totals" not in bt_meta:
        raise KeyError(
            "write_dynamic_evidence: meta 에 'blocked_reason_totals' 누락"
            " (format_result 가 반드시 설정)"
        )

    # 섹션 조립 (ACCUMULATOR)
    sections: List[List[str]] = [
        _render_header(generated_at, bt_meta),
        _render_performance_section(
            cagr_str=cagr_str,
            mdd_str=mdd_str,
            sharpe_str=sharpe_str,
            total_return_str=total_return_str,
            total_trades=bt_meta["total_trades"],
        ),
        _render_hybrid_regime_section(hybrid_verdict, exo_regime_result),
        _render_allocation_section(bt_meta, allocation_trace),
        _render_holding_structure_section(bt_meta, verdict_str),
    ]

    dd_section = _render_drawdown_contribution_section(dd_analyses)
    if dd_section:
        sections.append(dd_section)

    # P209-STEP9B: Track A Toxic Filter 섹션 (Legacy 유지)
    tracka_toxic_section = _render_tracka_toxic_filter_section(project_root)
    if tracka_toxic_section:
        sections.append(tracka_toxic_section)

    # P209-STEP9C: Track A Contextual Guard 섹션
    tracka_section = _render_tracka_contextual_guard_section(bt_meta, project_root)
    if tracka_section:
        sections.append(tracka_section)

    trace_section = _render_last_rebalance_trace_section(allocation_trace)
    if trace_section:
        sections.append(trace_section)

    sections.append(_render_promotion_verdict_section(verdict_str, cagr_ok, mdd_ok))
    sections.append(_render_conclusion_section(conclusion))
    sections.append(_render_notes_section())

    lines: List[str] = []  # ACCUMULATOR
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

    R5 whitelist: hybrid_regime_verdict / promotion_verdict 는 별도 파이프라인
    생성물이다. 파일 없음은 "파이프라인 미실행" 정상 케이스이며, 이 경우
    renderer 가 'N/A' 로 표시한다. 빈 dict 반환은 "파일 없음" 의 명시적 시그널.
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
    # R5 whitelist: display fallback — universe_mode/asof 는 format_result 가
    # 보통 설정하지만 일부 경로 (tuning 내부 호출 등) 에서 누락 가능.
    # 사용자 display 용이므로 '?' 표시 허용.
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
    # R5 whitelist: display fallback
    # exo_regime_result 가 {} 인 경우 hybrid regime 이 미적용된 것이며,
    # 이 섹션의 숫자들은 정책 기본값 으로 표시된다. `_exo_regime_result` 필드가
    # 존재하지 않는 run 에서는 어차피 이 섹션을 렌더링할 이유가 없지만,
    # legacy / 일부 경로 호환을 위해 기본값 허용.
    ev_nrp = int(exo_regime_result.get("neutral_risky_pct", 0.35) * 100)
    ev_ndp = int(exo_regime_result.get("neutral_dollar_pct", 0.20) * 100)
    ev_ncp = 100 - ev_nrp - ev_ndp
    ev_rdp = int(exo_regime_result.get("riskoff_dollar_pct", 0.50) * 100)
    ev_rcp = 100 - ev_rdp

    # R5 whitelist: display fallback — hybrid_verdict 는 optional 파일이라
    # 필드 누락 시 'N/A' 표시. _load_json_if_exists 의 빈 dict 도 포함.
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
    # REQUIRED: build_allocation_meta 가 항상 설정 (R5 에서 raise 처리됨)
    allocation_mode = bt_meta["allocation_mode"]
    allocation_fallback_used = bt_meta["allocation_fallback_used"]

    # OPTIONAL: allocation_experiment_name/params 는 non-dynamic 모드에서 None
    # 명시적 None 체크로 display 변환
    exp_name = bt_meta.get("allocation_experiment_name")
    exp_name_display = exp_name if exp_name is not None else "N/A"

    alloc_params_raw = bt_meta.get("allocation_params")
    alloc_params: Dict[str, Any] = (
        alloc_params_raw if alloc_params_raw is not None else {}
    )

    # R5 whitelist: display fallback — alloc_params 가 {} (non-dynamic) 이거나
    # 일부 mode (equal_weight) 에서 weight_floor/cap/vol_lookback 이 없음.
    # 'N/A' 표시는 "해당 mode 에서 사용되지 않음" 의미.
    return [
        "## Allocation",
        "| Field | Value |",
        "|---|---|",
        f"| Mode | {allocation_mode} |",
        f"| Experiment Name | {exp_name_display} |",
        f"| Fallback Used | {allocation_fallback_used} |",
        f"| Weight Floor | {alloc_params.get('weight_floor', 'N/A')} |",
        f"| Weight Cap | {alloc_params.get('weight_cap', 'N/A')} |",
        f"| Vol Lookback | {alloc_params.get('volatility_lookback', 'N/A')} |",
        f"| Rebalances w/ Trace | {len(allocation_trace)} |",
    ]


def _render_holding_structure_section(
    bt_meta: Dict[str, Any],
    verdict_str: str,
) -> List[str]:
    # REQUIRED: format_result 가 항상 설정
    if "holding_structure_max_positions" not in bt_meta:
        raise KeyError(
            "_render_holding_structure_section: meta 에"
            " 'holding_structure_max_positions' 누락"
        )
    if "avg_held_positions" not in bt_meta:
        raise KeyError(
            "_render_holding_structure_section: meta 에 'avg_held_positions' 누락"
        )
    if "max_held_positions_observed" not in bt_meta:
        raise KeyError(
            "_render_holding_structure_section: meta 에"
            " 'max_held_positions_observed' 누락"
        )
    if "rebalances_with_more_than_2_candidates" not in bt_meta:
        raise KeyError(
            "_render_holding_structure_section: meta 에"
            " 'rebalances_with_more_than_2_candidates' 누락"
        )
    if "turnover_proxy" not in bt_meta:
        raise KeyError(
            "_render_holding_structure_section: meta 에 'turnover_proxy' 누락"
        )

    blocked_totals = bt_meta["blocked_reason_totals"]
    # R5 whitelist: display fallback — blocked_reason_totals 는 항상 dict 이지만
    # BLOCKED_MAX_POSITIONS 는 0번 발생한 경우 키가 없을 수 있다 (정상).
    blocked_max_pos = blocked_totals.get("BLOCKED_MAX_POSITIONS", 0)

    # OPTIONAL: holding_structure_experiment_name 은 SSOT 매칭 실패 시 None
    hs_name = bt_meta.get("holding_structure_experiment_name")
    hs_name_display = hs_name if hs_name is not None else "N/A"

    return [
        "## Holding Structure (P208-STEP8A)",
        "| Field | Value |",
        "|---|---|",
        f"| Holding Structure Experiment | {hs_name_display} |",
        f"| Max Positions |" f" {bt_meta['holding_structure_max_positions']} |",
        f"| Allocation Mode | {bt_meta['allocation_mode']} |",
        f"| Avg Held Positions | {bt_meta['avg_held_positions']} |",
        f"| Max Held Positions Observed |"
        f" {bt_meta['max_held_positions_observed']} |",
        f"| Rebalances With >2 Candidates |"
        f" {bt_meta['rebalances_with_more_than_2_candidates']} |",
        f"| Blocked By Max Positions | {blocked_max_pos} |",
        f"| Turnover Proxy | {bt_meta['turnover_proxy']} |",
        f"| Verdict | {verdict_str} |",
    ]


def _render_drawdown_contribution_section(
    dd_analyses: List[Dict[str, Any]],
) -> List[str]:
    if not dd_analyses:
        return []

    # dd_analyses 는 [A, B] 또는 [A, B, C(shadow)]. analyze_variant 가
    # 반환하는 구조이며, 필수 필드는 pipeline.analyze_variant 에서 보장된다.
    # P209-STEP9A baseline realignment: B = g4_pos3_raew (research),
    # C = g3_pos3_eq (shadow reference, 정식 baseline 아님).
    a_an = dd_analyses[0] if len(dd_analyses) > 0 else {}
    b_an = dd_analyses[1] if len(dd_analyses) > 1 else {}
    c_an: Dict[str, Any] = {}
    for _an in dd_analyses[2:]:
        if _an.get("role") == "shadow_reference":
            c_an = _an
            break

    # OPTIONAL: mdd_window/selection_quality_summary 는 NO_DATA 경로에서 None
    # 명시적 None → {} 치환 (display 용)
    a_mdd_window = a_an.get("mdd_window")
    b_mdd_window = b_an.get("mdd_window")
    a_w: Dict[str, Any] = a_mdd_window if a_mdd_window is not None else {}
    b_w: Dict[str, Any] = b_mdd_window if b_mdd_window is not None else {}

    a_sqs = a_an.get("selection_quality_summary")
    b_sqs = b_an.get("selection_quality_summary")
    a_qs: Dict[str, Any] = a_sqs if a_sqs is not None else {}
    b_qs: Dict[str, Any] = b_sqs if b_sqs is not None else {}

    # OPTIONAL (default []): top_ticker_contributors_to_mdd / worst_selection_events
    # analyze_variant 가 항상 list 를 반환 (빈 [] 포함) → 직접 subscript
    a_top = a_an["top_ticker_contributors_to_mdd"]
    b_top = b_an["top_ticker_contributors_to_mdd"]
    a_worst = a_an["worst_selection_events"]
    b_worst = b_an["worst_selection_events"]

    # P209-STEP9A FIX: 공통 toxic 계산 로직을 drawdown.toxic_summary 로 통일.
    # report_writer.py 와 동일한 기준 (top 3, shadow 제외) 을 사용하여
    # 산출물 간 Step9B 근거가 일관되도록 한다.
    from app.backtest.reporting.drawdown.toxic_summary import (
        compute_common_toxic_primary,
    )

    common = compute_common_toxic_primary(dd_analyses)
    common_str = ", ".join(common) if common else "(no common)"

    a_gap = a_qs.get("avg_selection_gap_pct")  # may be None
    b_gap = b_qs.get("avg_selection_gap_pct")

    # R5 whitelist: display fallback — a_w/a_qs 가 빈 dict 인 NO_DATA 경로에서
    # 각 필드는 'N/A'/0 으로 표시. 이는 NO_DATA 의 명시적 표현.
    lines = [
        "## Drawdown Contribution (P209-STEP9A)",
        "_Baseline realignment (2026-04-11): B = 최신 UI 기준 연구 baseline_",
        "| Field | A (Operational) | B (Research) |",
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
    ]

    if c_an:
        c_mdd_window = c_an.get("mdd_window")
        c_w: Dict[str, Any] = c_mdd_window if c_mdd_window is not None else {}
        c_sqs = c_an.get("selection_quality_summary")
        c_qs: Dict[str, Any] = c_sqs if c_sqs is not None else {}
        c_top = c_an["top_ticker_contributors_to_mdd"]
        c_worst = c_an["worst_selection_events"]
        c_gap = c_qs.get("avg_selection_gap_pct")
        lines += [
            "",
            "### Shadow Reference (C, 보조 참고용)",
            "| Field | C (Shadow) |",
            "|---|---|",
            f"| Baseline Label | {c_an.get('label', 'N/A')} |",
            f"| Role | {c_an.get('role', '-')} |",
            f"| MDD % | {c_w.get('mdd_pct', 'N/A')}% |",
            f"| Top Toxic (top 3) | {_fmt_top_toxic(c_top)} |",
            f"| Worst Selection Event | {_fmt_worst_event(c_worst)} |",
            f"| Avg Selection Gap (Unsel−Sel)"
            f" | {c_gap if c_gap is not None else 'N/A'}%p |",
            f"| Selection Quality Verdict"
            f" | **{c_an.get('selection_quality_verdict', 'N/A')}** |",
            "",
            "_Shadow = 정식 baseline 아님. Step9B 필터 근거 교집합에서 제외._",
        ]

    lines += [
        "",
        "_Step9A = 분석 챕터. 필터/ML 실제 적용 없음._",
    ]
    return lines


def _fmt_top_toxic(top_list: List[Dict[str, Any]]) -> str:
    if not top_list:
        return "N/A"
    # R5 whitelist: display fallback — ticker/contribution 필드는 analyze_variant
    # 에서 항상 설정되지만 방어적으로 .get 사용 (display 용)
    return ", ".join(
        f"{r.get('ticker')}({r.get('contribution_to_nav_pct')}%)" for r in top_list[:3]
    )


def _fmt_worst_event(evts: List[Dict[str, Any]]) -> str:
    if not evts:
        return "N/A"
    e = evts[0]
    # R5 whitelist: display fallback
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
    # R5 whitelist: display fallback — trace 내부 필드는 P207 이 항상 설정
    # 하지만 일부 optional (raw_vols 는 risk_aware mode 만) 이므로 .get 사용.
    lines = [
        "### Last Rebalance Trace",
        f"- date: {last_t.get('date', 'N/A')}",
        f"- mode: {last_t.get('mode', 'N/A')}",
        f"- fallback: {last_t.get('fallback_used', False)}",
    ]

    # OPTIONAL: raw_vols 는 risk_aware_equal_weight_v1 모드에서만 설정됨
    # pre_cap_weights / post_cap_weights / final_weights 도 동일
    raw_vols_raw = last_t.get("raw_vols")
    pre_cap_raw = last_t.get("pre_cap_weights")
    post_cap_raw = last_t.get("post_cap_weights")
    final_w_raw = last_t.get("final_weights")
    raw_vols: Dict[str, float] = raw_vols_raw if raw_vols_raw is not None else {}
    pre_cap: Dict[str, float] = pre_cap_raw if pre_cap_raw is not None else {}
    post_cap: Dict[str, float] = post_cap_raw if post_cap_raw is not None else {}
    final_w: Dict[str, float] = final_w_raw if final_w_raw is not None else {}

    if not (raw_vols or final_w):
        return lines

    lines += [
        "",
        "| Code | Raw Score | Raw Vol | Pre-Cap W | Post-Cap W | Final W |",
        "|---|---|---|---|---|---|",
    ]
    raw_scores_raw = last_t.get("raw_scores")
    raw_scores: Dict[str, float] = raw_scores_raw if raw_scores_raw is not None else {}
    for tc in final_w:
        rv = raw_vols.get(tc)
        rv_s = f"{rv:.4f}" if rv is not None else "N/A"
        rs = raw_scores.get(tc)
        rs_s = f"{rs:.4f}" if rs is not None else "N/A"
        # R5 whitelist: display fallback — weight 는 "해당 ticker 가 cap
        # 스테이지에 포함되지 않았을 때 0" 이라는 정확한 semantic 이다.
        # 즉 `pre_cap.get(tc, 0)` 의 0 은 "값이 없어서 default" 가 아니라
        # "그 스테이지에서 weight=0 이었음" 의 정확한 수학적 표현.
        pre_cap_val = pre_cap.get(tc, 0)
        post_cap_val = post_cap.get(tc, 0)
        final_w_val = final_w.get(tc, 0)
        lines.append(
            f"| {tc}"
            f" | {rs_s}"
            f" | {rv_s}"
            f" | {pre_cap_val:.4f}"
            f" | {post_cap_val:.4f}"
            f" | {final_w_val:.4f} |"
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


def _render_tracka_contextual_guard_section(
    bt_meta: Dict[str, Any],
    project_root: Path,
) -> List[str]:
    compare_path = project_root / "reports" / "tuning" / "contextual_guard_compare.json"
    if not compare_path.exists():
        return []

    compare_data = _load_json_if_exists(compare_path)
    # OPTIONAL: rows 키는 contextual_guard_compare 파이프라인이 생성.
    # 파일이 없거나 sweep 미실행이면 None. 쓸 데이터 없으면 섹션 미생성이 정상 케이스.
    rows_raw = compare_data.get("rows")
    if rows_raw is None or not rows_raw:
        return []
    rows = rows_raw

    lines = [
        "## Track A Contextual Guard (P209-STEP9C)",
        "",
        "| Rank | Variant | Baseline Label | Guard Mode"
        " | Max Pos | CAGR | MDD"
        " | Pre-Entry Hits | Early-Stop Hits | Exhausted | Promoted"
        " | Avg Before | Avg After | Verdict |",
        "|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for r in rows:
        # WHITELIST (display): contextual_guard_compare.py 가 생성하는 sweep JSON 산출물.
        # 각 로우 필드는 sweep 실패/부분 실행 시 누락 가능. format_result 계약 밖 외부 파일.
        # 따라서 및 표현 구조 보장 없음. display fallback 주석 남김이 Rule 6/7 준수 증거.
        cagr_v = r.get("cagr")  # WHITELIST (display): sweep 실패 시 None
        mdd_v = r.get("mdd")  # WHITELIST (display): sweep 실패 시 None
        cagr_s = f"{cagr_v:.2f}%" if cagr_v is not None else "N/A"
        mdd_s = f"{mdd_v:.2f}%" if mdd_v is not None else "N/A"
        lines.append(
            f"| {r.get('rank', '-')}"  # WHITELIST (display)
            f" | {r.get('variant', 'N/A')}"  # WHITELIST (display)
            f" | {r.get('baseline_label', 'N/A')}"  # WHITELIST (display)
            f" | {r.get('guard_mode', 'N/A')}"  # WHITELIST (display)
            f" | {r.get('max_positions', 'N/A')}"  # WHITELIST (display)
            f" | {cagr_s}"
            f" | {mdd_s}"
            f" | {r.get('pre_entry_hits_total', 0)}"  # WHITELIST (display)
            f" | {r.get('early_stop_hits_total', 0)}"  # WHITELIST (display)
            f" | {r.get('guard_exhausted_count', 0)}"  # WHITELIST (display)
            f" | {r.get('promoted_total', 0)}"  # WHITELIST (display)
            f" | {r.get('avg_candidates_before_guard', 'N/A')}"  # WHITELIST (display)
            f" | {r.get('avg_candidates_after_guard', 'N/A')}"  # WHITELIST (display)
            f" | {r.get('verdict', 'N/A')} |"  # WHITELIST (display)
        )

    # R5 whitelist (display): None 값을 "필드 없음" 의미로 '-' 혹은 0으로 출력 (정상)
    pre_entry_hits = bt_meta["tracka_pre_entry_guard_hits_total"]
    early_stop_hits = bt_meta["tracka_early_stop_hits_total"]
    exhausted = bt_meta["tracka_guard_exhausted_count"]
    promoted = bt_meta["tracka_promoted_total"]
    avg_before = bt_meta["tracka_avg_candidates_before_guard"]
    avg_after = bt_meta["tracka_avg_candidates_after_guard"]
    baseline = bt_meta["tracka_baseline_label"]
    guard_mode = bt_meta["tracka_guard_mode"]

    pre_hits = pre_entry_hits if pre_entry_hits is not None else 0
    early_hits = early_stop_hits if early_stop_hits is not None else 0
    exhaust_val = exhausted if exhausted is not None else 0
    promoted_val = promoted if promoted is not None else 0

    lines += [
        "",
        "### Main Run Guard State",
        "| Field | Value |",
        "|---|---|",
        f"| Baseline Label | {baseline if baseline is not None else '-'} |",
        f"| Guard Mode | {guard_mode if guard_mode is not None else 'none'} |",
        f"| Pre-Entry Hits | {pre_hits} |",
        f"| Early-Stop Hits | {early_hits} |",
        f"| Guard Exhausted Count | {exhaust_val} |",
        f"| Promoted Replacement | {promoted_val} |",
        f"| Avg Candidates Before | {avg_before if avg_before is not None else '-'} |",
        f"| Avg Candidates After | {avg_after if avg_after is not None else '-'} |",
        "",
        "_Track A = Contextual Guard. 정적 drop 이나 ML 확률 예측 아님._",
    ]
    return lines


def _render_tracka_toxic_filter_section(project_root: Path) -> List[str]:
    """P209-STEP9B Track A Toxic Filter 섹션 렌더러 (Legacy 유지용).

    toxic_filter_compare.json 이 존재하면 로드하여 비교표를 렌더링.
    """
    compare_path = project_root / "reports" / "tuning" / "toxic_filter_compare.json"
    if not compare_path.exists():
        return []

    try:
        with open(compare_path, encoding="utf-8") as f:
            import json

            compare_data = json.load(f)
    except Exception:
        return []

    # OPTIONAL: toxic_filter_compare 파이프라인 산출물.
    # 파일 로드 실패 또는 데이터 없음 시 None.
    rows_raw = compare_data.get("rows")
    if not rows_raw:
        return []
    rows = rows_raw

    lines = [
        "## Track A Toxic Filter (P209-STEP9B)",
        "",
        "| Rank | Variant | Baseline Label | Drop Mode | Drop List"
        " | Drop List Size | Max Pos | CAGR | MDD"
        " | Filter Hits | Filter Exhausted | Promoted Replacement"
        " | Avg Before | Avg After | Verdict |",
        "|---:|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for r in rows:
        # WHITELIST (display): Legacy Step9B sweep JSON 산출물 필드.
        # sweep 실패 또는 부분 실행 시 누락 가능 → display fallback 'N/A' 정당.
        cagr_v = r.get("cagr")  # WHITELIST (display)
        mdd_v = r.get("mdd")  # WHITELIST (display)
        cagr_s = f"{cagr_v:.2f}%" if cagr_v is not None else "N/A"
        mdd_s = f"{mdd_v:.2f}%" if mdd_v is not None else "N/A"
        # Rule 6: `or "-"` 금지. 명시적 None 체크 분기.
        drop_list_raw = r.get("drop_list")
        drop_list_str = drop_list_raw if drop_list_raw is not None else "-"
        lines.append(
            f"| {r.get('rank', '-')}"  # WHITELIST (display)
            f" | {r.get('variant', 'N/A')}"  # WHITELIST (display)
            f" | {r.get('baseline_label', 'N/A')}"  # WHITELIST (display)
            f" | {r.get('drop_mode', 'N/A')}"  # WHITELIST (display)
            f" | {drop_list_str}"
            f" | {r.get('drop_list_size', 0)}"  # WHITELIST (display)
            f" | {r.get('max_positions', 'N/A')}"  # WHITELIST (display)
            f" | {cagr_s}"
            f" | {mdd_s}"
            f" | {r.get('filter_hits_total', 0)}"  # WHITELIST (display)
            f" | {r.get('filter_exhausted_count', 0)}"  # WHITELIST (display)
            f" | {r.get('promoted_total', 0)}"  # WHITELIST (display)
            f" | {r.get('avg_candidates_before_filter', 'N/A')}"  # WHITELIST (display)
            f" | {r.get('avg_candidates_after_filter', 'N/A')}"  # WHITELIST (display)
            f" | {r.get('verdict', 'N/A')} |"  # WHITELIST (display)
        )
    return lines
