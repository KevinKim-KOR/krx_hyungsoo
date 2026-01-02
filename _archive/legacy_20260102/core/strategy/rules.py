# -*- coding: utf-8 -*-
"""
core/strategy/rules.py
전략 규칙 및 HOLD_CORE 정의

주요 컴포넌트:
- StrategyRules: 전략별 규칙 정의
- SignalType: 신호 유형 (BUY/SELL/HOLD)
- HOLD_CORE 처리 로직
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import List, Dict, Optional
import pandas as pd

class SignalType(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    HOLD_CORE = "HOLD_CORE"  # 핵심보유 특별상태

@dataclass
class Signal:
    code: str
    signal_type: SignalType
    score: float
    reason: str
    timestamp: pd.Timestamp

class StrategyRules:
    """전략 규칙 정의 클래스"""
    
    def __init__(
        self,
        core_holdings: List[str],
        lookbacks: List[int] = [21, 63, 126],
        weights: List[float] = [0.5, 0.3, 0.2],
        top_n: int = 5,
        regime_filter: bool = True
    ):
        self.core_holdings = set(core_holdings)  # O(1) 조회를 위해 set 사용
        self.lookbacks = lookbacks
        self.weights = weights
        self.top_n = top_n
        self.regime_filter = regime_filter
        
        # 검증
        if len(lookbacks) != len(weights):
            raise ValueError("lookbacks와 weights의 길이가 일치해야 합니다")
        if abs(sum(weights) - 1.0) > 0.001:
            raise ValueError("weights의 합은 1이어야 합니다")

    def is_core_holding(self, code: str) -> bool:
        """핵심 보유 종목 여부 확인"""
        return code in self.core_holdings

    def should_ignore_sell_signal(self, code: str) -> bool:
        """매도 신호 무시 여부 (HOLD_CORE)"""
        return self.is_core_holding(code)

    def exclude_from_topn(self, ranked_codes: List[str]) -> List[str]:
        """TOPN 계산에서 핵심보유종목 제외"""
        return [code for code in ranked_codes if not self.is_core_holding(code)]

    def apply_core_holdings_rules(self, signals: List[Signal]) -> List[Signal]:
        """HOLD_CORE 규칙 적용"""
        result = []
        for signal in signals:
            if self.is_core_holding(signal.code):
                if signal.signal_type == SignalType.SELL:
                    # 매도 신호 무시, HOLD_CORE로 변경
                    signal.signal_type = SignalType.HOLD_CORE
                    signal.reason = f"{signal.reason} (HOLD_CORE 매도 제외)"
            result.append(signal)
        return result

    def get_buy_candidates(self, scores: Dict[str, float], current_holdings: List[str]) -> List[Signal]:
        """매수 후보 선정 (HOLD_CORE 보유 확인 포함)"""
        signals = []
        
        # 1. HOLD_CORE 중 미보유 종목 먼저 처리
        for code in self.core_holdings:
            if code not in current_holdings:
                signals.append(Signal(
                    code=code,
                    signal_type=SignalType.BUY,
                    score=scores.get(code, 0.0),
                    reason="HOLD_CORE 자동 매수",
                    timestamp=pd.Timestamp.now()
                ))

        # 2. 일반 종목 중 TOP N
        non_core_codes = [c for c, s in sorted(scores.items(), key=lambda x: x[1], reverse=True)
                         if c not in self.core_holdings][:self.top_n]
        
        for code in non_core_codes:
            if code not in current_holdings:
                signals.append(Signal(
                    code=code,
                    signal_type=SignalType.BUY,
                    score=scores[code],
                    reason=f"일반 TOP {self.top_n}",
                    timestamp=pd.Timestamp.now()
                ))

        return signals