# -*- coding: utf-8 -*-
"""
tests/integration/test_strategy_pipeline.py
전략 파이프라인 통합 테스트
"""
import pytest
import pandas as pd
import numpy as np
from datetime import date, timedelta

from core.strategy.signals import SignalGenerator
from core.risk.manager import RiskManager
from infra.data.updater import DataUpdater


class TestStrategyPipeline:
    """전략 파이프라인 통합 테스트"""
    
    @pytest.fixture
    def signal_generator(self):
        """신호 생성기"""
        return SignalGenerator(
            ma_period=20,
            rsi_period=14,
            adx_threshold=20.0
        )
    
    @pytest.fixture
    def risk_manager(self):
        """리스크 관리자"""
        return RiskManager(
            position_cap=0.3,
            cooldown_days=3
        )
    
    @pytest.fixture
    def sample_data(self):
        """샘플 데이터 생성"""
        dates = pd.date_range(end=date.today(), periods=100, freq='D')
        
        # 상승 추세 데이터
        close = pd.Series(
            100 + np.cumsum(np.random.randn(100) * 0.5 + 0.1),
            index=dates
        )
        high = close * 1.02
        low = close * 0.98
        volume = pd.Series(
            np.random.randint(1000000, 5000000, 100),
            index=dates
        )
        
        return {
            'close': close,
            'high': high,
            'low': low,
            'volume': volume
        }
    
    @pytest.mark.integration
    def test_momentum_signal_generation(self, signal_generator, sample_data):
        """모멘텀 신호 생성 테스트"""
        result = signal_generator.generate_momentum_signal(
            close=sample_data['close'],
            high=sample_data['high'],
            low=sample_data['low'],
            volume=sample_data['volume']
        )
        
        assert 'signal' in result
        assert result['signal'] in ['BUY', 'SELL', 'HOLD']
        assert 'score' in result
        assert 'indicators' in result
        
        indicators = result['indicators']
        assert 'rsi' in indicators
        assert 'macd_histogram' in indicators
        assert 'adx' in indicators
        
        print(f"Signal: {result['signal']}, Score: {result['score']:.3f}")
        print(f"RSI: {indicators['rsi']:.2f}, ADX: {indicators['adx']:.2f}")
    
    @pytest.mark.integration
    def test_combined_signal_generation(self, signal_generator, sample_data):
        """복합 신호 생성 테스트"""
        result = signal_generator.generate_combined_signal(
            close=sample_data['close'],
            high=sample_data['high'],
            low=sample_data['low'],
            volume=sample_data['volume'],
            weights=(0.5, 0.3, 0.2)
        )
        
        assert 'signal' in result
        assert 'confidence' in result
        assert 'components' in result
        
        components = result['components']
        assert 'momentum' in components
        assert 'trend' in components
        assert 'mean_reversion' in components
        
        print(f"Combined Signal: {result['signal']}")
        print(f"Confidence: {result['confidence']:.3f}")
        print(f"Components: M={components['momentum']['signal']}, "
              f"T={components['trend']['signal']}, "
              f"MR={components['mean_reversion']['signal']}")
    
    @pytest.mark.integration
    def test_risk_position_size_check(self, risk_manager):
        """포지션 크기 검증 테스트"""
        # 정상 케이스
        ok, msg = risk_manager.check_position_size('TEST', 0.0, 0.2)
        assert ok
        
        # 한도 초과
        ok, msg = risk_manager.check_position_size('TEST', 0.0, 0.5)
        assert not ok
        assert '초과' in msg
        
        print(f"Position size check: OK")
    
    @pytest.mark.integration
    def test_risk_cooldown(self, risk_manager):
        """쿨다운 검증 테스트"""
        symbol = 'TEST'
        today = date.today()
        
        # 초기 상태 (쿨다운 없음)
        ok, remaining = risk_manager.check_cooldown(symbol, today)
        assert ok
        
        # 매도 등록
        sell_date = today - timedelta(days=1)
        risk_manager.register_sell(symbol, sell_date)
        
        # 쿨다운 중
        ok, remaining = risk_manager.check_cooldown(symbol, today)
        assert not ok
        assert remaining == 2  # 3일 - 1일
        
        # 쿨다운 완료
        future_date = today + timedelta(days=5)
        ok, remaining = risk_manager.check_cooldown(symbol, future_date)
        assert ok
        
        print(f"Cooldown check: OK")
    
    @pytest.mark.integration
    def test_risk_drawdown_check(self, risk_manager):
        """낙폭 검증 테스트"""
        # NAV 시계열 (10% 하락)
        nav = pd.Series([100, 105, 110, 100, 95, 90])
        
        ok, mdd = risk_manager.check_drawdown(nav)
        
        # MDD = (90 - 110) / 110 = -18.2%
        assert not ok  # 한도(-15%) 초과
        assert mdd < -0.15
        
        print(f"Drawdown check: MDD={mdd:.2%}")
    
    @pytest.mark.integration
    def test_full_strategy_pipeline(self, signal_generator, risk_manager, sample_data):
        """전체 전략 파이프라인 테스트"""
        # Step 1: 신호 생성
        signal_result = signal_generator.generate_combined_signal(
            close=sample_data['close'],
            high=sample_data['high'],
            low=sample_data['low'],
            volume=sample_data['volume']
        )
        
        assert signal_result['signal'] in ['BUY', 'SELL', 'HOLD']
        
        # Step 2: 매수 신호인 경우 리스크 검증
        if signal_result['signal'] == 'BUY':
            symbol = 'TEST'
            current_price = sample_data['close'].iloc[-1]
            portfolio_value = 10000000  # 1천만원
            
            # 포지션 크기 계산
            quantity = risk_manager.calculate_position_size(
                symbol=symbol,
                signal_strength=signal_result['confidence'],
                volatility=sample_data['close'].pct_change().std(),
                available_cash=portfolio_value * 0.5,
                current_price=current_price
            )
            
            assert quantity > 0
            
            # 거래 검증
            ok, warnings = risk_manager.validate_trade(
                symbol=symbol,
                action='BUY',
                quantity=quantity,
                price=current_price,
                portfolio_value=portfolio_value,
                current_holdings={},
                current_date=date.today()
            )
            
            print(f"Trade validation: {'OK' if ok else 'REJECTED'}")
            if warnings:
                print(f"Warnings: {warnings}")
            
            assert isinstance(ok, bool)
        
        print(f"Full pipeline test: PASSED")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])
