"""
Telegram Sender Provider (D-P.56)

Fail-Closed: 토큰/chat_id 누락 시 발송 금지
"""

import os
import requests
from typing import Dict, Any, Optional


def send_telegram_message(
    message: str,
    parse_mode: Optional[str] = None
) -> Dict[str, Any]:
    """
    Telegram으로 메시지 발송
    
    Args:
        message: 발송할 메시지
        parse_mode: "HTML" 또는 "Markdown" (선택)
    
    Returns:
        {
            "success": bool,
            "provider": "TELEGRAM",
            "message_id": int or None,
            "error": str or None
        }
    
    Fail-Closed:
        - TELEGRAM_BOT_TOKEN 또는 TELEGRAM_CHAT_ID 누락 시 success=False
    """
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    
    # Fail-Closed: 토큰 또는 chat_id 누락
    if not bot_token:
        return {
            "success": False,
            "provider": "TELEGRAM",
            "message_id": None,
            "error": "TELEGRAM_BOT_TOKEN not configured"
        }
    
    if not chat_id:
        return {
            "success": False,
            "provider": "TELEGRAM",
            "message_id": None,
            "error": "TELEGRAM_CHAT_ID not configured"
        }
    
    # Build API URL
    api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    # Build payload
    payload = {
        "chat_id": chat_id,
        "text": message
    }
    
    if parse_mode:
        payload["parse_mode"] = parse_mode
    
    try:
        response = requests.post(api_url, json=payload, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        
        if result.get("ok"):
            message_id = result.get("result", {}).get("message_id")
            return {
                "success": True,
                "provider": "TELEGRAM",
                "message_id": message_id,
                "error": None
            }
        else:
            return {
                "success": False,
                "provider": "TELEGRAM",
                "message_id": None,
                "error": result.get("description", "Unknown Telegram API error")
            }
            
    except requests.exceptions.Timeout:
        return {
            "success": False,
            "provider": "TELEGRAM",
            "message_id": None,
            "error": "Telegram API timeout"
        }
    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "provider": "TELEGRAM",
            "message_id": None,
            "error": f"Request failed: {str(e)}"
        }
    except Exception as e:
        return {
            "success": False,
            "provider": "TELEGRAM",
            "message_id": None,
            "error": f"Unexpected error: {str(e)}"
        }
