"""레거시 패널 보존소.

cockpit.py에서 호출되지 않는 6개 render_* 함수를 격리 보존.
활성 경로에서는 import하지 않으며, 복원 필요 시 참조용으로만 사용.

Phase S1-B (2026-03-27) 이동.
"""

import json
import time
from datetime import datetime, timezone, timedelta

import pandas as pd
import requests
import streamlit as st

from pc_cockpit.services.config import (
    KST,
    BASE_DIR,
    LATEST_PATH,
    GUARDRAILS_PATH,
    SLOW_TIMEOUT,
    _ssot_require,
    get_ticker_name,
    compute_fingerprint,
)
from pc_cockpit.services.json_io import (
    load_json,
    save_json,
    save_params,
    apply_reco,
    run_script,
)


def render_params(params_data, portfolio_data, guardrails_data):
    st.warning(
        "⚠️ 레거시 화면: 이 화면은 워크플로우 탭(P170-UI)으로 주요 조작 기능이 통합되었습니다. 파라미터 구조 직접 관리가 필요한 경우에만 제한적으로 사용하세요."
    )
    if not params_data:
        st.error(
            "No strategy params found! Please initialize 'state/params/latest/strategy_params_latest.json'."
        )
    else:
        # Header Info
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**Strategy**: {params_data.get('strategy')}")
            st.write(f"**Version**: {params_data.get('version')}")
        with col2:
            current_fp = compute_fingerprint(params_data)
            st.metric("Current Fingerprint", current_fp)

        st.markdown("---")

        # Form
        with st.form("params_form"):
            if "params" not in params_data:
                st.error("SSOT 파일에 'params' 키가 없습니다.")
                st.stop()
            p = params_data["params"]

            # Universe
            st.subheader("Universe")
            universe_str = st.text_area(
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
            )
            c1.caption("`SSOT Key: max_position_pct`")
            max_dd_pct = c2.number_input(
                "최대 낙폭 (Max Drawdown %)",
                value=float(_ssot_require(p, "risk_limits", "max_drawdown_pct")),
            )
            c2.caption("`SSOT Key: max_drawdown_pct`")

            # Position Limits
            st.subheader("Position Limits")
            c1, c2 = st.columns(2)
            max_pos = c1.number_input(
                "최대 보유종목 수 (Max Positions)",
                value=int(_ssot_require(p, "position_limits", "max_positions")),
            )
            c1.caption("`SSOT Key: max_positions`")
            min_cash = c2.number_input(
                "최소 현금비율 (Min Cash %)",
                value=float(_ssot_require(p, "position_limits", "min_cash_pct")),
            )
            c2.caption("`SSOT Key: min_cash_pct`")

            # Decision Params
            st.subheader("Decision Thresholds")
            c1, c2, c3 = st.columns(3)
            entry_th = c1.number_input(
                "진입 임계값 (Entry Threshold)",
                value=float(_ssot_require(p, "decision_params", "entry_threshold")),
            )
            c1.caption("`SSOT Key: entry_threshold`")
            exit_th = c2.number_input(
                "손절/청산 임계값 (Stop Loss)",
                value=float(_ssot_require(p, "decision_params", "exit_threshold")),
            )
            c2.caption("`SSOT Key: exit_threshold (= stop_loss)`")
            adx_min = c3.number_input(
                "ADX 최소값 (ADX Min)",
                value=int(_ssot_require(p, "decision_params", "adx_filter_min")),
            )
            c3.caption("`SSOT Key: adx_filter_min`")

            # Weights (New in Recommendations/Review)
            st.subheader("Weights")
            c1, c2 = st.columns(2)
            w_mom = c1.number_input(
                "Weight Mom",
                value=float(_ssot_require(p, "decision_params", "weight_momentum")),
            )
            w_vol = c2.number_input(
                "Weight Vol",
                value=float(_ssot_require(p, "decision_params", "weight_volatility")),
            )

            c_btn1, c_btn2 = st.columns(2)
            with c_btn1:
                submit_local = st.form_submit_button("💾 Save Parameters (Local)")
            with c_btn2:
                submit_push = st.form_submit_button(
                    "🚀 Save & Push Bundle to OCI (1-Click Sync)"
                )

            submitted = submit_local or submit_push

            if submitted:
                # Update Data
                new_data = params_data.copy()
                KST = timezone(timedelta(hours=9))
                new_data["asof"] = datetime.now(KST).isoformat()
                new_params = p.copy()

                new_params["universe"] = [
                    t.strip() for t in universe_str.split(",") if t.strip()
                ]
                new_params["lookbacks"]["momentum_period"] = int(mom_period)
                new_params["lookbacks"]["volatility_period"] = int(vol_period)
                new_params["risk_limits"]["max_position_pct"] = float(max_pos_pct)
                new_params["risk_limits"]["max_drawdown_pct"] = float(max_dd_pct)
                new_params["position_limits"]["max_positions"] = int(max_pos)
                new_params["position_limits"]["min_cash_pct"] = float(min_cash)
                new_params["decision_params"]["entry_threshold"] = float(entry_th)
                new_params["decision_params"]["exit_threshold"] = float(exit_th)
                new_params["decision_params"]["adx_filter_min"] = int(adx_min)
                new_params["decision_params"]["weight_momentum"] = float(w_mom)
                new_params["decision_params"]["weight_volatility"] = float(w_vol)

                new_data["params"] = new_params

                # Save
                snap_path = save_params(new_data)
                new_fp = compute_fingerprint(new_data)

                # Fingerprint 즉시 갱신
                st.session_state["current_fingerprint"] = new_fp

                st.success(f"Saved (Local)! New Fingerprint: `{new_fp}`")

                if submit_push:
                    st.info("📦 Generating Bundle and Pushing to OCI...")

                    is_dry_run = st.session_state.get("is_dry_run", False)
                    is_replay = st.session_state.get("is_replay", False)
                    require_token = not (is_dry_run or is_replay)

                    push_allowed = False
                    token = st.session_state.get("ops_token", "")

                    if require_token:
                        if not token:
                            st.warning(
                                "⚠️ 로컬 저장은 됐지만 OCI Push 실패 → Drift 지속: LIVE Mode requires Confirm Token. Please enter it in the top tab first."
                            )
                        else:
                            push_allowed = True
                    else:
                        push_allowed = True

                    if push_allowed:
                        try:
                            resp = requests.post(
                                "http://localhost:8000/api/sync/push_bundle",
                                json={"token": token},
                                timeout=SLOW_TIMEOUT,
                            )
                            if resp.status_code == 200:
                                res_data = resp.json()
                                st.success(
                                    f"✅ 저장 + OCI 장착 완료( created_at={res_data.get('created_at')} )"
                                )
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.warning(
                                    f"⚠️ 로컬 저장은 됐지만 OCI Push 실패 → Drift 지속: {resp.text}"
                                )
                        except Exception as e:
                            st.warning(
                                f"⚠️ 로컬 저장은 됐지만 OCI Push 실패 → Drift 지속: {str(e)}"
                            )
                else:
                    time.sleep(1)
                    st.rerun()


def render_reco(params_data, portfolio_data, guardrails_data):
    SEARCH_DIR = BASE_DIR / "reports" / "pc" / "param_search" / "latest"
    SEARCH_LATEST_PATH = SEARCH_DIR / "param_search_latest.json"
    SCRIPT_PARAM_SEARCH = BASE_DIR / "deploy" / "pc" / "run_param_search.ps1"
    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader("Recommendations/Review Param Recommendations")
    with col2:
        if st.button("🔄 Run Analysis (Param Search)"):
            with st.spinner("Running Param Search Simulation..."):
                out, err, code = run_script(SCRIPT_PARAM_SEARCH)
                if code == 0:
                    st.success("Analysis Complete!")
                else:
                    st.error(f"Analysis Failed: {err}")

    reco_data = load_json(SEARCH_LATEST_PATH)
    if not reco_data:
        st.warning("No recommendations found. Run analysis first.")
    else:
        st.caption(f"Data Asof: {reco_data.get('asof', 'N/A')}")
        results = reco_data.get("results", [])

        if not results:
            st.warning("No results in recommendation file.")
        else:
            # Display Winner
            winner = reco_data.get("winner", {})
            st.success(
                f"🏆 Winner: Rank {winner.get('rank')} (Score: {winner.get('params', {}).get('metrics', {}).get('score_0_100', 'N/A')})"
            )

            # Table
            for idx, res in enumerate(results[:5]):  # Top 5
                with st.expander(
                    f"Rank {res['rank']} (Score: {res['score_0_100']})",
                    expanded=(idx == 0),
                ):
                    c1, c2, c3 = st.columns(3)
                    c1.metric(
                        "Return", f"{res['metrics']['avg_forward_return']*100:.1f}%"
                    )
                    c2.metric("Hit Rate", f"{res['metrics']['hit_rate']*100:.0f}%")
                    c3.metric("Sample N", res["metrics"]["sample_count"])

                    st.json(res["params"])

                    if st.button(f"Apply Rank {res['rank']}", key=f"apply_{idx}"):
                        if not params_data:
                            st.error("Base params not loaded.")
                        else:
                            new_p = apply_reco(params_data, res)
                            snap_path = save_params(new_p)
                            new_fp = compute_fingerprint(new_p)
                            st.success(f"Applied & Saved! New Fingerprint: `{new_fp}`")
                            st.rerun()


def render_review(params_data, portfolio_data, guardrails_data):
    REVIEW_DIR = BASE_DIR / "reports" / "pc" / "param_review" / "latest"
    REVIEW_JSON_PATH = REVIEW_DIR / "param_review_latest.json"
    REVIEW_MD_PATH = REVIEW_DIR / "param_review_latest.md"
    SCRIPT_PARAM_REVIEW = BASE_DIR / "deploy" / "pc" / "run_param_review.ps1"
    st.subheader("🧐 Strategy Parameter Review (Recommendations/Review)")

    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown("Compare candidates and make a final decision.")
    with col2:
        if st.button("📝 Generate Review Report"):
            with st.spinner("Analyzing..."):
                out, err, code = run_script(SCRIPT_PARAM_REVIEW)
                if code == 0:
                    st.success("Report Generated!")
                    st.rerun()
                else:
                    st.error(f"Generation Failed: {err}")

    review_data = load_json(REVIEW_JSON_PATH)
    if not review_data:
        st.info("No review report found. Click Generate to start.")
    else:
        # Display Recommendation
        rec = review_data.get("recommendation", {})
        cand_rank = rec.get("candidate_rank")
        st.info(
            f"💡 AI Suggestion: **Rank {cand_rank}** ({rec.get('level')}) - {rec.get('reason')}"
        )

        # Candidates List
        candidates = review_data.get("candidates", [])

        for cand in candidates:
            rank = cand["rank"]
            score = cand["score"]
            tags = cand.get("tags", [])

            with st.expander(f"Rank {rank} (Score: {score}) - {', '.join(tags)}"):
                c1, c2 = st.columns(2)

                with c1:
                    st.write("#### Analysis")
                    st.write(f"**Why Good**: {cand['analysis']['why_good']}")
                    st.write(f"**Risks**: {cand['analysis']['risk_factor']}")

                    st.json(cand["params"])

                with c2:
                    st.write("#### Metrics")
                    m = cand["metrics"]
                    st.metric(
                        "Proj. Return", f"{m.get('avg_forward_return',0)*100:.1f}%"
                    )
                    st.metric("Hit Rate", f"{m.get('hit_rate',0)*100:.0f}%")

                    st.markdown("---")
                    st.write("#### Action")

                    # Apply Logic with Confirmation
                    if st.button(f"Apply Candidate {rank}", key=f"promo_{rank}"):
                        st.session_state[f"confirm_promo_{rank}"] = True

                    if st.session_state.get(f"confirm_promo_{rank}"):
                        st.warning(
                            "Are you sure? This will update the local strategy parameters."
                        )
                        if st.button("Yes, Confirm Apply", key=f"confirm_btn_{rank}"):
                            # Apply!
                            if not params_data:
                                st.error("Baseline params not loaded.")
                            else:
                                new_p = apply_reco(
                                    params_data, cand
                                )  # Re-use apply_reco from Recommendations/Review logic
                                snap_path = save_params(new_p)
                                new_fp = compute_fingerprint(new_p)
                                st.success(f"Applied! New Fingerprint: `{new_fp}`")
                                st.info(
                                    "This change is LOCAL. Run 'Publish Bundle' (P100) when ready to deploy."
                                )
                                st.session_state[f"confirm_promo_{rank}"] = False
                                st.rerun()

        # Questions
        st.markdown("### ❓ Ask AI (Copy & Paste)")
        q_text = "\n".join([f"- {q}" for q in review_data.get("questions", [])])
        st.text_area("Questions", q_text, height=150)


def render_guardrails_legacy(params_data, portfolio_data, guardrails_data):
    st.header("🛡️ Execution Guardrails (P160 SSOT)")
    st.markdown(
        "Manage safety limits for `LIVE`, `DRY_RUN`, and `REPLAY` execution modes. Note: LIVE mode limits are read-only for safety."
    )

    caps = guardrails_data.get(
        "caps",
        {
            "max_total_notional_ratio": 1.0,
            "max_single_order_ratio": 1.0,
            "min_cash_reserve_ratio": 0.0,
        },
    )
    st.caption(
        f"**Hard Caps (Fail-Closed Boundaries):** Max Notional = {caps.get('max_total_notional_ratio')}, Max Single = {caps.get('max_single_order_ratio')}, Min Reserve = {caps.get('min_cash_reserve_ratio')}"
    )

    with st.form("guardrails_form"):
        c_live, c_dry, c_rep = st.columns(3)

        # LIVE (Readonly visually)
        with c_live:
            st.subheader("🔴 LIVE Mode")
            live = guardrails_data.get(
                "live",
                {
                    "max_total_notional_ratio": 0.3,
                    "max_single_order_ratio": 0.1,
                    "min_cash_reserve_ratio": 0.05,
                },
            )
            l_tot = st.number_input(
                "Max Total Notional Ratio",
                value=float(live.get("max_total_notional_ratio", 0.3)),
                key="l_tot",
                help="Read-only",
                disabled=True,
            )
            l_sgl = st.number_input(
                "Max Single Order Ratio",
                value=float(live.get("max_single_order_ratio", 0.1)),
                key="l_sgl",
                disabled=True,
            )
            l_csh = st.number_input(
                "Min Cash Reserve Ratio",
                value=float(live.get("min_cash_reserve_ratio", 0.05)),
                key="l_csh",
                disabled=True,
            )

        with c_dry:
            st.subheader("🧪 DRY_RUN Mode")
            dry = guardrails_data.get(
                "dry_run",
                {
                    "max_total_notional_ratio": 1.0,
                    "max_single_order_ratio": 1.0,
                    "min_cash_reserve_ratio": 0.0,
                },
            )
            d_tot = st.number_input(
                "Max Total Notional Ratio",
                value=float(dry.get("max_total_notional_ratio", 1.0)),
                key="d_tot",
            )
            d_sgl = st.number_input(
                "Max Single Order Ratio",
                value=float(dry.get("max_single_order_ratio", 1.0)),
                key="d_sgl",
            )
            d_csh = st.number_input(
                "Min Cash Reserve Ratio",
                value=float(dry.get("min_cash_reserve_ratio", 0.0)),
                key="d_csh",
            )

        with c_rep:
            st.subheader("⏪ REPLAY Mode")
            rep = guardrails_data.get(
                "replay",
                {
                    "max_total_notional_ratio": 1.0,
                    "max_single_order_ratio": 1.0,
                    "min_cash_reserve_ratio": 0.0,
                },
            )
            r_tot = st.number_input(
                "Max Total Notional Ratio",
                value=float(rep.get("max_total_notional_ratio", 1.0)),
                key="r_tot",
            )
            r_sgl = st.number_input(
                "Max Single Order Ratio",
                value=float(rep.get("max_single_order_ratio", 1.0)),
                key="r_sgl",
            )
            r_csh = st.number_input(
                "Min Cash Reserve Ratio",
                value=float(rep.get("min_cash_reserve_ratio", 0.0)),
                key="r_csh",
            )

        st.markdown("---")
        submit_guard = st.form_submit_button("💾 Save Guardrails (Local)")

        if submit_guard:
            new_guardrails = {
                "schema": "GUARDRAILS_V1",
                "live": live,  # Unchanged from UI due to disabled
                "dry_run": {
                    "max_total_notional_ratio": float(d_tot),
                    "max_single_order_ratio": float(d_sgl),
                    "min_cash_reserve_ratio": float(d_csh),
                },
                "replay": {
                    "max_total_notional_ratio": float(r_tot),
                    "max_single_order_ratio": float(r_sgl),
                    "min_cash_reserve_ratio": float(r_csh),
                },
                "caps": caps,
            }
            # Save
            save_json(GUARDRAILS_PATH, new_guardrails)
            st.success(
                "Guardrails saved locally! Go to 'Current Parameters' to push everything to OCI (1-Click Sync)."
            )


def render_backtest_legacy(params_data, portfolio_data, guardrails_data):
    st.warning(
        "⚠️ 레거시 화면: 이 화면은 워크플로우 탭(P170-UI)으로요 조작 및 지표 표시가 통합되었습니다. 시계열 지표 및 추가 상세 모니터링이 필요한 경우에 한하여 참고 바랍니다."
    )
    st.header("🧪 백테스트 실행 (P165)")
    st.caption("Strategy Bundle 기반으로 백테스트를 실행하고 결과를 확인합니다.")

    col_mode, col_run = st.columns([2, 1])
    with col_mode:
        bt_mode = st.radio(
            "Mode", ["quick (6M)", "full (3Y)"], horizontal=True, key="bt_mode"
        )
    mode_arg = "quick" if "quick" in bt_mode else "full"

    with col_run:
        st.write("")  # spacer
        run_bt = st.button("▶️ 백테스트 실행", key="run_backtest_btn", type="primary")

    if run_bt:
        with st.spinner(f"백테스트 실행 중 (mode={mode_arg})..."):
            try:
                from app.run_backtest import run_cli_backtest

                success = run_cli_backtest(mode=mode_arg)
                if success:
                    st.success("✅ 백테스트 완료!")
                    st.session_state["bt_ran"] = True
                else:
                    st.error("❌ 백테스트 실패 (로그 확인 필요)")
                    st.session_state["bt_ran"] = False
            except Exception as e:
                st.error(f"❌ 실행 오류: {e}")
                st.session_state["bt_ran"] = False

    # ── 결과 표시 (항상 최신 파일 기준) ──
    bt_result_path = (
        BASE_DIR / "reports" / "backtest" / "latest" / "backtest_result.json"
    )
    if bt_result_path.exists():
        bt_data = load_json(bt_result_path)
        if bt_data:
            st.divider()
            st.subheader("📊 최신 백테스트 결과")

            # Summary metrics
            bt_summary = bt_data.get("summary", {})
            bt_meta = bt_data.get("meta", {})
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("CAGR", f"{bt_summary.get('cagr', 0):.2f}%")
            c2.metric("MDD", f"{bt_summary.get('mdd', 0):.2f}%")
            c3.metric("Sharpe", f"{bt_summary.get('sharpe', 0):.4f}")
            c4.metric("Total Return", f"{bt_summary.get('total_return', 0):.2f}%")

            # Backtest params (unified names with Tuning tab)
            st.markdown("**사용된 파라미터:**")
            p_used = bt_meta.get("params_used", {})
            bpc1, bpc2, bpc3 = st.columns(3)
            bpc1.metric("모멘텀 기간", p_used.get("momentum_period", "?"))
            bpc1.caption("`SSOT Key: momentum_period`")
            bpc2.metric("손절/청산 임계값", f"{p_used.get('stop_loss', 0)}")
            bpc2.caption("`SSOT Key: stop_loss`")
            bpc3.metric("최대 보유종목 수", p_used.get("max_positions", "?"))
            bpc3.caption("`SSOT Key: max_positions`")

            # Meta info
            mc1, mc2, mc3, mc4 = st.columns(4)
            mc1.caption(
                f"기간: {bt_meta.get('start_date', '?')} ~ {bt_meta.get('end_date', '?')}"
            )
            mc2.caption(f"거래: {bt_meta.get('total_trades', 0)}건")
            ec_len = len(bt_meta.get("equity_curve", []))
            dr_len = len(bt_meta.get("daily_returns", []))
            mc3.caption(f"Equity Curve: {ec_len} pts")
            mc4.caption(f"Daily Returns: {dr_len} pts")

            if bt_meta.get("sharpe_reason"):
                st.caption(f"⚠️ Sharpe 비고: {bt_meta['sharpe_reason']}")
            if bt_meta.get("mdd_reason"):
                st.caption(f"⚠️ MDD 비고: {bt_meta['mdd_reason']}")

            # Ticker-level table
            st.subheader("📈 종목별 Buy&Hold 성과")
            bt_tickers = bt_data.get("tickers", {})
            if bt_tickers:
                rows = []
                for code, vals in bt_tickers.items():
                    rows.append(
                        {
                            "종목": f"{get_ticker_name(code)} ({code})",
                            "CAGR (%)": vals.get("cagr", 0),
                            "MDD (%)": vals.get("mdd", 0),
                            "Win Rate (%)": vals.get("win_rate", 0),
                        }
                    )
                df_tickers = pd.DataFrame(rows).sort_values("CAGR (%)", ascending=False)
                st.dataframe(df_tickers, use_container_width=True, hide_index=True)

            # Top Performers
            st.subheader("🏆 Top Performers")
            top_p = bt_data.get("top_performers", [])
            for i, tp in enumerate(top_p[:5]):
                st.write(
                    f"{i+1}. **{get_ticker_name(tp['ticker'])}** ({tp['ticker']}) — CAGR {tp['cagr']:.2f}%"
                )

            # LLM Copy Block
            st.divider()
            st.subheader("📋 LLM 복붙용 요약")
            llm_block = {
                "summary": bt_summary,
                "period": f"{bt_meta.get('start_date', '?')} ~ {bt_meta.get('end_date', '?')}",
                "universe": bt_meta.get("universe", []),
                "params": {
                    "momentum_period": bt_meta.get("params_used", {}).get(
                        "momentum_period"
                    ),
                    "stop_loss": bt_meta.get("params_used", {}).get("stop_loss"),
                    "max_positions": bt_meta.get("params_used", {}).get(
                        "max_positions"
                    ),
                },
                "top_performers": top_p[:5],
                "total_trades": bt_meta.get("total_trades", 0),
                "equity_curve_length": ec_len,
            }
            st.code(
                json.dumps(llm_block, indent=2, ensure_ascii=False), language="json"
            )
    else:
        st.info("아직 백테스트 결과가 없습니다. 위의 ▶️ 버튼을 클릭하여 실행하세요.")


def render_tune_legacy(params_data, portfolio_data, guardrails_data):
    st.warning(
        "⚠️ 레거시 화면: 이 화면은 워크플로우 탭(P170-UI)으로 기능이 통합되었습니다. Top 10 상세 트라이얼 조회 용도로 사용하세요."
    )
    st.header("🎛️ Optuna 하이퍼파라미터 튜닝 (P167)")
    st.caption(
        "Strategy Bundle 기반으로 Optuna TPE를 실행하여 최적 파라미터를 탐색합니다."
    )

    # Controls — P168: n_trials는 number_input(step=1)으로 변경
    tc1, tc2, tc3 = st.columns([1, 1, 1])
    with tc1:
        tune_mode = st.radio(
            "Mode", ["quick (6M)", "full (3Y)"], horizontal=True, key="tune_mode"
        )
    with tc2:
        tune_trials = st.number_input(
            "Trials 수", min_value=5, max_value=500, value=30, step=1, key="tune_trials"
        )
    with tc3:
        tune_seed = st.number_input("Seed (재현성)", value=42, step=1, key="tune_seed")

    tune_mode_arg = "quick" if "quick" in tune_mode else "full"

    run_tune_btn = st.button("▶️ Run Tune", key="run_tune_btn", type="primary")

    if run_tune_btn:
        with st.spinner(
            f"튜닝 실행 중 (mode={tune_mode_arg}, trials={tune_trials})... 수 분 소요될 수 있습니다."
        ):
            try:
                from app.run_tune import run_cli_tune

                success = run_cli_tune(
                    mode=tune_mode_arg, n_trials=tune_trials, seed=int(tune_seed)
                )
                if success:
                    st.success("✅ 튜닝 완료!")
                    st.session_state["tune_ran"] = True
                else:
                    st.error("❌ 튜닝 실패 (로그 확인 필요)")
                    st.session_state["tune_ran"] = False
            except Exception as e:
                st.error(f"❌ 실행 오류: {e}")
                st.session_state["tune_ran"] = False

    # ── 결과 표시 ──
    tune_result_path = BASE_DIR / "reports" / "tune" / "latest" / "tune_result.json"
    if tune_result_path.exists():
        tune_data = load_json(tune_result_path)
        if tune_data:
            st.divider()
            st.subheader("🏆 최적 파라미터")

            # Best params
            bp = tune_data.get("best_params", {})
            bs = tune_data.get("best_summary", {})
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Best Score", f"{tune_data.get('best_score', 0):.4f}")
            c2.metric("Sharpe", f"{bs.get('sharpe', 0):.4f}")
            c3.metric("MDD", f"{bs.get('mdd_pct', 0):.2f}%")
            c4.metric("CAGR", f"{bs.get('cagr', 0):.4f}%")

            # Best params detail — P168: 통일된 한글 명칭 + SSOT 키
            st.markdown("**Best Parameters:**")
            pc1, pc2, pc3 = st.columns(3)
            pc1.metric("모멘텀 기간", bp.get("momentum_period", "?"))
            pc1.caption("`SSOT Key: momentum_period`")
            pc2.metric("손절/청산 임계값", f"{bp.get('stop_loss', 0):.2f}")
            pc2.caption("`SSOT Key: stop_loss (= exit_threshold)`")
            pc3.metric("최대 보유종목 수", bp.get("max_positions", "?"))
            pc3.caption("`SSOT Key: max_positions`")

            # Meta
            tune_meta = tune_data.get("meta", {})
            mc1, mc2, mc3, mc4 = st.columns(4)
            mc1.caption(
                f"기간: {tune_meta.get('start_date', '?')} ~ {tune_meta.get('end_date', '?')}"
            )
            mc2.caption(
                f"Trials: {tune_meta.get('completed_trials', 0)}/{tune_meta.get('n_trials', 0)} (pruned: {tune_meta.get('pruned_trials', 0)})"
            )
            mc3.caption(f"Runtime: {tune_meta.get('runtime_sec', 0):.1f}s")
            mc4.caption(f"Trades: {tune_data.get('best_total_trades', 0)}")

            # ─── P168: Best Params 적용 + Apply+Backtest ────────────────
            st.divider()
            st.subheader("⚡ Best Params 적용")

            abc1, abc2 = st.columns(2)
            apply_btn = abc1.button(
                "✅ Best Params → Current Parameters 적용 (로컬 저장)",
                key="apply_best_params",
            )
            apply_bt_btn = abc2.button(
                "🚀 적용 + Backtest Full(3Y) 실행", key="apply_and_backtest"
            )

            if apply_btn or apply_bt_btn:
                # (1) Apply best_params to Current Parameters
                try:
                    _p_data = load_json(LATEST_PATH)
                    if _p_data:
                        _p = _p_data.get("params", {})
                        _p.setdefault("lookbacks", {})["momentum_period"] = bp.get(
                            "momentum_period"
                        )
                        _p.setdefault("decision_params", {})["exit_threshold"] = bp.get(
                            "stop_loss"
                        )
                        _p.setdefault("position_limits", {})["max_positions"] = bp.get(
                            "max_positions"
                        )
                        _p_data["params"] = _p
                        _p_data["asof"] = datetime.now(KST).isoformat()
                        save_params(_p_data)
                        st.success(
                            f"✅ Current Parameters 업데이트 완료!\n\n"
                            f"- 모멘텀 기간: **{bp.get('momentum_period')}**\n"
                            f"- 손절/청산 임계값: **{bp.get('stop_loss')}**\n"
                            f"- 최대 보유종목 수: **{bp.get('max_positions')}**"
                        )
                    else:
                        st.error("Current Parameters 파일을 찾을 수 없습니다.")
                except Exception as e:
                    st.error(f"파라미터 적용 실패: {e}")

                # (2) If Apply+Backtest, run backtest
                if apply_bt_btn:
                    with st.spinner("백테스트 실행 중 (Full 3Y)..."):
                        try:
                            from app.run_backtest import run_cli_backtest

                            success = run_cli_backtest(mode="full")
                            if success:
                                st.success(
                                    "✅ 백테스트 완료! (🧪 백테스트 탭에서도 확인 가능)"
                                )
                                # Show inline summary
                                _bt_data = load_json(
                                    BASE_DIR
                                    / "reports"
                                    / "backtest"
                                    / "latest"
                                    / "backtest_result.json"
                                )
                                if _bt_data:
                                    _bs = _bt_data.get("summary", {})
                                    _bm = _bt_data.get("meta", {})
                                    rc1, rc2, rc3, rc4 = st.columns(4)
                                    rc1.metric("CAGR", f"{_bs.get('cagr', 0):.2f}%")
                                    rc2.metric("MDD", f"{_bs.get('mdd', 0):.2f}%")
                                    rc3.metric("Sharpe", f"{_bs.get('sharpe', 0):.4f}")
                                    rc4.metric("Trades", _bm.get("total_trades", 0))
                            else:
                                st.error("❌ 백테스트 실패 (로그 확인 필요)")
                        except Exception as e:
                            st.error(f"❌ 백테스트 오류: {e}")

            # Top 10 trials table
            st.divider()
            st.subheader("📊 Top 10 Trials")
            top10 = tune_data.get("trials_top10", [])
            if top10:
                rows = []
                for t in top10:
                    rows.append(
                        {
                            "#": t.get("trial", ""),
                            "Score": t.get("score", 0),
                            "Sharpe": t.get("sharpe", 0),
                            "MDD %": t.get("mdd_pct", 0),
                            "CAGR": t.get("cagr", 0),
                            "Trades": t.get("total_trades", 0),
                            "모멘텀 기간": t.get("params", {}).get(
                                "momentum_period", ""
                            ),
                            "손절 임계값": t.get("params", {}).get("stop_loss", ""),
                            "최대 종목수": t.get("params", {}).get("max_positions", ""),
                        }
                    )
                st.dataframe(
                    pd.DataFrame(rows), use_container_width=True, hide_index=True
                )

            # LLM Copy Block
            st.divider()
            st.subheader("📋 LLM 복붙용 요약")
            llm_tune = {
                "best_params": bp,
                "best_score": tune_data.get("best_score"),
                "best_summary": bs,
                "best_total_trades": tune_data.get("best_total_trades"),
                "period": f"{tune_meta.get('start_date', '?')} ~ {tune_meta.get('end_date', '?')}",
                "universe": tune_meta.get("universe", []),
                "trials": f"{tune_meta.get('completed_trials', 0)}/{tune_meta.get('n_trials', 0)}",
                "runtime_sec": tune_meta.get("runtime_sec"),
                "scoring": "sharpe - 2.0*(mdd_pct/100) - 0.0002*total_trades",
            }
            st.code(json.dumps(llm_tune, indent=2, ensure_ascii=False), language="json")
    else:
        st.info("아직 튜닝 결과가 없습니다. 위의 ▶️ 버튼을 클릭하여 실행하세요.")
