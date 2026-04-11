#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pc_cockpit/views/helpers/allocation_panel.py — P207 allocation view helpers

P207-STEP7C allocation 관련 Streamlit 렌더러. workflow.py / parameter_editor.py
에 inline 으로 있던 블록을 순수 view 함수로 추출.

R6 원칙:
- 각 함수는 Streamlit 호출만 수행 (비즈니스 로직 없음)
- 입력 데이터 (bt_meta, base_dir, p) 는 이미 build 된 dict 를 받음
- display fallback (`.get(k, '?')` 등) 은 workflow.py 원본 동작을 그대로 보존
  하여 byte-level 동일한 렌더링을 유지한다 (결정 3: R6 = byte-level)

## R6 whitelist

이 모듈은 **Streamlit display rendering 전담** 이다. 모든
`.get(k, default)` 호출은 사용자에게 보이는 UI 표시용이며, R5 에서 정의된
display fallback whitelist 범위 내에 있다.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import streamlit as st


def render_allocation_caption(bt_meta: Dict[str, Any]) -> None:
    """Backtest 탭의 allocation 상세 caption (P207).

    workflow.py 의 "P207: allocation 상세 표시" 블록 이전.
    """
    # R6 whitelist: display fallback — workflow.py 원본 동작 보존
    _alloc = bt_meta.get("allocation_mode", "?")
    _bypass = bt_meta.get("bucket_bypass_applied", False)
    _bypass_tag = " (bucket bypass)" if _bypass else ""
    _wf = bt_meta.get("allocation_weight_floor")
    _wc = bt_meta.get("allocation_weight_cap")
    _fc_tag = f" | floor/cap: {_wf}/{_wc}" if _wf is not None else ""
    _fb = bt_meta.get("allocation_fallback_used", False)
    _fb_tag = " | fallback!" if _fb else ""
    st.caption(f"배분: {_alloc}{_bypass_tag}" f"{_fc_tag}{_fb_tag}")


def render_allocation_compare_expander(base_dir: Path) -> None:
    """Backtest 탭의 allocation 실험군 비교표 expander (P207-7C).

    `reports/tuning/allocation_constraint_compare.csv` 가 존재하면 로드해
    DataFrame 으로 표시.
    """
    _cmp_path = base_dir / "reports" / "tuning" / "allocation_constraint_compare.csv"
    if not _cmp_path.exists():
        return

    import pandas as _pd_cmp

    with st.expander("Allocation 실험군 비교"):
        _cdf = _pd_cmp.read_csv(_cmp_path)
        st.dataframe(_cdf, use_container_width=True)


def render_allocation_trace_expander(bt_meta: Dict[str, Any]) -> None:
    """Backtest 탭의 마지막 리밸런스 allocation trace expander (P207-7C)."""
    # R6 whitelist: display fallback — trace 가 없으면 빈 list
    _atrace = bt_meta.get("allocation_trace_by_rebalance_date", [])
    if not _atrace:
        return

    _last = _atrace[-1]
    with st.expander("Allocation Trace (마지막 리밸런스)"):
        st.json(_last)


def render_allocation_panel_for_parameters(p: Dict[str, Any]) -> str:
    """Parameters 탭의 Allocation 섹션 (P207).

    parameter_editor.py 의 "P207: Allocation" 섹션을 이전.

    Args:
        p: SSOT params dict (strategy_params_latest.json 의 "params" 하위)

    Returns:
        현재 선택된 allocation mode (Holding Structure 섹션 매칭에 사용)
    """
    st.subheader("Allocation (P207)")
    # R6 whitelist: display fallback — p.get("allocation", {}) 는 parameter_editor
    # 원본 동작 보존 (non-dynamic 모드에서 {} 일 수 있음)
    _cur_alloc = p.get("allocation", {})
    c1, c2 = st.columns(2)
    _alloc_modes = [
        "dynamic_equal_weight",
        "risk_aware_equal_weight_v1",
        "inverse_volatility_v1",
    ]
    _cur_mode = _cur_alloc.get("mode", "dynamic_equal_weight")
    _mi = _alloc_modes.index(_cur_mode) if _cur_mode in _alloc_modes else 0
    c1.selectbox(
        "Allocation Mode",
        _alloc_modes,
        index=_mi,
        disabled=True,
        key="_alloc_mode_display",
    )
    _wfl = _cur_alloc.get("weight_floor", "-")
    _wcp = _cur_alloc.get("weight_cap", "-")
    _exp_name = f"{_cur_mode}_{_wfl}_{_wcp}" if _cur_alloc else "N/A"
    c2.caption(f"floor/cap: {_wfl}/{_wcp}")
    st.caption(f"Experiment Name: {_exp_name}")
    return _cur_mode
