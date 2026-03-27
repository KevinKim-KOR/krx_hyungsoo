"""Replay mode controller (전역 스코프 블록을 함수로 래핑)."""

import json
from datetime import datetime

import requests
import streamlit as st

from pc_cockpit.services.config import KST, FAST_TIMEOUT, ASOF_OVERRIDE_PATH
from app.utils.portfolio_normalize import load_asof_override


def render_replay_controller():
    """Replay 모드 토글 UI를 렌더링하고 is_replay 상태를 반환한다."""
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
                        "simulate_trade_day": override_cfg.get(
                            "simulate_trade_day", False
                        ),
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
                                "Local": (
                                    "REPLAY" if override_cfg["enabled"] else "LIVE"
                                ),
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

    return is_replay
