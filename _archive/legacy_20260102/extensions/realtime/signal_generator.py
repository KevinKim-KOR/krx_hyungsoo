# -*- coding: utf-8 -*-
"""
extensions/realtime/signal_generator.py
실시간 매매 신호 생성
"""
import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import pandas as pd
import numpy as np

from core.data.filtering import get_filtered_universe
from infra.data.loader import load_price_data
from extensions.strategy.signal_generator import SignalGenerator
from extensions.strategy.risk_manager import RiskManager

logger = logging.getLogger(__name__)


@dataclass
class Signal:
    """매매 신호"""
    code: str
    name: str
    action: str  # 'BUY', 'SELL', 'HOLD'
    confidence: float
    target_weight: float
    current_price: float
    ma_value: float
    rsi_value: float
    maps_score: float
    reason: str


class RealtimeSignalGenerator:
    """실시간 신호 생성기"""
    
    def __init__(
        self,
        params: Dict,
        lookback_days: int = 126,
        cache_dir: Path = None
    ):
        """
        Args:
            params: 전략 파라미터
            lookback_days: 과거 데이터 기간
            cache_dir: 캐시 디렉토리
        """
        self.params = params
        self.lookback_days = lookback_days
        self.cache_dir = cache_dir or Path('data/cache')
        
        # 전략 컴포넌트 초기화
        self.signal_generator = SignalGenerator(
            ma_period=params.get('ma_period', 60),
            rsi_period=params.get('rsi_period', 14),
            rsi_overbought=params.get('rsi_overbought', 70),
            maps_buy_threshold=params.get('maps_buy_threshold', 1.0),
            maps_sell_threshold=params.get('maps_sell_threshold', -5.0)
        )
        
        self.risk_manager = RiskManager(
            max_positions=params.get('max_positions', 10),
            min_confidence=params.get('min_confidence', 0.1),
            portfolio_vol_target=params.get('portfolio_vol_target', 0.15),
            max_drawdown_threshold=params.get('max_drawdown_threshold', -0.15),
            cooldown_days=params.get('cooldown_days', 7),
            max_correlation=params.get('max_correlation', 0.7)
        )
        
        logger.info(f"신호 생성기 초기화: {params}")
    
    def generate_signals(self, target_date: date = None) -> List[Signal]:
        """
        매매 신호 생성
        
        Args:
            target_date: 신호 생성 날짜 (None이면 오늘)
            
        Returns:
            신호 리스트
        """
        if target_date is None:
            target_date = date.today()
        
        logger.info(f"신호 생성 시작: {target_date}")
        
        try:
            # 1. 유니버스 로드
            universe = get_filtered_universe()
            logger.info(f"유니버스: {len(universe)}개 종목")
            
            # 2. 가격 데이터 로드
            start_date = target_date - timedelta(days=self.lookback_days + 30)
            price_data = load_price_data(universe, start_date, target_date, self.cache_dir)
            
            if price_data.empty:
                logger.error("가격 데이터 없음")
                return []
            
            logger.info(f"가격 데이터: {price_data.shape}")
            
            # 3. 신호 생성
            raw_signals = self.signal_generator.generate_signals(price_data, target_date)
            logger.info(f"원시 신호: {len(raw_signals)}개")
            
            # 4. 리스크 필터링
            filtered_signals = self.risk_manager.filter_signals(
                raw_signals,
                price_data,
                target_date
            )
            logger.info(f"필터링 후: {len(filtered_signals)}개")
            
            # 5. 포트폴리오 구성
            portfolio = self.risk_manager.construct_portfolio(
                filtered_signals,
                price_data,
                target_date
            )
            
            # 6. Signal 객체 생성
            signals = []
            for code, weight in portfolio.items():
                signal_info = next((s for s in filtered_signals if s['code'] == code), None)
                if signal_info is None:
                    continue
                
                # 현재 가격
                try:
                    current_price = price_data.loc[(code, target_date), 'close']
                except:
                    current_price = 0.0
                
                signal = Signal(
                    code=code,
                    name=signal_info.get('name', code),
                    action='BUY' if weight > 0 else 'HOLD',
                    confidence=signal_info.get('confidence', 0.0),
                    target_weight=weight,
                    current_price=float(current_price),
                    ma_value=signal_info.get('ma', 0.0),
                    rsi_value=signal_info.get('rsi', 0.0),
                    maps_score=signal_info.get('maps', 0.0),
                    reason=signal_info.get('reason', '')
                )
                signals.append(signal)
            
            logger.info(f"최종 신호: {len(signals)}개")
            return signals
        
        except Exception as e:
            logger.error(f"신호 생성 실패: {e}", exc_info=True)
            return []
    
    def get_portfolio_summary(self, signals: List[Signal]) -> Dict:
        """
        포트폴리오 요약
        
        Args:
            signals: 신호 리스트
            
        Returns:
            요약 딕셔너리
        """
        if not signals:
            return {
                'total_positions': 0,
                'total_weight': 0.0,
                'avg_confidence': 0.0,
                'buy_count': 0,
                'sell_count': 0,
                'hold_count': 0
            }
        
        buy_signals = [s for s in signals if s.action == 'BUY']
        sell_signals = [s for s in signals if s.action == 'SELL']
        hold_signals = [s for s in signals if s.action == 'HOLD']
        
        return {
            'total_positions': len(signals),
            'total_weight': sum(s.target_weight for s in signals),
            'avg_confidence': np.mean([s.confidence for s in signals]),
            'buy_count': len(buy_signals),
            'sell_count': len(sell_signals),
            'hold_count': len(hold_signals),
            'top_signals': sorted(signals, key=lambda x: x.confidence, reverse=True)[:5]
        }
    
    def save_signals(self, signals: List[Signal], output_path: Path):
        """
        신호 저장
        
        Args:
            signals: 신호 리스트
            output_path: 저장 경로
        """
        if not signals:
            logger.warning("저장할 신호 없음")
            return
        
        # DataFrame 변환
        data = []
        for signal in signals:
            data.append({
                'code': signal.code,
                'name': signal.name,
                'action': signal.action,
                'confidence': signal.confidence,
                'target_weight': signal.target_weight,
                'current_price': signal.current_price,
                'ma_value': signal.ma_value,
                'rsi_value': signal.rsi_value,
                'maps_score': signal.maps_score,
                'reason': signal.reason
            })
        
        df = pd.DataFrame(data)
        
        # 저장
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, index=False, encoding='utf-8-sig')
        
        logger.info(f"신호 저장: {output_path}")
    
    def load_params_from_file(self, params_file: Path) -> Dict:
        """
        파라미터 파일 로드
        
        Args:
            params_file: 파라미터 파일 경로 (YAML 또는 JSON)
            
        Returns:
            파라미터 딕셔너리
        """
        import yaml
        import json
        
        if params_file.suffix == '.yaml' or params_file.suffix == '.yml':
            with open(params_file, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        elif params_file.suffix == '.json':
            with open(params_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            raise ValueError(f"지원하지 않는 파일 형식: {params_file.suffix}")
