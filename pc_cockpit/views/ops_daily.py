"""데일리 운영 탭 (P144) 렌더러."""

import subprocess
import sys
import time

import pandas as pd
import requests
import streamlit as st

from pc_cockpit.services.config import (
    BASE_DIR,
    FAST_TIMEOUT,
    SLOW_TIMEOUT,
    OCI_BACKEND_URL,
    LIVE_APPROVAL_LATEST_PATH,
    BUNDLE_LATEST_PATH,
)
from pc_cockpit.services.json_io import load_json
from pc_cockpit.services.live_approval import check_live_approval
from pc_cockpit.services.backend import check_backend_health, get_oci_ops_token


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
                with st.spinner("Pulling..."):
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
        st.caption("권장: Force는 '리포트 재생성 강제'(필요할 때만)")

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
                        "Auto Ops 차단: Step 2 Push 실패"
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
