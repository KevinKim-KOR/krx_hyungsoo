# -*- coding: utf-8 -*-
"""
extensions/notification/telegram_helper.py
텔레그램 전송 공통 기능

텔레그램 메시지 전송 및 로깅을 위한 헬퍼 함수
"""

import logging
from typing import Optional
from extensions.notification.telegram_sender import TelegramSender


logger = logging.getLogger(__name__)


class TelegramHelper:
    """텔레그램 헬퍼"""
    
    def __init__(self, bot_token: Optional[str] = None, chat_id: Optional[int] = None):
        """
        Args:
            bot_token: 텔레그램 봇 토큰 (선택)
            chat_id: 텔레그램 채팅 ID (선택)
        """
        try:
            self.sender = TelegramSender(bot_token, chat_id)
            logger.info("TelegramHelper 초기화 완료")
        except Exception as e:
            logger.error(f"TelegramHelper 초기화 실패: {e}")
            self.sender = None
    
    def send_with_logging(
        self,
        message: str,
        success_msg: str,
        fail_msg: str,
        parse_mode: str = 'Markdown'
    ) -> bool:
        """
        로깅과 함께 메시지 전송
        
        Args:
            message: 전송할 메시지
            success_msg: 성공 시 로그 메시지
            fail_msg: 실패 시 로그 메시지
            parse_mode: 파싱 모드 (기본: Markdown)
        
        Returns:
            전송 성공 여부
        """
        if not self.sender:
            logger.warning("텔레그램 전송기가 초기화되지 않았습니다")
            return False
        
        try:
            success = self.sender.send_custom(message, parse_mode)
            
            if success:
                logger.info(f"✅ {success_msg}")
            else:
                logger.warning(f"⚠️ {fail_msg}")
            
            return success
        
        except Exception as e:
            logger.error(f"텔레그램 전송 중 오류: {e}")
            return False
    
    def send_alert(
        self,
        title: str,
        message: str,
        parse_mode: str = 'Markdown'
    ) -> bool:
        """
        알림 메시지 전송 (제목 포함)
        
        Args:
            title: 알림 제목
            message: 알림 내용
            parse_mode: 파싱 모드
        
        Returns:
            전송 성공 여부
        """
        full_message = f"*{title}*\n\n{message}"
        return self.send_with_logging(
            full_message,
            f"{title} 전송 성공",
            f"{title} 전송 실패",
            parse_mode
        )
    
    def send_error_alert(self, error: Exception, context: str = "") -> bool:
        """
        에러 알림 전송
        
        Args:
            error: 예외 객체
            context: 에러 발생 컨텍스트
        
        Returns:
            전송 성공 여부
        """
        if not self.sender:
            return False
        
        try:
            return self.sender.send_error(error, context)
        except Exception as e:
            logger.error(f"에러 알림 전송 실패: {e}")
            return False


def send_telegram_safe(
    message: str,
    success_msg: str = "텔레그램 전송 성공",
    fail_msg: str = "텔레그램 전송 실패",
    parse_mode: str = 'Markdown'
) -> bool:
    """
    안전하게 텔레그램 메시지 전송 (에러 시 False 반환)
    
    Args:
        message: 전송할 메시지
        success_msg: 성공 시 로그 메시지
        fail_msg: 실패 시 로그 메시지
        parse_mode: 파싱 모드
    
    Returns:
        전송 성공 여부
    """
    try:
        helper = TelegramHelper()
        return helper.send_with_logging(message, success_msg, fail_msg, parse_mode)
    except Exception as e:
        logger.error(f"텔레그램 전송 실패: {e}")
        return False
