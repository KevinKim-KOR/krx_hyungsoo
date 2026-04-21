"""Slack notification helpers consolidated in one module."""

from __future__ import annotations

import os
import re
from typing import Any

import requests

try:
    from slack_sdk import WebClient  # type: ignore
    from slack_sdk.errors import SlackApiError  # type: ignore
except Exception:  # pragma: no cover - 선택적 의존성 처리
    WebClient = None  # type: ignore
    SlackApiError = Exception  # type: ignore

try:
    import pytz
    from croniter import croniter
except ImportError:  # pragma: no cover - 선택적 의존성 처리
    croniter = None
    pytz = None

from utils.logger import get_app_logger
from utils.report import format_kr_money
from utils.settings_loader import get_slack_channel

_LAST_ERROR: str | None = None
logger = get_app_logger()


# ---------------------------------------------------------------------------
# 슬랙 웹훅 관련 헬퍼
# ---------------------------------------------------------------------------


def send_slack_message(
    text: str,
    blocks: list[dict] | None = None,
    webhook_url: str | None = None,
    webhook_name: str | None = None,
) -> bool:
    """Send a Slack message using the provided webhook URL."""

    global _LAST_ERROR
    _LAST_ERROR = None

    if not webhook_url:
        _LAST_ERROR = "Missing Slack webhook URL"
        return False

    sanitized = text.replace("<pre>", "```").replace("</pre>", "```")
    if blocks:
        payload = {"text": sanitized, "blocks": blocks}
    else:
        payload = {"text": sanitized}

    try:
        response = requests.post(webhook_url, json=payload, timeout=10)
        response.raise_for_status()
        if response.text == "ok":
            logger.info("[SLACK] 메시지 전송 - %s", webhook_name or "Unknown Webhook")
            return True
        _LAST_ERROR = response.text or "unknown"
        return False
    except requests.exceptions.RequestException as exc:  # pragma: no cover - 단순 위임 예외 처리
        _LAST_ERROR = str(exc)
        return False
    except Exception as exc:  # pragma: no cover - 방어적 처리
        _LAST_ERROR = str(exc)
        return False


def get_last_error() -> str | None:
    return _LAST_ERROR


# ---------------------------------------------------------------------------
# 포맷팅 보조 함수
# ---------------------------------------------------------------------------


def strip_html_tags(value: str) -> str:
    try:
        return re.sub(r"<[^>]+>", "", value)
    except Exception:  # pragma: no cover - 방어적 처리
        return value


def _send_slack_message_via_bot(
    payload: dict[str, Any] | str,
    thread_ts: str | None = None,
) -> str | None:
    """
    전달받은 페이로드를 슬랙으로 전송합니다.
    성공 시 메시지의 ts(timestamp)를 반환하고, 실패 시 None을 반환합니다.
    """

    if isinstance(payload, str):
        text = payload
        blocks: list[dict[str, Any]] | None = None
    else:
        text = str(payload.get("text", ""))
        blocks = payload.get("blocks")

    channel = get_slack_channel()
    token = os.environ.get("SLACK_BOT_TOKEN")

    if not channel:
        logger.warning("Slack 채널이 설정되어 있지 않아 전송을 건너뜁니다.")
        return None

    if not token:
        logger.warning("SLACK_BOT_TOKEN 이 설정되지 않아 전송을 건너뜁니다.")
        return None

    if WebClient is None:
        logger.warning("slack_sdk 가 설치되어 있지 않아 슬랙 전송을 건너뜁니다.")
        return None

    client = WebClient(token=token)

    try:
        response = client.chat_postMessage(
            channel=channel,
            text=text or "Slack notification",
            blocks=blocks,
            thread_ts=thread_ts,
        )
        ts = response.get("ts")
        logger.info("Slack message sent via bot token (channel=%s, ts=%s)", channel, ts)
        return ts
    except SlackApiError as exc:  # pragma: no cover - 외부 API 호출 오류
        logger.error(
            "Slack API 호출 중 오류가 발생했습니다: %s",
            getattr(exc, "response", {}).get("error") or str(exc),
            exc_info=True,
        )
        return None
    except Exception:  # pragma: no cover - 방어적 처리
        logger.error("Slack 메시지 전송 중 알 수 없는 오류가 발생했습니다", exc_info=True)
        return None


def send_slack_message_v2(
    text: str,
    blocks: list[dict[str, Any]] | None = None,
    thread_ts: str | None = None,
) -> str | None:
    """
    범용 슬랙 메시지 전송 함수 (WebClient 기반).
    메시지의 ts(timestamp)를 반환합니다.
    """
    return _send_slack_message_via_bot({"text": text, "blocks": blocks}, thread_ts=thread_ts)


def _format_shares_for_country(quantity: Any) -> str:
    if not isinstance(quantity, (int, float)):
        return str(quantity)
    return f"{quantity:,.0f}"


def build_summary_line_from_summary_data(
    summary_data: dict[str, Any],
    money_formatter: callable = format_kr_money,
    *,
    use_html: bool,
    prefix: str | None = None,
    include_hold: bool = True,
) -> str:
    parts: list[str] = []

    if include_hold:
        held_count = summary_data.get("held_count")
        limit = summary_data.get("universe_count")
        if held_count is not None and limit is not None:
            try:
                parts.append(f"보유종목: {int(held_count)}/{int(limit)}")
            except (TypeError, ValueError):
                pass

    principal = money_formatter(float(summary_data.get("principal", 0.0) or 0.0))
    parts.append(f"원금: {principal}")

    parts.append(
        _format_return_with_amount(
            "일간",
            float(summary_data.get("daily_return_pct", 0.0) or 0.0),
            float(summary_data.get("daily_profit_loss", 0.0) or 0.0),
            money_formatter,
            use_html=use_html,
        )
    )
    parts.append(
        _format_return_with_amount(
            "평가",
            float(summary_data.get("eval_return_pct", 0.0) or 0.0),
            float(summary_data.get("eval_profit_loss", 0.0) or 0.0),
            money_formatter,
            use_html=use_html,
        )
    )
    parts.append(
        _format_return_with_amount(
            "누적",
            float(summary_data.get("cum_return_pct", 0.0) or 0.0),
            float(summary_data.get("cum_profit_loss", 0.0) or 0.0),
            money_formatter,
            use_html=use_html,
        )
    )

    cash = money_formatter(float(summary_data.get("total_cash", 0.0) or 0.0))
    equity = money_formatter(float(summary_data.get("total_equity", 0.0) or 0.0))
    parts.append(f"현금: {cash}")
    parts.append(f"평가금액: {equity}")

    body = " | ".join(parts)
    if prefix:
        return f"{prefix} {body}"
    return body


def build_summary_line_from_header(header_line: str, prefix: str | None = None) -> str:
    header_line_clean = header_line.split("<br>")[0]
    segments = [seg.strip() for seg in header_line_clean.split("|")]

    def _pick(label: str, default: str) -> str:
        for seg in segments:
            if label in seg:
                value = seg.split(":", 1)[1].strip()
                return f"{label}: {strip_html_tags(value)}"
        return default

    parts = [
        _pick("보유종목", "보유종목: -"),
        _pick("원금", "원금: -"),
        _pick("일간", "일간: +0.00%(0원)"),
        _pick("평가", "평가: +0.00%(0원)"),
        _pick("누적", "누적: +0.00%(0원)"),
        _pick("현금", "현금: 0원"),
        _pick("평가금액", "평가금액: 0원"),
    ]

    body = " | ".join(parts)
    if prefix:
        return f"{prefix} {body}"
    return body


def _format_return_with_amount(
    label: str,
    pct: float,
    amount: float,
    formatter: callable,
    *,
    use_html: bool,
) -> str:
    pct = float(pct or 0.0)
    amount = float(amount or 0.0)
    formatted_amount = formatter(amount)

    if use_html:
        color = "red" if pct > 0 else "blue" if pct < 0 else "black"
        return f'{label}: <span style="color:{color}">{pct:+.2f}%({formatted_amount})</span>'

    return f"{label}: {pct:+.2f}%({formatted_amount})"


__all__ = [
    "build_summary_line_from_summary_data",
    "build_summary_line_from_header",
    "get_last_error",
    "send_slack_message",
    "send_slack_message_v2",
    "strip_html_tags",
]
