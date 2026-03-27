"""Backend 연결 및 OCI 토큰 관리."""

import os
import time

import requests
import streamlit as st

from pc_cockpit.services.config import FAST_TIMEOUT


def check_backend_health():
    """Check connectivity and latency to Local Backend."""
    t0 = time.time()
    health = {"status": "UNKNOWN", "latency_ms": -1}
    try:
        r = requests.get(
            "http://localhost:8000/api/ssot/snapshot", timeout=FAST_TIMEOUT
        )
        latency = int((time.time() - t0) * 1000)
        status = "OK" if r.status_code == 200 else f"ERR_{r.status_code}"
        health = {"status": status, "latency_ms": latency}
    except Exception as e:
        health = {"status": "FAIL", "latency_ms": -1, "error": str(e)}
    return health


def get_oci_ops_token():
    """P203: Auto-load OCI_OPS_TOKEN from env, with UI override"""
    env_token = os.environ.get("OCI_OPS_TOKEN", "").strip()
    ui_token = st.session_state.get("ops_token", "").strip()

    if ui_token:
        return ui_token, "OVERRIDE(UI)"
    elif env_token:
        return env_token, "AUTO(.env)"
    else:
        return "", "MISSING"
