"""워크플로우 허브 (P170-UI) 렌더러."""

import time

import requests
import streamlit as st

from pc_cockpit.services.config import (
    BASE_DIR,
    LIVE_APPROVAL_LATEST_PATH,
    _ssot_require,
)
from pc_cockpit.services.json_io import load_json
from pc_cockpit.services.live_approval import (
    check_live_approval,
    handle_approve_live,
    handle_revoke_live,
)
from pc_cockpit.services.backend import get_oci_ops_token
from pc_cockpit.views.tune_card import render_tune_results_card
from pc_cockpit.views.parameter_editor import render_ssot_parameter_form


def _update_ssot_universe_mode(mode: str):
    """SSOT에 universe_mode를 저장한다."""
    import json

    path = BASE_DIR / "state" / "params" / "latest" / "strategy_params_latest.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("universe_mode") != mode:
        data["universe_mode"] = mode
        path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )


def _apply_scanner_snapshot_to_ssot():
    """최신 scanner snapshot의 selected_tickers를 SSOT에 반영."""
    import json

    snap_path = BASE_DIR / "reports" / "tuning" / "universe_snapshot_latest.json"
    ssot_path = BASE_DIR / "state" / "params" / "latest" / "strategy_params_latest.json"

    if not snap_path.exists():
        st.error("스냅샷 파일이 없습니다. 먼저 스캐너를 실행하세요.")
        return False

    snap = json.loads(snap_path.read_text(encoding="utf-8"))
    sel_tickers = snap.get("selected_tickers", [])
    if not sel_tickers:
        st.error("선택된 종목이 없습니다.")
        return False

    ssot = json.loads(ssot_path.read_text(encoding="utf-8"))
    ssot["universe_mode"] = "dynamic_etf_market"
    ssot["universe_tickers"] = sel_tickers
    ssot["universe_snapshot_id"] = snap.get("snapshot_id")
    ssot["universe_snapshot_sha256"] = snap.get("snapshot_sha256")

    ssot_path.write_text(
        json.dumps(ssot, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return True


def _render_dynamic_scanner_section():
    """Dynamic Scanner UI 섹션 (Step5D)."""
    import json

    snap_path = BASE_DIR / "reports" / "tuning" / "universe_snapshot_latest.json"

    with st.expander("Dynamic Scanner", expanded=False):
        # 현재 스냅샷 상태 표시
        if snap_path.exists():
            snap = json.loads(snap_path.read_text(encoding="utf-8"))
            c1, c2, c3 = st.columns(3)
            c1.metric("selected", snap.get("selected_count", 0))
            c2.metric("eligible", snap.get("scoring_eligible", 0))
            c3.metric("pool", snap.get("candidate_pool_size", 0))

            sha_short = (snap.get("snapshot_sha256") or "")[:12]
            sm = snap.get("scanner_mode", "?")
            ps = snap.get("previous_snapshot_exists", "?")
            ss = snap.get("selection_status", "?")
            st.caption(
                f"mode: {sm}"
                f" | snapshot: {snap.get('snapshot_id', '?')}"
                f" | sha: {sha_short}..."
            )
            st.caption(
                f"churn: {snap.get('churn_check_status', '?')}"
                f" | prev_snap: {ps}"
                f" | overlap: {snap.get('min_overlap_ratio', '?')}"
                f" | max_new: {snap.get('max_new_entries_per_refresh', '?')}"
                f" | status: {ss}"
            )
        else:
            st.info("아직 스캐너를 실행하지 않았습니다.")

        # 버튼 2개
        btn_col1, btn_col2 = st.columns(2)
        with btn_col1:
            if st.button(
                "Dynamic Scanner 실행",
                key="run_dynamic_scanner",
                use_container_width=True,
            ):
                with st.spinner("스캐너 실행 중..."):
                    try:
                        from app.scanner.run_scanner import run_scanner

                        result = run_scanner()
                        if result.get("result") == "OK":
                            st.success(
                                f"스캐너 완료: {result.get('selected_count', 0)}종목 선택"
                            )
                        else:
                            st.warning(f"스캐너: {result.get('result')}")
                        import time

                        time.sleep(1.0)
                        st.rerun()
                    except Exception as e:
                        st.error(f"스캐너 실행 실패: {e}")

        with btn_col2:
            if st.button(
                "스캐너 결과 SSOT 적용",
                key="apply_scanner_to_ssot",
                use_container_width=True,
            ):
                if _apply_scanner_snapshot_to_ssot():
                    st.success("SSOT에 dynamic universe 적용 완료")
                    import time

                    time.sleep(1.0)
                    st.rerun()


def init_workflow_session_state():
    """워크플로우 탭에서 사용하는 session state 초기화."""
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

    # P205-STEP4: 유니버스 모드 선택
    universe_mode = st.radio(
        "유니버스 모드",
        ["fixed_current", "expanded_candidates", "dynamic_etf_market"],
        index=0,
        key="universe_mode_radio",
        horizontal=True,
    )
    if universe_mode == "expanded_candidates":
        from app.tuning.universe_config import get_universe_list

        exp_list = get_universe_list("expanded_candidates")
        st.caption(f"확장 후보군: {len(exp_list)}종목")
    elif universe_mode == "dynamic_etf_market":
        _render_dynamic_scanner_section()

    colA, colB = st.columns(2)

    with colA:
        st.markdown("**🧪 Full 백테스트 실행 (P165)**")
        st.caption("현재 SSOT 파라미터 기준으로 전체 기간 백테스트를 실행합니다.")
        st.markdown(
            "- **결과 리포트**: 2번 섹션에서 확인 가능\n- **소요 시간**: 약 1~3분"
        )
        if st.button("▶️ Run Full Backtest", use_container_width=True):
            # SSOT에 universe_mode 반영
            _update_ssot_universe_mode(universe_mode)
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
            # SSOT에 universe_mode 반영
            _update_ssot_universe_mode(universe_mode)
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
                    b_um = bt_meta.get("universe_mode", "?")
                    b_us = bt_meta.get("universe_size", "?")
                    st.caption(
                        f"기간: {bt_meta.get('start_date', '?')}"
                        f" → {bt_meta.get('end_date', '?')}"
                        f" | 모드: {bt_meta.get('mode', '?')}"
                        f" | universe: {b_um}({b_us})"
                        f" | asof: {bt_meta.get('asof', '?')}"
                    )
                    # Step5E2: dynamic 진단
                    if bt_meta.get("dynamic_execution"):
                        _rp = bt_meta.get("total_rebalance_points", 0)
                        _ep = bt_meta.get("total_entry_pass_count", 0)
                        _oc = bt_meta.get("total_orders_created", 0)
                        _bf = bt_meta.get("total_buy_filled", 0)
                        st.caption(
                            f"Dynamic 실행: 예"
                            f" | 리밸런스: {_rp}"
                            f" | 진입통과: {_ep}"
                            f" | 주문: {_oc}"
                            f" | 매수체결: {_bf}"
                        )
                        if bt_meta.get("zero_trade_diagnostic"):
                            st.caption(
                                f"원인: {bt_meta.get('zero_trade_root_cause', '?')}"
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
            with st.spinner("Pushing to OCI..."):
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
