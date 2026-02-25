
import streamlit as st
import json
import hashlib
from datetime import datetime, timezone, timedelta
KST = timezone(timedelta(hours=9))
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
PARAMS_DIR = BASE_DIR / "state" / "params"
LATEST_PATH = PARAMS_DIR / "latest" / "strategy_params_latest.json"
SNAPSHOT_DIR = PARAMS_DIR / "snapshots"

# Portfolio Paths (P136.5)
PORTFOLIO_PATH = BASE_DIR / "state" / "portfolio" / "latest" / "portfolio_latest.json"

# Guardrails Paths (P160)
GUARDRAILS_PATH = BASE_DIR / "state" / "guardrails" / "latest" / "guardrails_latest.json"

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
    KST = timezone(timedelta(hours=9))
    timestamp = datetime.now(KST).strftime("%Y%m%d_%H%M%S")
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
    KST = timezone(timedelta(hours=9))
    new_data["asof"] = datetime.now(KST).isoformat()
    
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
        current_asof = datetime.now(KST).strftime("%Y-%m-%d")
        
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
guardrails_data = load_json(GUARDRAILS_PATH) or {}

# Create Tabs
tab_ops, tab_main, tab_reco, tab_timing, tab_port_edit, tab_review, tab_guardrails, tab_backtest, tab_tune = st.tabs([
    "🚀 Operations (P144)",
    "🔩 Current Parameters", 
    "🔎 Recommendations (P135)", 
    "⏱️ Holdings Timing (P136)",
    "💼 Portfolio Editor (P136.5)",
    "🧐 Param Review (P138)",
    "🛡️ Guardrails (P160)",
    "🧪 백테스트 (P165)",
    "🎛️ 튜닝 (P167)"
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
        st.text_input("Confirm Token", type="password", key="confirm_token", placeholder="Required for PUSH")
        
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
            token = st.session_state.get("confirm_token", "")
            if not token:
                st.warning("Token Required!")
            else:
                with st.spinner(f"Pushing..."):
                    try:
                        r = requests.post("http://localhost:8000/api/sync/push", 
                                          json={"token": token}, 
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
    
    col_run, col_force = st.columns([1, 1])
    with col_force:
        force_recompute = st.checkbox("☑ Force Recompute (Overwrite)", value=False, help="강제 재생성 (LIVE 모드에서는 무시됨)")
        
    with col_run:
        if st.button("▶️ Run Auto Ops Cycle", use_container_width=True):
             try:
                 oci_url = os.getenv("OCI_BACKEND_URL", "http://localhost:8001")
                 # P152: Send force query param
                 resp = requests.post(f"{oci_url}/api/live/cycle/run?confirm=true&force={str(force_recompute).lower()}", timeout=SLOW_TIMEOUT)
                 if resp.status_code == 200:
                     data = resp.json()
                     results = data.get("results", {})
                     
                     # Format summary
                     summary_str = " | ".join([f"{k.upper()}: {v}" for k, v in results.items() if k != "ops_summary"])
                     if not summary_str:
                         summary_str = "Auto Ops Completed via Orchestrator"
                         
                     # P154: Store result in session state to persist after rerun
                     st.session_state["last_cycle_result"] = f"✅ {summary_str}"
                     st.toast("Auto Ops Cycle Completed")
                 elif resp.status_code == 500:
                     data = resp.json()
                     detail = data.get("detail", {})
                     
                     if isinstance(detail, dict) and "ops_run" in detail:
                         results_dict = detail["ops_run"].get("results", {})
                         summary_parts = []
                         for k, v in results_dict.items():
                             if k == "ops_summary": continue
                             action = v.get("result", "UNKNOWN")
                             reason = v.get("reason", "")
                             desc = f"{action}" + (f" ({reason})" if reason else "")
                             summary_parts.append(f"{k.upper()}: {desc}")
                             
                         summary_str = " | ".join(summary_parts)
                         st.session_state["last_cycle_result"] = f"❌ {summary_str}"
                         st.error(f"Auto Ops Failed: {detail.get('reason')}")
                     else:
                         st.error(f"Trigger Failed: 500 - {detail}")
                 else:
                     st.error(f"Trigger Failed: {resp.status_code} - {resp.text}")
                     
                 time.sleep(1.5)
                 st.rerun()
             except Exception as e:
                 st.error(f"Trigger Failed: {e}")
                 
             
    # P154: Display persistent cycle result (Outside columns so it doesn't get squished)
    if "last_cycle_result" in st.session_state:
        st.info(st.session_state["last_cycle_result"])
             
    # 3. System Connectivity (Main Block Bottom)
    st.divider()
    st.markdown("#### 🔌 System Connectivity")
    if st.button("Check Connectivity 💓", key="conn_check_main"):
        h = check_backend_health()
        status_icon = "🟢" if h["status"] == "OK" else "🔴"
        
        c_lat, c_tout = st.columns(2)
        c_lat.metric("Backend Latency", f"{h['latency_ms']} ms", delta=status_icon)
        
        # Timeout Info
        disp_timeout = st.session_state.get("sync_timeout", 60)
        c_tout.caption(f"Settings: [Status {FAST_TIMEOUT}s] [Sync {disp_timeout}s]")
        
        if h["status"] != "OK":
            st.error(f"Status: {h['status']}")

    # End of Ops Tab


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
            mom_period = c1.number_input("모멘텀 기간 (Momentum Period)", value=p.get("lookbacks", {}).get("momentum_period", 20))
            c1.caption("`SSOT Key: momentum_period`")
            vol_period = c2.number_input("변동성 기간 (Volatility Period)", value=p.get("lookbacks", {}).get("volatility_period", 14))
            c2.caption("`SSOT Key: volatility_period`")
            
            # Risk Limits
            st.subheader("Risk Limits")
            c1, c2 = st.columns(2)
            max_pos_pct = c1.number_input("최대 포지션 비중 (Max Position %)", value=p.get("risk_limits", {}).get("max_position_pct", 0.25))
            c1.caption("`SSOT Key: max_position_pct`")
            max_dd_pct = c2.number_input("최대 낙폭 (Max Drawdown %)", value=p.get("risk_limits", {}).get("max_drawdown_pct", 0.15))
            c2.caption("`SSOT Key: max_drawdown_pct`")
            
            # Position Limits
            st.subheader("Position Limits")
            c1, c2 = st.columns(2)
            max_pos = c1.number_input("최대 보유종목 수 (Max Positions)", value=p.get("position_limits", {}).get("max_positions", 4))
            c1.caption("`SSOT Key: max_positions`")
            min_cash = c2.number_input("최소 현금비율 (Min Cash %)", value=p.get("position_limits", {}).get("min_cash_pct", 0.10))
            c2.caption("`SSOT Key: min_cash_pct`")
            
            # Decision Params
            st.subheader("Decision Thresholds")
            c1, c2, c3 = st.columns(3)
            entry_th = c1.number_input("진입 임계값 (Entry Threshold)", value=p.get("decision_params", {}).get("entry_threshold", 0.02))
            c1.caption("`SSOT Key: entry_threshold`")
            exit_th = c2.number_input("손절/청산 임계값 (Stop Loss)", value=p.get("decision_params", {}).get("exit_threshold", -0.03))
            c2.caption("`SSOT Key: exit_threshold (= stop_loss)`")
            adx_min = c3.number_input("ADX 최소값 (ADX Min)", value=p.get("decision_params", {}).get("adx_filter_min", 20))
            c3.caption("`SSOT Key: adx_filter_min`")
            
            # Weights (New in P135)
            st.subheader("Weights")
            c1, c2 = st.columns(2)
            w_mom = c1.number_input("Weight Mom", value=p.get("decision_params", {}).get("weight_momentum", 1.0))
            w_vol = c2.number_input("Weight Vol", value=p.get("decision_params", {}).get("weight_volatility", 0.0))
            
            c_btn1, c_btn2 = st.columns(2)
            with c_btn1:
                submit_local = st.form_submit_button("💾 Save Parameters (Local)")
            with c_btn2:
                submit_push = st.form_submit_button("🚀 Save & Push Bundle to OCI (1-Click Sync)")
            
            submitted = submit_local or submit_push
            
            if submitted:
                # Update Data
                new_data = params_data.copy()
                KST = timezone(timedelta(hours=9))
                new_data["asof"] = datetime.now(KST).isoformat()
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
                
                # Fingerprint 즉시 갱신
                st.session_state["current_fingerprint"] = new_fp
                
                st.success(f"Saved (Local)! New Fingerprint: `{new_fp}`")
                
                if submit_push:
                    st.info("📦 Generating Bundle and Pushing to OCI...")
                    
                    is_dry_run = st.session_state.get("is_dry_run", False)
                    is_replay = st.session_state.get("is_replay", False)
                    require_token = not (is_dry_run or is_replay)
                    
                    push_allowed = False
                    token = st.session_state.get("confirm_token", "")
                    
                    if require_token:
                        if not token:
                            st.warning("⚠️ 로컬 저장은 됐지만 OCI Push 실패 → Drift 지속: LIVE Mode requires Confirm Token. Please enter it in the top tab first.")
                        else:
                            push_allowed = True
                    else:
                        # REPLAY or DRY_RUN mode handling for tokenless push
                        # Will be evaluated by Backend server flag, but UI passes empty string if token is empty
                        push_allowed = True
                        
                    if push_allowed:
                        try:
                            # Must use SLOW_TIMEOUT as bundle generation might take a bit
                            resp = requests.post("http://localhost:8000/api/sync/push_bundle", json={"token": token}, timeout=SLOW_TIMEOUT)
                            if resp.status_code == 200:
                                res_data = resp.json()
                                st.success(f"✅ 저장 + OCI 장착 완료( created_at={res_data.get('created_at')} )")
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.warning(f"⚠️ 로컬 저장은 됐지만 OCI Push 실패 → Drift 지속: {resp.text}")
                        except Exception as e:
                            st.warning(f"⚠️ 로컬 저장은 됐지만 OCI Push 실패 → Drift 지속: {str(e)}")
                else:
                    time.sleep(1)
                    st.rerun()

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
                            st.rerun()

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
                    st.rerun()
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
             KST = timezone(timedelta(hours=9))
             portfolio_data = {"updated_at": datetime.now(KST).isoformat(), "total_value": 0, "cash": 0, "holdings": {}}
             save_json(PORTFOLIO_PATH, portfolio_data)
             st.rerun()
    # === 0. Sync Status & Push UI (P146.9 HOTFIX) ===
    if "port_sync_state" not in st.session_state:
        st.session_state["port_sync_state"] = "SYNCED"
        
    is_synced = st.session_state["port_sync_state"] == "SYNCED"
    
    st.markdown("#### 🔄 OCI 동기화 상태")
    c_stat, c_push = st.columns([3, 1])
    with c_stat:
        if is_synced:
            st.success("🟢 **SYNCED** (로컬 저장본과 OCI 반영본이 일치합니다)")
        else:
            st.error("🔴 **OUT_OF_SYNC** (로컬에만 저장됨! 우측 버튼을 눌러 OCI에 확정 반영해주세요)")
            
    with c_push:
        if st.button("📤 Push to OCI", disabled=is_synced, use_container_width=True):
            # Token Check
            is_live = not is_replay
            cached_token = st.session_state.get("push_token_input", "")
            
            if is_live and not cached_token:
                st.error("LIVE 모드: Operations 탭에서 Push Token을 먼저 입력해야 합니다.")
            else:
                with st.spinner("Pushing to OCI..."):
                    try:
                        r = requests.post("http://localhost:8000/api/sync/push", 
                                          json={"token": cached_token}, 
                                          timeout=SLOW_TIMEOUT)
                        if r.status_code == 200:
                            st.session_state["port_sync_state"] = "SYNCED"
                            st.success("✅ OCI 체인에 포트폴리오가 정상 반영되었습니다!")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error(f"Push Failed: {r.text}")
                    except Exception as e:
                        st.error(f"Error: {e}")
                        
    st.divider()

    # --- Portfolio Editor (P136.5) ---
    st.markdown("### 💼 포트폴리오 편집 (Local)")
    
    # Load Current
    port_data = load_portfolio()
    
    # 1. ASOF & Cash (Header)
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        current_asof = port_data.get("asof", "N/A")
        new_asof = st.text_input("기준일 (ASOF KST, YYYY-MM-DD)", value=current_asof, disabled=True)
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
                
            # Update Sync State
            st.session_state["port_sync_state"] = "OUT_OF_SYNC"
            st.success(f"✅ 포트폴리오 저장 완료 (Local)! (Asset: {final_payload['total_value']:,.0f})")
            st.toast("로컬에 임시저장 되었습니다! 위쪽의 'Push to OCI' 버튼을 눌러 OCI에 반영해주세요.")
            
            time.sleep(1)
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
                                st.rerun()

        # Questions
        st.markdown("### ❓ Ask AI (Copy & Paste)")
        q_text = "\n".join([f"- {q}" for q in review_data.get("questions", [])])
        st.text_area("Questions", q_text, height=150)


# TAB 6: Guardrails (P160)
with tab_guardrails:
    st.header("🛡️ Execution Guardrails (P160 SSOT)")
    st.markdown("Manage safety limits for `LIVE`, `DRY_RUN`, and `REPLAY` execution modes. Note: LIVE mode limits are read-only for safety.")
    
    caps = guardrails_data.get("caps", {"max_total_notional_ratio": 1.0, "max_single_order_ratio": 1.0, "min_cash_reserve_ratio": 0.0})
    st.caption(f"**Hard Caps (Fail-Closed Boundaries):** Max Notional = {caps.get('max_total_notional_ratio')}, Max Single = {caps.get('max_single_order_ratio')}, Min Reserve = {caps.get('min_cash_reserve_ratio')}")
    
    with st.form("guardrails_form"):
        c_live, c_dry, c_rep = st.columns(3)
        
        # LIVE (Readonly visually)
        with c_live:
            st.subheader("🔴 LIVE Mode")
            live = guardrails_data.get("live", {"max_total_notional_ratio": 0.3, "max_single_order_ratio": 0.1, "min_cash_reserve_ratio": 0.05})
            l_tot = st.number_input("Max Total Notional Ratio", value=float(live.get("max_total_notional_ratio", 0.3)), key="l_tot", help="Read-only", disabled=True)
            l_sgl = st.number_input("Max Single Order Ratio", value=float(live.get("max_single_order_ratio", 0.1)), key="l_sgl", disabled=True)
            l_csh = st.number_input("Min Cash Reserve Ratio", value=float(live.get("min_cash_reserve_ratio", 0.05)), key="l_csh", disabled=True)
            
        with c_dry:
            st.subheader("🧪 DRY_RUN Mode")
            dry = guardrails_data.get("dry_run", {"max_total_notional_ratio": 1.0, "max_single_order_ratio": 1.0, "min_cash_reserve_ratio": 0.0})
            d_tot = st.number_input("Max Total Notional Ratio", value=float(dry.get("max_total_notional_ratio", 1.0)), key="d_tot")
            d_sgl = st.number_input("Max Single Order Ratio", value=float(dry.get("max_single_order_ratio", 1.0)), key="d_sgl")
            d_csh = st.number_input("Min Cash Reserve Ratio", value=float(dry.get("min_cash_reserve_ratio", 0.0)), key="d_csh")
            
        with c_rep:
            st.subheader("⏪ REPLAY Mode")
            rep = guardrails_data.get("replay", {"max_total_notional_ratio": 1.0, "max_single_order_ratio": 1.0, "min_cash_reserve_ratio": 0.0})
            r_tot = st.number_input("Max Total Notional Ratio", value=float(rep.get("max_total_notional_ratio", 1.0)), key="r_tot")
            r_sgl = st.number_input("Max Single Order Ratio", value=float(rep.get("max_single_order_ratio", 1.0)), key="r_sgl")
            r_csh = st.number_input("Min Cash Reserve Ratio", value=float(rep.get("min_cash_reserve_ratio", 0.0)), key="r_csh")
            
        st.markdown("---")
        submit_guard = st.form_submit_button("💾 Save Guardrails (Local)")
        
        if submit_guard:
            new_guardrails = {
                "schema": "GUARDRAILS_V1",
                "live": live, # Unchanged from UI due to disabled
                "dry_run": {
                    "max_total_notional_ratio": float(d_tot),
                    "max_single_order_ratio": float(d_sgl),
                    "min_cash_reserve_ratio": float(d_csh)
                },
                "replay": {
                    "max_total_notional_ratio": float(r_tot),
                    "max_single_order_ratio": float(r_sgl),
                    "min_cash_reserve_ratio": float(r_csh)
                },
                "caps": caps
            }
            # Save
            save_json(GUARDRAILS_PATH, new_guardrails)
            st.success("Guardrails saved locally! Go to 'Current Parameters' to push everything to OCI (1-Click Sync).")

# ─── TAB 7: 🧪 백테스트 (P165) ─────────────────────────────────────────
with tab_backtest:
    st.header("🧪 백테스트 실행 (P165)")
    st.caption("Strategy Bundle 기반으로 백테스트를 실행하고 결과를 확인합니다.")

    col_mode, col_run = st.columns([2, 1])
    with col_mode:
        bt_mode = st.radio("Mode", ["quick (6M)", "full (3Y)"], horizontal=True, key="bt_mode")
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
    bt_result_path = BASE_DIR / "reports" / "backtest" / "latest" / "backtest_result.json"
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
            p_used = bt_meta.get('params_used', {})
            bpc1, bpc2, bpc3 = st.columns(3)
            bpc1.metric("모멘텀 기간", p_used.get('momentum_period', '?'))
            bpc1.caption("`SSOT Key: momentum_period`")
            bpc2.metric("손절/청산 임계값", f"{p_used.get('stop_loss', 0)}")
            bpc2.caption("`SSOT Key: stop_loss`")
            bpc3.metric("최대 보유종목 수", p_used.get('max_positions', '?'))
            bpc3.caption("`SSOT Key: max_positions`")

            # Meta info
            mc1, mc2, mc3, mc4 = st.columns(4)
            mc1.caption(f"기간: {bt_meta.get('start_date', '?')} ~ {bt_meta.get('end_date', '?')}")
            mc2.caption(f"거래: {bt_meta.get('total_trades', 0)}건")
            ec_len = len(bt_meta.get('equity_curve', []))
            dr_len = len(bt_meta.get('daily_returns', []))
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
                    rows.append({
                        "종목": f"{get_ticker_name(code)} ({code})",
                        "CAGR (%)": vals.get("cagr", 0),
                        "MDD (%)": vals.get("mdd", 0),
                        "Win Rate (%)": vals.get("win_rate", 0),
                    })
                df_tickers = pd.DataFrame(rows).sort_values("CAGR (%)", ascending=False)
                st.dataframe(df_tickers, use_container_width=True, hide_index=True)

            # Top Performers
            st.subheader("🏆 Top Performers")
            top_p = bt_data.get("top_performers", [])
            for i, tp in enumerate(top_p[:5]):
                st.write(f"{i+1}. **{get_ticker_name(tp['ticker'])}** ({tp['ticker']}) — CAGR {tp['cagr']:.2f}%")

            # LLM Copy Block
            st.divider()
            st.subheader("📋 LLM 복붙용 요약")
            llm_block = {
                "summary": bt_summary,
                "period": f"{bt_meta.get('start_date', '?')} ~ {bt_meta.get('end_date', '?')}",
                "universe": bt_meta.get("universe", []),
                "params": {
                    "momentum_period": bt_meta.get("params_used", {}).get("momentum_period"),
                    "stop_loss": bt_meta.get("params_used", {}).get("stop_loss"),
                    "max_positions": bt_meta.get("params_used", {}).get("max_positions"),
                },
                "top_performers": top_p[:5],
                "total_trades": bt_meta.get("total_trades", 0),
                "equity_curve_length": ec_len,
            }
            st.code(json.dumps(llm_block, indent=2, ensure_ascii=False), language="json")
    else:
        st.info("아직 백테스트 결과가 없습니다. 위의 ▶️ 버튼을 클릭하여 실행하세요.")

# ─── TAB 8: 🎛️ 튜닝 (P167/P168) ──────────────────────────────────────────
with tab_tune:
    st.header("🎛️ Optuna 하이퍼파라미터 튜닝 (P167)")
    st.caption("Strategy Bundle 기반으로 Optuna TPE를 실행하여 최적 파라미터를 탐색합니다.")

    # Controls — P168: n_trials는 number_input(step=1)으로 변경
    tc1, tc2, tc3 = st.columns([1, 1, 1])
    with tc1:
        tune_mode = st.radio("Mode", ["quick (6M)", "full (3Y)"], horizontal=True, key="tune_mode")
    with tc2:
        tune_trials = st.number_input("Trials 수", min_value=5, max_value=500, value=30, step=1, key="tune_trials")
    with tc3:
        tune_seed = st.number_input("Seed (재현성)", value=42, step=1, key="tune_seed")

    tune_mode_arg = "quick" if "quick" in tune_mode else "full"

    run_tune_btn = st.button("▶️ Run Tune", key="run_tune_btn", type="primary")

    if run_tune_btn:
        with st.spinner(f"튜닝 실행 중 (mode={tune_mode_arg}, trials={tune_trials})... 수 분 소요될 수 있습니다."):
            try:
                from app.run_tune import run_cli_tune
                success = run_cli_tune(mode=tune_mode_arg, n_trials=tune_trials, seed=int(tune_seed))
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
            mc1.caption(f"기간: {tune_meta.get('start_date', '?')} ~ {tune_meta.get('end_date', '?')}")
            mc2.caption(f"Trials: {tune_meta.get('completed_trials', 0)}/{tune_meta.get('n_trials', 0)} (pruned: {tune_meta.get('pruned_trials', 0)})")
            mc3.caption(f"Runtime: {tune_meta.get('runtime_sec', 0):.1f}s")
            mc4.caption(f"Trades: {tune_data.get('best_total_trades', 0)}")

            # ─── P168: Best Params 적용 + Apply+Backtest ────────────────
            st.divider()
            st.subheader("⚡ Best Params 적용")

            abc1, abc2 = st.columns(2)
            apply_btn = abc1.button("✅ Best Params → Current Parameters 적용 (로컬 저장)", key="apply_best_params")
            apply_bt_btn = abc2.button("🚀 적용 + Backtest Full(3Y) 실행", key="apply_and_backtest")

            if apply_btn or apply_bt_btn:
                # (1) Apply best_params to Current Parameters
                try:
                    _p_data = load_json(LATEST_PATH)
                    if _p_data:
                        _p = _p_data.get("params", {})
                        _p.setdefault("lookbacks", {})["momentum_period"] = bp.get("momentum_period")
                        _p.setdefault("decision_params", {})["exit_threshold"] = bp.get("stop_loss")
                        _p.setdefault("position_limits", {})["max_positions"] = bp.get("max_positions")
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
                                st.success("✅ 백테스트 완료! (🧪 백테스트 탭에서도 확인 가능)")
                                # Show inline summary
                                _bt_data = load_json(BASE_DIR / "reports" / "backtest" / "latest" / "backtest_result.json")
                                if _bt_data:
                                    _bs = _bt_data.get("summary", {})
                                    _bm = _bt_data.get("meta", {})
                                    rc1, rc2, rc3, rc4 = st.columns(4)
                                    rc1.metric("CAGR", f"{_bs.get('cagr', 0):.2f}%")
                                    rc2.metric("MDD", f"{_bs.get('mdd', 0):.2f}%")
                                    rc3.metric("Sharpe", f"{_bs.get('sharpe', 0):.4f}")
                                    rc4.metric("Trades", _bm.get('total_trades', 0))
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
                    rows.append({
                        "#": t.get("trial", ""),
                        "Score": t.get("score", 0),
                        "Sharpe": t.get("sharpe", 0),
                        "MDD %": t.get("mdd_pct", 0),
                        "CAGR": t.get("cagr", 0),
                        "Trades": t.get("total_trades", 0),
                        "모멘텀 기간": t.get("params", {}).get("momentum_period", ""),
                        "손절 임계값": t.get("params", {}).get("stop_loss", ""),
                        "최대 종목수": t.get("params", {}).get("max_positions", ""),
                    })
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

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
