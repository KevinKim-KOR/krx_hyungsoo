# -*- coding: utf-8 -*-
"""
extensions/strategy/signal_generator.py
MAPS 전략 신호 생성기
"""
import logging
from datetime import date
from typing import Dict, List
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class SignalGenerator:
    """MAPS 전략 신호 생성기"""
    
    def __init__(
        self,
        ma_period: int = 60,
        rsi_period: int = 14,
        rsi_overbought: int = 70,
        maps_buy_threshold: float = 1.0,
        maps_sell_threshold: float = -5.0
    ):
        """
        Args:
            ma_period: 이동평균 기간
            rsi_period: RSI 기간
            rsi_overbought: RSI 과매수 임계값
            maps_buy_threshold: MAPS 매수 임계값
            maps_sell_threshold: MAPS 매도 임계값
        """
        self.ma_period = ma_period
        self.rsi_period = rsi_period
        self.rsi_overbought = rsi_overbought
        self.maps_buy_threshold = maps_buy_threshold
        self.maps_sell_threshold = maps_sell_threshold
        
        logger.info(f"SignalGenerator 초기화: MA={ma_period}, RSI={rsi_period}")
    
    def generate_signals(
        self,
        price_data: pd.DataFrame,
        target_date: date
    ) -> List[Dict]:
        """
        매매 신호 생성
        
        Args:
            price_data: 가격 데이터 (MultiIndex: code, date)
            target_date: 신호 생성 날짜
            
        Returns:
            신호 리스트
        """
        signals = []
        
        # 종목별 처리
        codes = price_data.index.get_level_values(0).unique()
        
        for code in codes:
            try:
                # 종목 데이터 추출
                symbol_data = price_data.xs(code, level=0)
                
                if len(symbol_data) < self.ma_period:
                    continue
                
                # 지표 계산
                indicators = self._calculate_indicators(symbol_data)
                
                # 신호 생성
                signal = self._generate_signal(code, indicators, target_date)
                
                if signal:
                    signals.append(signal)
            
            except Exception as e:
                logger.debug(f"[{code}] 신호 생성 실패: {e}")
                continue
        
        return signals
    
    def _calculate_indicators(self, data: pd.DataFrame) -> Dict:
        """
        기술적 지표 계산
        
        Args:
            data: 종목 가격 데이터
            
        Returns:
            지표 딕셔너리
        """
        close = data['close']
        
        # 이동평균
        ma = close.rolling(window=self.ma_period).mean()
        
        # RSI
        rsi = self._calculate_rsi(close, self.rsi_period)
        
        # 모멘텀 (20일)
        momentum = close.pct_change(20)
        
        # MAPS 점수 (간단한 버전)
        # MA 위치 점수
        ma_score = ((close - ma) / ma * 100).fillna(0)
        
        # RSI 점수 (과매수 페널티)
        rsi_score = (50 - rsi) / 10  # RSI 50 기준, 낮을수록 좋음
        
        # 모멘텀 점수
        momentum_score = momentum * 100
        
        # MAPS = MA점수 + RSI점수 + 모멘텀점수
        maps = ma_score + rsi_score + momentum_score
        
        return {
            'ma': ma.iloc[-1] if len(ma) > 0 else 0,
            'rsi': rsi.iloc[-1] if len(rsi) > 0 else 50,
            'momentum': momentum.iloc[-1] if len(momentum) > 0 else 0,
            'maps': maps.iloc[-1] if len(maps) > 0 else 0,
            'close': close.iloc[-1] if len(close) > 0 else 0
        }
    
    def _calculate_rsi(self, prices: pd.Series, period: int) -> pd.Series:
        """RSI 계산"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def _generate_signal(
        self,
        code: str,
        indicators: Dict,
        target_date: date
    ) -> Dict:
        """
        개별 신호 생성
        
        Args:
            code: 종목 코드
            indicators: 지표 딕셔너리
            target_date: 신호 날짜
            
        Returns:
            신호 딕셔너리 또는 None
        """
        maps = indicators['maps']
        rsi = indicators['rsi']
        
        # 매수 신호
        if maps >= self.maps_buy_threshold and rsi < self.rsi_overbought:
            confidence = min(maps / 10, 1.0)  # 0~1 정규화
            
            return {
                'code': code,
                'name': code,
                'action': 'BUY',
                'confidence': confidence,
                'ma': indicators['ma'],
                'rsi': indicators['rsi'],
                'maps': maps,
                'momentum': indicators['momentum'],
                'close': indicators['close'],
                'reason': f"MAPS={maps:.1f}, RSI={rsi:.0f}"
            }
        
        # 매도 신호
        elif maps <= self.maps_sell_threshold:
            return {
                'code': code,
                'name': code,
                'action': 'SELL',
                'confidence': 0.0,
                'ma': indicators['ma'],
                'rsi': indicators['rsi'],
                'maps': maps,
                'momentum': indicators['momentum'],
                'close': indicators['close'],
                'reason': f"MAPS={maps:.1f} (약세)"
            }
        
        return None
