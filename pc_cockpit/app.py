import streamlit as st
import json
import hashlib
from datetime import datetime
from pathlib import Path

# Config
st.set_page_config(page_title="KRX Strategy Cockpit", layout="wide")
BASE_DIR = Path(__file__).parent.parent
PARAMS_DIR = BASE_DIR / "state" / "strategy_params"
LATEST_PATH = PARAMS_DIR / "latest" / "strategy_params_latest.json"
SNAPSHOT_DIR = PARAMS_DIR / "snapshots"

# Ensure directories exist
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

def load_params():
    if LATEST_PATH.exists():
        return json.loads(LATEST_PATH.read_text(encoding="utf-8"))
    return None

def save_params(data):
    # 1. Save Latest
    json_str = json.dumps(data, indent=2, ensure_ascii=False)
    LATEST_PATH.write_text(json_str, encoding="utf-8")
    
    # 2. Save Snapshot
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    snapshot_path = SNAPSHOT_DIR / f"strategy_params_{timestamp}.json"
    snapshot_path.write_text(json_str, encoding="utf-8")
    return snapshot_path

def compute_fingerprint(data):
    json_str = json.dumps(data, sort_keys=True) # Canonical form for hashing
    # Make sure to handle potential diffs in whitespace for display vs hash
    # Actually, simpler to hash the json string we save.
    return hashlib.sha256(json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]

# UI
st.title("🚀 KRX Strategy Cockpit V1")

params_data = load_params()

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
            
            new_data["params"] = new_params
            
            # Save
            snap_path = save_params(new_data)
            new_fp = compute_fingerprint(new_data)
            
            st.success(f"Saved! New Fingerprint: `{new_fp}`")
            st.info(f"Snapshot created at: `{snap_path}`")
            
            # Rerun to update UI
            # st.experimental_rerun() # might cause loop if not careful, just show success for now.
