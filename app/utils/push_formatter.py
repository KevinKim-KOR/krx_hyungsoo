"""
Push Formatter (C-P.22)
공용 포맷터 - Preview와 Sender가 100% 동일한 텍스트/버튼 생성

주의:
- 순수 함수(Pure-ish) 설계
- 외부 의존(네트워크/파일 I/O) 금지
- Secret Injection 방지 검증 필수
"""

import re
from typing import Dict, List, Optional, Tuple

# Secret key names to block (from PUSH_CHANNELS_V1 contract)
SECRET_KEY_NAMES = [
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "TELEGRAM_TOKEN",
    "SLACK_WEBHOOK_URL",
    "SLACK_TOKEN",
    "SMTP_HOST",
    "SMTP_USER",
    "SMTP_PASS",
    "SMTP_PASSWORD",
    "EMAIL_TO",
    "EMAIL_PASSWORD",
    "API_KEY",
    "API_SECRET",
]

# Suspicious patterns for template injection
INJECTION_PATTERNS = [
    r"\{\{",      # Jinja/Mustache template
    r"\}\}",      # Jinja/Mustache template
    r"\$\{",      # Shell/JS interpolation
    r"\$\(",      # Shell command substitution
]


def check_secret_injection(text: str, additional_secret_keys: Optional[List[str]] = None) -> Tuple[bool, Optional[str]]:
    """
    Secret Injection 검증
    
    Args:
        text: 검증할 텍스트
        additional_secret_keys: 추가로 차단할 시크릿 키 이름 목록
        
    Returns:
        (is_safe: bool, blocked_reason: Optional[str])
        - is_safe=True: 안전
        - is_safe=False: 차단, blocked_reason에 사유
    """
    if not text:
        return (True, None)
    
    # 1. Template injection patterns
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, text):
            return (False, "SECRET_INJECTION_SUSPECTED")
    
    # 2. Secret key names in text
    all_keys = SECRET_KEY_NAMES.copy()
    if additional_secret_keys:
        all_keys.extend(additional_secret_keys)
    
    text_upper = text.upper()
    for key in all_keys:
        if key.upper() in text_upper:
            return (False, "SECRET_KEY_NAME_IN_TEXT")
    
    return (True, None)


def format_console(message: Dict, asof: str) -> Dict:
    """
    CONSOLE 채널용 포맷
    
    Args:
        message: 메시지 데이터 (message_id, title, content, push_type 등)
        asof: 포맷 시각 (호출자가 주입)
        
    Returns:
        {text_preview, actions_preview, blocked, blocked_reason}
    """
    title = message.get("title", "")
    content = message.get("content", message.get("body", ""))
    push_type = message.get("push_type", "ALERT")
    
    text = f"[{push_type}] {title}\n{content}" if title else content
    
    # Secret injection check
    is_safe, reason = check_secret_injection(text)
    
    return {
        "text_preview": text if is_safe else "[BLOCKED]",
        "actions_preview": [],
        "blocked": not is_safe,
        "blocked_reason": reason
    }


def format_telegram(message: Dict, asof: str) -> Dict:
    """
    TELEGRAM 채널용 포맷 (Markdown)
    """
    title = message.get("title", "")
    content = message.get("content", message.get("body", ""))
    push_type = message.get("push_type", "ALERT")
    
    # Telegram Markdown format
    text = f"*[{push_type}]* {title}\n\n{content}" if title else content
    
    # Secret injection check
    is_safe, reason = check_secret_injection(text)
    
    return {
        "text_preview": text if is_safe else "[BLOCKED]",
        "actions_preview": [],
        "blocked": not is_safe,
        "blocked_reason": reason
    }


def format_slack(message: Dict, asof: str) -> Dict:
    """
    SLACK 채널용 포맷 (mrkdwn)
    """
    title = message.get("title", "")
    content = message.get("content", message.get("body", ""))
    push_type = message.get("push_type", "ALERT")
    
    # Slack mrkdwn format
    text = f"*[{push_type}]* {title}\n{content}" if title else content
    
    # Secret injection check
    is_safe, reason = check_secret_injection(text)
    
    return {
        "text_preview": text if is_safe else "[BLOCKED]",
        "actions_preview": [],
        "blocked": not is_safe,
        "blocked_reason": reason
    }


def format_email(message: Dict, asof: str) -> Dict:
    """
    EMAIL 채널용 포맷 (Plain text + HTML)
    """
    title = message.get("title", "")
    content = message.get("content", message.get("body", ""))
    push_type = message.get("push_type", "ALERT")
    
    subject = f"[{push_type}] {title}" if title else f"[{push_type}] Notification"
    body = content
    
    text = f"Subject: {subject}\n\n{body}"
    
    # Secret injection check
    is_safe, reason = check_secret_injection(text)
    
    return {
        "text_preview": text if is_safe else "[BLOCKED]",
        "actions_preview": [],
        "blocked": not is_safe,
        "blocked_reason": reason
    }


# Channel formatter registry
CHANNEL_FORMATTERS = {
    "CONSOLE": format_console,
    "TELEGRAM": format_telegram,
    "SLACK": format_slack,
    "EMAIL": format_email,
}


def format_message_for_channel(channel: str, message: Dict, asof: str) -> Dict:
    """
    지정된 채널에 맞게 메시지 포맷팅
    
    Args:
        channel: 채널명 (CONSOLE, TELEGRAM, SLACK, EMAIL)
        message: 메시지 데이터
        asof: 포맷 시각
        
    Returns:
        포맷팅된 결과 (text_preview, actions_preview, blocked, blocked_reason)
    """
    formatter = CHANNEL_FORMATTERS.get(channel.upper(), format_console)
    return formatter(message, asof)


def render_all_channels(message: Dict, asof: str, channels: Optional[List[str]] = None) -> List[Dict]:
    """
    모든 채널에 대해 메시지 렌더링
    
    Args:
        message: 메시지 데이터
        asof: 렌더 시각
        channels: 렌더할 채널 목록 (None이면 전체)
        
    Returns:
        채널별 렌더링 결과 리스트
    """
    if channels is None:
        channels = ["CONSOLE", "TELEGRAM", "SLACK", "EMAIL"]
    
    results = []
    for channel in channels:
        render = format_message_for_channel(channel, message, asof)
        results.append({
            "channel": channel,
            "message_id": message.get("message_id", message.get("id", "")),
            **render,
            "secret_injection_check": "PASS" if not render.get("blocked") else "BLOCKED"
        })
    
    return results
