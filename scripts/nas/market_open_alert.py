#!/usr/bin/env python3.8
# -*- coding: utf-8 -*-
"""
scripts/nas/market_open_alert.py
장 시작 알림 (포트폴리오 현황)
"""
import sys
import logging
from datetime import date
from pathlib import Path

# 프로젝트 루트를 PYTHONPATH에 추가
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from extensions.monitoring import PerformanceTracker
from extensions.notification.telegram_sender import TelegramSender
from infra.logging.setup import setup_logging

# 로깅 설정
setup_logging()
logger = logging.getLogger(__name__)


def main():
    """장 시작 알림"""
    logger.info("=" * 60)
    logger.info("장 시작 알림")
    logger.info("=" * 60)
    
    try:
        # 최근 성과 조회
        perf_tracker = PerformanceTracker()
        latest = perf_tracker.get_latest_performance()
        
        if not latest:
            logger.warning("성과 데이터 없음")
            return 0
        
        # 메시지 생성
        message = "*[장 시작] 포트폴리오 현황*\n\n"
        message += f"📅 {date.today()}\n\n"
        message += f"💰 총 자산: {latest['total_value']:,.0f}원\n"
        message += f"💵 현금: {latest['cash']:,.0f}원\n"
        message += f"📊 포지션: {latest['position_count']}개\n"
        message += f"📈 누적 수익률: {latest['cumulative_return']:.2%}\n\n"
        message += "_오늘도 좋은 하루 되세요!_"
        
        # 텔레그램 전송
        sender = TelegramSender()
        success = sender.send_custom(message, parse_mode='Markdown')
        
        if success:
            logger.info("✅ 장 시작 알림 전송 성공")
        else:
            logger.warning("⚠️ 장 시작 알림 전송 실패")
        
        return 0
    
    except Exception as e:
        logger.error(f"❌ 장 시작 알림 실패: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
