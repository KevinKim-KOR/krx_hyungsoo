#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pc_cockpit/views/helpers/toxic_filter_panel.py — P209-STEP9B UI helper

Track A Toxic Filter 관련 Streamlit 렌더러 3개.
workflow.py / parameter_editor.py 에서 호출.

R6 원칙: 순수 view 함수. 데이터 변환 없음.

P209-STEP9B FIX (2026-04-11):
- Parameters 탭에서 baseline / drop_mode 까지 표시 (지시문 요구)
- display fallback 은 "데이터 없음" 시각 표현으로만 사용. silent bug 은닉 금지.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import streamlit as st


def render_toxic_filter_panel_for_parameters(p: Dict[str, Any]) -> None:
    """Parameters 탭의 Track A Toxic Filter 섹션 (P209-STEP9B).

    표시 내용:
    - Primary Drop / Extended Drop list
    - 현재 운영 baseline label + 현재 drop_mode (SSOT 의 operational baseline +
      해당 실험군 중 drop_mode='none' A0)
    - 등록된 6개 실험군 목록과 각 variant 의 baseline/drop_mode

    Args:
        p: SSOT params dict
    """
    st.subheader("Track A Toxic Filter (P209-STEP9B)")

    config = p.get("tracka_toxic_filter")
    if config is None:
        st.info("tracka_toxic_filter 설정 없음 (비활성)")
        return

    # 필수 필드 — param_loader 가 이미 검증했으므로 직접 subscript
    primary = config["primary_drop_list"]
    extended = config["extended_drop_list"]
    apply_stage = config["apply_stage"]

    c1, c2, c3 = st.columns(3)
    c1.metric("Primary Drop", ", ".join(primary))
    c2.metric("Extended Drop", ", ".join(extended))
    # 운영 baseline 은 drawdown_analysis_baselines 에서 읽음
    dd_baselines = p.get("drawdown_analysis_baselines") or {}
    op_baseline = dd_baselines.get("operational", "N/A")
    c3.metric("Operational Baseline", op_baseline)

    st.caption(f"Apply Stage: `{apply_stage}`")

    # 실험군 목록 표시 (name / baseline_label / drop_mode / drop_list_size)
    experiments = p.get("tracka_toxic_filter_experiments")
    if experiments:
        import pandas as _pd

        exp_rows = [
            {
                "variant": e["name"],
                "baseline_label": e["baseline_label"],
                "drop_mode": e["drop_mode"],
                "drop_list_size": len(e["drop_list"]),
                "drop_list": ",".join(e["drop_list"]) if e["drop_list"] else "-",
            }
            for e in experiments
        ]
        st.caption(
            f"등록된 실험군: {len(experiments)}개"
            f" (A0~A2 = pos2 baseline, B0~B2 = pos3 baseline)"
        )
        st.dataframe(_pd.DataFrame(exp_rows), use_container_width=True)
    else:
        st.caption("실험군 미등록")


def render_toxic_filter_compare_expander(base_dir: Path) -> None:
    """Backtest 탭의 Track A Toxic Filter 비교표 expander (P209-STEP9B).

    `reports/tuning/toxic_filter_compare.csv` 가 존재하면 DataFrame 표시.
    """
    _cmp_path = base_dir / "reports" / "tuning" / "toxic_filter_compare.csv"
    if not _cmp_path.exists():
        return

    import pandas as _pd

    with st.expander(
        "Toxic Filter Compare (P209-STEP9B)",
        expanded=True,
    ):
        _df = _pd.read_csv(_cmp_path)
        st.dataframe(_df, use_container_width=True)
        st.caption(
            "정렬: MDD 오름차순 → CAGR 내림차순."
            " verdict 기준: CAGR > 15 AND MDD < 10."
            " 상세 진단(Q1~Q4) 은 `toxic_filter_compare.md` 참조."
        )


def render_toxic_filter_evidence_caption(bt_meta: Dict[str, Any]) -> None:
    """Evidence/Backtest 탭의 toxic filter 요약 caption (P209-STEP9B).

    지시문 요구 필드 전체 표시: baseline / drop_mode / drop_list /
    filter hits / exhausted / promoted / verdict (main run 기준).

    R5 whitelist: bt_meta 는 format_result 가 Track A 필드를 항상 주입 한다.
    필터 미실행 (drop_list=[]) 시 hits/exhausted/promoted=0, drop_list=[]
    이라는 정확한 의미이므로 None 분기 불필요.
    """
    # 필수 필드 — format_result 가 항상 주입
    hits = bt_meta.get("tracka_filter_hits_total", 0)
    exhausted = bt_meta.get("tracka_filter_exhausted_count", 0)
    promoted = bt_meta.get("tracka_promoted_total", 0)
    baseline = bt_meta.get("tracka_baseline_label") or "-"
    drop_mode = bt_meta.get("tracka_drop_mode") or "none"
    drop_list = bt_meta.get("tracka_drop_list_used") or []
    drop_list_str = ",".join(drop_list) if drop_list else "-"

    st.caption(
        f"Track A Toxic Filter:"
        f" baseline=`{baseline}`"
        f" | drop_mode=`{drop_mode}`"
        f" | drop_list={drop_list_str}"
        f" | hits={hits}"
        f" | exhausted={exhausted}"
        f" | promoted={promoted}"
    )
