#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
pc/ml/feature_engineering.py
ML 모델을 위한 특징 엔지니어링

MAPS 점수를 개선하기 위한 추가 특징 생성:
- 기술적 지표 (RSI, MACD, Bollinger Bands)
- 모멘텀 지표 (ROC, MOM)
- 변동성 지표 (ATR, Historical Volatility)
- 거시 지표 (KOSPI 상관관계, 섹터 강도)
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class FeatureEngineer:
    """특징 엔지니어링 클래스"""
    
    def __init__(self):
        """초기화"""
        pass
    
    def calculate_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        기술적 지표 계산
        
        Args:
            df: OHLCV 데이터프레임 (columns: open, high, low, close, volume)
        
        Returns:
            특징이 추가된 데이터프레임
        """
        df = df.copy()
        
        # 1. RSI (Relative Strength Index)
        df['rsi_14'] = self._calculate_rsi(df['close'], period=14)
        df['rsi_28'] = self._calculate_rsi(df['close'], period=28)
        
        # 2. MACD (Moving Average Convergence Divergence)
        macd, signal, hist = self._calculate_macd(df['close'])
        df['macd'] = macd
        df['macd_signal'] = signal
        df['macd_hist'] = hist
        
        # 3. Bollinger Bands
        bb_upper, bb_middle, bb_lower = self._calculate_bollinger_bands(df['close'])
        df['bb_upper'] = bb_upper
        df['bb_middle'] = bb_middle
        df['bb_lower'] = bb_lower
        df['bb_width'] = (bb_upper - bb_lower) / bb_middle
        df['bb_position'] = (df['close'] - bb_lower) / (bb_upper - bb_lower)
        
        # 4. Moving Averages
        for period in [5, 10, 20, 50, 100, 200]:
            df[f'ma_{period}'] = df['close'].rolling(window=period).mean()
            df[f'ma_{period}_diff'] = (df['close'] - df[f'ma_{period}']) / df[f'ma_{period}']
        
        # 5. Volume Indicators
        df['volume_ma_20'] = df['volume'].rolling(window=20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_ma_20']
        
        logger.info(f"✅ 기술적 지표 계산 완료: {len(df)}행")
        return df
    
    def calculate_momentum_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        모멘텀 지표 계산
        
        Args:
            df: 가격 데이터프레임
        
        Returns:
            모멘텀 특징이 추가된 데이터프레임
        """
        df = df.copy()
        
        # 1. Rate of Change (ROC)
        for period in [5, 10, 20, 60]:
            df[f'roc_{period}'] = df['close'].pct_change(periods=period)
        
        # 2. Momentum (MOM)
        for period in [5, 10, 20]:
            df[f'mom_{period}'] = df['close'] - df['close'].shift(period)
        
        # 3. Stochastic Oscillator
        df['stoch_k'], df['stoch_d'] = self._calculate_stochastic(df)
        
        # 4. Williams %R
        df['williams_r'] = self._calculate_williams_r(df)
        
        logger.info(f"✅ 모멘텀 지표 계산 완료: {len(df)}행")
        return df
    
    def calculate_volatility_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        변동성 지표 계산
        
        Args:
            df: 가격 데이터프레임
        
        Returns:
            변동성 특징이 추가된 데이터프레임
        """
        df = df.copy()
        
        # 1. ATR (Average True Range)
        df['atr_14'] = self._calculate_atr(df, period=14)
        df['atr_28'] = self._calculate_atr(df, period=28)
        
        # 2. Historical Volatility
        for period in [10, 20, 60]:
            df[f'volatility_{period}'] = df['close'].pct_change().rolling(window=period).std() * np.sqrt(252)
        
        # 3. Parkinson's Volatility (High-Low)
        df['parkinson_vol'] = np.sqrt(
            (1 / (4 * np.log(2))) * 
            np.log(df['high'] / df['low']) ** 2
        ).rolling(window=20).mean()
        
        logger.info(f"✅ 변동성 지표 계산 완료: {len(df)}행")
        return df
    
    def calculate_macro_indicators(
        self, 
        df: pd.DataFrame, 
        kospi_df: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """
        거시 지표 계산
        
        Args:
            df: 종목 가격 데이터프레임
            kospi_df: KOSPI 지수 데이터프레임
        
        Returns:
            거시 특징이 추가된 데이터프레임
        """
        df = df.copy()
        
        # 1. KOSPI 상관관계 (있으면)
        if kospi_df is not None:
            # 60일 rolling correlation
            df['kospi_corr_60'] = df['close'].pct_change().rolling(window=60).corr(
                kospi_df['close'].pct_change()
            )
        
        # 2. 베타 계산 (KOSPI 대비)
        if kospi_df is not None:
            df['beta_60'] = self._calculate_beta(df['close'], kospi_df['close'], period=60)
        
        logger.info(f"✅ 거시 지표 계산 완료: {len(df)}행")
        return df
    
    def create_features(
        self, 
        df: pd.DataFrame,
        kospi_df: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """
        모든 특징 생성
        
        Args:
            df: OHLCV 데이터프레임
            kospi_df: KOSPI 지수 데이터프레임 (선택)
        
        Returns:
            모든 특징이 추가된 데이터프레임
        """
        logger.info("=" * 60)
        logger.info("특징 엔지니어링 시작")
        logger.info("=" * 60)
        
        # 1. 기술적 지표
        df = self.calculate_technical_indicators(df)
        
        # 2. 모멘텀 지표
        df = self.calculate_momentum_indicators(df)
        
        # 3. 변동성 지표
        df = self.calculate_volatility_indicators(df)
        
        # 4. 거시 지표
        df = self.calculate_macro_indicators(df, kospi_df)
        
        # 5. NaN 제거 (초기 기간)
        original_len = len(df)
        df = df.dropna()
        logger.info(f"NaN 제거: {original_len}행 → {len(df)}행")
        
        logger.info("=" * 60)
        logger.info(f"✨ 특징 엔지니어링 완료: {len(df.columns)}개 컬럼")
        logger.info("=" * 60)
        
        return df
    
    # ============================================================
    # Private Methods (지표 계산 헬퍼)
    # ============================================================
    
    def _calculate_rsi(self, series: pd.Series, period: int = 14) -> pd.Series:
        """RSI 계산"""
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def _calculate_macd(
        self, 
        series: pd.Series, 
        fast: int = 12, 
        slow: int = 26, 
        signal: int = 9
    ) -> tuple:
        """MACD 계산"""
        ema_fast = series.ewm(span=fast, adjust=False).mean()
        ema_slow = series.ewm(span=slow, adjust=False).mean()
        macd = ema_fast - ema_slow
        macd_signal = macd.ewm(span=signal, adjust=False).mean()
        macd_hist = macd - macd_signal
        return macd, macd_signal, macd_hist
    
    def _calculate_bollinger_bands(
        self, 
        series: pd.Series, 
        period: int = 20, 
        std_dev: float = 2.0
    ) -> tuple:
        """Bollinger Bands 계산"""
        middle = series.rolling(window=period).mean()
        std = series.rolling(window=period).std()
        upper = middle + (std * std_dev)
        lower = middle - (std * std_dev)
        return upper, middle, lower
    
    def _calculate_stochastic(
        self, 
        df: pd.DataFrame, 
        k_period: int = 14, 
        d_period: int = 3
    ) -> tuple:
        """Stochastic Oscillator 계산"""
        low_min = df['low'].rolling(window=k_period).min()
        high_max = df['high'].rolling(window=k_period).max()
        k = 100 * (df['close'] - low_min) / (high_max - low_min)
        d = k.rolling(window=d_period).mean()
        return k, d
    
    def _calculate_williams_r(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Williams %R 계산"""
        high_max = df['high'].rolling(window=period).max()
        low_min = df['low'].rolling(window=period).min()
        williams_r = -100 * (high_max - df['close']) / (high_max - low_min)
        return williams_r
    
    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """ATR (Average True Range) 계산"""
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = true_range.rolling(window=period).mean()
        return atr
    
    def _calculate_beta(
        self, 
        stock_series: pd.Series, 
        market_series: pd.Series, 
        period: int = 60
    ) -> pd.Series:
        """베타 계산 (시장 대비)"""
        stock_returns = stock_series.pct_change()
        market_returns = market_series.pct_change()
        
        covariance = stock_returns.rolling(window=period).cov(market_returns)
        market_variance = market_returns.rolling(window=period).var()
        beta = covariance / market_variance
        
        return beta


def main():
    """테스트 함수"""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    
    from core.db import SessionLocal
    from core.fetchers import OHLCVFetcher
    
    # 샘플 데이터 로드
    db = SessionLocal()
    fetcher = OHLCVFetcher(db)
    
    # 삼성전자 데이터
    df = fetcher.get_ohlcv("005930", start_date="2023-01-01", end_date="2024-12-31")
    
    if df.empty:
        logger.error("데이터 없음")
        return
    
    # 특징 엔지니어링
    engineer = FeatureEngineer()
    df_features = engineer.create_features(df)
    
    print("\n생성된 특징:")
    print(df_features.columns.tolist())
    print(f"\n총 {len(df_features.columns)}개 특징")
    print(f"데이터 행 수: {len(df_features)}")
    
    db.close()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    main()
