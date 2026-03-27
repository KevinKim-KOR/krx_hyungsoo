"""KRX Strategy Cockpit — 부트스트랩 + 탭 라우팅."""

import streamlit as st

from pc_cockpit.services.config import (
    OCI_BACKEND_URL,
    LATEST_PATH,
    PORTFOLIO_PATH,
    GUARDRAILS_PATH,
)
from pc_cockpit.services.json_io import load_json
from pc_cockpit.views.ops_daily import render_ops_p144
from pc_cockpit.views.workflow import (
    init_workflow_session_state,
    render_workflow_p170,
)
from pc_cockpit.views.replay_controller import render_replay_controller
from pc_cockpit.views.timing import render_timing
from pc_cockpit.views.portfolio_editor import render_port_edit

# ── 초기화 ──
init_workflow_session_state()

if not OCI_BACKEND_URL or not OCI_BACKEND_URL.strip():
    st.error(
        "환경변수 OCI_BACKEND_URL이 설정되지 않았습니다. "
        ".env 파일 또는 start.bat에서 설정하세요."
    )
    st.stop()

# ── 페이지 설정 ──
st.set_page_config(page_title="KRX Strategy Cockpit", layout="wide")
st.title("🚀 KRX Strategy Cockpit V1.7")

# ── Replay 모드 ──
is_replay = render_replay_controller()

# ── 데이터 로딩 ──
params_data = load_json(LATEST_PATH)
portfolio_data = load_json(PORTFOLIO_PATH)
guardrails_data = load_json(GUARDRAILS_PATH) or {}


# ── 정비창 (Advanced) ──
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


# ── 탭 라우팅 ──
top_tab_ops, top_tab_wf, top_tab_adv = st.tabs(
    ["🚀 데일리 운영 (P144)", "🧭 워크플로우 (P170)", "🛠️ 정비창 (Advanced)"]
)

with top_tab_ops:
    render_ops_p144(params_data, portfolio_data, guardrails_data)

with top_tab_wf:
    render_workflow_p170(params_data, portfolio_data, guardrails_data)

with top_tab_adv:
    render_advanced_panel(params_data, portfolio_data, guardrails_data)
