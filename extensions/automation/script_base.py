# -*- coding: utf-8 -*-
"""
extensions/automation/script_base.py
스크립트 공통 기능 제공

모든 NAS 스크립트의 베이스 클래스
- 프로젝트 루트 설정
- 로깅 초기화
- 에러 처리
- 공통 유틸리티
"""

import sys
import logging
from pathlib import Path
from typing import Callable, Any
from functools import wraps

from infra.logging.setup import setup_logging


class ScriptBase:
    """스크립트 베이스 클래스"""
    
    def __init__(self, script_name: str):
        """
        Args:
            script_name: 스크립트 이름 (로깅용)
        """
        self.script_name = script_name
        self.setup_environment()
        self.setup_logging()
    
    def setup_environment(self):
        """환경 설정 (PYTHONPATH 추가)"""
        project_root = Path(__file__).parent.parent.parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
    
    def setup_logging(self):
        """로깅 설정"""
        setup_logging()
        self.logger = logging.getLogger(self.script_name)
    
    def log_header(self, message: str):
        """
        로깅 헤더 출력
        
        Args:
            message: 헤더 메시지
        """
        self.logger.info("=" * 60)
        self.logger.info(message)
        self.logger.info("=" * 60)
    
    def log_footer(self):
        """로깅 푸터 출력"""
        self.logger.info("=" * 60)


def handle_script_errors(script_name: str = "Script"):
    """
    스크립트 에러 처리 데코레이터
    
    Args:
        script_name: 스크립트 이름
    
    Usage:
        @handle_script_errors("장중 알림")
        def main():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> int:
            logger = logging.getLogger(script_name)
            
            try:
                result = func(*args, **kwargs)
                return result if result is not None else 0
            
            except Exception as e:
                logger.error(f"❌ {script_name} 실패: {e}", exc_info=True)
                
                # 텔레그램 에러 알림 시도 (선택적)
                try:
                    from extensions.notification.telegram_sender import TelegramSender
                    sender = TelegramSender()
                    sender.send_error(e, script_name)
                except:
                    pass
                
                return 1
        
        return wrapper
    return decorator


def log_execution_time(func: Callable) -> Callable:
    """
    실행 시간 로깅 데코레이터
    
    Usage:
        @log_execution_time
        def main():
            ...
    """
    @wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        import time
        logger = logging.getLogger(func.__name__)
        
        start_time = time.time()
        logger.info(f"시작: {func.__name__}")
        
        result = func(*args, **kwargs)
        
        elapsed_time = time.time() - start_time
        logger.info(f"완료: {func.__name__} (소요 시간: {elapsed_time:.2f}초)")
        
        return result
    
    return wrapper
