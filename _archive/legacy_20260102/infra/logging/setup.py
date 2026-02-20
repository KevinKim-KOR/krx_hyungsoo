# -*- coding: utf-8 -*-
"""
infra/logging/setup.py
로깅 설정 (개발 규칙 준수)
"""
import logging
import logging.handlers
from pathlib import Path
from datetime import datetime
from datetime import timezone, timedelta
KST = timezone(timedelta(hours=9))
import sys


def setup_logging(
    name: str = 'krx_alertor',
    log_dir: Path = None,
    level: int = logging.INFO,
    console: bool = True,
    file: bool = True
) -> logging.Logger:
    """
    로깅 설정
    
    Args:
        name: 로거 이름
        log_dir: 로그 디렉토리 (기본: logs/)
        level: 로그 레벨
        console: 콘솔 출력 여부
        file: 파일 출력 여부
        
    Returns:
        설정된 로거
    """
    # 로거 생성
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # 기존 핸들러 제거
    logger.handlers.clear()
    
    # 포맷터
    formatter = logging.Formatter(
        fmt='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 콘솔 핸들러
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    # 파일 핸들러
    if file:
        if log_dir is None:
            log_dir = Path('logs')
        
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # 일별 로그 파일
        today = datetime.now(KST).strftime('%Y-%m-%d')
        log_file = log_dir / f'{name}_{today}.log'
        
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=30,  # 30일 보관
            encoding='utf-8'
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """로거 가져오기"""
    return logging.getLogger(name)


class LogContext:
    """로그 컨텍스트 매니저"""
    
    def __init__(self, logger: logging.Logger, message: str, level: int = logging.INFO):
        """
        Args:
            logger: 로거
            message: 시작 메시지
            level: 로그 레벨
        """
        self.logger = logger
        self.message = message
        self.level = level
        self.start_time = None
    
    def __enter__(self):
        """컨텍스트 시작"""
        self.start_time = datetime.now(KST)
        self.logger.log(self.level, f"{self.message} 시작")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """컨텍스트 종료"""
        elapsed = (datetime.now(KST) - self.start_time).total_seconds()
        
        if exc_type is None:
            self.logger.log(self.level, f"{self.message} 완료 (소요: {elapsed:.2f}초)")
        else:
            self.logger.error(f"{self.message} 실패 (소요: {elapsed:.2f}초): {exc_val}")
        
        return False  # 예외 전파


def log_function_call(logger: logging.Logger):
    """함수 호출 로깅 데코레이터"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            func_name = func.__name__
            logger.debug(f"{func_name} 호출: args={args}, kwargs={kwargs}")
            
            try:
                result = func(*args, **kwargs)
                logger.debug(f"{func_name} 완료")
                return result
            except Exception as e:
                logger.error(f"{func_name} 실패: {e}", exc_info=True)
                raise
        
        return wrapper
    return decorator
