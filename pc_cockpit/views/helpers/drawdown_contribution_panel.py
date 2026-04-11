#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pc_cockpit/views/helpers/drawdown_contribution_panel.py — P209 drawdown view helper

P209-STEP9A drawdown contribution 관련 Streamlit 렌더러. workflow.py 에 inline
으로 있던 약 215줄의 expander 블록을 순수 view 함수로 추출.

R6 원칙 + R6 whitelist: `allocation_panel.py` 와 동일.
display rendering 전담 모듈이며, bt_meta 의 `drawdown_analysis_comparison`
sub-dict 의 필드들을 화면에 표시하는 역할만 한다.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import streamlit as st


def render_drawdown_contribution_panel(bt_meta: Dict[str, Any], base_dir: Path) -> None:
    """Backtest 탭의 P209 drawdown contribution summary expander.

    구성:
    - MDD window (A) 표시
    - A vs B 비교 요약 DataFrame
    - Top Toxic side-by-side (A, B)
    - 공통 Toxic 하이라이트
    - Worst Selection Events side-by-side (gap 포함)
    - Bucket Risk side-by-side
    - 전체 리포트 파일 경로 caption

    bt_meta 에 drawdown 관련 필드가 없으면 아무것도 렌더링하지 않음 (early return).
    """
    # R6 whitelist: display fallback — drawdown 분석 미실행 시 필드 없음
    _dd_peak = bt_meta.get("drawdown_peak_date")
    _dd_trough = bt_meta.get("drawdown_trough_date")
    _dd_top = bt_meta.get("top_ticker_contributors_to_mdd") or []
    _dd_qs = bt_meta.get("selection_quality_summary") or {}
    _dd_verdict = bt_meta.get("selection_quality_verdict")
    _dd_worst = bt_meta.get("worst_selection_events") or []
    _dd_bucket = bt_meta.get("bucket_risk_summary") or {}
    _dd_cmp = bt_meta.get("drawdown_analysis_comparison") or {}

    if not (_dd_peak or _dd_top or _dd_qs):
        return

    with st.expander(
        "Drawdown Contribution Summary" " (P209-STEP9A, analysis-only)",
        expanded=False,
    ):
        import pandas as _pd_dd

        st.markdown(
            f"**MDD Window (A)**: peak=`{_dd_peak}`"
            f" → trough=`{_dd_trough}`"
            f" ({bt_meta.get('mdd_window_length', '-')}"
            " days)"
        )

        _op_label = _dd_cmp.get("operational_baseline_label", "-")
        _op_mdd = _dd_cmp.get("operational_mdd_pct")
        _op_gap = _dd_cmp.get("operational_avg_selection_gap_pct")
        _b_label = _dd_cmp.get("research_baseline_label", "-")
        _b_verdict = _dd_cmp.get("research_baseline_verdict", "N/A")
        _b_mdd = _dd_cmp.get("research_mdd_pct")
        _b_gap = _dd_cmp.get("research_avg_selection_gap_pct")
        # A군: main meta의 selection_quality_summary 사용
        # B군: drawdown_analysis_comparison에 주입된 B 필드 사용
        _a_pr = _dd_cmp.get(
            "operational_positive_forward_ratio",
            _dd_qs.get("positive_forward_ratio"),
        )
        _a_avg = _dd_cmp.get(
            "operational_avg_forward_return_pct",
            _dd_qs.get("avg_forward_return_pct"),
        )
        _a_miss = _dd_cmp.get("operational_events_with_better_unselected")
        _b_pr = _dd_cmp.get("research_positive_forward_ratio")
        _b_avg = _dd_cmp.get("research_avg_forward_return_pct")
        _b_miss = _dd_cmp.get("research_events_with_better_unselected")

        # A vs B 요약 테이블
        st.markdown("**A vs B 비교 요약**")
        _cmp_rows = [
            {
                "group": "A (operational)",
                "label": _op_label,
                "mdd_pct": _op_mdd,
                "verdict": _dd_verdict,
                "positive_ratio": _a_pr,
                "avg_fwd_pct": _a_avg,
                "avg_selection_gap_pct": _op_gap,
                "events_miss_better_unsel": _a_miss,
            },
            {
                "group": "B (research)",
                "label": _b_label,
                "mdd_pct": _b_mdd,
                "verdict": _b_verdict,
                "positive_ratio": _b_pr,
                "avg_fwd_pct": _b_avg,
                "avg_selection_gap_pct": _b_gap,
                "events_miss_better_unsel": _b_miss,
            },
        ]
        st.dataframe(
            _pd_dd.DataFrame(_cmp_rows),
            use_container_width=True,
        )

        # Top Toxic side-by-side
        _b_top = _dd_cmp.get("research_top_toxic_tickers") or []
        _col_a, _col_b = st.columns(2)
        with _col_a:
            st.markdown(f"**A=`{_op_label}` Top Toxic**")
            if _dd_top:
                st.dataframe(
                    _pd_dd.DataFrame(_dd_top),
                    use_container_width=True,
                )
            else:
                st.caption("데이터 없음")
        with _col_b:
            st.markdown(f"**B=`{_b_label}` Top Toxic**")
            if _b_top:
                st.dataframe(
                    _pd_dd.DataFrame(_b_top),
                    use_container_width=True,
                )
            else:
                st.caption("데이터 없음")

        # 공통 toxic 하이라이트
        _a_set = {r.get("ticker") for r in _dd_top[:5]}
        _b_set = {r.get("ticker") for r in _b_top[:5]}
        _common = sorted(t for t in (_a_set & _b_set) if t)
        if _common:
            st.info(
                "🔥 A ∩ B 공통 Toxic Tickers: "
                f"{', '.join(_common)}"
                " — Step9B Track A 필터 1순위 후보"
            )
        else:
            st.caption("A/B 공통 Toxic 없음 — 보유구조별" " 선택 경로가 독립적임")

        # Worst Selection Events side-by-side (gap 포함)
        _b_worst = _dd_cmp.get("research_worst_selection_events") or []
        _col_aw, _col_bw = st.columns(2)
        with _col_aw:
            st.markdown(f"**A=`{_op_label}` Worst Events**")
            if _dd_worst:
                st.dataframe(
                    _pd_dd.DataFrame(_worst_rows(_dd_worst)),
                    use_container_width=True,
                )
            else:
                st.caption("데이터 없음")
        with _col_bw:
            st.markdown(f"**B=`{_b_label}` Worst Events**")
            if _b_worst:
                st.dataframe(
                    _pd_dd.DataFrame(_worst_rows(_b_worst)),
                    use_container_width=True,
                )
            else:
                st.caption("데이터 없음")

        # Bucket risk side-by-side
        _b_bucket = _dd_cmp.get("research_bucket_risk_summary") or {}
        if _dd_bucket or _b_bucket:
            _col_ab, _col_bb = st.columns(2)
            with _col_ab:
                st.markdown(f"**A=`{_op_label}` Bucket Risk**")
                if _dd_bucket:
                    st.dataframe(
                        _pd_dd.DataFrame(
                            [{"bucket": k, **v} for k, v in _dd_bucket.items()]
                        ),
                        use_container_width=True,
                    )
                else:
                    st.caption("데이터 없음")
            with _col_bb:
                st.markdown(f"**B=`{_b_label}` Bucket Risk**")
                if _b_bucket:
                    st.dataframe(
                        _pd_dd.DataFrame(
                            [{"bucket": k, **v} for k, v in _b_bucket.items()]
                        ),
                        use_container_width=True,
                    )
                else:
                    st.caption("데이터 없음")

        _dd_md_path = (
            base_dir / "reports" / "tuning" / "drawdown_contribution_report.md"
        )
        if _dd_md_path.exists():
            st.caption(
                f"전체 리포트: `{_dd_md_path.name}`" " — Step9B 필터 설계 근거용"
            )


def _worst_rows(evts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Worst selection events 리스트를 DataFrame 행으로 변환 (R6 display helper)."""
    return [
        {
            "rebalance_date": e.get("rebalance_date"),
            "selected": ",".join(e.get("selected_tickers", []) or []),
            "worst_ticker": e.get("worst_ticker"),
            "worst_ret%": e.get("worst_return_pct"),
            "avg_sel%": e.get("avg_forward_return_pct"),
            "avg_unsel%": e.get("avg_unselected_forward_return_pct"),
            "gap%p": e.get("selection_gap_pct"),
            "best_unsel": e.get("best_unselected_ticker"),
        }
        for e in evts
    ]
