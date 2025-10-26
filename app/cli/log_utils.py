"""Logging helpers per NEW docs."""
from __future__ import annotations
import os
import traceback

SLACK_CHANNEL_DEFAULT = os.getenv("SLACK_CHANNEL", "invest_ops")


def send_verbose_log_to_slack(message: str, level: str = "ERROR", channel: str | None = None) -> None:
    """Thin wrapper; integrates with existing notifications if available.
    No-op if notification backend is unavailable.
    """
    channel = channel or SLACK_CHANNEL_DEFAULT
    payload = f"[{level}] {message}"
    try:
        # Prefer existing notifications module
        try:
            import notifications  # root-level module if present
            if hasattr(notifications, "send_slack"):
                notifications.send_slack(payload, channel=channel)
                return
        except Exception:
            pass
        # Fallback: print to stderr
        print(payload)
    except Exception:
        print("[ERROR] send_verbose_log_to_slack failed:\n" + traceback.format_exc())
