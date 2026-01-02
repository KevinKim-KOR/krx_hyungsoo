# -*- coding: utf-8 -*-
"""
extensions/notification/telegram_sender.py
텔레그램 알림 전송
"""
import logging
from datetime import date
from typing import List, Optional
from pathlib import Path
from dotenv import load_dotenv
import os

# .env 파일 로드
load_dotenv()

from extensions.realtime.signal_generator import Signal
from infra.notify.telegram import TelegramNotifier
from .formatter import (
    format_daily_signals,
    format_portfolio_summary,
    format_rebalancing_actions,
    format_error_message
)

logger = logging.getLogger(__name__)


class TelegramSender:
    """텔레그램 알림 전송기"""
    
    def __init__(self, bot_token: Optional[str] = None, chat_id: Optional[int] = None):
        """
        Args:
            bot_token: 텔레그램 봇 토큰
            chat_id: 텔레그램 채팅 ID
        """
        try:
            self.notifier = TelegramNotifier(bot_token, chat_id)
            logger.info("TelegramSender 초기화 완료")
        except Exception as e:
            logger.error(f"TelegramSender 초기화 실패: {e}")
            self.notifier = None
    
    def send_daily_signals(
        self,
        signals: List[Signal],
        target_date: date,
        summary: Optional[dict] = None
    ) -> bool:
        """
        일일 매매 신호 전송
        
        Args:
            signals: 신호 리스트
            target_date: 신호 날짜
            summary: 포트폴리오 요약 (선택)
            
        Returns:
            성공 여부
        """
        if not self.notifier:
            logger.warning("텔레그램 알림 미설정")
            return False
        
        try:
            # 신호 메시지
            message = format_daily_signals(signals, target_date)
            
            # 포트폴리오 요약 추가 (선택)
            if summary:
                message += "\n\n" + format_portfolio_summary(signals, summary)
            
            # 전송
            success = self.notifier.send(message, parse_mode='Markdown')
            
            if success:
                logger.info(f"텔레그램 알림 전송 성공: {len(signals)}개 신호")
            else:
                logger.error("텔레그램 알림 전송 실패")
            
            return success
        
        except Exception as e:
            logger.error(f"텔레그램 알림 전송 중 오류: {e}")
            return False
    
    def send_rebalancing_actions(self, actions: List, target_date: date) -> bool:
        """
        리밸런싱 액션 전송
        
        Args:
            actions: 액션 리스트
            target_date: 날짜
            
        Returns:
            성공 여부
        """
        if not self.notifier:
            logger.warning("텔레그램 알림 미설정")
            return False
        
        try:
            message = f"*[리밸런싱] {target_date}*\n\n"
            message += format_rebalancing_actions(actions)
            
            success = self.notifier.send(message, parse_mode='Markdown')
            
            if success:
                logger.info(f"리밸런싱 알림 전송 성공: {len(actions)}개 액션")
            else:
                logger.error("리밸런싱 알림 전송 실패")
            
            return success
        
        except Exception as e:
            logger.error(f"리밸런싱 알림 전송 중 오류: {e}")
            return False
    
    def send_error(self, error: Exception, context: str = "") -> bool:
        """
        에러 알림 전송
        
        Args:
            error: 예외 객체
            context: 에러 발생 컨텍스트
            
        Returns:
            성공 여부
        """
        if not self.notifier:
            return False
        
        try:
            message = format_error_message(error, context)
            return self.notifier.send(message, parse_mode='Markdown')
        
        except Exception as e:
            logger.error(f"에러 알림 전송 중 오류: {e}")
            return False
    
    def send_custom(self, message: str, parse_mode: str = 'Markdown') -> bool:
        """
        커스텀 메시지 전송
        
        Args:
            message: 메시지
            parse_mode: 파싱 모드
            
        Returns:
            성공 여부
        """
        if not self.notifier:
            logger.warning("텔레그램 알림 미설정")
            return False
        
        return self.notifier.send(message, parse_mode)


def send_daily_signals(
    signals: List[Signal],
    target_date: date,
    summary: Optional[dict] = None,
    bot_token: Optional[str] = None,
    chat_id: Optional[int] = None
) -> bool:
    """
    일일 신호 전송 헬퍼 함수
    
    Args:
        signals: 신호 리스트
        target_date: 신호 날짜
        summary: 포트폴리오 요약
        bot_token: 봇 토큰 (선택)
        chat_id: 채팅 ID (선택)
        
    Returns:
        성공 여부
    """
    sender = TelegramSender(bot_token, chat_id)
    return sender.send_daily_signals(signals, target_date, summary)
