#!/usr/bin/env python3.8
# -*- coding: utf-8 -*-
"""
scripts/nas/daily_report_alert.py
일일 리포트 알림 (실제 포트폴리오 기반)
"""
import sys
import os
from datetime import date
from pathlib import Path
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 프로젝트 루트를 PYTHONPATH에 추가
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from extensions.automation.script_base import ScriptBase, handle_script_errors
from extensions.automation.daily_report import DailyReport

# 스크립트 베이스 초기화
script = ScriptBase("daily_report_alert")
logger = script.logger


@handle_script_errors("일일 리포트")
def main():
    """메인 실행 함수"""
    script.log_header("일일 리포트 생성 시작")
    
    print("=" * 60)
    print("일일 리포트 생성 시작")
    print("=" * 60)
    
    # 텔레그램 설정
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    
    if not bot_token or not chat_id:
        logger.warning("텔레그램 설정 없음 - 콘솔 출력만")
        print("⚠️ 텔레그램 설정 없음 (.env 파일 확인)")
        telegram_enabled = False
    else:
        telegram_enabled = True
        print(f"✅ 텔레그램 설정 확인")
    
    # 일일 리포트 생성
    reporter = DailyReport(
        telegram_enabled=telegram_enabled,
        bot_token=bot_token,
        chat_id=chat_id
    )
    
    # 리포트 생성 (실제 포트폴리오 기반)
    report = reporter.generate_report(target_date=date.today())
    
    # 콘솔 출력
    print("\n" + "=" * 60)
    print("일일 리포트")
    print("=" * 60)
    print(report)
    print("=" * 60)
    
    if telegram_enabled:
        logger.info("✅ 일일 리포트 생성 및 텔레그램 전송 완료")
        print("✅ 텔레그램 전송 완료")
    else:
        logger.info("✅ 일일 리포트 생성 완료 (텔레그램 미전송)")
        print("✅ 리포트 생성 완료")
    
    script.log_footer()
    return 0


if __name__ == "__main__":
    sys.exit(main())
