#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
indicators.py 단위 테스트

실행: pytest tests/test_indicators.py -v
"""

import pytest
import pandas as pd
import numpy as np
from indicators import sma, ema, pct_change_n, adx, mfi, rsi, turnover_stats


class TestBasicIndicators:
    """기본 지표 테스트"""
    
    def test_sma_simple(self):
        """단순 이동평균 계산 검증"""
        data = pd.Series([10, 20, 30, 40, 50], index=pd.date_range("2025-01-01", periods=5))
        result = sma(data, 3)
        
        # 처음 2개는 NaN (min_periods=3)
        assert pd.isna(result.iloc[0])
        assert pd.isna(result.iloc[1])
        
        # 3번째부터 계산
        assert result.iloc[2] == 20.0  # (10+20+30)/3
        assert result.iloc[3] == 30.0  # (20+30+40)/3
        assert result.iloc[4] == 40.0  # (30+40+50)/3
    
    def test_ema_convergence(self):
        """지수 이동평균 수렴 검증"""
        data = pd.Series([100] * 50, index=pd.date_range("2025-01-01", periods=50))
        result = ema(data, 10)
        
        # 충분한 기간 후 원본 값에 수렴
        assert abs(result.iloc[-1] - 100.0) < 0.01
    
    def test_pct_change_n(self):
        """N일 수익률 계산 검증"""
        data = pd.Series([100, 110, 120, 130, 140], index=pd.date_range("2025-01-01", periods=5))
        result = pct_change_n(data, 2)
        
        # 2일 전 대비 수익률
        assert pd.isna(result.iloc[0])
        assert pd.isna(result.iloc[1])
        assert abs(result.iloc[2] - 0.20) < 0.01  # 120/100 - 1 = 0.20
        assert abs(result.iloc[3] - 0.18181) < 0.01  # 130/110 - 1
        assert abs(result.iloc[4] - 0.16666) < 0.01  # 140/120 - 1


class TestOscillators:
    """오실레이터 지표 테스트"""
    
    def test_rsi_extreme_values(self):
        """RSI 극단값 테스트"""
        # 지속 상승 → RSI 100에 근접
        up_trend = pd.Series(range(1, 51), index=pd.date_range("2025-01-01", periods=50))
        rsi_up = rsi(up_trend, 14)
        assert rsi_up.iloc[-1] > 90  # 강한 상승
        
        # 지속 하락 → RSI 0에 근접
        down_trend = pd.Series(range(50, 0, -1), index=pd.date_range("2025-01-01", periods=50))
        rsi_down = rsi(down_trend, 14)
        assert rsi_down.iloc[-1] < 10  # 강한 하락
    
    def test_adx_trending_market(self):
        """ADX 추세 강도 테스트"""
        # 강한 추세 시장
        dates = pd.date_range("2025-01-01", periods=50)
        high = pd.Series(range(100, 150), index=dates)
        low = pd.Series(range(90, 140), index=dates)
        close = pd.Series(range(95, 145), index=dates)
        
        adx_val = adx(high, low, close, 14)
        
        # 강한 추세에서 ADX는 높아야 함
        assert adx_val.iloc[-1] > 20
    
    def test_mfi_range(self):
        """MFI 범위 검증 (0-100)"""
        dates = pd.date_range("2025-01-01", periods=50)
        high = pd.Series(np.random.uniform(90, 110, 50), index=dates)
        low = pd.Series(np.random.uniform(80, 100, 50), index=dates)
        close = pd.Series(np.random.uniform(85, 105, 50), index=dates)
        volume = pd.Series(np.random.uniform(1000, 5000, 50), index=dates)
        
        mfi_val = mfi(high, low, close, volume, 14)
        
        # MFI는 0-100 범위
        valid = mfi_val.dropna()
        assert (valid >= 0).all()
        assert (valid <= 100).all()


class TestTurnoverStats:
    """거래대금 통계 테스트"""
    
    def test_turnover_calculation(self):
        """거래대금 = 종가 * 거래량"""
        dates = pd.date_range("2025-01-01", periods=30)
        close = pd.Series([100] * 30, index=dates)
        volume = pd.Series([1000] * 30, index=dates)
        
        mean, std, z = turnover_stats(close, volume, 20)
        
        # 일정한 거래대금 → Z-score는 0에 근접
        assert abs(z.iloc[-1]) < 0.1
        assert mean.iloc[-1] == 100000  # 100 * 1000
    
    def test_turnover_spike_detection(self):
        """거래량 급증 탐지"""
        dates = pd.date_range("2025-01-01", periods=30)
        close = pd.Series([100] * 30, index=dates)
        volume = pd.Series([1000] * 29 + [5000], index=dates)  # 마지막 날 5배 급증
        
        mean, std, z = turnover_stats(close, volume, 20)
        
        # 마지막 날 Z-score가 높아야 함
        assert z.iloc[-1] > 2.0


class TestEdgeCases:
    """엣지 케이스 테스트"""
    
    def test_empty_series(self):
        """빈 시리즈 처리"""
        empty = pd.Series([], dtype=float)
        result = sma(empty, 10)
        assert result.empty
    
    def test_insufficient_data(self):
        """데이터 부족 시 NaN 반환"""
        short = pd.Series([1, 2, 3], index=pd.date_range("2025-01-01", periods=3))
        result = sma(short, 10)  # 10일 SMA인데 데이터 3개
        assert result.isna().all()
    
    def test_nan_handling(self):
        """NaN 값 포함 시 처리"""
        data = pd.Series([10, np.nan, 30, 40, 50], index=pd.date_range("2025-01-01", periods=5))
        result = sma(data, 3)
        
        # NaN이 있어도 계산 가능한 부분은 계산
        assert not result.isna().all()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
