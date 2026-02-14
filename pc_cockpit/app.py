
import streamlit as st
import json
import hashlib
from datetime import datetime
from pathlib import Path
import pandas as pd
import altair as alt
import subprocess
import sys

# Add project root to path for util imports
BASE_DIR = Path(__file__).parent.parent
sys.path.append(str(BASE_DIR))

from app.utils.admin_utils import normalize_portfolio, load_asof_override

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
st.title("🚀 KRX Strategy Cockpit V1.7")

# REPLAY MODE CHECK (P143)
override_cfg = load_asof_override()
if override_cfg.get("enabled"):
    st.error(f"🔴 REPLAY MODE ACTIVE (Data Basis: {override_cfg.get('asof_kst')})")
    st.caption("System outputs will be generated based on this snapshot date.")

params_data = load_json(LATEST_PATH)
portfolio_data = load_json(PORTFOLIO_PATH)

# Create Tabs
tab_main, tab_reco, tab_timing, tab_port_edit, tab_review = st.tabs([
    "🔩 Current Parameters", 
    "🔎 Recommendations (P135)", 
    "⏱️ Holdings Timing (P136)",
    "💼 Portfolio Editor (P136.5)",
    "🧐 Param Review (P138)"
])

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

    timing_data = load_json(TIMING_LATEST_PATH)
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
            cash = c2.number_input("Cash (KRW)", value=int(portfolio_data.get("cash", 0)))
            
            # Holdings Editor - Simple Text Area JSON editor style or multi-row?
            # Streamlit data_editor is best for list of dicts.
            
            # Convert holdings to list for editor
            raw_holdings = portfolio_data.get("holdings", {})
            # Handle list vs dict
            if isinstance(raw_holdings, list):
                holdings_list = raw_holdings
            else:
                holdings_list = []
                for t, info in raw_holdings.items():
                    info['ticker'] = t
                    holdings_list.append(info)
            
            # Prepare DF for editor
            df_edit = pd.DataFrame(holdings_list)
            # Ensure columns exist
            required_cols = ["ticker", "quantity", "avg_price"]
            for c in required_cols:
                if c not in df_edit.columns:
                    df_edit[c] = "" if c=="ticker" else 0
            
            st.write("Holdings (Edit below, Add rows for new tickers)")
            edited_df = st.data_editor(df_edit, num_rows="dynamic")
            
            if st.form_submit_button("💾 Save Portfolio"):
                # Reconstruct JSON
                new_holdings = {}
                for idx, row in edited_df.iterrows():
                    t = str(row["ticker"]).strip()
                    if t:
                        new_holdings[t] = {
                            "quantity": int(row.get("quantity", 0)),
                            "avg_price": float(row.get("avg_price", 0)),
                            "weight_pct": 0.0 # Recalculate if needed or ignore
                        }
                
                # Update Data
                portfolio_data["total_value"] = total_val
                portfolio_data["cash"] = cash
                portfolio_data["holdings"] = new_holdings
                portfolio_data["updated_at"] = datetime.utcnow().isoformat()
                
                # P143: Normalize SSOT
                portfolio_data = normalize_portfolio(portfolio_data)
                
                save_json(PORTFOLIO_PATH, portfolio_data)
                st.success("Portfolio Saved!")
                st.success("Portfolio Saved!")

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
