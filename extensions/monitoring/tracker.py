# -*- coding: utf-8 -*-
"""
extensions/monitoring/tracker.py
신호 및 성과 추적
"""
import logging
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import List, Dict, Optional
import pandas as pd

from extensions.realtime.signal_generator import Signal

logger = logging.getLogger(__name__)


class SignalTracker:
    """신호 이력 추적"""
    
    def __init__(self, db_path: Path = None):
        """
        Args:
            db_path: SQLite DB 경로
        """
        self.db_path = db_path or Path('data/monitoring/signals.db')
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._init_db()
        logger.info(f"SignalTracker 초기화: {self.db_path}")
    
    def _init_db(self):
        """DB 초기화"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 신호 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_date DATE NOT NULL,
                code TEXT NOT NULL,
                name TEXT,
                action TEXT NOT NULL,
                confidence REAL,
                target_weight REAL,
                current_price REAL,
                ma_value REAL,
                rsi_value REAL,
                maps_score REAL,
                reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(signal_date, code)
            )
        """)
        
        # 인덱스
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_signals_date 
            ON signals(signal_date)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_signals_code 
            ON signals(code)
        """)
        
        conn.commit()
        conn.close()
    
    def save_signals(self, signals: List[Signal], signal_date: date):
        """
        신호 저장
        
        Args:
            signals: 신호 리스트
            signal_date: 신호 날짜
        """
        if not signals:
            logger.warning(f"저장할 신호 없음: {signal_date}")
            return
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for signal in signals:
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO signals 
                    (signal_date, code, name, action, confidence, target_weight,
                     current_price, ma_value, rsi_value, maps_score, reason)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    signal_date.isoformat(),
                    signal.code,
                    signal.name,
                    signal.action,
                    signal.confidence,
                    signal.target_weight,
                    signal.current_price,
                    signal.ma_value,
                    signal.rsi_value,
                    signal.maps_score,
                    signal.reason
                ))
            except Exception as e:
                logger.error(f"신호 저장 실패 [{signal.code}]: {e}")
        
        conn.commit()
        conn.close()
        
        logger.info(f"신호 저장 완료: {signal_date}, {len(signals)}개")
    
    def get_signals(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        code: Optional[str] = None
    ) -> pd.DataFrame:
        """
        신호 조회
        
        Args:
            start_date: 시작 날짜
            end_date: 종료 날짜
            code: 종목 코드
            
        Returns:
            신호 DataFrame
        """
        conn = sqlite3.connect(self.db_path)
        
        query = "SELECT * FROM signals WHERE 1=1"
        params = []
        
        if start_date:
            query += " AND signal_date >= ?"
            params.append(start_date.isoformat())
        
        if end_date:
            query += " AND signal_date <= ?"
            params.append(end_date.isoformat())
        
        if code:
            query += " AND code = ?"
            params.append(code)
        
        query += " ORDER BY signal_date DESC, code"
        
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        
        return df
    
    def get_signal_stats(self, days: int = 30) -> Dict:
        """
        신호 통계
        
        Args:
            days: 조회 기간 (일)
            
        Returns:
            통계 딕셔너리
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 최근 N일 통계
        cursor.execute("""
            SELECT 
                COUNT(*) as total_signals,
                SUM(CASE WHEN action = 'BUY' THEN 1 ELSE 0 END) as buy_count,
                SUM(CASE WHEN action = 'SELL' THEN 1 ELSE 0 END) as sell_count,
                AVG(confidence) as avg_confidence,
                AVG(maps_score) as avg_maps
            FROM signals
            WHERE signal_date >= date('now', '-' || ? || ' days')
        """, (days,))
        
        row = cursor.fetchone()
        conn.close()
        
        return {
            'total_signals': row[0] or 0,
            'buy_count': row[1] or 0,
            'sell_count': row[2] or 0,
            'avg_confidence': row[3] or 0.0,
            'avg_maps': row[4] or 0.0
        }


class PerformanceTracker:
    """성과 추적"""
    
    def __init__(self, db_path: Path = None):
        """
        Args:
            db_path: SQLite DB 경로
        """
        self.db_path = db_path or Path('data/monitoring/performance.db')
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._init_db()
        logger.info(f"PerformanceTracker 초기화: {self.db_path}")
    
    def _init_db(self):
        """DB 초기화"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 일일 성과 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                performance_date DATE NOT NULL UNIQUE,
                total_value REAL,
                cash REAL,
                positions_value REAL,
                daily_return REAL,
                cumulative_return REAL,
                position_count INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 포지션 스냅샷 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS position_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot_date DATE NOT NULL,
                code TEXT NOT NULL,
                quantity INTEGER,
                avg_price REAL,
                current_price REAL,
                market_value REAL,
                weight REAL,
                unrealized_pnl REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(snapshot_date, code)
            )
        """)
        
        # 인덱스
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_daily_performance_date 
            ON daily_performance(performance_date)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_position_snapshots_date 
            ON position_snapshots(snapshot_date)
        """)
        
        conn.commit()
        conn.close()
    
    def save_daily_performance(
        self,
        performance_date: date,
        total_value: float,
        cash: float,
        positions_value: float,
        daily_return: float,
        cumulative_return: float,
        position_count: int
    ):
        """
        일일 성과 저장
        
        Args:
            performance_date: 날짜
            total_value: 총 자산
            cash: 현금
            positions_value: 포지션 가치
            daily_return: 일일 수익률
            cumulative_return: 누적 수익률
            position_count: 포지션 수
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO daily_performance
            (performance_date, total_value, cash, positions_value, 
             daily_return, cumulative_return, position_count)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            performance_date.isoformat(),
            total_value,
            cash,
            positions_value,
            daily_return,
            cumulative_return,
            position_count
        ))
        
        conn.commit()
        conn.close()
        
        logger.info(f"일일 성과 저장: {performance_date}, 수익률={daily_return:.2%}")
    
    def get_performance(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> pd.DataFrame:
        """
        성과 조회
        
        Args:
            start_date: 시작 날짜
            end_date: 종료 날짜
            
        Returns:
            성과 DataFrame
        """
        conn = sqlite3.connect(self.db_path)
        
        query = "SELECT * FROM daily_performance WHERE 1=1"
        params = []
        
        if start_date:
            query += " AND performance_date >= ?"
            params.append(start_date.isoformat())
        
        if end_date:
            query += " AND performance_date <= ?"
            params.append(end_date.isoformat())
        
        query += " ORDER BY performance_date"
        
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        
        return df
    
    def get_latest_performance(self) -> Optional[Dict]:
        """최근 성과 조회"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM daily_performance
            ORDER BY performance_date DESC
            LIMIT 1
        """)
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return {
            'date': row[1],
            'total_value': row[2],
            'cash': row[3],
            'positions_value': row[4],
            'daily_return': row[5],
            'cumulative_return': row[6],
            'position_count': row[7]
        }
