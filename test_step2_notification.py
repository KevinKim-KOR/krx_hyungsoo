#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Step 2 테스트: 텔레그램 알림 시스템
"""
from datetime import date, timedelta
from pathlib import Path
from extensions.realtime import RealtimeSignalGenerator
from extensions.notification import send_daily_signals

print("=" * 60)
print("Step 2: 텔레그램 알림 시스템 테스트")
print("=" * 60)

# 1. 파라미터 로드
print("\n1. 파라미터 로드...")
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
print(f"   파라미터: {params}")

# 2. 신호 생성
print("\n2. 신호 생성...")
test_date = date.today() - timedelta(days=1)
print(f"   테스트 날짜: {test_date}")

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
        
        # 3. 메시지 포맷 테스트
        print("\n3. 메시지 포맷 테스트...")
        from extensions.notification.formatter import format_daily_signals
        
        message = format_daily_signals(signals, test_date)
        print("\n--- 생성된 메시지 ---")
        print(message)
        print("--- 메시지 끝 ---")
        
        # 4. 텔레그램 전송 테스트
        print("\n4. 텔레그램 전송 테스트...")
        
        # 텔레그램 설정 확인
        try:
            from infra.notify.telegram import TelegramNotifier
            notifier = TelegramNotifier()
            print("   ✅ 텔레그램 설정 확인됨")
            
            # 전송 여부 확인
            response = input("\n   실제로 텔레그램 메시지를 전송하시겠습니까? (y/N): ")
            
            if response.lower() == 'y':
                success = send_daily_signals(signals, test_date, summary)
                
                if success:
                    print("   ✅ 텔레그램 알림 전송 성공!")
                else:
                    print("   ❌ 텔레그램 알림 전송 실패")
            else:
                print("   ⏭️  전송 건너뜀")
        
        except Exception as e:
            print(f"   ⚠️ 텔레그램 설정 오류: {e}")
            print("   secret/config.yaml 파일을 확인하세요.")
    
    else:
        print("   ⚠️ 신호 없음 (데이터 부족 또는 조건 미충족)")
        print("   테스트 메시지만 전송합니다...")
        
        # 테스트 메시지
        from extensions.notification.telegram_sender import TelegramSender
        
        try:
            sender = TelegramSender()
            test_message = f"""*[테스트] 알림 시스템 점검*

📅 날짜: {test_date}
📊 신호 수: 0개

⚠️ 오늘은 매수 신호가 없습니다.

_이 메시지는 테스트 메시지입니다._
"""
            
            response = input("\n   테스트 메시지를 전송하시겠습니까? (y/N): ")
            
            if response.lower() == 'y':
                success = sender.send_custom(test_message)
                
                if success:
                    print("   ✅ 테스트 메시지 전송 성공!")
                else:
                    print("   ❌ 테스트 메시지 전송 실패")
            else:
                print("   ⏭️  전송 건너뜀")
        
        except Exception as e:
            print(f"   ⚠️ 텔레그램 설정 오류: {e}")

except Exception as e:
    print(f"   ❌ 신호 생성 실패: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("Step 2 테스트 완료!")
print("=" * 60)
