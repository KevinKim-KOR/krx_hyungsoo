# -*- coding: utf-8 -*-
"""
extensions/automation/signal_generator.py
자동 매매 신호 생성

기능:
- MAPS 점수 계산
- Top N 종목 선정
- 포지션 크기 계산
- 매수/매도 신호 생성
"""

from datetime import date, timedelta
from typing import Optional, List, Dict
import pandas as pd
import logging
from pathlib import Path

from core.strategy.signals import SignalGenerator
from extensions.automation.regime_monitor import RegimeMonitor
from extensions.automation.data_updater import DataUpdater

logger = logging.getLogger(__name__)


class AutoSignalGenerator:
    """
    자동 매매 신호 생성 클래스
    
    기능:
    1. MAPS 점수 계산
    2. 레짐 기반 포지션 조정
    3. 매수/매도 신호 생성
    """
    
    def __init__(
        self,
        ma_period: int = 60,
        max_positions: int = 10,
        universe_file: Optional[str] = None
    ):
        """
        Args:
            ma_period: 이동평균 기간
            max_positions: 최대 보유 종목 수
            universe_file: 유니버스 파일 경로
        """
        self.strategy = SignalGenerator(
            ma_period=ma_period,
            rsi_period=14,
            rsi_overbought=70,
            maps_enabled=True
        )
        self.regime_monitor = RegimeMonitor()
        self.data_updater = DataUpdater(universe_file)
        self.max_positions = max_positions
        
    def generate_daily_signals(
        self,
        target_date: Optional[date] = None,
        current_holdings: Optional[List[str]] = None
    ) -> Dict:
        """
        일별 매매 신호 생성
        
        Args:
            target_date: 대상 날짜 (None이면 오늘)
            current_holdings: 현재 보유 종목 리스트
        
        Returns:
            Dict: 매매 신호
                - buy_signals: 매수 신호 리스트
                - sell_signals: 매도 신호 리스트
                - regime_info: 레짐 정보
        """
        try:
            if target_date is None:
                target_date = date.today()
            
            if current_holdings is None:
                current_holdings = []
            
            logger.info(f"매매 신호 생성 시작: {target_date}")
            
            # 1. 레짐 분석
            regime_info = self.regime_monitor.analyze_daily_regime(target_date)
            if regime_info is None:
                logger.error("레짐 분석 실패")
                return self._empty_signals()
            
            logger.info(
                f"현재 레짐: {regime_info['regime']} "
                f"(신뢰도: {regime_info['confidence']:.2%})"
            )
            
            # 2. 방어 모드 확인
            if regime_info['defense_mode']:
                logger.warning("⚠️ 방어 모드: 매수 신호 없음")
                return {
                    'buy_signals': [],
                    'sell_signals': [],
                    'regime_info': regime_info,
                    'message': '방어 모드 - 매수 스킵'
                }
            
            # 3. 가격 데이터 로드
            codes = self.data_updater.load_universe()
            if not codes:
                logger.error("유니버스 로드 실패")
                return self._empty_signals()
            
            # 최근 1년 데이터
            start_date = target_date - timedelta(days=365)
            end_date = target_date
            
            from infra.data.loader import load_price_data
            price_data = load_price_data(
                universe=codes,
                start_date=start_date,
                end_date=end_date
            )
            
            if price_data.empty:
                logger.error("가격 데이터 없음")
                return self._empty_signals()
            
            # 4. MAPS 점수 계산
            logger.info("MAPS 점수 계산 중...")
            
            # 간단한 MAPS 점수: 최근 MA 대비 현재 가격
            maps_scores = {}
            for code in codes:
                try:
                    code_data = price_data.xs(code, level='code')
                    if len(code_data) < self.strategy.ma_period:
                        continue
                    
                    # MA 계산
                    ma = code_data['close'].rolling(self.strategy.ma_period).mean()
                    current_price = code_data['close'].iloc[-1]
                    current_ma = ma.iloc[-1]
                    
                    # MAPS 점수 = (현재가 - MA) / MA * 100
                    maps_score = ((current_price - current_ma) / current_ma) * 100
                    maps_scores[code] = maps_score
                    
                except Exception as e:
                    continue
            
            if not maps_scores:
                logger.warning("신호 없음")
                return self._empty_signals()
            
            # 5. Top N 종목 선정
            # MAPS 점수가 양수인 종목만 (상승 추세)
            buy_candidates = {
                code: score 
                for code, score in maps_scores.items() 
                if score > 0
            }
            
            if not buy_candidates:
                logger.info("매수 후보 없음")
                buy_signals = []
            else:
                # MAPS 점수 기준 정렬
                sorted_candidates = sorted(
                    buy_candidates.items(),
                    key=lambda x: x[1],
                    reverse=True
                )
                
                # 레짐 기반 포지션 수 조정
                position_ratio = regime_info['position_ratio']
                target_positions = int(self.max_positions * position_ratio)
                target_positions = max(1, min(target_positions, self.max_positions))
                
                logger.info(
                    f"목표 포지션 수: {target_positions} "
                    f"(비율: {position_ratio:.0%})"
                )
                
                # 이미 보유 중인 종목 제외
                new_candidates = [
                    (code, score) 
                    for code, score in sorted_candidates 
                    if code not in current_holdings
                ]
                
                # 필요한 만큼만 선정
                needed = target_positions - len(current_holdings)
                if needed > 0:
                    top_candidates = new_candidates[:needed]
                    
                    buy_signals = [
                        {
                            'code': code,
                            'maps_score': float(score),
                            'confidence': 0.7,
                            'reason': 'maps_signal'
                        }
                        for code, score in top_candidates
                    ]
                else:
                    buy_signals = []
            
            # 6. 매도 신호 (보유 중인 종목 중 MAPS 점수가 음수인 것)
            sell_signals = []
            for code in current_holdings:
                if code in maps_scores and maps_scores[code] < 0:
                    sell_signals.append({
                        'code': code,
                        'reason': 'negative_maps_score'
                    })
            
            logger.info(f"✅ 신호 생성 완료: 매수 {len(buy_signals)}개, 매도 {len(sell_signals)}개")
            
            return {
                'buy_signals': buy_signals,
                'sell_signals': sell_signals,
                'regime_info': regime_info,
                'target_positions': target_positions if buy_signals else 0
            }
            
        except Exception as e:
            logger.error(f"신호 생성 실패: {e}")
            import traceback
            traceback.print_exc()
            return self._empty_signals()
    
    def _empty_signals(self) -> Dict:
        """빈 신호 반환"""
        return {
            'buy_signals': [],
            'sell_signals': [],
            'regime_info': None,
            'message': '신호 생성 실패'
        }
    
    def format_signals_for_display(self, signals: Dict) -> str:
        """
        신호를 사람이 읽기 쉬운 형식으로 변환
        
        Args:
            signals: 신호 딕셔너리
        
        Returns:
            str: 포맷된 문자열
        """
        lines = []
        lines.append("=" * 50)
        lines.append("📊 일일 매매 신호")
        lines.append("=" * 50)
        
        # 레짐 정보
        if signals.get('regime_info'):
            regime_info = signals['regime_info']
            regime_emoji = {
                'bull': '📈',
                'bear': '📉',
                'neutral': '➡️'
            }
            emoji = regime_emoji.get(regime_info['regime'], '❓')
            
            lines.append(f"\n{emoji} 시장 레짐: {regime_info['regime'].upper()}")
            lines.append(f"   신뢰도: {regime_info['confidence']:.1%}")
            lines.append(f"   포지션 비율: {regime_info['position_ratio']:.0%}")
            
            if regime_info['defense_mode']:
                lines.append("   ⚠️ 방어 모드 활성화")
        
        # 매수 신호
        buy_signals = signals.get('buy_signals', [])
        if buy_signals:
            lines.append(f"\n🟢 매수 신호 ({len(buy_signals)}개):")
            for i, signal in enumerate(buy_signals, 1):
                lines.append(
                    f"   {i}. {signal['code']} "
                    f"(MAPS: {signal['maps_score']:.2f})"
                )
        else:
            lines.append("\n🟢 매수 신호: 없음")
        
        # 매도 신호
        sell_signals = signals.get('sell_signals', [])
        if sell_signals:
            lines.append(f"\n🔴 매도 신호 ({len(sell_signals)}개):")
            for i, signal in enumerate(sell_signals, 1):
                lines.append(
                    f"   {i}. {signal['code']} "
                    f"(사유: {signal['reason']})"
                )
        else:
            lines.append("\n🔴 매도 신호: 없음")
        
        lines.append("\n" + "=" * 50)
        
        return "\n".join(lines)
