# -*- coding: utf-8 -*-
"""
core/risk/position.py
포지션 관리 및 리스크 규칙
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class Position:
    """포지션 정보"""
    code: str
    quantity: float
    avg_price: float
    last_update: datetime
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    
    @property
    def market_value(self) -> float:
        """시장가치"""
        return self.quantity * self.avg_price
    
    def should_stop_loss(self, current_price: float) -> bool:
        """손절 조건 확인"""
        if self.stop_loss is None or self.quantity <= 0:
            return False
        return current_price <= self.stop_loss
    
    def should_take_profit(self, current_price: float) -> bool:
        """익절 조건 확인"""
        if self.take_profit is None or self.quantity <= 0:
            return False
        return current_price >= self.take_profit

class PositionManager:
    """포지션 관리자"""
    
    def __init__(self, max_position_count: int = 5):
        self.max_position_count = max_position_count
        self.positions: dict[str, Position] = {}
    
    def add_position(self, position: Position) -> bool:
        """새 포지션 추가"""
        if len(self.positions) >= self.max_position_count and position.code not in self.positions:
            return False
        self.positions[position.code] = position
        return True
    
    def remove_position(self, code: str) -> Optional[Position]:
        """포지션 제거"""
        return self.positions.pop(code, None)
    
    def get_position(self, code: str) -> Optional[Position]:
        """포지션 조회"""
        return self.positions.get(code)
    
    def update_position(self, code: str, quantity: float, price: float) -> None:
        """포지션 업데이트"""
        if code not in self.positions:
            self.positions[code] = Position(
                code=code,
                quantity=quantity,
                avg_price=price,
                last_update=datetime.now()
            )
        else:
            pos = self.positions[code]
            total_value = pos.quantity * pos.avg_price + quantity * price
            new_quantity = pos.quantity + quantity
            if new_quantity > 0:
                pos.avg_price = total_value / new_quantity
            pos.quantity = new_quantity
            pos.last_update = datetime.now()
    
    def get_total_exposure(self) -> float:
        """총 익스포저"""
        return sum(pos.market_value for pos in self.positions.values())
    
    def get_position_weights(self) -> dict[str, float]:
        """포지션별 비중"""
        total = self.get_total_exposure()
        if total == 0:
            return {code: 0.0 for code in self.positions}
        return {code: pos.market_value / total 
                for code, pos in self.positions.items()}