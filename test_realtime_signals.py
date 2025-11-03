#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
실시간 신호 생성 테스트 스크립트
"""
from datetime import date, timedelta
from pathlib import Path
from extensions.realtime import RealtimeSignalGenerator, PositionTracker, RealtimeDataCollector

print("=" * 60)
print("실시간 신호 생성 테스트")
print("=" * 60)

# 1. 데이터 수집 테스트
print("\n1. 데이터 수집 테스트...")
collector = RealtimeDataCollector()

# 어제 날짜로 테스트 (오늘은 데이터가 없을 수 있음)
test_date = date.today() - timedelta(days=1)
print(f"   테스트 날짜: {test_date}")

# 데이터 검증
validation = collector.validate_data(test_date)
print(f"   검증 결과:")
print(f"     - 총 종목: {validation['total']}")
print(f"     - 정상: {validation['valid']}")
print(f"     - 누락: {validation['missing']}")
print(f"     - 오래됨: {validation['outdated']}")
print(f"     - 손상: {validation['corrupted']}")

# 2. 신호 생성 테스트
print("\n2. 신호 생성 테스트...")

# 기본 파라미터 (best_params.json에서 로드 가능)
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
        # 포트폴리오 요약
        summary = generator.get_portfolio_summary(signals)
        print(f"\n   포트폴리오 요약:")
        print(f"     - 총 포지션: {summary['total_positions']}")
        print(f"     - 총 비중: {summary['total_weight']:.1%}")
        print(f"     - 평균 신뢰도: {summary['avg_confidence']:.2f}")
        print(f"     - 매수: {summary['buy_count']}, 매도: {summary['sell_count']}, 유지: {summary['hold_count']}")
        
        # 상위 신호
        print(f"\n   상위 5개 신호:")
        for i, signal in enumerate(summary['top_signals'], 1):
            print(f"     {i}. {signal.code} ({signal.name})")
            print(f"        액션: {signal.action}, 비중: {signal.target_weight:.1%}, 신뢰도: {signal.confidence:.2f}")
            print(f"        가격: {signal.current_price:,.0f}원, MAPS: {signal.maps_score:.2f}")
        
        # 신호 저장
        output_path = Path(f"reports/realtime/signals_{test_date:%Y%m%d}.csv")
        generator.save_signals(signals, output_path)
        print(f"\n   신호 저장: {output_path}")
    else:
        print("   ⚠️ 신호 없음 (데이터 부족 또는 조건 미충족)")

except Exception as e:
    print(f"   ❌ 신호 생성 실패: {e}")
    import traceback
    traceback.print_exc()

# 3. 포지션 추적 테스트
print("\n3. 포지션 추적 테스트...")
tracker = PositionTracker()

# 현재 가격 (신호에서 추출)
current_prices = {s.code: s.current_price for s in signals} if signals else {}

# 현재 포지션 조회
current_positions = tracker.get_current_positions(current_prices)
print(f"   현재 포지션: {len(current_positions)}개")

if current_positions:
    total_value = sum(pos.market_value for pos in current_positions)
    print(f"   총 가치: {total_value:,.0f}원")
    
    for pos in current_positions[:5]:
        print(f"     - {pos.code}: {pos.quantity}주, {pos.market_value:,.0f}원 ({pos.weight:.1%})")

# 리밸런싱 액션
if signals and current_prices:
    target_weights = {s.code: s.target_weight for s in signals}
    actions = tracker.get_rebalancing_actions(
        current_positions,
        target_weights,
        current_prices
    )
    
    print(f"\n   리밸런싱 액션: {len(actions)}개")
    
    # 매수/매도 액션만 표시
    active_actions = [a for a in actions if a.action_type != 'HOLD']
    print(f"   실행 필요: {len(active_actions)}개")
    
    for action in active_actions[:10]:
        print(f"     - {action.action_type} {action.code}: {abs(action.quantity_diff)}주")
        print(f"       현재 비중: {action.current_weight:.1%} → 목표: {action.target_weight:.1%}")
        print(f"       예상 금액: {action.estimated_amount:,.0f}원")

print("\n" + "=" * 60)
print("테스트 완료!")
print("=" * 60)
