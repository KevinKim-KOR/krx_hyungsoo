#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Phase 2 재테스트 - 로깅 유틸리티
"""
import sys
from pathlib import Path
from datetime import datetime
import logging


class DualLogger:
    """콘솔과 파일에 동시에 로그를 출력하는 클래스"""
    
    def __init__(self, log_file: Path, level=logging.INFO):
        """
        Args:
            log_file: 로그 파일 경로
            level: 로깅 레벨
        """
        self.log_file = log_file
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        
        # 로거 설정
        self.logger = logging.getLogger(f"phase2_{log_file.stem}")
        self.logger.setLevel(level)
        
        # 기존 핸들러 제거
        self.logger.handlers.clear()
        
        # 파일 핸들러
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(level)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)
        
        # 콘솔 핸들러
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_formatter = logging.Formatter('%(message)s')
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
        
        # 시작 로그
        self.logger.info("=" * 70)
        self.logger.info(f"로그 파일: {log_file}")
        self.logger.info(f"시작 시간: {datetime.now():%Y-%m-%d %H:%M:%S}")
        self.logger.info("=" * 70)
    
    def info(self, message):
        """정보 로그"""
        self.logger.info(message)
    
    def warning(self, message):
        """경고 로그"""
        self.logger.warning(message)
    
    def error(self, message):
        """에러 로그"""
        self.logger.error(message)
    
    def section(self, title):
        """섹션 헤더"""
        self.logger.info("")
        self.logger.info(title)
        self.logger.info("-" * 70)
    
    def success(self, message):
        """성공 메시지"""
        self.logger.info(f"[OK] {message}")
    
    def fail(self, message):
        """실패 메시지"""
        self.logger.error(f"[FAIL] {message}")
    
    def warn(self, message):
        """경고 메시지"""
        self.logger.warning(f"[WARN] {message}")
    
    def finish(self):
        """종료 로그"""
        self.logger.info("")
        self.logger.info("=" * 70)
        self.logger.info(f"종료 시간: {datetime.now():%Y-%m-%d %H:%M:%S}")
        self.logger.info("=" * 70)


def create_logger(step_name: str, project_root: Path) -> DualLogger:
    """
    단계별 로거 생성
    
    Args:
        step_name: 단계 이름 (예: "phase0_train_test")
        project_root: 프로젝트 루트 경로
    
    Returns:
        DualLogger 인스턴스
    """
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = project_root / 'logs' / 'backtest' / f"{step_name}_{timestamp}.log"
    
    return DualLogger(log_file)
