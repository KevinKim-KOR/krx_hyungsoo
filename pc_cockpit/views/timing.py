"""보유 타이밍 분석 (P136) 렌더러."""

import time

import pandas as pd
import streamlit as st

from pc_cockpit.services.config import BASE_DIR, get_ticker_name
from pc_cockpit.services.json_io import load_json, run_script


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
            st.info("Running Backtest... (Simulation)")
            time.sleep(1)
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
            ticker_opts = [h["ticker"] for h in holdings]
            selected_ticker = st.selectbox(
                "Select Ticker for Details",
                ticker_opts,
                format_func=get_ticker_name,
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
                        "PnL %",
                        f"{pnl_pct:+.2f}%",
                        delta=f"{curr - avg:,.0f} KRW",
                    )

                # Lookback Events
                events = target.get("lookback_events", [])
                if events:
                    st.write("#### Recent Signal Events (60 Days)")
                    event_df = pd.DataFrame(events)
                    st.dataframe(event_df)
                else:
                    st.write("No signal changes in lookback period.")
