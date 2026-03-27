"""pc_cockpit 공용 상수 및 순수 유틸리티."""

import hashlib
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

from dotenv import load_dotenv

KST = timezone(timedelta(hours=9))

# Timeouts
FAST_TIMEOUT = 10  # Status checks
SLOW_TIMEOUT = 150  # Sync/Push/Pull

# Project root (pc_cockpit/services/config.py -> 3단 상위)
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(BASE_DIR))

load_dotenv(BASE_DIR / ".env")

OCI_BACKEND_URL = os.environ.get("OCI_BACKEND_URL")

# ── Path 상수 ──
PARAMS_DIR = BASE_DIR / "state" / "params"
LATEST_PATH = PARAMS_DIR / "latest" / "strategy_params_latest.json"
SNAPSHOT_DIR = PARAMS_DIR / "snapshots"

PORTFOLIO_PATH = BASE_DIR / "state" / "portfolio" / "latest" / "portfolio_latest.json"

GUARDRAILS_PATH = (
    BASE_DIR / "state" / "guardrails" / "latest" / "guardrails_latest.json"
)

SEARCH_DIR = BASE_DIR / "reports" / "pc" / "param_search" / "latest"
SEARCH_LATEST_PATH = SEARCH_DIR / "param_search_latest.json"

LIVE_APPROVAL_LATEST_PATH = (
    BASE_DIR / "state" / "strategy_bundle" / "latest" / "live_approval.json"
)
LIVE_APPROVAL_SNAPSHOT_DIR = BASE_DIR / "state" / "strategy_bundle" / "snapshots"
LIVE_APPROVAL_SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
BUNDLE_LATEST_PATH = (
    BASE_DIR / "state" / "strategy_bundle" / "latest" / "strategy_bundle_latest.json"
)

TIMING_DIR = BASE_DIR / "reports" / "pc" / "holding_timing" / "latest"
TIMING_LATEST_PATH = TIMING_DIR / "holding_timing_latest.json"

SCRIPT_PARAM_SEARCH = BASE_DIR / "deploy" / "pc" / "run_param_search.ps1"
SCRIPT_HOLDING_TIMING = BASE_DIR / "deploy" / "pc" / "run_holding_timing.ps1"

ASOF_OVERRIDE_PATH = BASE_DIR / "state" / "runtime" / "asof_override_latest.json"

SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

# Ticker Map
TICKER_MAP = {
    "069500": "KODEX 200",
    "229200": "KODEX KONEX",
    "114800": "KODEX INVERSE",
    "122630": "KODEX LEVERAGE",
}


def _ssot_require(params_obj: dict, *keys: str):
    """SSOT params에서 중첩 키를 꺼낸다. 키가 없으면 KeyError."""
    current = params_obj
    path = []
    for k in keys:
        path.append(k)
        if not isinstance(current, dict) or k not in current:
            raise KeyError(f"SSOT 필수 키 누락: {'.'.join(path)}")
        current = current[k]
    return current


def get_ticker_name(code):
    return f"{code} ({TICKER_MAP.get(code, 'Unknown')})"


def format_file_mtime(path: Path) -> str:
    if not path.exists():
        return "-"
    return datetime.fromtimestamp(path.stat().st_mtime, tz=KST).strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def compute_fingerprint(data):
    return hashlib.sha256(
        json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")
    ).hexdigest()[:16]
