#!/usr/bin/env python3.8
# -*- coding: utf-8 -*-
"""
scripts/nas/market_open_alert.py
장 시작 알림 (포트폴리오 현황)
"""
import sys
from datetime import date
from pathlib import Path

# 프로젝트 루트를 PYTHONPATH에 추가
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from extensions.automation.script_base import ScriptBase, handle_script_errors
from extensions.automation.portfolio_helper import PortfolioHelper
from extensions.notification.telegram_helper import TelegramHelper

# 스크립트 베이스 초기화
script = ScriptBase("market_open_alert")
logger = script.logger


@handle_script_errors("장 시작 알림")
def main():
    """장 시작 알림 (실제 포트폴리오 기반)"""
    script.log_header("장 시작 알림")
    
    # 포트폴리오 로드
    portfolio = PortfolioHelper()
    data = portfolio.load_full_data()
    
    if not data or not data.get('summary'):
        logger.warning("포트폴리오 데이터 없음")
        return 0
    
    summary = data['summary']
    holdings_count = data['holdings_count']
    
    # 메시지 생성
    message = "*[장 시작] 포트폴리오 현황*\n\n"
    message += f"📅 {date.today().strftime('%Y년 %m월 %d일 (%A)')}\n\n"
    message += f"💰 총 평가액: `{summary['total_value']:,.0f}원`\n"
    message += f"💵 총 매입액: `{summary['total_cost']:,.0f}원`\n"
    message += f"📈 평가손익: {PortfolioHelper.format_return(summary['return_amount'], summary['return_pct'])}\n"
    message += f"📊 보유 종목: `{holdings_count}개`\n\n"
    message += "_오늘도 좋은 하루 되세요!_ 🚀"
    
    # 텔레그램 전송
    telegram = TelegramHelper()
    telegram.send_with_logging(
        message,
        "장 시작 알림 전송 성공",
        "장 시작 알림 전송 실패"
    )
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
