# -*- coding: utf-8 -*-
"""
extensions/monitoring/regime.py
시장 레짐(상태) 감지
"""
import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, Optional, Tuple
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class RegimeDetector:
    """시장 레짐 감지기"""
    
    def __init__(
        self,
        cache_dir: Path = None,
        lookback_days: int = 60
    ):
        """
        Args:
            cache_dir: 캐시 디렉토리
            lookback_days: 과거 데이터 기간
        """
        self.cache_dir = cache_dir or Path('data/cache')
        self.lookback_days = lookback_days
        
        logger.info(f"RegimeDetector 초기화: lookback={lookback_days}일")
    
    def detect_regime(
        self,
        target_date: date,
        benchmark_code: str = '069500'  # KODEX 200
    ) -> Dict:
        """
        시장 레짐 감지
        
        Args:
            target_date: 분석 날짜
            benchmark_code: 벤치마크 종목 코드
            
        Returns:
            레짐 정보 딕셔너리
        """
        try:
            # 벤치마크 데이터 로드
            cache_file = self.cache_dir / f"{benchmark_code}.parquet"
            
            if not cache_file.exists():
                logger.warning(f"벤치마크 데이터 없음: {benchmark_code}")
                return self._default_regime()
            
            df = pd.read_parquet(cache_file, engine='pyarrow')
            
            # 날짜 필터
            if df.index.name in ['날짜', 'date']:
                df = df.reset_index()
                df = df.rename(columns={'날짜': 'date'})
            
            df['date'] = pd.to_datetime(df['date']).dt.date
            
            # 기간 필터
            start_date = target_date - timedelta(days=self.lookback_days + 30)
            df = df[(df['date'] >= start_date) & (df['date'] <= target_date)]
            
            if len(df) < 20:
                logger.warning(f"데이터 부족: {len(df)}일")
                return self._default_regime()
            
            # 레짐 계산
            regime = self._calculate_regime(df)
            regime['date'] = target_date
            regime['benchmark'] = benchmark_code
            
            logger.info(f"레짐 감지: {regime['state']}, 변동성={regime['volatility']:.2%}")
            
            return regime
        
        except Exception as e:
            logger.error(f"레짐 감지 실패: {e}")
            return self._default_regime()
    
    def _calculate_regime(self, df: pd.DataFrame) -> Dict:
        """
        레짐 계산
        
        Args:
            df: 가격 데이터
            
        Returns:
            레짐 딕셔너리
        """
        close = df['close'].values
        
        # 수익률
        returns = pd.Series(close).pct_change().dropna()
        
        # 변동성 (20일 기준, 연율화)
        volatility = returns.tail(20).std() * np.sqrt(252)
        
        # 추세 (60일 MA)
        ma_60 = pd.Series(close).rolling(60).mean().iloc[-1]
        current_price = close[-1]
        trend = (current_price - ma_60) / ma_60 if ma_60 > 0 else 0
        
        # 모멘텀 (20일)
        momentum = (close[-1] - close[-20]) / close[-20] if len(close) >= 20 else 0
        
        # 레짐 분류
        state = self._classify_regime(volatility, trend, momentum)
        
        return {
            'state': state,
            'volatility': volatility,
            'trend': trend,
            'momentum': momentum,
            'current_price': current_price,
            'ma_60': ma_60
        }
    
    def _classify_regime(
        self,
        volatility: float,
        trend: float,
        momentum: float
    ) -> str:
        """
        레짐 분류
        
        Args:
            volatility: 변동성
            trend: 추세
            momentum: 모멘텀
            
        Returns:
            레짐 상태 ('bull', 'bear', 'sideways', 'volatile')
        """
        # 변동성 기준
        high_vol = volatility > 0.25  # 연 25% 이상
        
        # 추세 기준
        strong_uptrend = trend > 0.05  # MA 대비 +5% 이상
        strong_downtrend = trend < -0.05  # MA 대비 -5% 이하
        
        # 모멘텀 기준
        positive_momentum = momentum > 0.02  # 20일 +2% 이상
        negative_momentum = momentum < -0.02  # 20일 -2% 이하
        
        # 분류
        if high_vol:
            return 'volatile'  # 고변동성
        elif strong_uptrend and positive_momentum:
            return 'bull'  # 강세장
        elif strong_downtrend and negative_momentum:
            return 'bear'  # 약세장
        else:
            return 'sideways'  # 횡보장
    
    def _default_regime(self) -> Dict:
        """기본 레짐"""
        return {
            'state': 'unknown',
            'volatility': 0.0,
            'trend': 0.0,
            'momentum': 0.0,
            'current_price': 0.0,
            'ma_60': 0.0,
            'date': None,
            'benchmark': None
        }
    
    def detect_regime_change(
        self,
        current_regime: Dict,
        previous_regime: Dict
    ) -> Tuple[bool, str]:
        """
        레짐 변경 감지
        
        Args:
            current_regime: 현재 레짐
            previous_regime: 이전 레짐
            
        Returns:
            (변경 여부, 변경 메시지)
        """
        if not current_regime or not previous_regime:
            return False, ""
        
        current_state = current_regime.get('state', 'unknown')
        previous_state = previous_regime.get('state', 'unknown')
        
        if current_state == previous_state:
            return False, ""
        
        # 변경 메시지
        message = f"시장 레짐 변경: {previous_state} → {current_state}"
        
        # 상세 정보
        current_vol = current_regime.get('volatility', 0)
        previous_vol = previous_regime.get('volatility', 0)
        vol_change = current_vol - previous_vol
        
        message += f"\n변동성: {previous_vol:.2%} → {current_vol:.2%} ({vol_change:+.2%})"
        
        logger.warning(message)
        
        return True, message
    
    def get_regime_description(self, regime: Dict) -> str:
        """
        레짐 설명
        
        Args:
            regime: 레짐 딕셔너리
            
        Returns:
            설명 텍스트
        """
        state = regime.get('state', 'unknown')
        
        descriptions = {
            'bull': '🟢 강세장 - 상승 추세, 긍정적 모멘텀',
            'bear': '🔴 약세장 - 하락 추세, 부정적 모멘텀',
            'sideways': '🟡 횡보장 - 방향성 불분명',
            'volatile': '⚠️ 고변동성 - 리스크 관리 필요',
            'unknown': '❓ 알 수 없음 - 데이터 부족'
        }
        
        description = descriptions.get(state, '알 수 없음')
        
        # 상세 정보 추가
        if state != 'unknown':
            description += f"\n변동성: {regime.get('volatility', 0):.2%}"
            description += f"\n추세: {regime.get('trend', 0):+.2%}"
            description += f"\n모멘텀: {regime.get('momentum', 0):+.2%}"
        
        return description
