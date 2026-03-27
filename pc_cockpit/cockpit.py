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

from pc_cockpit.views.replay_controller import render_replay_controller
from pc_cockpit.views.timing import render_timing
from pc_cockpit.views.portfolio_editor import render_port_edit

# Config
st.set_page_config(page_title="KRX Strategy Cockpit", layout="wide")


# UI


st.title("🚀 KRX Strategy Cockpit V1.7")

# REPLAY MODE CONTROLLER
is_replay = render_replay_controller()


params_data = load_json(LATEST_PATH)
portfolio_data = load_json(PORTFOLIO_PATH)
guardrails_data = load_json(GUARDRAILS_PATH) or {}


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
