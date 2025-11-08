# -*- coding: utf-8 -*-
"""
scripts/automation/run_daily_report.py
일일 리포트 실행 스크립트

NAS Cron에서 실행:
    0 16 * * 1-5 python3 /path/to/run_daily_report.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import os
from datetime import date
import logging

from extensions.automation.daily_report import DailyReport

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """메인 함수"""
    try:
        # 환경 변수 로드
        bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        chat_id = os.getenv('TELEGRAM_CHAT_ID')
        
        # 텔레그램 활성화 여부
        telegram_enabled = bool(bot_token and chat_id)
        
        if not telegram_enabled:
            logger.warning("텔레그램 설정이 없습니다. 로그 모드로 실행합니다.")
        
        # 리포트 생성
        reporter = DailyReport(
            telegram_enabled=telegram_enabled,
            bot_token=bot_token,
            chat_id=chat_id
        )
        
        # 실행
        logger.info("일일 리포트 생성 시작")
        
        report = reporter.generate_report(
            target_date=date.today(),
            current_holdings=[],  # TODO: 실제 보유 종목 입력
            portfolio_value=None,  # TODO: 실제 포트폴리오 가치 입력
            initial_capital=10000000
        )
        
        print(report)
        logger.info("일일 리포트 생성 완료")
        
    except Exception as e:
        logger.error(f"일일 리포트 생성 실패: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
