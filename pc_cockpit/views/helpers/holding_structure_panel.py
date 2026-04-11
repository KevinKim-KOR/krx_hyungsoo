#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pc_cockpit/views/helpers/holding_structure_panel.py — P208 holding structure view

P208-STEP8A holding structure 관련 Streamlit 렌더러. workflow.py /
parameter_editor.py 에 inline 으로 있던 블록을 순수 view 함수로 추출.

R6 원칙 + R6 whitelist: `allocation_panel.py` 와 동일.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import streamlit as st

from pc_cockpit.services.config import _ssot_require


def render_holding_structure_compare_expander(base_dir: Path) -> None:
    """Backtest 탭의 G1~G8 holding structure 비교표 expander (P208-STEP8A).

    `reports/tuning/holding_structure_compare.csv` 가 존재하면 로드해 DataFrame
    으로 표시.
    """
    _hs_cmp_path = base_dir / "reports" / "tuning" / "holding_structure_compare.csv"
    if not _hs_cmp_path.exists():
        return

    import pandas as _pd_hs

    with st.expander(
        "Holding Structure 비교 (G1~G8, P208)",
        expanded=True,
    ):
        _hdf = _pd_hs.read_csv(_hs_cmp_path)
        st.dataframe(_hdf, use_container_width=True)


def render_holding_structure_caption(bt_meta: Dict[str, Any]) -> None:
    """Backtest 탭의 holding structure 요약 caption (P208-STEP8A).

    현재 실행의 experiment name / max_positions / avg_held 등을 한 줄로 표시.
    """
    # R6 whitelist: display fallback — workflow.py 원본 동작 보존
    _hs_name = bt_meta.get("holding_structure_experiment_name")
    _hs_maxp = bt_meta.get("holding_structure_max_positions")
    _hs_avg = bt_meta.get("avg_held_positions")
    _hs_max_obs = bt_meta.get("max_held_positions_observed")
    _hs_blocked = (bt_meta.get("blocked_reason_totals") or {}).get(
        "BLOCKED_MAX_POSITIONS", 0
    )
    st.caption(
        f"Holding Structure:"
        f" experiment={_hs_name or 'N/A'}"
        f" | max_positions={_hs_maxp}"
        f" | avg_held={_hs_avg}"
        f" | max_held_obs={_hs_max_obs}"
        f" | blocked_max_pos={_hs_blocked}"
    )


def render_holding_structure_panel_for_parameters(
    p: Dict[str, Any], current_allocation_mode: str
) -> None:
    """Parameters 탭의 Holding Structure 섹션 (P208-STEP8A).

    parameter_editor.py 의 "P208-STEP8A: Holding Structure" 섹션을 이전.

    Args:
        p: SSOT params dict
        current_allocation_mode: allocation_panel 에서 반환한 현재 mode
            (holding_structure_experiments 매칭에 사용)
    """
    st.subheader("Holding Structure (P208)")
    _cur_max_pos = int(_ssot_require(p, "position_limits", "max_positions"))
    # R6 whitelist: display fallback — holding_structure_experiments 는 SSOT
    # 필수 키가 아니므로 없을 수 있음 (`or []` 는 None → [] 명시 변환)
    _hs_exps = p.get("holding_structure_experiments") or []
    _current_hs_name = None
    for _hse in _hs_exps:
        if (
            _hse.get("max_positions") == _cur_max_pos
            and _hse.get("allocation_mode") == current_allocation_mode
        ):
            _current_hs_name = _hse.get("name")
            break
    _hs_display = _current_hs_name or "N/A (현재 SSOT 조합에 매칭 실험군 없음)"
    c1h, c2h, c3h = st.columns(3)
    c1h.metric("Current Experiment", _hs_display)
    c2h.metric("max_positions", _cur_max_pos)
    c3h.metric("allocation_mode", current_allocation_mode)
    st.caption(
        f"등록된 실험군: {len(_hs_exps)}개"
        f" (G1~G8 = pos[2,3,4,5] ×"
        f" [dynamic_equal_weight, risk_aware_equal_weight_v1])"
    )
