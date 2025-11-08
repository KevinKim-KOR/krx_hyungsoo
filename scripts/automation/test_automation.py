# -*- coding: utf-8 -*-
"""
scripts/automation/test_automation.py
자동화 시스템 테스트

Day 1 모듈 테스트:
- DataUpdater
- RegimeMonitor
- AutoSignalGenerator
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from datetime import date
import logging

from extensions.automation.data_updater import DataUpdater
from extensions.automation.regime_monitor import RegimeMonitor
from extensions.automation.signal_generator import AutoSignalGenerator

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_data_updater():
    """데이터 수집 테스트"""
    print("\n" + "="*60)
    print("1. 데이터 수집 테스트")
    print("="*60)
    
    updater = DataUpdater()
    
    # 최신 날짜 조회
    latest_date = updater.get_latest_date()
    print(f"최신 데이터 날짜: {latest_date}")
    
    # KOSPI 데이터 수집
    kospi_data = updater.update_kospi_index()
    if kospi_data is not None:
        print(f"✅ KOSPI 데이터: {len(kospi_data)}일")
        print(f"   기간: {kospi_data.index[0].date()} ~ {kospi_data.index[-1].date()}")
    else:
        print("❌ KOSPI 데이터 수집 실패")


def test_regime_monitor():
    """레짐 감지 테스트"""
    print("\n" + "="*60)
    print("2. 레짐 감지 테스트")
    print("="*60)
    
    monitor = RegimeMonitor()
    
    # 현재 레짐 분석
    result = monitor.analyze_daily_regime()
    if result:
        print(f"✅ 레짐 분석 완료:")
        print(f"   날짜: {result['date']}")
        print(f"   레짐: {result['regime']}")
        print(f"   신뢰도: {result['confidence']:.2%}")
        print(f"   포지션 비율: {result['position_ratio']:.0%}")
        print(f"   방어 모드: {'예' if result['defense_mode'] else '아니오'}")
    else:
        print("❌ 레짐 분석 실패")
    
    # 레짐 변경 감지
    change = monitor.check_regime_change()
    if change:
        print(f"\n🔄 레짐 변경 감지!")
        print(f"   {change['old_regime']} → {change['new_regime']}")
    else:
        print("\n레짐 변경 없음")
    
    # 요약 통계
    summary = monitor.get_regime_summary(days=30)
    if summary:
        print(f"\n📊 최근 30일 통계:")
        print(f"   총 일수: {summary['total_days']}일")
        print(f"   레짐 변경: {summary['regime_changes']}회")
        print(f"   레짐 분포: {summary['regime_counts']}")


def test_signal_generator():
    """매매 신호 생성 테스트"""
    print("\n" + "="*60)
    print("3. 매매 신호 생성 테스트")
    print("="*60)
    
    generator = AutoSignalGenerator(max_positions=10)
    
    # 신호 생성
    signals = generator.generate_daily_signals(
        current_holdings=[]  # 빈 포트폴리오로 시작
    )
    
    # 결과 출력
    formatted = generator.format_signals_for_display(signals)
    print(formatted)


def main():
    """메인 함수"""
    print("\n" + "="*60)
    print("자동화 시스템 테스트")
    print("="*60)
    
    try:
        # 1. 데이터 수집 테스트
        test_data_updater()
        
        # 2. 레짐 감지 테스트
        test_regime_monitor()
        
        # 3. 매매 신호 생성 테스트
        test_signal_generator()
        
        print("\n" + "="*60)
        print("✅ 모든 테스트 완료!")
        print("="*60)
        
    except Exception as e:
        logger.error(f"테스트 실패: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
