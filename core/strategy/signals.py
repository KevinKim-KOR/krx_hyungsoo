# -*- coding: utf-8 -*-
"""
core/strategy/signals.py
매매 신호 생성 로직 (친구 코드 참고)
"""
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np
from core.indicators import (
    sma, ema, rsi, macd, adx, mfi,
    bollinger_bands, stochastic, williams_r
)


class SignalGenerator:
    """매매 신호 생성기"""
    
    def __init__(
        self,
        ma_period: int = 60,
        rsi_period: int = 14,
        rsi_overbought: int = 70,
        rsi_oversold: int = 30,
        adx_threshold: float = 25.0,
        mfi_threshold: float = 40.0
    ):
        """
        Args:
            ma_period: 이동평균 기간
            rsi_period: RSI 기간
            rsi_overbought: RSI 과매수 기준
            rsi_oversold: RSI 과매도 기준
            adx_threshold: ADX 최소 기준 (추세 강도)
            mfi_threshold: MFI 최소 기준
        """
        self.ma_period = ma_period
        self.rsi_period = rsi_period
        self.rsi_overbought = rsi_overbought
        self.rsi_oversold = rsi_oversold
        self.adx_threshold = adx_threshold
        self.mfi_threshold = mfi_threshold
    
    def generate_momentum_signal(
        self,
        close: pd.Series,
        high: Optional[pd.Series] = None,
        low: Optional[pd.Series] = None,
        volume: Optional[pd.Series] = None
    ) -> Dict[str, any]:
        """
        모멘텀 신호 생성
        
        Returns:
            {
                'signal': 'BUY' | 'SELL' | 'HOLD',
                'score': float,
                'indicators': {...}
            }
        """
        # 1. 이동평균
        ma = sma(close, self.ma_period)
        price_vs_ma = (close.iloc[-1] / ma.iloc[-1] - 1.0) * 100 if not ma.empty else 0.0
        
        # 2. RSI
        rsi_val = rsi(close, self.rsi_period).iloc[-1] if len(close) >= self.rsi_period else 50.0
        
        # 3. MACD
        macd_line, signal_line, histogram = macd(close)
        macd_cross = histogram.iloc[-1] if not histogram.empty else 0.0
        
        # 4. ADX (추세 강도)
        adx_val = 0.0
        if high is not None and low is not None:
            adx_series = adx(high, low, close)
            adx_val = adx_series.iloc[-1] if not adx_series.empty else 0.0
        
        # 5. MFI (자금 흐름)
        mfi_val = 50.0
        if high is not None and low is not None and volume is not None:
            mfi_series = mfi(high, low, close, volume)
            mfi_val = mfi_series.iloc[-1] if not mfi_series.empty else 50.0
        
        # 신호 판단
        signal = 'HOLD'
        score = 0.0
        
        # 매수 조건
        buy_conditions = [
            price_vs_ma > 0,  # 이동평균 위
            rsi_val < self.rsi_overbought,  # 과매수 아님
            macd_cross > 0,  # MACD 골든크로스
            adx_val > self.adx_threshold,  # 추세 강함
            mfi_val > self.mfi_threshold  # 자금 유입
        ]
        
        # 매도 조건
        sell_conditions = [
            price_vs_ma < -5,  # 이동평균 5% 이하
            rsi_val > self.rsi_overbought,  # 과매수
            macd_cross < 0,  # MACD 데드크로스
        ]
        
        if sum(buy_conditions) >= 3:
            signal = 'BUY'
            score = sum(buy_conditions) / len(buy_conditions)
        elif sum(sell_conditions) >= 2:
            signal = 'SELL'
            score = -sum(sell_conditions) / len(sell_conditions)
        
        return {
            'signal': signal,
            'score': score,
            'indicators': {
                'price_vs_ma': price_vs_ma,
                'rsi': rsi_val,
                'macd_histogram': macd_cross,
                'adx': adx_val,
                'mfi': mfi_val
            }
        }
    
    def generate_trend_following_signal(
        self,
        close: pd.Series,
        high: Optional[pd.Series] = None,
        low: Optional[pd.Series] = None
    ) -> Dict[str, any]:
        """
        추세 추종 신호 생성 (친구 코드 참고)
        
        Returns:
            {
                'signal': 'BUY' | 'SELL' | 'HOLD',
                'trend_strength': float,
                'indicators': {...}
            }
        """
        # 1. 이동평균 (단기/장기)
        ma_short = sma(close, 20)
        ma_long = sma(close, 60)
        
        ma_cross = 0.0
        if not ma_short.empty and not ma_long.empty:
            ma_cross = (ma_short.iloc[-1] / ma_long.iloc[-1] - 1.0) * 100
        
        # 2. ADX (추세 강도)
        adx_val = 0.0
        if high is not None and low is not None:
            adx_series = adx(high, low, close)
            adx_val = adx_series.iloc[-1] if not adx_series.empty else 0.0
        
        # 3. 가격 모멘텀
        momentum_20 = (close.iloc[-1] / close.iloc[-20] - 1.0) * 100 if len(close) >= 20 else 0.0
        momentum_60 = (close.iloc[-1] / close.iloc[-60] - 1.0) * 100 if len(close) >= 60 else 0.0
        
        # 신호 판단
        signal = 'HOLD'
        trend_strength = 0.0
        
        # 상승 추세
        if ma_cross > 0 and adx_val > 25 and momentum_20 > 0:
            signal = 'BUY'
            trend_strength = min(adx_val / 50.0, 1.0)  # 0~1 정규화
        # 하락 추세
        elif ma_cross < -5 or momentum_20 < -10:
            signal = 'SELL'
            trend_strength = -min(abs(ma_cross) / 10.0, 1.0)
        
        return {
            'signal': signal,
            'trend_strength': trend_strength,
            'indicators': {
                'ma_cross': ma_cross,
                'adx': adx_val,
                'momentum_20': momentum_20,
                'momentum_60': momentum_60
            }
        }
    
    def generate_mean_reversion_signal(
        self,
        close: pd.Series,
        high: Optional[pd.Series] = None,
        low: Optional[pd.Series] = None
    ) -> Dict[str, any]:
        """
        평균 회귀 신호 생성
        
        Returns:
            {
                'signal': 'BUY' | 'SELL' | 'HOLD',
                'deviation': float,
                'indicators': {...}
            }
        """
        # 1. Bollinger Bands
        upper, middle, lower = bollinger_bands(close, n=20, std_dev=2.0)
        
        bb_position = 0.5
        if not upper.empty and not lower.empty:
            bb_width = upper.iloc[-1] - lower.iloc[-1]
            if bb_width > 0:
                bb_position = (close.iloc[-1] - lower.iloc[-1]) / bb_width
        
        # 2. RSI
        rsi_val = rsi(close, 14).iloc[-1] if len(close) >= 14 else 50.0
        
        # 3. Williams %R
        wr_val = 0.0
        if high is not None and low is not None:
            wr_series = williams_r(high, low, close, 14)
            wr_val = wr_series.iloc[-1] if not wr_series.empty else -50.0
        
        # 신호 판단
        signal = 'HOLD'
        deviation = bb_position - 0.5  # -0.5 ~ +0.5
        
        # 과매도 (매수 기회)
        if bb_position < 0.2 and rsi_val < 30 and wr_val < -80:
            signal = 'BUY'
        # 과매수 (매도 기회)
        elif bb_position > 0.8 and rsi_val > 70 and wr_val > -20:
            signal = 'SELL'
        
        return {
            'signal': signal,
            'deviation': deviation,
            'indicators': {
                'bb_position': bb_position,
                'rsi': rsi_val,
                'williams_r': wr_val
            }
        }
    
    def generate_combined_signal(
        self,
        close: pd.Series,
        high: Optional[pd.Series] = None,
        low: Optional[pd.Series] = None,
        volume: Optional[pd.Series] = None,
        weights: Tuple[float, float, float] = (0.5, 0.3, 0.2)
    ) -> Dict[str, any]:
        """
        복합 신호 생성 (모멘텀 + 추세 + 평균회귀)
        
        Args:
            weights: (모멘텀, 추세, 평균회귀) 가중치
            
        Returns:
            {
                'signal': 'BUY' | 'SELL' | 'HOLD',
                'confidence': float,
                'components': {...}
            }
        """
        # 1. 각 전략 신호 생성
        momentum = self.generate_momentum_signal(close, high, low, volume)
        trend = self.generate_trend_following_signal(close, high, low)
        mean_rev = self.generate_mean_reversion_signal(close, high, low)
        
        # 2. 신호 점수 계산
        signal_scores = {
            'BUY': 0.0,
            'SELL': 0.0,
            'HOLD': 0.0
        }
        
        # 모멘텀
        if momentum['signal'] == 'BUY':
            signal_scores['BUY'] += weights[0] * abs(momentum['score'])
        elif momentum['signal'] == 'SELL':
            signal_scores['SELL'] += weights[0] * abs(momentum['score'])
        else:
            signal_scores['HOLD'] += weights[0]
        
        # 추세
        if trend['signal'] == 'BUY':
            signal_scores['BUY'] += weights[1] * abs(trend['trend_strength'])
        elif trend['signal'] == 'SELL':
            signal_scores['SELL'] += weights[1] * abs(trend['trend_strength'])
        else:
            signal_scores['HOLD'] += weights[1]
        
        # 평균회귀
        if mean_rev['signal'] == 'BUY':
            signal_scores['BUY'] += weights[2]
        elif mean_rev['signal'] == 'SELL':
            signal_scores['SELL'] += weights[2]
        else:
            signal_scores['HOLD'] += weights[2]
        
        # 3. 최종 신호 결정
        final_signal = max(signal_scores, key=signal_scores.get)
        confidence = signal_scores[final_signal]
        
        return {
            'signal': final_signal,
            'confidence': confidence,
            'components': {
                'momentum': momentum,
                'trend': trend,
                'mean_reversion': mean_rev
            },
            'scores': signal_scores
        }


def create_default_signal_generator() -> SignalGenerator:
    """기본 신호 생성기 생성"""
    return SignalGenerator(
        ma_period=60,
        rsi_period=14,
        rsi_overbought=70,
        rsi_oversold=30,
        adx_threshold=25.0,
        mfi_threshold=40.0
    )
