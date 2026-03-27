"""LIVE 승인/철회 관리."""

import hashlib
import os
import socket
import uuid
from datetime import datetime

import streamlit as st

from pc_cockpit.services.config import (
    KST,
    LATEST_PATH,
    LIVE_APPROVAL_LATEST_PATH,
    LIVE_APPROVAL_SNAPSHOT_DIR,
    BUNDLE_LATEST_PATH,
)
from pc_cockpit.services.json_io import load_json, save_json


def check_live_approval():
    approval = load_json(LIVE_APPROVAL_LATEST_PATH)
    if not approval:
        return False, "live_approval.json 없음"
    if approval.get("status") != "APPROVED":
        return False, f"현재 상태: {approval.get('status')}"

    curr_params_sha256 = (
        hashlib.sha256(LATEST_PATH.read_bytes()).hexdigest()
        if LATEST_PATH.exists()
        else ""
    )

    bundle_data = load_json(BUNDLE_LATEST_PATH)
    if not bundle_data:
        return False, "strategy_bundle_latest.json 누락"
    curr_bundle_payload_sha256 = bundle_data.get("integrity", {}).get(
        "payload_sha256", ""
    )

    inputs = approval.get("inputs", {})
    if inputs.get("params_sha256") != curr_params_sha256:
        return False, "파라미터 해시 불일치 (파라미터가 변경됨)"
    if inputs.get("bundle_payload_sha256") != curr_bundle_payload_sha256:
        return False, "번들 페이로드 해시 불일치"

    return True, "APPROVED"


def handle_approve_live():
    curr_params_sha256 = (
        hashlib.sha256(LATEST_PATH.read_bytes()).hexdigest()
        if LATEST_PATH.exists()
        else ""
    )
    bundle_data = load_json(BUNDLE_LATEST_PATH)
    bundle_id = bundle_data.get("bundle_id", "") if bundle_data else ""
    payload_sha256 = (
        bundle_data.get("integrity", {}).get("payload_sha256", "")
        if bundle_data
        else ""
    )

    if not curr_params_sha256 or not payload_sha256:
        st.error("파라미터 또는 번들 파일 누락으로 승인 불가.")
        return

    approval_payload = {
        "schema": "LIVE_APPROVAL_V1",
        "approval_id": str(uuid.uuid4()),
        "status": "APPROVED",
        "approved_at": datetime.now(KST).isoformat(),
        "approved_by": os.environ.get(
            "COMPUTERNAME", socket.gethostname() or "UNKNOWN"
        ),
        "intent": "ALLOW_SYNC_AND_RUN",
        "inputs": {
            "params_sha256": curr_params_sha256,
            "bundle_payload_sha256": payload_sha256,
            "bundle_id": bundle_id,
            "mode": "LIVE",
        },
    }

    LIVE_APPROVAL_LATEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    save_json(LIVE_APPROVAL_LATEST_PATH, approval_payload)
    snap_name = f"live_approval_{datetime.now(KST).strftime('%Y%m%d_%H%M%S')}.json"
    save_json(LIVE_APPROVAL_SNAPSHOT_DIR / snap_name, approval_payload)
    st.success("✅ LIVE 승인(APPROVED) 완료! OCI 반영 및 워크플로우 진행이 허용됩니다.")


def handle_revoke_live():
    approval = load_json(LIVE_APPROVAL_LATEST_PATH)
    if not approval:
        st.warning("승인 파일이 없습니다.")
        return

    approval["status"] = "REVOKED"
    approval["approved_at"] = datetime.now(KST).isoformat()
    approval["approved_by"] = os.environ.get(
        "COMPUTERNAME", socket.gethostname() or "UNKNOWN"
    )

    save_json(LIVE_APPROVAL_LATEST_PATH, approval)
    snap_name = f"live_approval_{datetime.now(KST).strftime('%Y%m%d_%H%M%S')}.json"
    save_json(LIVE_APPROVAL_SNAPSHOT_DIR / snap_name, approval)
    st.success("🚫 LIVE 승인 철회(REVOKED) 완료. OCI 반영 및 운영이 즉시 차단됩니다.")
