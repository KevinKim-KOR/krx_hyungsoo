"""포트폴리오 편집기 (P136.5) 렌더러."""

import json
import time
from datetime import datetime, timezone, timedelta

import pandas as pd
import streamlit as st

from pc_cockpit.services.config import KST, PORTFOLIO_PATH
from pc_cockpit.services.json_io import load_portfolio, save_json
from app.utils.portfolio_normalize import normalize_portfolio


def render_port_edit(params_data, portfolio_data, guardrails_data):
    st.subheader("💼 Portfolio Editor (SSOT)")
    st.warning(
        "⚠️ Editing this directly modifies 'state/portfolio/latest/portfolio_latest.json'. Use with caution. Changes must be synced to OCI manually or via bundle."
    )

    if not portfolio_data:
        st.error("Portfolio data not found.")
        if st.button("Initialize Empty Portfolio"):
            KST_local = timezone(timedelta(hours=9))
            portfolio_data = {
                "updated_at": datetime.now(KST_local).isoformat(),
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
