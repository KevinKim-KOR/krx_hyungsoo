# -*- coding: utf-8 -*-
"""secrets 라우터 — /api/secrets/status, /api/secrets/self_test."""

import json
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException

from backend.utils import KST, BASE_DIR, REPORTS_DIR, logger

router = APIRouter()

# --- 상수 ---
REQUIRED_SECRETS = [
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "SLACK_WEBHOOK_URL",
    "SMTP_HOST",
    "SMTP_USER",
    "SMTP_PASS",
    "EMAIL_TO",
]

SELF_TEST_LATEST = BASE_DIR / "reports" / "ops" / "secrets" / "self_test_latest.json"
SELF_TEST_SNAPSHOTS_DIR = BASE_DIR / "reports" / "ops" / "secrets" / "snapshots"

# Channel requirements from PUSH_CHANNELS_V1
CHANNEL_REQUIREMENTS = {
    "TELEGRAM": ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"],
    "SLACK": ["SLACK_WEBHOOK_URL"],
    "EMAIL": ["SMTP_HOST", "SMTP_USER", "SMTP_PASS", "EMAIL_TO"],
}


# --- 헬퍼 ---
def run_secrets_self_test() -> dict:
    """시크릿 Self-Test 실행"""
    import os

    # Optional: try to load .env
    provider = "ENV_ONLY"
    try:
        from dotenv import load_dotenv

        env_file = BASE_DIR / ".env"
        if env_file.exists():
            load_dotenv(env_file)
            provider = "DOTENV_OPTIONAL"
    except ImportError:
        pass

    # Check all secrets
    all_secrets: set[str] = set()
    for secrets in CHANNEL_REQUIREMENTS.values():
        all_secrets.update(secrets)

    secrets_status = {}
    for secret_name in all_secrets:
        secrets_status[secret_name] = bool(os.environ.get(secret_name))

    # Evaluate by channel
    missing_required_by_channel: dict[str, list[str]] = {}
    ready_channels: list[str] = []

    for channel, required in CHANNEL_REQUIREMENTS.items():
        missing = [s for s in required if not secrets_status.get(s, False)]
        missing_required_by_channel[channel] = missing
        if not missing:
            ready_channels.append(channel)

    # Decision (Fail Closed)
    if ready_channels:
        decision = "SELF_TEST_PASS"
        reason = (
            f"{ready_channels[0]} channel ready "
            f"({len(CHANNEL_REQUIREMENTS[ready_channels[0]])} secrets present)"
        )
    else:
        decision = "SELF_TEST_FAIL"
        reason = "No external channel ready"

    present_count = sum(1 for v in secrets_status.values() if v)

    result = {
        "schema": "SECRETS_SELF_TEST_V1",
        "asof": datetime.now(KST).isoformat(),
        "provider": provider,
        "secrets_checked_count": len(all_secrets),
        "present_count": present_count,
        "missing_required_by_channel": missing_required_by_channel,
        "decision": decision,
        "reason": reason,
    }

    return result


# --- 라우트 ---
@router.get("/api/secrets/status", summary="시크릿 존재 여부 조회")
def get_secrets_status():
    """Secrets Status API (C-P.19) - 값 노출 금지, present 여부만"""
    import os

    # Optional: try to load .env if python-dotenv is available
    try:
        from dotenv import load_dotenv

        env_file = BASE_DIR / ".env"
        if env_file.exists():
            load_dotenv(env_file)
    except ImportError:
        pass  # python-dotenv not installed, use system env only

    secrets_map = {}
    for secret_name in REQUIRED_SECRETS:
        # Only check presence, NEVER log or return values
        secrets_map[secret_name] = {"present": bool(os.environ.get(secret_name))}

    return {
        "status": "ready",
        "schema": "SECRETS_STATUS_V1",
        "asof": datetime.now(KST).isoformat(),
        "row_count": len(REQUIRED_SECRETS),
        "rows": [{"provider": "ENV_ONLY", "secrets": secrets_map}],
        "error": None,
    }


@router.get("/api/secrets/self_test", summary="시크릿 Self-Test 결과 조회")
def get_secrets_self_test():
    """Secrets Self-Test Latest (C-P.20)"""
    if not SELF_TEST_LATEST.exists():
        return {
            "status": "empty",
            "schema": "SECRETS_SELF_TEST_V1",
            "row_count": 0,
            "rows": [],
            "error": "No self-test result yet. Run POST /api/secrets/self_test/run",
        }

    try:
        data = json.loads(SELF_TEST_LATEST.read_text(encoding="utf-8"))
        return {
            "status": "ready",
            "schema": "SECRETS_SELF_TEST_V1",
            "asof": data.get("asof"),
            "row_count": 1,
            "rows": [data],
            "error": None,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@router.post("/api/secrets/self_test/run", summary="시크릿 Self-Test 실행")
def run_secrets_self_test_api():
    """Secrets Self-Test Run (C-P.20) - No external network calls"""
    try:
        result = run_secrets_self_test()

        # Save latest
        SELF_TEST_LATEST.parent.mkdir(parents=True, exist_ok=True)
        SELF_TEST_LATEST.write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        # Save snapshot
        SELF_TEST_SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
        snapshot_name = f"self_test_{datetime.now(KST).strftime('%Y%m%d_%H%M%S')}.json"
        snapshot_path = SELF_TEST_SNAPSHOTS_DIR / snapshot_name
        snapshot_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        logger.info(f"Self-test complete: {result['decision']}")

        return {
            "result": "OK",
            "decision": result["decision"],
            "reason": result["reason"],
            "snapshot_path": str(snapshot_path.relative_to(BASE_DIR)),
        }
    except Exception as e:
        logger.error(f"Self-test error: {e}")
        raise HTTPException(
            status_code=500, detail={"result": "FAILED", "reason": str(e)}
        )
