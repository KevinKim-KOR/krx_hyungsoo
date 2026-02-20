# ... existing code ...

# TAB Backtest UI MVP (P146)
with tab_timing:
    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader("P136 Holdings Timing Analysis & Backtest")
    with col2:
        if st.button("🔄 Run Analysis (Timing)"):
            with st.spinner("Analyzing Holdings..."):
                out, err, code = run_script(SCRIPT_HOLDING_TIMING)
                if code == 0:
                    st.success("Analysis Complete!")
                    st.rerun()
                else:
                    st.error(f"Analysis Failed: {err}")

    timing_data = load_json(TIMING_LATEST_PATH)
    
    # ... existing timing display ...
    
    st.divider()
    
    # P146: Backtest UI MVP
    st.subheader("🧪 Backtest Simulation (MVP)")
    
    # Simple Controls
    bc1, bc2 = st.columns(2)
    with bc1:
         bt_mode = st.selectbox("Backtest Mode", ["Quick (Last 1 Year)", "Full (3 Years)"])
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

    # LLM Copy Area
    st.markdown("#### 🧠 Ask LLM (Context)")
    
    llm_context = ""
    if timing_data:
        holdings_txt = "\n".join([f"- {h['ticker']}: {h['qty']} (PnL: {h.get('metrics',{}).get('pnl_pct',0):.1f}%)" for h in timing_data.get("holdings", [])])
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
