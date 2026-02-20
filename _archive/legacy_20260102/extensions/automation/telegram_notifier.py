# -*- coding: utf-8 -*-
"""
extensions/automation/telegram_notifier.py
텔레그램 알림 시스템

기능:
- 매매 신호 알림
- 레짐 변경 알림
- 방어 모드 알림
- 일일/주간 리포트
"""

from datetime import date, datetime
from datetime import timezone, timedelta
KST = timezone(timedelta(hours=9))
from typing import Optional, List, Dict
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """
    텔레그램 알림 클래스
    
    기능:
    1. 매매 신호 알림
    2. 레짐 변경 알림
    3. 방어 모드 알림
    
    Note:
        실제 텔레그램 봇 사용 시 python-telegram-bot 패키지 필요
        현재는 로그 출력으로 대체
    """
    
    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
        enabled: bool = False
    ):
        """
        Args:
            bot_token: 텔레그램 봇 토큰
            chat_id: 채팅 ID
            enabled: 알림 활성화 여부
        """
        self.bot_token = bot_token or os.getenv('TELEGRAM_BOT_TOKEN')
        self.chat_id = chat_id or os.getenv('TELEGRAM_CHAT_ID')
        self.enabled = enabled
        
        if self.enabled and (not self.bot_token or not self.chat_id):
            logger.warning("텔레그램 설정이 없습니다. 로그 모드로 작동합니다.")
            self.enabled = False
    
    def send_message(self, message: str, parse_mode: str = 'Markdown') -> bool:
        """
        메시지 전송
        
        Args:
            message: 전송할 메시지
            parse_mode: 파싱 모드 (Markdown, HTML)
            
        Returns:
            bool: 전송 성공 여부
        """
        if not self.enabled:
            logger.info(f"[텔레그램 알림 - 비활성화 모드]\n{message}")
            return False
        
        try:
            import requests
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            data = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': parse_mode
            }
            response = requests.post(url, json=data, timeout=10)
            response.raise_for_status()
            logger.info(f"텔레그램 메시지 전송 성공: {len(message)}자")
            return True
        except Exception as e:
            logger.error(f"텔레그램 전송 실패: {e}")
            return False
    
    def send_buy_signals(self, signals: List[Dict]):
        """
        매수 신호 알림
        
        Args:
            signals: 매수 신호 리스트
        """
        if not signals:
            return
        
        message_lines = [
            "🟢 *매수 신호*",
            f"📅 {datetime.now(KST).strftime('%Y-%m-%d %H:%M')}",
            ""
        ]
        
        for i, signal in enumerate(signals, 1):
            code = signal['code']
            score = signal['maps_score']
            message_lines.append(
                f"{i}. `{code}` (MAPS: {score:.2f})"
            )
        
        message_lines.append("")
        message_lines.append(f"총 {len(signals)}개 종목")
        
        self.send_message("\n".join(message_lines))
    
    def send_sell_signals(self, signals: List[Dict]):
        """
        매도 신호 알림
        
        Args:
            signals: 매도 신호 리스트
        """
        if not signals:
            return
        
        message_lines = [
            "🔴 *매도 신호*",
            f"📅 {datetime.now(KST).strftime('%Y-%m-%d %H:%M')}",
            ""
        ]
        
        for i, signal in enumerate(signals, 1):
            code = signal['code']
            reason = signal['reason']
            message_lines.append(
                f"{i}. `{code}` ({reason})"
            )
        
        message_lines.append("")
        message_lines.append(f"총 {len(signals)}개 종목")
        
        self.send_message("\n".join(message_lines))
    
    def send_regime_change(
        self,
        old_regime: str,
        new_regime: str,
        confidence: float,
        date_str: str
    ):
        """
        레짐 변경 알림
        
        Args:
            old_regime: 이전 레짐
            new_regime: 새 레짐
            confidence: 신뢰도
            date_str: 날짜
        """
        regime_emoji = {
            'bull': '📈',
            'bear': '📉',
            'neutral': '➡️'
        }
        
        regime_name = {
            'bull': '상승장',
            'bear': '하락장',
            'neutral': '중립장'
        }
        
        old_emoji = regime_emoji.get(old_regime, '❓')
        new_emoji = regime_emoji.get(new_regime, '❓')
        old_name = regime_name.get(old_regime, old_regime)
        new_name = regime_name.get(new_regime, new_regime)
        
        message = f"""🔄 *레짐 변경 감지!*

📅 날짜: {date_str}
{old_emoji} 이전: {old_name}
{new_emoji} 현재: {new_name}
📊 신뢰도: {confidence:.1%}

전략을 조정하세요!"""
        
        self.send_message(message)
    
    def send_defense_mode_alert(
        self,
        is_entering: bool,
        reason: str,
        date_str: str
    ):
        """
        방어 모드 알림
        
        Args:
            is_entering: 진입 여부 (True: 진입, False: 해제)
            reason: 사유
            date_str: 날짜
        """
        if is_entering:
            message = f"""⚠️ *방어 모드 진입!*

📅 날짜: {date_str}
🛡️ 사유: {reason}

매수를 중단하고 현금 보유를 늘리세요."""
        else:
            message = f"""✅ *방어 모드 해제*

📅 날짜: {date_str}
💚 정상 모드로 복귀

매수 재개 가능합니다."""
        
        self.send_message(message)
    
    def send_market_crash_alert(
        self,
        crash_type: str,
        decline_pct: float,
        date_str: str
    ):
        """
        시장 급락 알림
        
        Args:
            crash_type: 급락 유형
            decline_pct: 하락률
            date_str: 날짜
        """
        message = f"""🚨 *시장 급락 감지!*

📅 날짜: {date_str}
📉 하락률: {decline_pct:.2f}%
⚠️ 유형: {crash_type}

포트폴리오를 점검하세요!"""
        
        self.send_message(message)
