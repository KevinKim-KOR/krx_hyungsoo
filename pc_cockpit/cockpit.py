import streamlit as st
import json
import os
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pandas as pd
import altair as alt
import requests
import time

# ── services/views imports ──
from pc_cockpit.services.config import (
    KST,
    FAST_TIMEOUT,
    SLOW_TIMEOUT,
    BASE_DIR,
    OCI_BACKEND_URL,
    PARAMS_DIR,
    LATEST_PATH,
    SNAPSHOT_DIR,
    PORTFOLIO_PATH,
    GUARDRAILS_PATH,
    SEARCH_DIR,
    SEARCH_LATEST_PATH,
    LIVE_APPROVAL_LATEST_PATH,
    LIVE_APPROVAL_SNAPSHOT_DIR,
    BUNDLE_LATEST_PATH,
    TIMING_DIR,
    TIMING_LATEST_PATH,
    SCRIPT_PARAM_SEARCH,
    SCRIPT_HOLDING_TIMING,
    ASOF_OVERRIDE_PATH,
    TICKER_MAP,
    _ssot_require,
    get_ticker_name,
    format_file_mtime,
    compute_fingerprint,
)
from pc_cockpit.services.json_io import (
    load_json,
    save_json,
    save_params,
    apply_tune_best_params_to_ssot,
    load_portfolio,
    apply_reco,
    run_script,
)
from pc_cockpit.services.promotion_verdict import refresh_promotion_verdict_local
from pc_cockpit.services.live_approval import (
    check_live_approval,
    handle_approve_live,
    handle_revoke_live,
)
from pc_cockpit.services.backend import check_backend_health, get_oci_ops_token
from pc_cockpit.views.tune_card import render_tune_results_card
from pc_cockpit.views.parameter_editor import render_ssot_parameter_form
from pc_cockpit.views.ops_daily import render_ops_p144
from pc_cockpit.views.workflow import (
    init_workflow_session_state,
    render_workflow_p170,
)

# P195: Initialize token in session state to prevent KeyError crash
init_workflow_session_state()

if not OCI_BACKEND_URL or not OCI_BACKEND_URL.strip():
    st.error(
        "환경변수 OCI_BACKEND_URL이 설정되지 않았습니다. "
        ".env 파일 또는 start.bat에서 설정하세요."
    )
    st.stop()

from app.utils.portfolio_normalize import normalize_portfolio
from pc_cockpit.views.replay_controller import render_replay_controller

# Config
st.set_page_config(page_title="KRX Strategy Cockpit", layout="wide")


# UI


st.title("🚀 KRX Strategy Cockpit V1.7")

# REPLAY MODE CONTROLLER
is_replay = render_replay_controller()


params_data = load_json(LATEST_PATH)
portfolio_data = load_json(PORTFOLIO_PATH)
guardrails_data = load_json(GUARDRAILS_PATH) or {}


def render_timing(params_data, portfolio_data, guardrails_data):
    TIMING_DIR = BASE_DIR / "reports" / "pc" / "holding_timing" / "latest"
    TIMING_LATEST_PATH = TIMING_DIR / "holding_timing_latest.json"
    SCRIPT_HOLDING_TIMING = BASE_DIR / "deploy" / "pc" / "run_holding_timing.ps1"
    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader("P136 Holdings Timing Analysis")
    with col2:
        if st.button("🔄 Run Analysis (Timing)"):
            with st.spinner("Analyzing Holdings..."):
                out, err, code = run_script(SCRIPT_HOLDING_TIMING)
                if code == 0:
                    st.success("Analysis Complete!")
                    st.rerun()
                else:
                    st.error(f"Analysis Failed: {err}")

    # P146: Backtest UI MVP
    st.divider()
    st.markdown("#### 🧪 Backtest Simulation (MVP)")

    # Simple Controls
    bc1, bc2 = st.columns(2)
    with bc1:
        bt_mode = st.selectbox(
            "Backtest Mode", ["Quick (Last 1 Year)", "Full (3 Years)"]
        )
    with bc2:
        if st.button("▶️ Run Backtest"):
            # For MVP, reuse holding timing script or dedicated backtest script?
            # User requested "Run Backtest : PC:8000 ... Save Result ... Copy for LLM"
            # We can trigger a new script `deploy/pc/run_backtest.ps1`
            st.info("Running Backtest... (Simulation)")
            time.sleep(1)

            # Mock Result Generation for MVP Speed (Actual implementation needs script)
            # Or we call an API?
            # Let's assume we call a script.
            pass

    timing_data = load_json(TIMING_LATEST_PATH)
    if timing_data:
        # LLM Copy Area
        st.markdown("#### 🧠 Ask LLM (Context)")

        holdings_txt = "\n".join(
            [
                f"- {h['ticker']}: {h['qty']} (PnL: {h.get('metrics',{}).get('pnl_pct',0):.1f}%)"
                for h in timing_data.get("holdings", [])
            ]
        )
        llm_context = f"""
        [Backtest Context]
        Strategy: {params_data.get('strategy', 'Unknown')}
        Market Date: {timing_data.get('asof', 'N/A')}
        Holdings:
        {holdings_txt}

        Metrics:
        - Hit Rate: TBD
        - CAGR: TBD

        Question:
        Analyze the current portfolio status and suggest improvements.
        """.strip()

        st.text_area("Copy this to Gemini/GPT:", value=llm_context, height=200)

    st.divider()
    st.subheader("📊 Current Holdings Analysis")
    if not timing_data:
        st.warning("No timing analysis found.")
    else:
        st.caption(f"Analysis Asof: {timing_data.get('asof', 'N/A')}")
        holdings = timing_data.get("holdings", [])

        if not holdings:
            st.info("No holdings found in portfolio.")
        else:
            # Summary Table with PnL
            df_summary = []
            for h in holdings:
                curr = h.get("current_price", 0)
                avg = h.get("avg_price", 0)
                pnl_pct = ((curr / avg) - 1) * 100 if avg > 0 else 0.0

                df_summary.append(
                    {
                        "Ticker": get_ticker_name(h["ticker"]),
                        "Qty": h["qty"],
                        "Avg Price": f"{avg:,.0f}",
                        "Current": f"{curr:,.0f}",
                        "PnL %": f"{pnl_pct:+.2f}%",
                        "Signal": h.get("current_signal", "UNKNOWN"),
                        "Reason": h.get("signal_reason", ""),
                    }
                )

            st.dataframe(pd.DataFrame(df_summary))

            # Details
            # Use raw ticker for selection, but show name
            ticker_opts = [h["ticker"] for h in holdings]
            selected_ticker = st.selectbox(
                "Select Ticker for Details", ticker_opts, format_func=get_ticker_name
            )

            target = next((h for h in holdings if h["ticker"] == selected_ticker), None)

            if target:
                col1, col2 = st.columns(2)
                with col1:
                    sig = target.get("current_signal", "UNKNOWN")
                    color = (
                        "green" if sig == "BUY" else "red" if sig == "SELL" else "gray"
                    )
                    st.markdown(f"### Signal: :{color}[{sig}]")
                    st.write(f"**Reason**: {target.get('signal_reason')}")
                    st.info(f"💡 **Hint**: {target.get('next_trigger_hint')}")

                with col2:
                    m = target.get("metrics", {})
                    st.metric("Momentum", f"{m.get('momentum_val',0):.1%}")
                    st.metric("Volatility", f"{m.get('volatility_val',0):.1%}")

                    # PnL Metric
                    curr = target.get("current_price", 0)
                    avg = target.get("avg_price", 0)
                    pnl_pct = ((curr / avg) - 1) * 100 if avg > 0 else 0.0
                    st.metric(
                        "PnL %", f"{pnl_pct:+.2f}%", delta=f"{curr - avg:,.0f} KRW"
                    )

                # Lookback Events
                events = target.get("lookback_events", [])
                if events:
                    st.write("#### Recent Signal Events (60 Days)")
                    event_df = pd.DataFrame(events)
                    st.dataframe(event_df)
                else:
                    st.write("No signal changes in lookback period.")


def render_port_edit(params_data, portfolio_data, guardrails_data):
    st.subheader("💼 Portfolio Editor (SSOT)")
    st.warning(
        "⚠️ Editing this directly modifies 'state/portfolio/latest/portfolio_latest.json'. Use with caution. Changes must be synced to OCI manually or via bundle."
    )

    if not portfolio_data:
        st.error("Portfolio data not found.")
        if st.button("Initialize Empty Portfolio"):
            KST = timezone(timedelta(hours=9))
            portfolio_data = {
                "updated_at": datetime.now(KST).isoformat(),
                "total_value": 0,
                "cash": 0,
                "holdings": {},
            }
            save_json(PORTFOLIO_PATH, portfolio_data)
            st.rerun()
    # === 0. Sync Status & Push UI (P146.9 HOTFIX) ===
    if "port_sync_state" not in st.session_state:
        st.session_state["port_sync_state"] = "SYNCED"

    is_synced = st.session_state["port_sync_state"] == "SYNCED"

    st.markdown("#### 🔄 OCI 동기화 상태")
    if is_synced:
        st.success(
            "🟢 **SYNCED** (로컬 저장본과 OCI 반영본이 일치합니다. OCI 동기화: 워크플로우 탭 1-Click Sync 사용)"
        )
    else:
        st.error(
            "🔴 **OUT_OF_SYNC** (로컬에만 저장됨! OCI 동기화는 워크플로우 탭의 '1-Click Sync'를 이용하세요.)"
        )

    st.divider()

    # --- Portfolio Editor (P136.5) ---
    st.markdown("### 💼 포트폴리오 편집 (Local)")

    # Load Current
    port_data = load_portfolio()

    # 1. ASOF & Cash (Header)
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        current_asof = port_data.get("asof", "N/A")
        new_asof = st.text_input(
            "기준일 (ASOF KST, YYYY-MM-DD)", value=current_asof, disabled=True
        )
    with c2:
        current_cash = port_data.get("cash", 0.0)
        new_cash = st.number_input(
            "현금 (Cash)", value=float(current_cash), step=10000.0, format="%.0f"
        )
    with c3:
        # Read-only Total Value (Will be recalculated on save)
        st.metric("총자산 (Total Value)", f"{port_data.get('total_value', 0):,.0f} KRW")

    # 2. Holdings Editor
    st.markdown("#### 보유 종목 (Holdings)")
    current_positions = port_data.get("positions", [])

    # Convert to DataFrame for Editor
    # Schema: ticker, quantity, average_price, current_price, weight_pct
    df_pos = pd.DataFrame(current_positions)
    if df_pos.empty:
        df_pos = pd.DataFrame(
            columns=[
                "ticker",
                "quantity",
                "average_price",
                "current_price",
                "weight_pct",
            ]
        )

    # Rename for Korean UI
    col_map = {
        "ticker": "종목코드",
        "quantity": "수량",
        "average_price": "평단가",
        "current_price": "현재가",
        "weight_pct": "비중(%)",
    }
    df_pos_ui = df_pos.rename(columns=col_map)

    # Editable Config
    edited_df = st.data_editor(
        df_pos_ui,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "종목코드": st.column_config.TextColumn(required=True),
            "수량": st.column_config.NumberColumn(min_value=0, step=1, format="%d"),
            "평단가": st.column_config.NumberColumn(min_value=0, format="%.0f"),
            "현재가": st.column_config.NumberColumn(min_value=0, format="%.0f"),
            "비중(%)": st.column_config.NumberColumn(
                disabled=True, help="저장 시 자동 계산됩니다."
            ),
        },
        hide_index=True,
    )

    # 3. Save Action
    if st.button("💾 포트폴리오 저장 (Save & Normalize)"):
        try:
            # Reconstruct Positions
            # Reverse Column Map
            rev_map = {v: k for k, v in col_map.items()}
            final_df = edited_df.rename(columns=rev_map)

            # Convert to list of dicts
            new_positions = final_df.to_dict(orient="records")

            # Clean types
            clean_positions = []
            for p in new_positions:
                if not p.get("ticker"):
                    continue
                clean_positions.append(
                    {
                        "ticker": str(p["ticker"]),
                        "quantity": int(p.get("quantity", 0)),
                        "average_price": float(p.get("average_price", 0.0)),
                        "current_price": float(p.get("current_price", 0.0)),
                        "weight_pct": 0.0,  # Will be calc by normalize
                    }
                )

            # Construct Payload
            payload = {
                "asof": new_asof.strip(),
                "cash": float(new_cash),
                "connections": port_data.get("connections", {}),
                "positions": clean_positions,
                "total_value": 0.0,  # Will be calc by normalize
            }

            # Normalize (Strict Validation)
            final_payload = normalize_portfolio(payload)

            # Save
            with open(PORTFOLIO_PATH, "w", encoding="utf-8") as f:
                json.dump(final_payload, f, indent=2)

            # Update Sync State
            st.session_state["port_sync_state"] = "OUT_OF_SYNC"
            st.success(
                f"✅ 포트폴리오 저장 완료 (Local)! (Asset: {final_payload['total_value']:,.0f})"
            )
            st.toast(
                "로컬에 임시저장 되었습니다! 위쪽의 'Push to OCI' 버튼을 눌러 OCI에 반영해주세요."
            )

            time.sleep(1)
            st.rerun()

        except Exception as e:
            st.error(f"Save Failed: {str(e)}")


def render_advanced_panel(params_data, portfolio_data, guardrails_data):
    st.header("🛠️ 정비창 (Advanced)")
    st.warning("⚠️ 실험/복구용 창고. 운영 기본 동선 아님.")
    st.caption("운영에 의미 있는 LAB 2종 및 개별 기능 테스트를 공간입니다.")

    module_options = [
        "선택 안함",
        "Holdings Timing (P136)",
        "Portfolio Editor (P136.5)",
    ]
    selected_module = st.selectbox("모듈 선택", module_options)
    st.divider()

    if selected_module == "Holdings Timing (P136)":
        st.info("💡 보유 종목의 타이밍 상황판(운영 보조) 목적입니다.")
        render_timing(params_data, portfolio_data, guardrails_data)
    elif selected_module == "Portfolio Editor (P136.5)":
        st.warning("⚠️ SSOT/현실 잔고 보정 목적입니다.")
        render_port_edit(params_data, portfolio_data, guardrails_data)


# Main App Routing
top_tab_ops, top_tab_wf, top_tab_adv = st.tabs(
    ["🚀 데일리 운영 (P144)", "🧭 워크플로우 (P170)", "🛠️ 정비창 (Advanced)"]
)

with top_tab_ops:
    render_ops_p144(params_data, portfolio_data, guardrails_data)

with top_tab_wf:
    render_workflow_p170(params_data, portfolio_data, guardrails_data)

with top_tab_adv:
    render_advanced_panel(params_data, portfolio_data, guardrails_data)
