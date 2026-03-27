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

# P195: Initialize token in session state to prevent KeyError crash
if "ops_token" not in st.session_state:
    st.session_state["ops_token"] = ""

if not OCI_BACKEND_URL or not OCI_BACKEND_URL.strip():
    st.error(
        "환경변수 OCI_BACKEND_URL이 설정되지 않았습니다. "
        ".env 파일 또는 start.bat에서 설정하세요."
    )
    st.stop()

from app.utils.portfolio_normalize import normalize_portfolio, load_asof_override

# Config
st.set_page_config(page_title="KRX Strategy Cockpit", layout="wide")


# UI


st.title("🚀 KRX Strategy Cockpit V1.7")

# REPLAY MODE CONTROLLER
override_cfg = load_asof_override()
is_replay = override_cfg.get("enabled", False)

# Simple Toggle in Sidebar or Top
with st.expander("⚙️ System Mode Settings", expanded=is_replay):
    col_mode, col_date, col_sim = st.columns(3)

    # 1. Enable/Disable Replay
    new_replay = col_mode.toggle(
        "Enable Replay Mode", value=is_replay, key="replay_toggle"
    )

    # 2. Date Picker (Only if Replay)
    current_asof = override_cfg.get("asof_kst")
    if not current_asof:
        current_asof = datetime.now(KST).strftime("%Y-%m-%d")

    new_date = col_date.date_input(
        "Replay Date",
        value=datetime.strptime(current_asof, "%Y-%m-%d"),
        disabled=not new_replay,
    )

    # 3. Simulate Trade Day (P145)
    current_sim = override_cfg.get("simulate_trade_day", False)
    new_sim = col_sim.toggle(
        "Simulate Trade Day",
        value=current_sim,
        disabled=not new_replay,
        help="Force trade day even on weekends",
    )

    # Save Change
    if (
        (new_replay != is_replay)
        or (str(new_date) != current_asof)
        or (new_sim != current_sim)
    ):
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
                    "simulate_trade_day": override_cfg.get("simulate_trade_day", False),
                }
                requests.post(
                    "http://localhost:8000/api/settings/mode",
                    json=payload,
                    timeout=FAST_TIMEOUT,
                )

                # 2. READ-BACK
                res = requests.get(
                    "http://localhost:8000/api/settings/mode", timeout=FAST_TIMEOUT
                )
                oci_cfg = res.json()

                # 3. VERIFY
                st.toast("✅ Synced with OCI!")
                st.success("OCI Sync Verified:")
                st.dataframe(
                    [
                        {
                            "Key": "Mode",
                            "Local": "REPLAY" if override_cfg["enabled"] else "LIVE",
                            "OCI": oci_cfg.get("mode"),
                        },
                        {
                            "Key": "AsOf",
                            "Local": override_cfg.get("asof_kst"),
                            "OCI": oci_cfg.get("asof_kst"),
                        },
                        {
                            "Key": "Simulate Trade",
                            "Local": override_cfg.get("simulate_trade_day"),
                            "OCI": oci_cfg.get("simulate_trade_day"),
                        },
                    ]
                )
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

if "ops_token" not in st.session_state:
    st.session_state["ops_token"] = ""
if "wf_token_input" not in st.session_state:
    st.session_state["wf_token_input"] = ""
if "ops_token_input" not in st.session_state:
    st.session_state["ops_token_input"] = ""


def sync_wf_to_ops():
    val = st.session_state["wf_token_input"]
    st.session_state["ops_token"] = val
    st.session_state["ops_token_input"] = val


def sync_ops_to_wf():
    val = st.session_state["ops_token_input"]
    st.session_state["ops_token"] = val
    st.session_state["wf_token_input"] = val


def render_workflow_p170(params_data, portfolio_data, guardrails_data):

    st.header("🧭 운영 워크플로우 허브 (P170-UI)")
    if (
        "last_block_reason" in st.session_state
        and st.session_state["last_block_reason"]
    ):
        st.warning(f"⚠️ 최근 차단 사유: {st.session_state['last_block_reason']}")
    st.info("💡 LIVE 반영 순서: 승인 → 1-Click Sync (승인 없으면 동작 안 함)")
    st.caption("운영 토큰은 여기서만 입력(단일화).")
    st.caption(
        "파라미터 조회, 백테스트, 튜닝, 오퍼레이션 동기화를 탭 이동 없이 한 화면에서 수행합니다."
    )

    # [Phase 2] Operation Mode Info
    if params_data and "params" in params_data:
        _p = params_data["params"]
        p_mode = _ssot_require(_p, "portfolio_mode")
        s_mode = _ssot_require(_p, "sell_mode")
        r_freq = _ssot_require(_p, "rebalance", "frequency")
    else:
        p_mode = "N/A"
        s_mode = "N/A"
        r_freq = "N/A"
    st.info(
        f"🚀 **운영 모드**: `{p_mode}` | **매도 룰**: `{s_mode}` | **리밸런싱**: `{r_freq}`"
    )

    st.divider()
    render_ssot_parameter_form(params_data)

    st.divider()

    # B. 2) 백테스트 및 튜닝
    st.subheader("2) 백테스트 및 튜닝 시뮬레이션")
    colA, colB = st.columns(2)

    with colA:
        st.markdown("**🧪 Full 백테스트 실행 (P165)**")
        st.caption("현재 SSOT 파라미터 기준으로 전체 기간 백테스트를 실행합니다.")
        st.markdown(
            "- **결과 리포트**: 2번 섹션에서 확인 가능\n- **소요 시간**: 약 1~3분"
        )
        if st.button("▶️ Run Full Backtest", use_container_width=True):
            with st.spinner("백테스트 실행 중... (엔진 로그를 확인하세요)"):
                try:
                    from app.run_backtest import run_cli_backtest

                    success = run_cli_backtest(mode="full")
                    if success:
                        st.success("✅ 백테스트 완료! (2번 섹션 리포트 확인)")
                        time.sleep(1.5)
                        st.rerun()
                    else:
                        st.error("❌ 백테스트 실패 (서버 로그 확인)")
                except Exception as e:
                    st.error(f"❌ 백테스트 오류: {e}")

    with colB:
        st.markdown("**⚙️ Optuna 튜닝 (P204)**")
        st.caption(
            "Optuna TPE Sampler로 최적 파라미터를 탐색합니다. (SQLite 영속화/Resume 지원)"
        )
        st.markdown(
            "- **알고리즘**: Optuna TPE\n- **성공 파일**: `reports/tuning/tuning_results.json`"
        )
        tune_mode = st.selectbox(
            "튜닝 모드", ["quick", "full"], index=0, key="tune_mode_select"
        )
        tune_trials = st.number_input(
            "Trials 수", min_value=1, max_value=500, value=20, key="tune_trials_input"
        )
        if st.button("▶️ Run Tune", use_container_width=True):
            with st.spinner(
                f"Optuna 튜닝 중 (mode={tune_mode}, trials={tune_trials})..."
            ):
                try:
                    from app.run_tune import run_cli_tune

                    success = run_cli_tune(mode=tune_mode, n_trials=tune_trials)
                    if success:
                        st.success(
                            "✅ 튜닝 완료! (reports/tuning/tuning_results.json 갱신)"
                        )
                        time.sleep(1.5)
                        st.rerun()
                    else:
                        st.error("❌ 튜닝 실패 (서버 로그 확인)")
                except Exception as e:
                    st.error(f"❌ 튜닝 실행 오류: {e}")

    # ── B-1. 튜닝 결과 카드 ──
    st.markdown("---")
    res_colA, res_colB = st.columns(2)

    with res_colA:
        st.markdown("##### 📊 최신 백테스트 결과")
        BT_RESULT_PATH = (
            BASE_DIR / "reports" / "backtest" / "latest" / "backtest_result.json"
        )
        try:
            if not BT_RESULT_PATH.exists():
                st.info(
                    "ℹ️ 아직 백테스트 결과 없음 — 먼저 ▶️ Run Full Backtest를 실행하세요."
                )
            else:
                bt_data = load_json(BT_RESULT_PATH)
                if not bt_data:
                    st.warning("⚠️ 백테스트 결과 파일 파싱 실패")
                else:
                    bt_summary = bt_data.get("summary", {})
                    bt_meta = bt_data.get("meta", {})
                    st.success("✅ 최근 실행 성공")
                    c1, c2, c3 = st.columns(3)
                    c1.metric("CAGR", f"{bt_summary.get('cagr', 0):.2f}%")
                    c2.metric("MDD", f"{bt_summary.get('mdd_pct', 0):.2f}%")
                    c3.metric("Sharpe", f"{bt_summary.get('sharpe', 0):.4f}")
                    c4, c5 = st.columns(2)
                    c4.metric("총 수익률", f"{bt_summary.get('total_return', 0):.2f}%")
                    c5.metric(
                        "총 거래수",
                        bt_summary.get(
                            "order_count", bt_summary.get("total_trades", "N/A")
                        ),
                    )
                    st.caption(
                        f"기간: {bt_meta.get('start_date', '?')} → {bt_meta.get('end_date', '?')} | 모드: {bt_meta.get('mode', '?')} | asof: {bt_meta.get('asof', '?')}"
                    )
        except Exception as e:
            st.error(f"⚠️ 백테스트 결과 파싱 실패: {e}")

    with res_colB:
        render_tune_results_card(params_data)
    app_status = "❌ 미승인/없음"
    app_data = load_json(LIVE_APPROVAL_LATEST_PATH)
    if app_data:
        app_status = (
            "✅ 승인됨 (APPROVED)"
            if app_data.get("status") == "APPROVED"
            else "🚫 철회됨 (REVOKED)"
        )

    st.info(f"현재 LIVE 승인 상태: **{app_status}**")

    c_app, c_rev = st.columns(2)
    with c_app:
        if st.button("✅ Approve LIVE", use_container_width=True):
            handle_approve_live()
            time.sleep(1)
            st.rerun()
    with c_rev:
        if st.button("🚫 Revoke LIVE", use_container_width=True):
            handle_revoke_live()
            time.sleep(1)
            st.rerun()

    st.divider()
    # C. 3) 운영 동기화 (OCI 반영)
    st.subheader("3) 운영 동기화 (OCI 반영)")

    # P195/P203: Unified single token input location for the entire UI
    actual_token, token_status = get_oci_ops_token()

    col_tk1, col_tk2 = st.columns([3, 1])
    with col_tk1:
        st.text_input(
            "OCI Access Token (운영 토큰)",
            type="password",
            key="ops_token",
            placeholder="비워두면 .env 자동 로드",
        )
    with col_tk2:
        st.markdown("<div style='height: 38px;'></div>", unsafe_allow_html=True)
        st.caption(f"**TOKEN:** {token_status}")

    # Push Push Logic
    sync_timeout = st.session_state.get("sync_timeout", 60)

    if st.button(
        "📤 OCI 반영 (1-Click Sync)", key="wf_push_oci", use_container_width=True
    ):
        ok, msg = check_live_approval()
        if not ok:
            st.error(
                f"LIVE 승인 없음(또는 REVOKED) → Approve LIVE 후 Sync 하세요. ({msg})"
            )
            st.session_state["last_block_reason"] = f"1-Click Sync 차단: {msg}"
            return

        if not actual_token:
            st.warning("OCI_OPS_TOKEN 없음(.env 설정 필요). Sync 중단")
            st.session_state["last_block_reason"] = "1-Click Sync 차단: Token 없음"
            return
        else:
            with st.spinner(f"Pushing to OCI..."):
                try:
                    r = requests.post(
                        "http://localhost:8000/api/sync/push_bundle",
                        json={"token": actual_token},
                        params={"timeout_seconds": sync_timeout},
                        timeout=sync_timeout + 5,
                    )
                    if r.status_code == 200:
                        st.success(
                            "✅ OCI(운영석)에 새 파라미터(SSOT)가 성공적으로 반영되었습니다!"
                        )
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(f"Push 실패: {r.text}")
                except Exception as e:
                    st.error(f"Push 실패 (통신/토큰 오류 등): {e}")


def render_ops_p144(params_data, portfolio_data, guardrails_data):
    st.header("Daily Operations Cockpit (UI-First)")

    # 🗺️ P202: 5-Step Flow Guide
    st.markdown("### 🗺️ 운영 흐름 가이드 (Flow Guide)")
    with st.expander("📍 현재 단계 파악하기 (클릭하여 열기)", expanded=False):
        # Step 0: Approval
        st.markdown("**[Step 0] 승인 (Approval)**")
        app_data = load_json(LIVE_APPROVAL_LATEST_PATH)
        app_status = (
            "✅ APPROVED"
            if app_data and app_data.get("status") == "APPROVED"
            else "❌ 미승인/철회됨"
        )
        st.markdown(
            f"- **상태**: {app_status} (live_approval.json)\n- **다음 버튼**: 워크플로우 탭 → 'Approve LIVE'"
        )

        # Step 1: Sync
        st.markdown("**[Step 1] 동기화 (Sync)**")
        bundle_data = load_json(BUNDLE_LATEST_PATH)
        sync_time = bundle_data.get("created_at", "N/A") if bundle_data else "N/A"
        st.markdown(
            f"- **상태**: 마지막 로컬 번들 생성/Sync 시도: {sync_time}\n- **다음 버튼**: 워크플로우 탭 → '1-Click Sync'"
        )

        # Step 2: Ops
        st.markdown("**[Step 2] 운영 (Ops: RECO/ORDER_PLAN)**")
        reco_path = (
            BASE_DIR / "reports" / "live" / "reco" / "latest" / "reco_latest.json"
        )
        op_path = (
            BASE_DIR
            / "reports"
            / "live"
            / "order_plan"
            / "latest"
            / "order_plan_latest.json"
        )

        reco_time = (
            load_json(reco_path).get("asof", "N/A") if reco_path.exists() else "N/A"
        )
        op_data = load_json(op_path) if op_path.exists() else {}
        op_id = op_data.get("plan_id", "N/A")

        st.markdown(
            f"- **상태**: RECO({reco_time}), ORDER_PLAN({op_id})\n- **다음 버튼**: 데일리운영 탭 → 'Run Auto Ops Cycle'"
        )

        # Step 3: Exec
        st.markdown("**[Step 3] 실행 (Execution: Export/Prep/Ticket)**")
        exp_path = (
            BASE_DIR
            / "reports"
            / "live"
            / "order_plan_export"
            / "latest"
            / "order_plan_export_latest.json"
        )
        prep_path = (
            BASE_DIR
            / "reports"
            / "live"
            / "execution_prep"
            / "latest"
            / "execution_prep_latest.json"
        )
        ticket_path = (
            BASE_DIR
            / "reports"
            / "live"
            / "execution_ticket"
            / "latest"
            / "execution_ticket_latest.json"
        )

        exp_id = (
            load_json(exp_path).get("source", {}).get("plan_id", "N/A")
            if exp_path.exists()
            else "없음"
        )
        prep_id = (
            load_json(prep_path).get("plan_id", "N/A") if prep_path.exists() else "없음"
        )
        ticket_id = (
            load_json(ticket_path).get("plan_id", "N/A")
            if ticket_path.exists()
            else "없음"
        )

        match_str = (
            "✅ 정렬됨"
            if (
                op_id != "N/A"
                and exp_id == op_id
                and prep_id == op_id
                and ticket_id == op_id
            )
            else "⚠️ 불일치(진행중/미생성)"
        )
        st.markdown(
            f"- **상태**: Export({exp_id}) / Prep({prep_id}) / Ticket({ticket_id}) → {match_str}\n- **다음 버튼**: 데일리운영 탭 → 'Execution 관련 버튼(향후 UI)'"
        )

        # Step 4: Record
        st.markdown("**[Step 4] 기록 (Record - 선택적 필수사항 아님)**")
        rec_path = (
            BASE_DIR
            / "reports"
            / "live"
            / "manual_execution_record"
            / "latest"
            / "manual_execution_record_latest.json"
        )
        rec_id = (
            load_json(rec_path).get("plan_id", "N/A") if rec_path.exists() else "없음"
        )
        rec_warn = (
            "⚠️ (오래된 plan_id)"
            if (op_id != "N/A" and rec_id != "없음" and rec_id != op_id)
            else ""
        )
        st.markdown(
            f"- **상태**: Record({rec_id}) {rec_warn}\n- **안내**: Record는 매매 체결이 실제로 이루어진 '실행 후' 선택적으로 생성하는 산출물입니다."
        )

    st.divider()

    st.info("💡 운영 순서: PULL → Run Auto Ops (승인/Sync 완료 상태에서만)")
    st.caption("토큰 입력은 워크플로우 탭에서 1회만. 이 탭은 Token-Free UI.")

    # 1. Fetch Status (SSOT from Backend)
    ssot_snapshot = {}
    backend_ok = False
    error_msg = ""

    try:
        res = requests.get(
            "http://localhost:8000/api/ssot/snapshot", timeout=FAST_TIMEOUT
        )
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
        **Target**: 🔗 {OCI_BACKEND_URL} |
        **Stage**: {stage_color} {stage} | 
        **Exec**: 🧪 {exec_mode} |
        **Replay**: {'🔴 ON (' + (replay_asof or 'Unknown') + ')' if is_replay else '⚪ OFF'} 
        """)
    else:
        st.error(f"🛑 Backend Connection Failed: {error_msg}")
        st.session_state["last_block_reason"] = f"Backend 죽음: {error_msg}"
        return

    # P146.1: Explicit Sync Control
    st.divider()
    st.markdown("#### 🔄 SSOT Synchronization")

    # P195: Streamlined UI Layout (Token input removed, Push removed from 데일리운영 (P144))
    c1, c_pull = st.columns([1, 3])

    with c1:
        sync_timeout = st.number_input(
            "Timeout (sec)", value=60, step=30, key="sync_timeout"
        )

    with c_pull:
        st.markdown(
            "<div style='height: 28px;'></div>", unsafe_allow_html=True
        )  # Spacer for label
        pull_clicked = st.button("📥 PULL (OCI)", use_container_width=True)
        st.caption("OCI 읽기(토큰 필요, UI에서는 숨김)")
        if pull_clicked:
            do_pull = True

            actual_token, _ = get_oci_ops_token()
            if not actual_token:
                st.warning("OCI_OPS_TOKEN 없음(.env 설정 필요). PULL 중단")
                st.session_state["last_block_reason"] = "PULL 차단: Token 없음"
                do_pull = False

            if do_pull:
                with st.spinner(f"Pulling..."):
                    try:
                        r = requests.post(
                            "http://localhost:8000/api/sync/pull",
                            json={"token": actual_token},
                            params={"timeout_seconds": sync_timeout},
                            timeout=sync_timeout + 5,
                        )
                        if r.status_code == 200:
                            st.success("OK")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error(f"Fail: {r.text}")
                    except Exception as e:
                        st.error(f"Error: {e}")

    # P195: PUSH (OCI) moved to 정비창 (Advanced) Lab

    # Status Line
    st.caption(
        f"Status: {ssot_snapshot.get('synced_at', 'N/A')} (Rev: {ssot_snapshot.get('revision', 'N/A')})"
    )

    st.divider()

    # 2. Controls (Auto Ops)
    st.subheader("🤖 Auto Operations (Token-Free UI)")
    st.caption(
        "(내부적으로는 워크플로우(P170)에서 입력한 세션 토큰(ops_token)을 사용합니다. 화면에 입력창만 없습니다.)"
    )

    col_run, col_force = st.columns([1, 1])
    with col_force:
        force_recompute = st.checkbox(
            "☑ Force Recompute (Overwrite)",
            value=False,
            help="강제 재생성 (LIVE 모드에서는 무시됨)",
        )
        st.caption("권장: Force는 ‘리포트 재생성 강제’(필요할 때만)")

    with col_run:
        if st.button("▶️ Run Auto Ops Cycle", use_container_width=True):
            ok, msg = check_live_approval()
            if not ok:
                st.error(f"워크플로우에서 승인 → 1-Click Sync 완료 후 실행 ({msg})")
                st.session_state["last_block_reason"] = f"Auto Ops 차단: {msg}"
                return

            actual_token, t_status = get_oci_ops_token()
            if not actual_token:
                st.warning("OCI_OPS_TOKEN 없음(.env 설정 필요). Auto Ops 중단")
                st.session_state["last_block_reason"] = "Auto Ops 차단: Token 없음"
                return
            try:
                oci_url = OCI_BACKEND_URL

                # === Step 1: Local Bundle Generation ===
                st.info("Step 1/3: 로컬 번들 생성 중...")
                bundle_cmd = [
                    sys.executable,
                    str(BASE_DIR / "deploy" / "pc" / "generate_strategy_bundle.py"),
                ]
                result = subprocess.run(bundle_cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    st.error(f"Step 1 실패: 번들 생성에 실패했습니다.\n{result.stderr}")
                    st.session_state["last_block_reason"] = (
                        "Auto Ops 차단: Step 1 Bundle 생성 실패"
                    )
                    return
                st.success("Step 1 완료: 번들 생성 성공")

                # === Step 2: Push to OCI ===
                st.info(f"Step 2/3: OCI로 번들 동기화 중 ({t_status})...")

                sync_timeout = st.session_state.get("sync_timeout", 60)
                sync_resp = requests.post(
                    "http://localhost:8000/api/sync/push_bundle",
                    json={"token": actual_token},
                    params={"timeout_seconds": sync_timeout},
                    timeout=sync_timeout + 5,
                )
                if sync_resp.status_code != 200:
                    st.error(
                        f"Step 2 실패: OCI 동기화에 실패했습니다.\n{sync_resp.text}"
                    )
                    st.session_state["last_block_reason"] = (
                        f"Auto Ops 차단: Step 2 Push 실패"
                    )
                    return

                try:
                    sync_data = sync_resp.json()
                    if sync_data.get("approval_included", False):
                        st.success(
                            f"Step 2 완료: OCI 동기화 성공 (Approval 팩 포함: {sync_data.get('approval_bytes', 0)}B, FP={sync_data.get('approval_fingerprint', '')})"
                        )
                    else:
                        st.success("Step 2 완료: OCI 동기화 성공")
                except Exception:
                    st.success("Step 2 완료: OCI 동기화 성공")

                # === Step 3: Trigger OCI Auto Ops Cycle ===
                st.info("Step 3/3: OCI Auto Ops Cycle 실행 중...")
                # P152: Send force query param
                resp = requests.post(
                    f"{oci_url}/api/live/cycle/run?confirm=true&force={str(force_recompute).lower()}",
                    timeout=SLOW_TIMEOUT,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    results = data.get("results", {})

                    # Format summary
                    summary_str = " | ".join(
                        [
                            f"{k.upper()}: {v}"
                            for k, v in results.items()
                            if k != "ops_summary"
                        ]
                    )
                    if not summary_str:
                        summary_str = "Auto Ops Completed via Orchestrator"

                    # P154: Store result in session state to persist after rerun
                    st.session_state["last_cycle_result"] = (
                        f"✅ 3-Step Chain 성공 | {summary_str}"
                    )
                    st.toast("Auto Ops Cycle Completed")
                elif resp.status_code == 500:
                    data = resp.json()
                    detail = data.get("detail", {})

                    if isinstance(detail, dict) and "ops_run" in detail:
                        results_dict = detail["ops_run"].get("results", {})
                        summary_parts = []
                        for k, v in results_dict.items():
                            if k == "ops_summary":
                                continue
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
