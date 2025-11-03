#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Step 3 테스트: 모니터링 및 로깅 시스템
"""
from datetime import date, timedelta
from pathlib import Path
from extensions.realtime import RealtimeSignalGenerator
from extensions.monitoring import SignalTracker, PerformanceTracker, DailyReporter, RegimeDetector

print("=" * 60)
print("Step 3: 모니터링 및 로깅 시스템 테스트")
print("=" * 60)

# 테스트 날짜
test_date = date.today() - timedelta(days=1)
print(f"\n테스트 날짜: {test_date}")

# 1. 신호 추적 테스트
print("\n1. 신호 추적 테스트...")
tracker = SignalTracker()

# 테스트 신호 생성
print("   신호 생성 중...")
params = {
    'ma_period': 60,
    'rsi_period': 14,
    'rsi_overbought': 70,
    'maps_buy_threshold': 1.0,
    'maps_sell_threshold': -5.0,
    'max_positions': 10,
    'min_confidence': 0.1,
    'portfolio_vol_target': 0.15,
    'max_drawdown_threshold': -0.15,
    'cooldown_days': 7,
    'max_correlation': 0.7
}

generator = RealtimeSignalGenerator(params)

try:
    signals = generator.generate_signals(test_date)
    print(f"   생성된 신호: {len(signals)}개")
    
    if signals:
        # 신호 저장
        tracker.save_signals(signals, test_date)
        print("   ✅ 신호 DB 저장 완료")
        
        # 신호 조회
        saved_signals = tracker.get_signals(start_date=test_date, end_date=test_date)
        print(f"   조회된 신호: {len(saved_signals)}개")
        
        # 통계
        stats = tracker.get_signal_stats(days=30)
        print(f"\n   최근 30일 통계:")
        print(f"     - 총 신호: {stats['total_signals']}개")
        print(f"     - 매수: {stats['buy_count']}개")
        print(f"     - 매도: {stats['sell_count']}개")
        print(f"     - 평균 신뢰도: {stats['avg_confidence']:.2f}")
    else:
        print("   ⚠️ 신호 없음")

except Exception as e:
    print(f"   ❌ 신호 생성 실패: {e}")
    signals = []

# 2. 성과 추적 테스트
print("\n2. 성과 추적 테스트...")
perf_tracker = PerformanceTracker()

# 테스트 성과 데이터 저장
print("   테스트 성과 데이터 저장...")
perf_tracker.save_daily_performance(
    performance_date=test_date,
    total_value=10000000,  # 1000만원
    cash=2000000,  # 200만원
    positions_value=8000000,  # 800만원
    daily_return=0.015,  # 1.5%
    cumulative_return=0.12,  # 12%
    position_count=len(signals) if signals else 0
)
print("   ✅ 성과 데이터 저장 완료")

# 최근 성과 조회
latest = perf_tracker.get_latest_performance()
if latest:
    print(f"\n   최근 성과:")
    print(f"     - 날짜: {latest['date']}")
    print(f"     - 총 자산: {latest['total_value']:,.0f}원")
    print(f"     - 일일 수익률: {latest['daily_return']:.2%}")
    print(f"     - 누적 수익률: {latest['cumulative_return']:.2%}")

# 3. 일일 리포트 테스트
print("\n3. 일일 리포트 생성 테스트...")
reporter = DailyReporter(tracker, perf_tracker)

report = reporter.generate_daily_report(test_date, signals)
print("\n--- 생성된 리포트 ---")
print(report[:500])  # 처음 500자만 출력
print("...")
print("--- 리포트 끝 ---")

# 리포트 저장
output_dir = Path('reports/daily')
reporter.save_report(test_date, report, output_dir)
print(f"\n   ✅ 리포트 저장: {output_dir / f'report_{test_date:%Y%m%d}.md'}")

# 4. 레짐 감지 테스트
print("\n4. 시장 레짐 감지 테스트...")
regime_detector = RegimeDetector()

regime = regime_detector.detect_regime(test_date)
print(f"\n   레짐 정보:")
print(f"     - 상태: {regime['state']}")
print(f"     - 변동성: {regime['volatility']:.2%}")
print(f"     - 추세: {regime['trend']:+.2%}")
print(f"     - 모멘텀: {regime['momentum']:+.2%}")

# 레짐 설명
description = regime_detector.get_regime_description(regime)
print(f"\n   레짐 설명:")
for line in description.split('\n'):
    print(f"     {line}")

# 5. 주간 요약 테스트
print("\n5. 주간 요약 생성 테스트...")
weekly_summary = reporter.generate_weekly_summary(test_date)
print("\n--- 주간 요약 (일부) ---")
print(weekly_summary[:400])
print("...")
print("--- 요약 끝 ---")

# 6. DB 파일 확인
print("\n6. 생성된 DB 파일:")
db_dir = Path('data/monitoring')
if db_dir.exists():
    for db_file in db_dir.glob('*.db'):
        size = db_file.stat().st_size
        print(f"   - {db_file.name}: {size:,} bytes")

print("\n" + "=" * 60)
print("Step 3 테스트 완료!")
print("=" * 60)
print("\n다음 파일들이 생성되었습니다:")
print("  - data/monitoring/signals.db (신호 이력)")
print("  - data/monitoring/performance.db (성과 추적)")
print(f"  - reports/daily/report_{test_date:%Y%m%d}.md (일일 리포트)")
