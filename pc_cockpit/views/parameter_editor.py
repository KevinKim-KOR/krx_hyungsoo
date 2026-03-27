"""SSOT 파라미터 편집 폼 (render_workflow_p170 내부에서 호출)."""

import time
from datetime import datetime

import streamlit as st

from pc_cockpit.services.config import KST, _ssot_require, compute_fingerprint
from pc_cockpit.services.json_io import save_params


def render_ssot_parameter_form(params_data):
    """1) 현재 파라미터 (SSOT) 섹션."""
    st.subheader("1) 현재 파라미터 (SSOT)")
    if params_data:
        if "params" not in params_data:
            st.error("SSOT 파일에 'params' 키가 없습니다. 파일 구조를 확인하세요.")
            return
        p = params_data["params"]
        with st.expander("⚙️ 파라미터 수정 (Click to expand)", expanded=False):
            with st.form("wf_params_form"):
                # Universe
                st.subheader("Universe")
                universe_str = st.text_input(
                    "Tickers (comma separated)",
                    ", ".join(_ssot_require(p, "universe")),
                )

                # Lookbacks
                st.subheader("Lookbacks")
                c1, c2 = st.columns(2)
                mom_period = c1.number_input(
                    "모멘텀 기간 (Momentum Period)",
                    value=_ssot_require(p, "lookbacks", "momentum_period"),
                )
                c1.caption("`SSOT Key: momentum_period`")
                vol_period = c2.number_input(
                    "변동성 기간 (Volatility Period)",
                    value=_ssot_require(p, "lookbacks", "volatility_period"),
                )
                c2.caption("`SSOT Key: volatility_period`")

                # Risk Limits
                st.subheader("Risk Limits")
                c1, c2 = st.columns(2)
                max_pos_pct = c1.number_input(
                    "최대 포지션 비중 (Max Position %)",
                    value=float(_ssot_require(p, "risk_limits", "max_position_pct")),
                    step=0.01,
                )
                c1.caption("`SSOT Key: max_position_pct`")
                c2.markdown(
                    f"**현재 설정**: 전체 자본의 **{max_pos_pct*100:.1f}%**를 단일 종목에 최대 투자."
                )

                # Position Limits
                st.subheader("Position Limits")
                c1, c2 = st.columns(2)
                max_pos = c1.number_input(
                    "최대 편입 종목 수 (Max Positions)",
                    value=int(_ssot_require(p, "position_limits", "max_positions")),
                    min_value=1,
                )
                c1.caption("`SSOT Key: max_positions`")
                min_cash_pct = c2.number_input(
                    "최소 현금 비중 (Min Cash %)",
                    value=float(_ssot_require(p, "position_limits", "min_cash_pct")),
                    step=0.01,
                )
                c2.caption("`SSOT Key: min_cash_pct`")

                # Decision Params
                st.subheader("Decision Params")
                c1, c2 = st.columns(2)
                entry = c1.number_input(
                    "진입 임계치 (Entry Threshold)",
                    value=float(_ssot_require(p, "decision_params", "entry_threshold")),
                    step=0.01,
                )
                c1.caption("`SSOT Key: entry_threshold`")
                exit_th = c2.number_input(
                    "청산 임계치 (Exit Threshold)",
                    value=float(_ssot_require(p, "decision_params", "exit_threshold")),
                    step=0.01,
                )
                c2.caption("`SSOT Key: exit_threshold`")

                # Rebalance Rule
                st.subheader("Rebalance Rule")
                c1, c2 = st.columns(2)
                freq_opts = [
                    "DAILY",
                    "WEEKLY",
                    "MONTHLY",
                    "QUARTERLY",
                    "YEARLY",
                ]
                cur_freq = p.get("rebalance_rule", {}).get("frequency", "MONTHLY")
                freq_idx = freq_opts.index(cur_freq) if cur_freq in freq_opts else 2
                freq = c1.selectbox("리밸런싱 주기", freq_opts, index=freq_idx)
                c1.caption("`SSOT Key: rebalance_rule.frequency`")

                st.divider()
                if st.form_submit_button("💾 Save Parameters to SSOT"):
                    try:
                        new_params = params_data.copy()
                        target_p = new_params.setdefault("params", {})

                        target_p["universe"] = [
                            t.strip() for t in universe_str.split(",") if t.strip()
                        ]
                        target_p.setdefault("lookbacks", {})["momentum_period"] = int(
                            mom_period
                        )
                        target_p.setdefault("lookbacks", {})["volatility_period"] = int(
                            vol_period
                        )
                        target_p.setdefault("risk_limits", {})["max_position_pct"] = (
                            float(max_pos_pct)
                        )
                        target_p.setdefault("position_limits", {})["max_positions"] = (
                            int(max_pos)
                        )
                        target_p.setdefault("position_limits", {})["min_cash_pct"] = (
                            float(min_cash_pct)
                        )
                        target_p.setdefault("decision_params", {})[
                            "entry_threshold"
                        ] = float(entry)
                        target_p.setdefault("decision_params", {})["exit_threshold"] = (
                            float(exit_th)
                        )
                        target_p.setdefault("rebalance_rule", {})["frequency"] = freq

                        new_params["asof"] = datetime.now(KST).isoformat()
                        save_params(new_params)
                        st.success(
                            f"✅ 파라미터가 저장되었습니다 (Fingerprint: {compute_fingerprint(new_params)})"
                        )
                        time.sleep(1.5)
                        st.rerun()
                    except Exception as e:
                        st.error(f"저장 실패: {e}")
    else:
        st.warning("Current Parameters를 불러올 수 없습니다.")
