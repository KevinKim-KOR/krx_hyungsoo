# -*- coding: utf-8 -*-
"""
extensions/realtime/position_tracker.py
포지션 추적 및 리밸런싱 액션 생성
"""
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass
import pandas as pd
import sqlite3

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """현재 포지션"""
    code: str
    name: str
    quantity: int
    avg_price: float
    current_price: float
    market_value: float
    weight: float
    unrealized_pnl: float
    unrealized_pnl_pct: float


@dataclass
class Action:
    """리밸런싱 액션"""
    code: str
    name: str
    action_type: str  # 'BUY', 'SELL', 'HOLD'
    current_weight: float
    target_weight: float
    weight_diff: float
    current_quantity: int
    target_quantity: int
    quantity_diff: int
    current_price: float
    estimated_amount: float
    priority: int  # 실행 우선순위 (1=높음)
    reason: str


class PositionTracker:
    """포지션 추적기"""
    
    def __init__(
        self,
        db_path: Path = None,
        initial_capital: float = 10_000_000
    ):
        """
        Args:
            db_path: 포지션 DB 경로
            initial_capital: 초기 자본
        """
        self.db_path = db_path or Path('data/positions.db')
        self.initial_capital = initial_capital
        
        # DB 초기화
        self._init_db()
        
        logger.info(f"포지션 추적기 초기화: {self.db_path}")
    
    def _init_db(self):
        """DB 초기화"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 포지션 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS positions (
                code TEXT PRIMARY KEY,
                name TEXT,
                quantity INTEGER,
                avg_price REAL,
                last_updated TEXT
            )
        """)
        
        # 거래 이력 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                code TEXT,
                name TEXT,
                action TEXT,
                quantity INTEGER,
                price REAL,
                amount REAL,
                reason TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 포트폴리오 스냅샷 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS portfolio_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                total_value REAL,
                cash REAL,
                positions_value REAL,
                num_positions INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        conn.close()
    
    def get_current_positions(self, current_prices: Dict[str, float]) -> List[Position]:
        """
        현재 포지션 조회
        
        Args:
            current_prices: 현재 가격 딕셔너리 {code: price}
            
        Returns:
            포지션 리스트
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT code, name, quantity, avg_price FROM positions WHERE quantity > 0")
        rows = cursor.fetchall()
        conn.close()
        
        positions = []
        total_value = 0.0
        
        for code, name, quantity, avg_price in rows:
            current_price = current_prices.get(code, avg_price)
            market_value = quantity * current_price
            total_value += market_value
            
            unrealized_pnl = (current_price - avg_price) * quantity
            unrealized_pnl_pct = (current_price / avg_price - 1) * 100 if avg_price > 0 else 0
            
            positions.append(Position(
                code=code,
                name=name,
                quantity=quantity,
                avg_price=avg_price,
                current_price=current_price,
                market_value=market_value,
                weight=0.0,  # 나중에 계산
                unrealized_pnl=unrealized_pnl,
                unrealized_pnl_pct=unrealized_pnl_pct
            ))
        
        # 비중 계산
        if total_value > 0:
            for pos in positions:
                pos.weight = pos.market_value / total_value
        
        return positions
    
    def get_rebalancing_actions(
        self,
        current_positions: List[Position],
        target_weights: Dict[str, float],
        current_prices: Dict[str, float],
        total_capital: float = None
    ) -> List[Action]:
        """
        리밸런싱 액션 생성
        
        Args:
            current_positions: 현재 포지션
            target_weights: 목표 비중 {code: weight}
            current_prices: 현재 가격 {code: price}
            total_capital: 총 자본 (None이면 현재 포트폴리오 가치)
            
        Returns:
            액션 리스트
        """
        # 현재 포트폴리오 가치 계산
        if total_capital is None:
            total_capital = sum(pos.market_value for pos in current_positions)
            if total_capital == 0:
                total_capital = self.initial_capital
        
        # 현재 포지션 딕셔너리
        current_dict = {pos.code: pos for pos in current_positions}
        
        # 모든 종목 (현재 + 목표)
        all_codes = set(current_dict.keys()) | set(target_weights.keys())
        
        actions = []
        
        for code in all_codes:
            # 현재 상태
            current_pos = current_dict.get(code)
            current_weight = current_pos.weight if current_pos else 0.0
            current_quantity = current_pos.quantity if current_pos else 0
            current_price = current_prices.get(code, 0.0)
            
            # 목표 상태
            target_weight = target_weights.get(code, 0.0)
            target_value = total_capital * target_weight
            target_quantity = int(target_value / current_price) if current_price > 0 else 0
            
            # 차이 계산
            weight_diff = target_weight - current_weight
            quantity_diff = target_quantity - current_quantity
            
            # 액션 결정
            if abs(weight_diff) < 0.01:  # 1% 미만 차이는 무시
                action_type = 'HOLD'
                priority = 3
                reason = "비중 차이 미미"
            elif quantity_diff > 0:
                action_type = 'BUY'
                priority = 1 if weight_diff > 0.05 else 2
                reason = f"목표 비중 {target_weight:.1%} 달성"
            elif quantity_diff < 0:
                action_type = 'SELL'
                priority = 1 if weight_diff < -0.05 else 2
                reason = f"목표 비중 {target_weight:.1%} 조정"
            else:
                action_type = 'HOLD'
                priority = 3
                reason = "변동 없음"
            
            # 예상 금액
            estimated_amount = abs(quantity_diff) * current_price
            
            # 액션 생성
            action = Action(
                code=code,
                name=current_pos.name if current_pos else code,
                action_type=action_type,
                current_weight=current_weight,
                target_weight=target_weight,
                weight_diff=weight_diff,
                current_quantity=current_quantity,
                target_quantity=target_quantity,
                quantity_diff=quantity_diff,
                current_price=current_price,
                estimated_amount=estimated_amount,
                priority=priority,
                reason=reason
            )
            
            actions.append(action)
        
        # 우선순위 정렬
        actions.sort(key=lambda x: (x.priority, -abs(x.weight_diff)))
        
        return actions
    
    def execute_action(self, action: Action, execution_date: date = None):
        """
        액션 실행 (DB 업데이트)
        
        Args:
            action: 실행할 액션
            execution_date: 실행 날짜
        """
        if execution_date is None:
            execution_date = date.today()
        
        if action.action_type == 'HOLD':
            return
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # 현재 포지션 조회
            cursor.execute("SELECT quantity, avg_price FROM positions WHERE code = ?", (action.code,))
            row = cursor.fetchone()
            
            if row:
                current_quantity, current_avg_price = row
            else:
                current_quantity, current_avg_price = 0, 0.0
            
            # 새로운 수량 및 평균 단가 계산
            if action.action_type == 'BUY':
                new_quantity = current_quantity + action.quantity_diff
                total_cost = current_quantity * current_avg_price + action.quantity_diff * action.current_price
                new_avg_price = total_cost / new_quantity if new_quantity > 0 else 0.0
            else:  # SELL
                new_quantity = current_quantity + action.quantity_diff  # quantity_diff는 음수
                new_avg_price = current_avg_price  # 매도 시 평균 단가 유지
            
            # 포지션 업데이트
            if new_quantity > 0:
                cursor.execute("""
                    INSERT OR REPLACE INTO positions (code, name, quantity, avg_price, last_updated)
                    VALUES (?, ?, ?, ?, ?)
                """, (action.code, action.name, new_quantity, new_avg_price, execution_date.isoformat()))
            else:
                cursor.execute("DELETE FROM positions WHERE code = ?", (action.code,))
            
            # 거래 이력 저장
            cursor.execute("""
                INSERT INTO transactions (date, code, name, action, quantity, price, amount, reason)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                execution_date.isoformat(),
                action.code,
                action.name,
                action.action_type,
                abs(action.quantity_diff),
                action.current_price,
                action.estimated_amount,
                action.reason
            ))
            
            conn.commit()
            logger.info(f"액션 실행: {action.action_type} {action.code} {abs(action.quantity_diff)}주")
        
        except Exception as e:
            conn.rollback()
            logger.error(f"액션 실행 실패: {e}")
            raise
        
        finally:
            conn.close()
    
    def save_snapshot(self, positions: List[Position], snapshot_date: date = None):
        """
        포트폴리오 스냅샷 저장
        
        Args:
            positions: 포지션 리스트
            snapshot_date: 스냅샷 날짜
        """
        if snapshot_date is None:
            snapshot_date = date.today()
        
        total_value = sum(pos.market_value for pos in positions)
        positions_value = total_value
        cash = 0.0  # TODO: 현금 추적 구현
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO portfolio_snapshots (date, total_value, cash, positions_value, num_positions)
            VALUES (?, ?, ?, ?, ?)
        """, (
            snapshot_date.isoformat(),
            total_value,
            cash,
            positions_value,
            len(positions)
        ))
        
        conn.commit()
        conn.close()
        
        logger.info(f"스냅샷 저장: {snapshot_date} (총 가치: {total_value:,.0f}원)")
    
    def get_transaction_history(self, start_date: date = None, end_date: date = None) -> pd.DataFrame:
        """
        거래 이력 조회
        
        Args:
            start_date: 시작 날짜
            end_date: 종료 날짜
            
        Returns:
            거래 이력 DataFrame
        """
        conn = sqlite3.connect(self.db_path)
        
        query = "SELECT * FROM transactions WHERE 1=1"
        params = []
        
        if start_date:
            query += " AND date >= ?"
            params.append(start_date.isoformat())
        
        if end_date:
            query += " AND date <= ?"
            params.append(end_date.isoformat())
        
        query += " ORDER BY date DESC, created_at DESC"
        
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        
        return df
