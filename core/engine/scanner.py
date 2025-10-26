# -*- coding: utf-8 -*-
"""
core/engine/scanner.py
시장 스캐너 엔진 - 전략 신호 생성

책임:
- 전략 규칙에 따른 신호 생성
- HOLD_CORE 규칙 적용
- 레짐 필터 적용
"""
from __future__ import annotations
from typing import List, Dict, Optional
import pandas as pd
import numpy as np

from core.strategy.rules import StrategyRules, Signal, SignalType
from core.metrics.performance import calc_returns
from core.risk.position import Position

class MarketScanner:
    """시장 스캐너 엔진"""
    
    def __init__(
        self,
        rules: StrategyRules,
        prices: pd.DataFrame,  # code/date/close의 멀티인덱스 DataFrame
        positions: Optional[List[Position]] = None,
    ):
        self.rules = rules
        self.prices = prices
        self.current_positions = positions or []
        
        # 현재 보유 종목
        self.holdings = [p.code for p in self.current_positions if p.quantity > 0]

    def _calc_momentum_scores(self) -> Dict[str, float]:
        """모멘텀 스코어 계산"""
        scores = {}
        
        for code in self.prices.index.get_level_values('code').unique():
            series = self.prices.loc[code]['close']
            if len(series) < max(self.rules.lookbacks):
                continue

            # 룩백별 수익률 계산
            returns = []
            for lb, w in zip(self.rules.lookbacks, self.rules.weights):
                try:
                    ret = calc_returns(series, lookback=lb)
                    returns.append(ret * w)
                except Exception:
                    returns.append(0.0)
            
            # 가중평균 스코어
            scores[code] = sum(returns)
            
        return scores

    def _check_regime(self) -> bool:
        """레짐 체크 (KODEX 200 > 200일선)"""
        if not self.rules.regime_filter:
            return True
            
        try:
            kodex = self.prices.loc['069500']['close']  # KODEX 200
            if len(kodex) < 200:
                return True
            
            ma200 = kodex.rolling(200, min_periods=200).mean()
            return kodex.iloc[-1] > ma200.iloc[-1]
        except Exception:
            return True  # 실패 시 안전하게 True 반환

    def generate_signals(self) -> List[Signal]:
        """신호 생성"""
        signals = []
        
        # 1. 레짐 체크
        if not self._check_regime():
            return [Signal(
                code="MARKET",
                signal_type=SignalType.HOLD,
                score=0.0,
                reason="레짐 필터 - KODEX200 < 200일선",
                timestamp=pd.Timestamp.now()
            )]

        # 2. 모멘텀 스코어 계산
        scores = self._calc_momentum_scores()
        
        # 3. 매수 후보 선정 (HOLD_CORE 포함)
        buy_signals = self.rules.get_buy_candidates(scores, self.holdings)
        signals.extend(buy_signals)
        
        # 4. 매도 신호 생성 및 HOLD_CORE 규칙 적용
        for pos in self.current_positions:
            if pos.quantity <= 0:
                continue
                
            # 스코어가 하위 20%면 매도 고려
            score = scores.get(pos.code, 0.0)
            score_rank = sum(1 for s in scores.values() if s > score) / len(scores)
            
            if score_rank > 0.8:  # 하위 20%
                signals.append(Signal(
                    code=pos.code,
                    signal_type=SignalType.SELL,
                    score=score,
                    reason=f"모멘텀 하위 20% (스코어: {score:.2f})",
                    timestamp=pd.Timestamp.now()
                ))
            else:
                signals.append(Signal(
                    code=pos.code,
                    signal_type=SignalType.HOLD,
                    score=score,
                    reason=f"모멘텀 유지 (스코어: {score:.2f})",
                    timestamp=pd.Timestamp.now()
                ))
        
        # 5. HOLD_CORE 규칙 최종 적용
        signals = self.rules.apply_core_holdings_rules(signals)
        
        return signals
