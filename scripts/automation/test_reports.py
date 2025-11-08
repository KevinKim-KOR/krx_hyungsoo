# -*- coding: utf-8 -*-
"""
scripts/automation/test_reports.py
리포트 시스템 테스트

Day 2 모듈 테스트:
- TelegramNotifier
- DailyReport
- WeeklyReport
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from datetime import date, timedelta
import logging

from extensions.automation.telegram_notifier import TelegramNotifier
from extensions.automation.daily_report import DailyReport
from extensions.automation.weekly_report import WeeklyReport

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_telegram_notifier():
    """텔레그램 알림 테스트"""
    print("\n" + "="*60)
    print("1. 텔레그램 알림 테스트")
    print("="*60)
    
    notifier = TelegramNotifier(enabled=False)  # 로그 모드
    
    # 매수 신호 테스트
    buy_signals = [
        {'code': '139260', 'maps_score': 36.97, 'confidence': 0.8},
        {'code': '395270', 'maps_score': 36.52, 'confidence': 0.75},
        {'code': '395160', 'maps_score': 35.68, 'confidence': 0.7},
    ]
    notifier.send_buy_signals(buy_signals)
    
    # 매도 신호 테스트
    sell_signals = [
        {'code': '123456', 'reason': 'negative_maps_score'},
    ]
    notifier.send_sell_signals(sell_signals)
    
    # 레짐 변경 테스트
    notifier.send_regime_change(
        old_regime='neutral',
        new_regime='bull',
        confidence=0.85,
        date_str='2025-11-08'
    )
    
    # 방어 모드 테스트
    notifier.send_defense_mode_alert(
        is_entering=True,
        reason='하락장, 신뢰도 90%',
        date_str='2025-11-08'
    )
    
    print("✅ 텔레그램 알림 테스트 완료")


def test_daily_report():
    """일일 리포트 테스트"""
    print("\n" + "="*60)
    print("2. 일일 리포트 테스트")
    print("="*60)
    
    reporter = DailyReport(telegram_enabled=False)
    
    # 리포트 생성
    report = reporter.generate_report(
        target_date=date.today(),
        current_holdings=['139260', '395270', '395160'],
        portfolio_value=11500000,
        initial_capital=10000000
    )
    
    print(report)
    print("\n✅ 일일 리포트 테스트 완료")


def test_weekly_report():
    """주간 리포트 테스트"""
    print("\n" + "="*60)
    print("3. 주간 리포트 테스트")
    print("="*60)
    
    reporter = WeeklyReport(telegram_enabled=False)
    
    # 포트폴리오 히스토리 생성 (예시)
    today = date.today()
    portfolio_history = []
    for i in range(7):
        day = today - timedelta(days=6-i)
        value = 10000000 + (i * 100000)  # 점진적 증가
        portfolio_history.append({
            'date': day,
            'value': value,
            'return_pct': ((value - 10000000) / 10000000) * 100
        })
    
    # 리포트 생성
    report = reporter.generate_report(
        end_date=today,
        portfolio_history=portfolio_history
    )
    
    print(report)
    print("\n✅ 주간 리포트 테스트 완료")


def main():
    """메인 함수"""
    print("\n" + "="*60)
    print("리포트 시스템 테스트")
    print("="*60)
    
    try:
        # 1. 텔레그램 알림 테스트
        test_telegram_notifier()
        
        # 2. 일일 리포트 테스트
        test_daily_report()
        
        # 3. 주간 리포트 테스트
        test_weekly_report()
        
        print("\n" + "="*60)
        print("✅ 모든 테스트 완료!")
        print("="*60)
        
    except Exception as e:
        logger.error(f"테스트 실패: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
