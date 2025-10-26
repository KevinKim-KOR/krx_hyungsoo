"""
infra/notify/telegram.py
텔레그램 알림 어댑터
"""
import os
import yaml
from pathlib import Path
import requests
from typing import List, Dict, Any, Optional

class TelegramNotifier:
    """텔레그램 알림 발송"""
    
    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[int] = None
    ):
        # 1. bot_token과 chat_id가 직접 전달되면 그것을 사용
        # 2. 없으면 secret/config.yaml에서 로드
        if not bot_token or not chat_id:
            config_path = Path(__file__).parent.parent.parent / "secret" / "config.yaml"
            if config_path.exists():
                with open(config_path, encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                    bot_token = bot_token or config['notifications']['telegram']['bot_token']
                    chat_id = chat_id or config['notifications']['telegram']['chat_id']
        
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        
        if not self.bot_token or not self.chat_id:
            raise ValueError("Telegram bot_token과 chat_id가 설정되지 않았습니다.")
    
    def send(self, message: str, parse_mode: str = 'Markdown') -> bool:
        """
        메시지 발송
        
        Args:
            message: 보낼 메시지
            parse_mode: 'Markdown' 또는 'HTML'
        """
        try:
            url = f"{self.base_url}/sendMessage"
            data = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': parse_mode
            }
            response = requests.post(url, json=data)
            response.raise_for_status()
            return True
            
        except Exception as e:
            print(f"Telegram 알림 발송 실패: {e}")
            return False

def send_to_telegram(message: str, parse_mode: str = 'Markdown') -> bool:
    """
    텔레그램 알림 발송 헬퍼 함수
    """
    notifier = TelegramNotifier()
    return notifier.send(message, parse_mode)

def send_alerts(signals: List[Dict[str, Any]], template: str = "default_v1") -> None:
    """
    신호 알림을 텔레그램으로 전송
    
    Args:
        signals: 신호 리스트
        template: 템플릿 ID
    """
    # HTML 포맷 사용 (마크다운보다 더 안정적)
    message = f"<b>[{template}] 전략 신호 알림</b>\n\n"
    
    for signal in signals:
        code = signal['code']
        signal_type = signal['signal_type']
        score = signal['score']
        reason = signal['reason']
        
        message += f"• <code>{code}</code>: <b>{signal_type}</b>\n"
        message += f"  스코어: <code>{score:.2f}</code>\n"
        message += f"  사유: {reason}\n\n"
    
    send_to_telegram(message, parse_mode='HTML')