#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pc_cockpit/views/helpers/contextual_guard_panel.py — P209-STEP9C UI helper

Track A Contextual Guard 관련 Streamlit 렌더러.
workflow.py / parameter_editor.py 에서 호출.

R6 원칙: 순수 view 함수. 데이터 변환 없음.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import streamlit as st


def render_contextual_guard_panel_for_parameters(p: Dict[str, Any]) -> None:
    """Parameters 탭의 Track A Contextual Guard 섹션 (P209-STEP9C)."""
    st.subheader("Track A Contextual Guard (P209-STEP9C)")

    # OPTIONAL: tracka_contextual_guard 는 Step9C 상위 파라미터 블록.
    # 미설정 시 None 이며 가드 비활성화 상태임을 의미 (legitimate).
    config = p.get("tracka_contextual_guard")
    if config is None:
        st.info("tracka_contextual_guard 설정 없음 (비활성)")
        return

    req_keys = [
        "pre_entry_recent_return_days",
        "pre_entry_recent_return_min",
        "pre_entry_drawdown_days",
        "pre_entry_drawdown_min",
        "pre_entry_vol_spike_ratio_max",
        "early_stop_days_from_entry",
        "early_stop_drawdown_from_entry",
    ]
    for k in req_keys:
        if k not in config:
            st.error(f"tracka_contextual_guard 필수 키 누락: {k}")
            return

    c1, c2, c3, c4 = st.columns(4)
    ret_min_pct = config["pre_entry_recent_return_min"] * 100
    ret_days = config["pre_entry_recent_return_days"]
    c1.metric("Pre-Entry Ret Limit", f"{ret_min_pct:.1f}% ({ret_days}D)")
    dd_min_pct = config["pre_entry_drawdown_min"] * 100
    dd_days = config["pre_entry_drawdown_days"]
    c2.metric("Pre-Entry DD Limit", f"{dd_min_pct:.1f}% ({dd_days}D)")
    c3.metric("Pre-Entry Vol Limit", f"{config['pre_entry_vol_spike_ratio_max']:.1f}x")
    early_dd_pct = config["early_stop_drawdown_from_entry"] * 100
    early_days = config["early_stop_days_from_entry"]
    c4.metric("Early-Stop Limit", f"{early_dd_pct:.1f}% ({early_days}D)")

    # REQUIRED: param_loader 가 이미 검증한 필수필드. 누락 시 KeyError.
    st.caption(f"Apply Stage: `{config['guard_apply_stage']}`")

    # OPTIONAL: drawdown_analysis_baselines 는 baseline realignment 환경에서 누락 가능.
    # Rule 6: `or {}` 금지. 모듈 None 체크.
    dd_baselines_raw = p.get("drawdown_analysis_baselines")
    dd_baselines: dict = dd_baselines_raw if dd_baselines_raw is not None else {}
    # OPTIONAL: drawdown_analysis_baselines 는 param_loader 유효성 검증 범위 밖.
    # baseline realignment 전, 또는 Step9A 없이 실실하면 눈락 가능.
    # WHITELIST (display): operational 키 누락 시 'N/A' 표시 = "해당 기능 미설정" 의 명시 표현.
    op_baseline = dd_baselines.get("operational", "N/A")  # WHITELIST (display)
    st.caption(f"Operational Baseline: {op_baseline}")

    # OPTIONAL: Step9C 실험군 설정. 미설정 시 None 가능 (legitimate).
    experiments = p.get("tracka_contextual_guard_experiments")
    if experiments:
        import pandas as _pd

        exp_rows = [
            {
                "variant": e["name"],
                "baseline_label": e["baseline_label"],
                "guard_mode": e["guard_mode"],
            }
            for e in experiments
        ]
        st.caption(f"등록된 실험군: {len(experiments)}개")
        st.dataframe(_pd.DataFrame(exp_rows), use_container_width=True)
    else:
        st.caption("실험군 미등록")


def render_contextual_guard_compare_expander(base_dir: Path) -> None:
    """Backtest 탭의 Track A Contextual Guard 비교표 expander."""
    _cmp_path = base_dir / "reports" / "tuning" / "contextual_guard_compare.csv"
    if not _cmp_path.exists():
        return

    import pandas as _pd

    with st.expander("Contextual Guard Compare (P209-STEP9C)", expanded=True):
        _df = _pd.read_csv(_cmp_path)
        st.dataframe(_df, use_container_width=True)
        st.caption(
            "정렬: MDD 오름차순 → CAGR 내림차순."
            " verdict 기준: CAGR > 15 AND MDD < 10."
            " 상세 분석은 `contextual_guard_compare.md` 참조."
        )


def render_contextual_guard_evidence_caption(
    bt_meta: Dict[str, Any], base_dir: Path = None
) -> None:
    """Evidence/Backtest 탭의 guard 요약 caption."""
    if "tracka_guard_mode" not in bt_meta:
        st.caption("Track A Contextual Guard: (구버전 산출물 — Step9C 메타 없음)")
        return

    baseline = bt_meta["tracka_baseline_label"]
    guard_mode = bt_meta["tracka_guard_mode"]
    pre_entry = bt_meta["tracka_pre_entry_guard_hits_total"]
    early_stop = bt_meta["tracka_early_stop_hits_total"]
    promoted = bt_meta["tracka_promoted_total"]
    exhausted = bt_meta["tracka_guard_exhausted_count"]

    verdict = (
        "N/A"  # WHITELIST (display): compare 파일 미존재 또는 값 누락 시 'N/A' 표시
    )
    if base_dir is not None:
        try:
            import json

            cmp_path = base_dir / "reports" / "tuning" / "contextual_guard_compare.json"
            if cmp_path.exists():
                with open(cmp_path, encoding="utf-8") as f:
                    cmp_data = json.load(f)
                # OPTIONAL: rows 키는 sweep 미실행 시 없을 수 있음
                rows_raw = cmp_data.get("rows")
                for r in rows_raw if rows_raw is not None else []:
                    # WHITELIST (display): JSON 로우 필드 누락 가능 → 'N/A'
                    if (
                        r.get("baseline_label") == baseline
                        and r.get("guard_mode") == guard_mode
                    ):
                        verdict = r.get("verdict", "N/A")  # WHITELIST (display)
                        break
        except Exception as e:
            # Rule 6: silent catch 금지. UI에 명시 오류 표시.
            st.caption(f"[WARN] Verdict 조회 실패: {e}")

    baseline_str = baseline if baseline is not None else "-"

    st.caption(
        f"Track A Contextual Guard:"
        f" baseline=`{baseline_str}`"
        f" | guard=`{guard_mode}`"
        f" | pre-entry hits={pre_entry}"
        f" | early-stop hits={early_stop}"
        f" | exhausted={exhausted}"
        f" | promoted={promoted}"
        f" | verdict={verdict}"
    )
