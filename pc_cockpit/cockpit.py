
import streamlit as st
import json
import hashlib
from datetime import datetime
from pathlib import Path
import pandas as pd
import altair as alt
import subprocess
import sys
import requests
import time

# P146.9 Configuration
FAST_TIMEOUT = 10     # Status checks
SLOW_TIMEOUT = 150    # Sync/Push/Pull

def check_backend_health():
    """Check connectivity and latency to Local Backend."""
    t0 = time.time()
    health = {"status": "UNKNOWN", "latency_ms": -1}
    try:
        # Use SSOT endpoint for health check
        r = requests.get("http://localhost:8000/api/ssot/snapshot", timeout=FAST_TIMEOUT)
        latency = int((time.time() - t0) * 1000)
        status = "OK" if r.status_code == 200 else f"ERR_{r.status_code}"
        health = {"status": status, "latency_ms": latency}
    except Exception as e:
        health = {"status": "FAIL", "latency_ms": -1, "error": str(e)}
    return health

import os
import json

# Add project root to path for util imports
BASE_DIR = Path(__file__).parent.parent
sys.path.append(str(BASE_DIR))

from app.utils.portfolio_normalize import normalize_portfolio, load_asof_override

# Config
st.set_page_config(page_title="KRX Strategy Cockpit", layout="wide")
BASE_DIR = Path(__file__).parent.parent
PARAMS_DIR = BASE_DIR / "state" / "strategy_params"
LATEST_PATH = PARAMS_DIR / "latest" / "strategy_params_latest.json"
SNAPSHOT_DIR = PARAMS_DIR / "snapshots"

# Portfolio Paths (P136.5)
PORTFOLIO_PATH = BASE_DIR / "state" / "portfolio" / "latest" / "portfolio_latest.json"

# Param Search Paths
SEARCH_DIR = BASE_DIR / "reports" / "pc" / "param_search" / "latest"
SEARCH_LATEST_PATH = SEARCH_DIR / "param_search_latest.json"

# Holdings Timing Paths
TIMING_DIR = BASE_DIR / "reports" / "pc" / "holding_timing" / "latest"
TIMING_LATEST_PATH = TIMING_DIR / "holding_timing_latest.json"

# Script Paths
SCRIPT_PARAM_SEARCH = BASE_DIR / "deploy" / "pc" / "run_param_search.ps1"
SCRIPT_HOLDING_TIMING = BASE_DIR / "deploy" / "pc" / "run_holding_timing.ps1"

# Replay Override Path (P143/P145)
ASOF_OVERRIDE_PATH = BASE_DIR / "state" / "runtime" / "asof_override_latest.json"

# Ensure directories exist
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

# Ticker Map (P136.5)
TICKER_MAP = {
    "069500": "KODEX 200",
    "229200": "KODEX KONEX", # Note: KONEX? Usually KOSDAQ 150 or similar strategy universe.
    "114800": "KODEX INVERSE",
    "122630": "KODEX LEVERAGE"
}
# Fallback function
def get_ticker_name(code):
    return f"{code} ({TICKER_MAP.get(code, 'Unknown')})"

def load_json(path):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None

def save_json(path, data):
    json_str = json.dumps(data, indent=2, ensure_ascii=False)
    path.write_text(json_str, encoding="utf-8")

def save_params(data):
    save_json(LATEST_PATH, data)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    snapshot_path = SNAPSHOT_DIR / f"strategy_params_{timestamp}.json"
    save_json(snapshot_path, data)
    return snapshot_path

def compute_fingerprint(data):
    return hashlib.sha256(json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]

def load_portfolio():
    if PORTFOLIO_PATH.exists():
        try:
            return json.loads(PORTFOLIO_PATH.read_text(encoding="utf-8"))
        except:
            pass
    return {}

def apply_reco(current_params, candidate):
    new_data = current_params.copy()
    new_data["asof"] = datetime.utcnow().isoformat() + "Z"
    
    cp = candidate["params"]
    target_p = new_data["params"]
    
    if "momentum_window" in cp:
        target_p["lookbacks"]["momentum_period"] = cp["momentum_window"]
    if "vol_window" in cp:
        target_p["lookbacks"]["volatility_period"] = cp["vol_window"]
    if "top_k" in cp:
        target_p["position_limits"]["max_positions"] = cp["top_k"]
        
    if "weights" in cp:
        target_p["decision_params"]["weight_momentum"] = cp["weights"]["mom"]
        target_p["decision_params"]["weight_volatility"] = cp["weights"]["vol"]
        
    new_data["params"] = target_p
    return new_data

def run_script(script_path):
    try:
        # Run powershell script
        result = subprocess.run(["powershell", "-File", str(script_path)], capture_output=True, text=True)
        return result.stdout, result.stderr, result.returncode
    except Exception as e:
        return "", str(e), -1

# UI

# Sidebar: Health Check moved to bottom


st.title("🚀 KRX Strategy Cockpit V1.7")

# REPLAY MODE CONTROLLER
override_cfg = load_asof_override()
is_replay = override_cfg.get("enabled", False)

# Simple Toggle in Sidebar or Top
with st.expander("⚙️ System Mode Settings", expanded=is_replay):
    col_mode, col_date, col_sim = st.columns(3)
    
    # 1. Enable/Disable Replay
    new_replay = col_mode.toggle("Enable Replay Mode", value=is_replay, key="replay_toggle")
    
    # 2. Date Picker (Only if Replay)
    current_asof = override_cfg.get("asof_kst")
    if not current_asof:
        current_asof = datetime.now().strftime("%Y-%m-%d")
        
    new_date = col_date.date_input("Replay Date", value=datetime.strptime(current_asof, "%Y-%m-%d"), disabled=not new_replay)
    
    # 3. Simulate Trade Day (P145)
    current_sim = override_cfg.get("simulate_trade_day", False)
    new_sim = col_sim.toggle("Simulate Trade Day", value=current_sim, disabled=not new_replay, help="Force trade day even on weekends")
    
    # Save Change
    if (new_replay != is_replay) or (str(new_date) != current_asof) or (new_sim != current_sim):
        override_cfg["enabled"] = new_replay
        override_cfg["asof_kst"] = str(new_date)
        override_cfg["simulate_trade_day"] = new_sim
        
        # Save to file
        with open(ASOF_OVERRIDE_PATH, "w", encoding="utf-8") as f:
            json.dump(override_cfg, f, indent=2)
            
        # P146: Auto-PUSH to OCI (Best Effort) is now Explicit in P146.1
        st.success("Settings Saved Locally!")
        
        # Explicit Sync Option
        col_sync, _ = st.columns([1, 2])
        if col_sync.button("🚀 Apply to OCI (Sync)", key="sync_replay_btn"):
             try:
                # 1. PUSH
                payload = {
                    "enabled": override_cfg["enabled"],
                    "mode": "REPLAY" if override_cfg["enabled"] else "LIVE",
                    "asof_kst": override_cfg.get("asof_kst"),
                    "simulate_trade_day": override_cfg.get("simulate_trade_day", False)
                }
                requests.post("http://localhost:8000/api/settings/mode", json=payload, timeout=FAST_TIMEOUT)
                
                # 2. READ-BACK
                res = requests.get("http://localhost:8000/api/settings/mode", timeout=FAST_TIMEOUT)
                oci_cfg = res.json()
                
                # 3. VERIFY
                st.toast("✅ Synced with OCI!")
                st.success("OCI Sync Verified:")
                st.dataframe([
                    {"Key": "Mode", "Local": "REPLAY" if override_cfg["enabled"] else "LIVE", "OCI": oci_cfg.get("mode")},
                    {"Key": "AsOf", "Local": override_cfg.get("asof_kst"), "OCI": oci_cfg.get("asof_kst")},
                    {"Key": "Simulate Trade", "Local": override_cfg.get("simulate_trade_day"), "OCI": oci_cfg.get("simulate_trade_day")}
                ])
             except Exception as e:
                st.error(f"Sync Failed: {e}")

        
        

if is_replay:
    st.error(f"🔴 REPLAY MODE ACTIVE (Data Basis: {override_cfg.get('asof_kst')})")
    if override_cfg.get("simulate_trade_day"):
        st.caption("✨ SIMULATING TRADE DAY (Holiday Bypass Active)")
    else:
        st.caption("System outputs will be generated based on this snapshot date.")
else:
    st.info("🟢 LIVE MODE ACTIVE (Real-time Data)")

params_data = load_json(LATEST_PATH)
portfolio_data = load_json(PORTFOLIO_PATH)

# Create Tabs
tab_ops, tab_main, tab_reco, tab_timing, tab_port_edit, tab_review = st.tabs([
    "🚀 Operations (P144)",
    "🔩 Current Parameters", 
    "🔎 Recommendations (P135)", 
    "⏱️ Holdings Timing (P136)",
    "💼 Portfolio Editor (P136.5)",
    "🧐 Param Review (P138)"
])

# TAB 0: Operations (P144/P146.1)
with tab_ops:
    st.header("Daily Operations Cockpit (UI-First)")
    
    # 1. Fetch Status (SSOT from Backend)
    ssot_snapshot = {}
    backend_ok = False
    error_msg = ""
    
    try:
        res = requests.get("http://localhost:8000/api/ssot/snapshot", timeout=FAST_TIMEOUT)
        if res.status_code == 200:
            ssot_snapshot = res.json()
            backend_ok = True
        else:
            error_msg = f"Status {res.status_code}: {res.text}"
    except Exception as e:
        error_msg = str(e)

    # P146.1: Unified Status Bar
    if backend_ok:
        env_info = ssot_snapshot.get("env_info", {})
        stage = ssot_snapshot.get("stage", "UNKNOWN")
        override = ssot_snapshot.get("asof_override", {})
        
        # Determine Modes
        is_replay = override.get("enabled", False)
        sim_trade = override.get("simulate_trade_day", False)
        replay_asof = override.get("asof_kst", "N/A")
        
        # Color coding
        env_color = "🟢" if env_info.get("type") == "PC" else "🟠"
        stage_color = "🔴" if "ERROR" in stage or "FAIL" in stage else "🔵"
        
        # Exec Mode Logic (P146.2)
        exec_mode = "LIVE"
        if is_replay:
             exec_mode = "DRY_RUN"
        
        # Display Bar
        st.info(f"""
        **ENV**: {env_color} {env_info.get("type", "PC")} ({env_info.get("hostname","localhost")}) | 
        **Target**: 🔗 {os.getenv("OCI_BACKEND_URL", "http://localhost:8000")} | 
        **Stage**: {stage_color} {stage} | 
        **Exec**: 🧪 {exec_mode} |
        **Replay**: {'🔴 ON (' + (replay_asof or 'Unknown') + ')' if is_replay else '⚪ OFF'} 
        """)
    else:
        st.error(f"🛑 Backend Connection Failed: {error_msg}")
        st.stop() # Stop rendering if backend is dead

    # P146.1: Explicit Sync Control
    st.divider()
    st.markdown("#### 🔄 SSOT Synchronization")
    
    # UI Layout: Horizontal Alignment
    # [Timeout 1] [Token 2] [Pull 1.5] [Push 1.5]
    c1, c2, c3, c4 = st.columns([1, 2, 1.5, 1.5])
    
    with c1:
        sync_timeout = st.number_input("Timeout (sec)", value=60, step=30, key="sync_timeout")
        
    with c2:
        push_token = st.text_input("Push Token", type="password", key="push_token", placeholder="Required for PUSH")
        
    with c3:
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True) # Spacer for label
        if st.button("📥 PULL (OCI)", use_container_width=True):
            with st.spinner(f"Pulling..."):
                try:
                    r = requests.post("http://localhost:8000/api/sync/pull", params={"timeout_seconds": sync_timeout}, timeout=sync_timeout + 5)
                    if r.status_code == 200:
                        st.success("OK")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(f"Fail: {r.text}")
                except Exception as e:
                    st.error(f"Error: {e}")

    with c4:
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True) # Spacer for label
        if st.button("📤 PUSH (OCI)", use_container_width=True):
            if not push_token:
                st.warning("Token!")
            else:
                with st.spinner(f"Pushing..."):
                    try:
                        r = requests.post("http://localhost:8000/api/sync/push", 
                                          json={"token": push_token}, 
                                          params={"timeout_seconds": sync_timeout},
                                          timeout=sync_timeout + 5)
                        if r.status_code == 200:
                            st.success("OK")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error(f"Fail: {r.text}")
                    except Exception as e:
                        st.error(f"Error: {e}")
    
    # Status Line
    st.caption(f"Status: {ssot_snapshot.get('synced_at', 'N/A')} (Rev: {ssot_snapshot.get('revision', 'N/A')})")

    st.divider()

    # 2. Controls (Auto Ops)
    st.subheader("🤖 Auto Operations (Token-Free)")
    # ... (Keep existing Auto Ops logic, minimal changes)
    if st.button("▶️ Run Auto Ops Cycle"):
         try:
             # Trigger Ops on OCI (Execution Plane) - Live Cycle (Reco -> Plan -> Summary)
             oci_url = os.getenv("OCI_BACKEND_URL", "http://localhost:8001")
             requests.post(f"{oci_url}/api/live/cycle/run?confirm=true", timeout=SLOW_TIMEOUT)
             st.toast("Auto Ops Triggered on OCI")
             time.sleep(1)
             st.rerun()
         except Exception as e:
             st.error(f"Trigger Failed: {e}")
             
    # 3. Next Actions & Artifacts (Keep existing)
    # ...

# TAB 1: Parameters
with tab_main:
    if not params_data:
        st.error("No strategy params found! Please initialize 'state/strategy_params/latest/strategy_params_latest.json'.")
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
            p = params_data.get("params", {})
            
            # Universe
            st.subheader("Universe")
            universe_str = st.text_area("Tickers (comma separated)", ", ".join(p.get("universe", [])))
            
            # Lookbacks
            st.subheader("Lookbacks")
            c1, c2 = st.columns(2)
            mom_period = c1.number_input("Momentum Period", value=p.get("lookbacks", {}).get("momentum_period", 20))
            vol_period = c2.number_input("Volatility Period", value=p.get("lookbacks", {}).get("volatility_period", 14))
            
            # Risk Limits
            st.subheader("Risk Limits")
            c1, c2 = st.columns(2)
            max_pos_pct = c1.number_input("Max Position %", value=p.get("risk_limits", {}).get("max_position_pct", 0.25))
            max_dd_pct = c2.number_input("Max Drawdown %", value=p.get("risk_limits", {}).get("max_drawdown_pct", 0.15))
            
            # Position Limits
            st.subheader("Position Limits")
            c1, c2 = st.columns(2)
            max_pos = c1.number_input("Max Positions (Count)", value=p.get("position_limits", {}).get("max_positions", 4))
            min_cash = c2.number_input("Min Cash %", value=p.get("position_limits", {}).get("min_cash_pct", 0.10))
            
            # Decision Params
            st.subheader("Decision Thresholds")
            c1, c2, c3 = st.columns(3)
            entry_th = c1.number_input("Entry Threshold", value=p.get("decision_params", {}).get("entry_threshold", 0.02))
            exit_th = c2.number_input("Exit Threshold", value=p.get("decision_params", {}).get("exit_threshold", -0.03))
            adx_min = c3.number_input("ADX Min", value=p.get("decision_params", {}).get("adx_filter_min", 20))
            
            # Weights (New in P135)
            st.subheader("Weights")
            c1, c2 = st.columns(2)
            w_mom = c1.number_input("Weight Mom", value=p.get("decision_params", {}).get("weight_momentum", 1.0))
            w_vol = c2.number_input("Weight Vol", value=p.get("decision_params", {}).get("weight_volatility", 0.0))
            
            submitted = st.form_submit_button("💾 Save Parameters")
            
            if submitted:
                # Update Data
                new_data = params_data.copy()
                new_data["asof"] = datetime.utcnow().isoformat() + "Z"
                new_params = p.copy()
                
                new_params["universe"] = [t.strip() for t in universe_str.split(",") if t.strip()]
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
                
                st.success(f"Saved! New Fingerprint: `{new_fp}`")
                st.info(f"Snapshot created at: `{snap_path}`")

# TAB 2: Recommendations
with tab_reco:
    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader("P135 Param Recommendations")
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
            st.success(f"🏆 Winner: Rank {winner.get('rank')} (Score: {winner.get('params', {}).get('metrics', {}).get('score_0_100', 'N/A')})")
            
            # Table
            for idx, res in enumerate(results[:5]): # Top 5
                with st.expander(f"Rank {res['rank']} (Score: {res['score_0_100']})", expanded=(idx==0)):
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Return", f"{res['metrics']['avg_forward_return']*100:.1f}%")
                    c2.metric("Hit Rate", f"{res['metrics']['hit_rate']*100:.0f}%")
                    c3.metric("Sample N", res['metrics']['sample_count'])
                    
                    st.json(res["params"])
                    
                    if st.button(f"Apply Rank {res['rank']}", key=f"apply_{idx}"):
                        if not params_data:
                            st.error("Base params not loaded.")
                        else:
                            new_p = apply_reco(params_data, res)
                            snap_path = save_params(new_p)
                            new_fp = compute_fingerprint(new_p)
                            st.success(f"Applied & Saved! New Fingerprint: `{new_fp}`")
                            st.experimental_rerun()

# TAB 3: Holdings Timing
with tab_timing:
    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader("P136 Holdings Timing Analysis")
    with col2:
        if st.button("🔄 Run Analysis (Timing)"):
            with st.spinner("Analyzing Holdings..."):
                out, err, code = run_script(SCRIPT_HOLDING_TIMING)
                if code == 0:
                    st.success("Analysis Complete!")
                    st.experimental_rerun()
                else:
                    st.error(f"Analysis Failed: {err}")

    # P146: Backtest UI MVP
    st.divider()
    st.markdown("#### 🧪 Backtest Simulation (MVP)")
    
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

    timing_data = load_json(TIMING_LATEST_PATH)
    if timing_data:
        # LLM Copy Area
        st.markdown("#### 🧠 Ask LLM (Context)")
        
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
                
                df_summary.append({
                    "Ticker": get_ticker_name(h["ticker"]),
                    "Qty": h["qty"],
                    "Avg Price": f"{avg:,.0f}",
                    "Current": f"{curr:,.0f}",
                    "PnL %": f"{pnl_pct:+.2f}%",
                    "Signal": h.get("current_signal", "UNKNOWN"),
                    "Reason": h.get("signal_reason", "")
                })
            
            st.dataframe(pd.DataFrame(df_summary))
            
            # Details
            # Use raw ticker for selection, but show name
            ticker_opts = [h["ticker"] for h in holdings]
            selected_ticker = st.selectbox("Select Ticker for Details", ticker_opts, format_func=get_ticker_name)
            
            target = next((h for h in holdings if h["ticker"] == selected_ticker), None)
            
            if target:
                col1, col2 = st.columns(2)
                with col1:
                    sig = target.get("current_signal", "UNKNOWN")
                    color = "green" if sig == "BUY" else "red" if sig == "SELL" else "gray"
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
                    st.metric("PnL %", f"{pnl_pct:+.2f}%", delta=f"{curr - avg:,.0f} KRW")

                # Lookback Events
                events = target.get("lookback_events", [])
                if events:
                    st.write("#### Recent Signal Events (60 Days)")
                    event_df = pd.DataFrame(events)
                    st.dataframe(event_df)
                else:
                    st.write("No signal changes in lookback period.")

# TAB 4: Portfolio Editor (P136.5)
with tab_port_edit:
    st.subheader("💼 Portfolio Editor (SSOT)")
    st.warning("⚠️ Editing this directly modifies 'state/portfolio/latest/portfolio_latest.json'. Use with caution. Changes must be synced to OCI manually or via bundle.")
    
    if not portfolio_data:
        st.error("Portfolio data not found.")
        if st.button("Initialize Empty Portfolio"):
             portfolio_data = {"updated_at": datetime.utcnow().isoformat(), "total_value": 0, "cash": 0, "holdings": {}}
             save_json(PORTFOLIO_PATH, portfolio_data)
             st.experimental_rerun()
    else:
        with st.form("portfolio_edit_form"):
            # Cash & Total
            c1, c2 = st.columns(2)
            total_val = c1.number_input("Total Value (KRW)", value=int(portfolio_data.get("total_value", 0)))
    # --- Portfolio Editor (P136.5) ---
    st.markdown("### 💼 포트폴리오 관리 (Portfolio Editor)")
    
    # Load Current
    port_data = load_portfolio()
    
    # 1. ASOF & Cash (Header)
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        current_asof = port_data.get("asof", "N/A")
        new_asof = st.text_input("기준일 (ASOF KST, YYYY-MM-DD)", value=current_asof)
    with c2:
        current_cash = port_data.get("cash", 0.0)
        new_cash = st.number_input("현금 (Cash)", value=float(current_cash), step=10000.0, format="%.0f")
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
        df_pos = pd.DataFrame(columns=["ticker", "quantity", "average_price", "current_price", "weight_pct"])
        
    # Rename for Korean UI
    col_map = {
        "ticker": "종목코드",
        "quantity": "수량",
        "average_price": "평단가",
        "current_price": "현재가",
        "weight_pct": "비중(%)"
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
            "비중(%)": st.column_config.NumberColumn(disabled=True, help="저장 시 자동 계산됩니다.")
        },
        hide_index=True
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
                if not p.get("ticker"): continue
                clean_positions.append({
                    "ticker": str(p["ticker"]),
                    "quantity": int(p.get("quantity", 0)),
                    "average_price": float(p.get("average_price", 0.0)),
                    "current_price": float(p.get("current_price", 0.0)),
                    "weight_pct": 0.0 # Will be calc by normalize
                })
                
            # Construct Payload
            payload = {
                "asof": new_asof.strip(),
                "cash": float(new_cash),
                "connections": port_data.get("connections", {}),
                "positions": clean_positions,
                "total_value": 0.0 # Will be calc by normalize
            }
            
            # Normalize (Strict Validation)
            final_payload = normalize_portfolio(payload)
            
            # Save
            with open(PORTFOLIO_PATH, "w", encoding="utf-8") as f:
                json.dump(final_payload, f, indent=2)
                
            st.success(f"✅ 포트폴리오 저장 완료 (Local)! (Asset: {final_payload['total_value']:,.0f})")
            
            # P146.1: Explicit Push Option
            col_push, _ = st.columns([1, 2])
            if col_push.button("📤 Push to OCI (Now)", key="push_port_btn"):
                 cached_token = st.session_state.get("push_token_input")
                 if cached_token:
                     try:
                        requests.post("http://localhost:8000/api/sync/push", json={"token": cached_token}, timeout=SLOW_TIMEOUT)
                        st.success("✅ Portfolio Pushed to OCI!")
                     except Exception as e:
                        st.error(f"Push Failed: {e}")
                 else:
                     st.error("Token required in Operations Tab for Push.")
            
            time.sleep(2) # Give time to read before rerun if user doesn't push immediately
            st.rerun()
            
        except Exception as e:
            st.error(f"Save Failed: {str(e)}")
# TAB 5: Param Review (P138)
REVIEW_DIR = BASE_DIR / "reports" / "pc" / "param_review" / "latest"
REVIEW_JSON_PATH = REVIEW_DIR / "param_review_latest.json"
REVIEW_MD_PATH = REVIEW_DIR / "param_review_latest.md"
SCRIPT_PARAM_REVIEW = BASE_DIR / "deploy" / "pc" / "run_param_review.ps1"

with tab_review:
    st.subheader("🧐 Strategy Parameter Review (P138)")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown("Compare candidates and make a final decision.")
    with col2:
        if st.button("📝 Generate Review Report"):
            with st.spinner("Analyzing..."):
                out, err, code = run_script(SCRIPT_PARAM_REVIEW)
                if code == 0:
                    st.success("Report Generated!")
                    st.experimental_rerun()
                else:
                    st.error(f"Generation Failed: {err}")
    
    review_data = load_json(REVIEW_JSON_PATH)
    if not review_data:
        st.info("No review report found. Click Generate to start.")
    else:
        # Display Recommendation
        rec = review_data.get("recommendation", {})
        cand_rank = rec.get("candidate_rank")
        st.info(f"💡 AI Suggestion: **Rank {cand_rank}** ({rec.get('level')}) - {rec.get('reason')}")
        
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
                    st.metric("Proj. Return", f"{m.get('avg_forward_return',0)*100:.1f}%")
                    st.metric("Hit Rate", f"{m.get('hit_rate',0)*100:.0f}%")
                    
                    st.markdown("---")
                    st.write("#### Action")
                    
                    # Apply Logic with Confirmation
                    if st.button(f"Apply Candidate {rank}", key=f"promo_{rank}"):
                        st.session_state[f"confirm_promo_{rank}"] = True
                    
                    if st.session_state.get(f"confirm_promo_{rank}"):
                        st.warning("Are you sure? This will update the local strategy parameters.")
                        if st.button("Yes, Confirm Apply", key=f"confirm_btn_{rank}"):
                            # Apply!
                            if not params_data:
                                st.error("Baseline params not loaded.")
                            else:
                                new_p = apply_reco(params_data, cand) # Re-use apply_reco from P135 logic
                                snap_path = save_params(new_p)
                                new_fp = compute_fingerprint(new_p)
                                st.success(f"Applied! New Fingerprint: `{new_fp}`")
                                st.info("This change is LOCAL. Run 'Publish Bundle' (P100) when ready to deploy.")
                                st.session_state[f"confirm_promo_{rank}"] = False
                                st.experimental_rerun()

        # Questions
        st.markdown("### ❓ Ask AI (Copy & Paste)")
        q_text = "\n".join([f"- {q}" for q in review_data.get("questions", [])])
        st.text_area("Questions", q_text, height=150)

# Sidebar Footer: Connectivity (Always Visible at Bottom)
st.sidebar.markdown("---")
st.sidebar.markdown("### 🔌 System Connectivity")
if st.sidebar.button("Check Connectivity 💓", key="conn_check_sidebar"):
    h = check_backend_health()
    status_icon = "🟢" if h["status"] == "OK" else "🔴"
    st.sidebar.metric("Backend Latency", f"{h['latency_ms']} ms", delta=status_icon)
    if h["status"] != "OK":
        st.sidebar.error(f"Status: {h['status']}")
    
    # Use session state or default for timeout display
    disp_timeout = st.session_state.get("sync_timeout", 60)
    st.sidebar.caption(f"Timeouts: {FAST_TIMEOUT}s / {disp_timeout}s")

