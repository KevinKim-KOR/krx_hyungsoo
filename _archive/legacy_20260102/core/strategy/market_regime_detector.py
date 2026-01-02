# -*- coding: utf-8 -*-
"""
core/strategy/market_regime_detector.py
시장 레짐 감지 시스템

목표: 시장 상황에 따른 동적 전략 전환

Week 3 최종 버전 (2025-11-08)
- MA 50/200일 기반 레짐 분류
- 포지션 비율: 상승장 100~120%, 중립장 80%, 하락장 40~60%
- 방어 모드: 신뢰도 85% 이상만 매수 스킵
- 성과: CAGR 27.05%, Sharpe 1.51, MDD -19.92%
"""
from typing import Dict, Optional, Tuple
from datetime import date
import pandas as pd
import numpy as np
import logging
import yaml
from pathlib import Path

logger = logging.getLogger(__name__)


class MarketRegimeDetector:
    """
    시장 레짐 감지기
    
    기능:
    1. 시장 추세 분석 (이동평균 기반)
    2. 레짐 분류 (상승장/하락장/중립장)
    3. 추세 강도 측정
    
    목표:
    - 상승장: 공격적 전략 (100% 포지션)
    - 하락장: 방어적 전략 (현금 보유)
    - 중립장: 혼합 전략 (50% 포지션)
    """
    
    def __init__(
        self,
        # 이동평균 파라미터 (None이면 YAML에서 로드)
        short_ma_period: Optional[int] = None,
        long_ma_period: Optional[int] = None,
        
        # 레짐 분류 임계값 (None이면 YAML에서 로드)
        bull_threshold: Optional[float] = None,
        bear_threshold: Optional[float] = None,
        
        # 추세 강도 파라미터 (None이면 YAML에서 로드)
        trend_strength_period: Optional[int] = None,
        
        # 활성화 플래그
        enable_regime_detection: bool = True,
        
        # 설정 파일 경로
        config_path: Optional[str] = None
    ):
        """
        Args:
            short_ma_period: 단기 이동평균 기간 (None이면 YAML에서 로드)
            long_ma_period: 장기 이동평균 기간 (None이면 YAML에서 로드)
            bull_threshold: 상승장 임계값 (%) (None이면 YAML에서 로드)
            bear_threshold: 하락장 임계값 (%) (None이면 YAML에서 로드)
            trend_strength_period: 추세 강도 계산 기간 (None이면 YAML에서 로드)
            enable_regime_detection: 레짐 감지 활성화
            config_path: 설정 파일 경로 (None이면 기본 경로)
        """
        # YAML 설정 로드
        config = self._load_config(config_path)
        
        # 파라미터 설정 (인자 우선, 없으면 YAML, 없으면 기본값)
        self.short_ma_period = short_ma_period or config.get('short_ma_period', 50)
        self.long_ma_period = long_ma_period or config.get('long_ma_period', 200)
        self.bull_threshold = bull_threshold if bull_threshold is not None else config.get('bull_threshold', 0.02)
        self.bear_threshold = bear_threshold if bear_threshold is not None else config.get('bear_threshold', -0.02)
        self.trend_strength_period = trend_strength_period or config.get('trend_strength_period', 20)
        self.enable_regime_detection = enable_regime_detection
        
        # 현재 레짐
        self.current_regime: str = 'neutral'
        
        # 통계
        self.stats = {
            'bull_days': 0,
            'bear_days': 0,
            'neutral_days': 0,
            'regime_changes': 0
        }
        
        logger.info(f"MarketRegimeDetector 초기화: "
                   f"MA={self.short_ma_period}/{self.long_ma_period}일, "
                   f"임계값={self.bull_threshold*100:.1f}/{self.bear_threshold*100:.1f}%")
    
    def _load_config(self, config_path: Optional[str] = None) -> Dict:
        """YAML 설정 파일 로드"""
        if config_path is None:
            # 기본 경로: project_root/config/regime_params.yaml
            project_root = Path(__file__).parent.parent.parent
            config_path = project_root / "config" / "regime_params.yaml"
        else:
            config_path = Path(config_path)
        
        if not config_path.exists():
            logger.warning(f"설정 파일 없음: {config_path}, 기본값 사용")
            return {}
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                regime_config = config.get('regime_detection', {})
                logger.info(f"✅ 설정 파일 로드: {config_path}")
                return regime_config
        except Exception as e:
            logger.error(f"설정 파일 로드 실패: {e}, 기본값 사용")
            return {}
    
    def calculate_moving_averages(
        self,
        market_data: pd.DataFrame,
        current_date: date
    ) -> Tuple[Optional[float], Optional[float]]:
        """
        이동평균 계산
        
        Args:
            market_data: 시장 데이터 (Date 인덱스, Close 컬럼)
            current_date: 현재 날짜
        
        Returns:
            tuple: (단기MA, 장기MA)
        """
        try:
            # 현재 날짜까지의 데이터
            current_ts = pd.Timestamp(current_date)
            hist_data = market_data[market_data.index <= current_ts]
            
            if len(hist_data) < self.long_ma_period:
                return None, None
            
            # 단기 이동평균
            short_ma = hist_data['close'].tail(self.short_ma_period).mean()
            
            # 장기 이동평균
            long_ma = hist_data['close'].tail(self.long_ma_period).mean()
            
            return float(short_ma.iloc[0] if hasattr(short_ma, 'iloc') else short_ma), \
                   float(long_ma.iloc[0] if hasattr(long_ma, 'iloc') else long_ma)
            
        except Exception as e:
            logger.error(f"이동평균 계산 실패: {e}")
            return None, None
    
    def calculate_trend_strength(
        self,
        market_data: pd.DataFrame,
        current_date: date
    ) -> Optional[float]:
        """
        추세 강도 계산
        
        방법: 최근 N일간 상승일 비율
        
        Args:
            market_data: 시장 데이터
            current_date: 현재 날짜
        
        Returns:
            float: 추세 강도 (0~1, 1이 가장 강한 상승)
        """
        try:
            # 현재 날짜까지의 데이터
            current_ts = pd.Timestamp(current_date)
            hist_data = market_data[market_data.index <= current_ts]
            
            if len(hist_data) < self.trend_strength_period:
                return None
            
            # 최근 N일 데이터
            recent_data = hist_data.tail(self.trend_strength_period)
            
            # 일별 수익률
            daily_returns = recent_data['close'].pct_change()
            
            # 상승일 비율
            up_days = (daily_returns > 0).sum()
            total_days = len(daily_returns) - 1  # NaN 제외
            
            if total_days == 0:
                return None
            
            trend_strength = up_days / total_days
            
            return float(trend_strength.iloc[0] if hasattr(trend_strength, 'iloc') else trend_strength)
            
        except Exception as e:
            logger.error(f"추세 강도 계산 실패: {e}")
            return None
    
    def detect_regime(
        self,
        market_data: pd.DataFrame,
        current_date: date
    ) -> Tuple[str, float]:
        """
        시장 레짐 감지
        
        Args:
            market_data: 시장 데이터 (KOSPI)
            current_date: 현재 날짜
        
        Returns:
            tuple: (레짐, 신뢰도)
        """
        if not self.enable_regime_detection:
            return 'neutral', 0.5
        
        try:
            # 이동평균 계산
            short_ma, long_ma = self.calculate_moving_averages(market_data, current_date)
            
            if short_ma is None or long_ma is None:
                return 'neutral', 0.5
            
            # MA 차이 비율
            ma_diff_pct = (short_ma / long_ma - 1.0)
            
            # 추세 강도 계산
            trend_strength = self.calculate_trend_strength(market_data, current_date)
            if trend_strength is None:
                trend_strength = 0.5
            
            # 레짐 분류
            prev_regime = self.current_regime
            
            if ma_diff_pct >= self.bull_threshold:
                # 상승장
                regime = 'bull'
                confidence = min(1.0, 0.5 + ma_diff_pct * 10)  # 차이가 클수록 신뢰도 증가
                self.stats['bull_days'] += 1
                
            elif ma_diff_pct <= self.bear_threshold:
                # 하락장
                regime = 'bear'
                confidence = min(1.0, 0.5 + abs(ma_diff_pct) * 10)
                self.stats['bear_days'] += 1
                
            else:
                # 중립장
                regime = 'neutral'
                confidence = 0.5
                self.stats['neutral_days'] += 1
            
            # 레짐 변경 감지
            if regime != prev_regime:
                self.stats['regime_changes'] += 1
                logger.info(f"레짐 변경! {current_date}: {prev_regime} → {regime} "
                          f"(MA차이={ma_diff_pct*100:.2f}%, 추세강도={trend_strength:.2f})")
            
            self.current_regime = regime
            
            return regime, confidence
            
        except Exception as e:
            logger.error(f"레짐 감지 실패: {e}")
        except Exception as e:
            logger.error(f"레짐 감지 실패: {e}")
            return 'neutral', 0.5

    def detect_regime_v2(
        self,
        market_data: pd.DataFrame,
        current_date: date,
        ma_period: int = 200
    ) -> Tuple[str, float]:
        """
        시장 레짐 감지 V2 (단순 Price vs MA)
        
        Args:
            market_data: 시장 데이터
            current_date: 현재 날짜
            ma_period: MA 기간 (기본 200)

        Returns:
            tuple: (레짐, 신뢰도)
        """
        if not self.enable_regime_detection:
            return 'neutral', 0.5
        
        try:
            current_ts = pd.Timestamp(current_date)
            hist_data = market_data[market_data.index <= current_ts]
            
            if len(hist_data) < ma_period:
                return 'neutral', 0.5
            
            # MA 계산
            ma = hist_data['close'].tail(ma_period).mean()
            current_price = hist_data['close'].iloc[-1]
            
            # Price vs MA
            if current_price < ma:
                # Bear: 가격이 MA 아래
                regime = 'bear'
                # 신뢰도는 괴리율로 (최대 1.0)
                diff = (ma - current_price) / ma
                confidence = min(0.5 + diff * 5, 1.0)
                self.stats['bear_days'] += 1
            else:
                # Bull: 가격이 MA 위
                regime = 'bull'
                diff = (current_price - ma) / ma
                confidence = min(0.5 + diff * 5, 1.0)
                self.stats['bull_days'] += 1
                
            if self.current_regime != regime:
                 logger.debug(f"Regime V2 Change: {self.current_regime} -> {regime} (Price={current_price:.2f}, MA({ma_period})={ma:.2f})")
            
            self.current_regime = regime
            return regime, confidence
            
        except Exception as e:
            logger.error(f"Regime V2 Error: {e}")
            return regime, confidence, is_golden_cross
            
        except Exception as e:
            logger.error(f"레짐 감지(Dual) 실패: {e}")
            return 'neutral', 0.5, False

    def _calculate_wilders_rma(self, series: pd.Series, period: int) -> pd.Series:
        """
        Wilder's Smoothing (RMA) 계산
        RMA_t = (RMA_{t-1} * (n-1) + X_t) / n
        """
        return series.ewm(alpha=1/period, adjust=False).mean()

    def _calculate_adx(
        self, 
        limit_data: pd.DataFrame, 
        period: int = 14
    ) -> float:
        """
        ADX 계산 (Wilder's Smoothing 적용)
        """
        try:
            if len(limit_data) < period * 2: # 충분한 데이터 필요
                return 0.0
                
            high = limit_data['high']
            low = limit_data['low']
            close = limit_data['close']
            
            # 1. TR, +DM, -DM 계산
            tr1 = high - low
            tr2 = (high - close.shift(1)).abs()
            tr3 = (low - close.shift(1)).abs()
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            
            up_move = high - high.shift(1)
            down_move = low.shift(1) - low
            
            plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
            minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
            
            plus_dm = pd.Series(plus_dm, index=limit_data.index)
            minus_dm = pd.Series(minus_dm, index=limit_data.index)
            
            # 2. Wilder's Smoothing (TR, +DM, -DM)
            tr_smooth = self._calculate_wilders_rma(tr, period)
            plus_dm_smooth = self._calculate_wilders_rma(plus_dm, period)
            minus_dm_smooth = self._calculate_wilders_rma(minus_dm, period)
            
            # 3. DI+, DI- 계산
            plus_di = 100 * (plus_dm_smooth / tr_smooth)
            minus_di = 100 * (minus_dm_smooth / tr_smooth)
            
            # 4. DX 계산
            dx = 100 * (abs(plus_di - minus_di) / (plus_di + minus_di + 1e-9))
            
            # 5. ADX (DX의 RMA)
            adx = self._calculate_wilders_rma(dx, period)
            
            return adx.iloc[-1]
            
        except Exception as e:
            # logger.error(f"ADX Calc Error: {e}")
            return 0.0

    def detect_regime_adx(
        self,
        market_data: pd.DataFrame,
        current_date: date,
        long_ma_period: int = 200,
        short_ma_period: int = 60,
        adx_period: int = 14,
        adx_threshold: float = 20.0
    ) -> Tuple[str, float, bool, bool]:
        """
        시장 레짐 감지 V4 (ADX Chop Filter)
        
        Args:
            market_data: 시장 데이터
            current_date: 현재 날짜
            long_ma_period: 장기 MA (레짐 정의용)
            short_ma_period: 단기 MA (Golden Cross용)
            adx_period: ADX 기간
            adx_threshold: Chop 기준 (ADX < threshold -> Chop)

        Returns:
            tuple: (레짐, 신뢰도, 골든크로스여부, 찹여부)
        """
        if not self.enable_regime_detection:
            return 'neutral', 0.5, False, False
        
        try:
            current_ts = pd.Timestamp(current_date)
            hist_data = market_data[market_data.index <= current_ts]
            
            if len(hist_data) < max(long_ma_period, adx_period * 2):
                return 'neutral', 0.5, False, False
            
            # 1. Basic Regime & Golden Cross (Phase 8 Logic)
            long_ma = hist_data['close'].tail(long_ma_period).mean()
            short_ma = hist_data['close'].tail(short_ma_period).mean()
            current_price = hist_data['close'].iloc[-1]
            
            if current_price >= long_ma:
                regime = 'bull'
                confidence = 1.0
            else:
                regime = 'bear'
                confidence = 1.0
                
            is_golden_cross = short_ma > long_ma
            
            # 2. Chop Detection (ADX)
            # ADX 계산을 위해 충분한 길이의 데이터 전달
            adx_val = self._calculate_adx(hist_data.tail(adx_period * 5), adx_period)
            is_chop = adx_val < adx_threshold
            
            return regime, confidence, is_golden_cross, is_chop
            
        except Exception as e:
            logger.error(f"레짐 감지(ADX) 실패: {e}")
            return 'neutral', 0.5, False, False
    
    def get_position_ratio(
        self,
        regime: str,
        confidence: float
    ) -> float:
        """
        레짐에 따른 포지션 비율 계산
        """
        if regime == 'bull':
            return 1.0 + (confidence - 0.5) * 0.4
        elif regime == 'bear':
            return 0.0
        else:
            return 0.8
            
    def should_enter_defense_mode(
        self,
        regime: str,
        confidence: float
    ) -> bool:
        return regime == 'bear' and confidence >= 0.85
    
    def get_stats(self) -> Dict:
        """통계 조회"""
        total_days = sum([
            self.stats['bull_days'],
            self.stats['bear_days'],
            self.stats['neutral_days']
        ])
        
        return {
            **self.stats,
            'total_days': total_days,
            'bull_pct': (self.stats['bull_days'] / total_days * 100) if total_days > 0 else 0,
            'bear_pct': (self.stats['bear_days'] / total_days * 100) if total_days > 0 else 0,
            'neutral_pct': (self.stats['neutral_days'] / total_days * 100) if total_days > 0 else 0,
            'current_regime': self.current_regime
        }
    
    def reset_stats(self):
        """통계 초기화"""
        self.stats = {
            'bull_days': 0,
            'bear_days': 0,
            'neutral_days': 0,
            'regime_changes': 0
        }
        self.current_regime = 'neutral'


__all__ = ['MarketRegimeDetector']
