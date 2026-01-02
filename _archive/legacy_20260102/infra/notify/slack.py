# -*- coding: utf-8 -*-
"""
infra/notify/slack.py
Slack 알림 어댑터
"""
import json
import os
from typing import Optional
import requests

class SlackNotifier:
    """Slack 알림 발송"""
    
    def __init__(
        self,
        webhook_url: Optional[str] = None,
        channel: Optional[str] = None
    ):
        self.webhook_url = webhook_url or os.environ.get("SLACK_WEBHOOK_URL")
        self.channel = channel or os.environ.get("SLACK_CHANNEL")
        
        # 웹훅 URL이 없으면 모의 알림만 출력
        self.mock_mode = not bool(self.webhook_url)
    
    def send(self, message: str, blocks: Optional[list] = None) -> bool:
        """
        메시지 발송
        - message: 기본 텍스트
        - blocks: Slack Block Kit 포맷 (옵션)
        """
        payload = {"text": message}
        if self.channel:
            payload["channel"] = self.channel
        if blocks:
            payload["blocks"] = blocks
            
        if self.mock_mode:
            print("\n=== [MOCK] Slack 알림 ===")
            print(f"Channel: {self.channel}")
            print(f"Message: {message}")
            if blocks:
                print("Blocks:")
                for block in blocks:
                    if block['type'] == 'section':
                        print(f"- {block['text']['text']}")
            print("========================\n")
            return True
            
        try:
            response = requests.post(
                self.webhook_url,
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            return True
            
        except Exception as e:
            print(f"Slack 알림 발송 실패: {e}")
            return False

def send_to_slack(
    message: str,
    webhook_url: Optional[str] = None,
    channel: Optional[str] = None,
    blocks: Optional[list] = None
) -> bool:
    """
    Slack 알림 발송 헬퍼 함수
    """
    notifier = SlackNotifier(webhook_url, channel)
    return notifier.send(message, blocks)

def send_alerts(signals: list, template: str = "default_v1") -> None:
    """
    신호 알림을 Slack으로 전송
    
    Args:
        signals: 신호 리스트
        template: 템플릿 ID
    """
    message = f"*[{template}] 전략 신호 알림*\n"
    blocks = []
    
    for signal in signals:
        signal_text = (
            f"- {signal['code']}: {signal['signal_type']} "
            f"(스코어: {signal['score']:.2f}, {signal['reason']})"
        )
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": signal_text}})
    
    send_to_slack(message, blocks=blocks)