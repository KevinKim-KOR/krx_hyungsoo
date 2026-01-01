# -*- coding: utf-8 -*-
"""
extensions/ui/backtest_database.py
백테스트 히스토리 데이터베이스

기능:
- 백테스트 결과 저장
- 히스토리 조회
- 파라미터 비교
"""

import sqlite3
from datetime import datetime
from typing import Optional, List, Dict
import pandas as pd
import json
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class BacktestDatabase:
    """
    백테스트 히스토리 데이터베이스
    
    기능:
    1. 백테스트 결과 저장
    2. 히스토리 조회
    3. 파라미터별 비교
    """
    
    def __init__(self, db_path: str = "data/output/backtest_history.db"):
        """
        Args:
            db_path: 데이터베이스 파일 경로
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()
    
    def _init_database(self):
        """데이터베이스 초기화"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 백테스트 히스토리 테이블
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS backtest_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    params_json TEXT NOT NULL,
                    cagr REAL,
                    sharpe_ratio REAL,
                    max_drawdown REAL,
                    total_return_pct REAL,
                    num_trades INTEGER,
                    regime_stats_json TEXT,
                    notes TEXT
                )
            """)
            
            conn.commit()
    
    def save_result(
        self,
        params: Dict,
        results: Dict,
        notes: Optional[str] = None
    ) -> int:
        """
        백테스트 결과 저장
        
        Args:
            params: 파라미터 딕셔너리
            results: 결과 딕셔너리
            notes: 메모
        
        Returns:
            int: 저장된 레코드 ID
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO backtest_history (
                        params_json, cagr, sharpe_ratio, max_drawdown,
                        total_return_pct, num_trades, regime_stats_json, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    json.dumps(params, ensure_ascii=False),
                    results.get('cagr'),
                    results.get('sharpe_ratio'),
                    results.get('max_drawdown'),
                    results.get('total_return_pct'),
                    results.get('num_trades'),
                    json.dumps(results.get('regime_stats', {}), ensure_ascii=False),
                    notes
                ))
                
                conn.commit()
                return cursor.lastrowid
                
        except Exception as e:
            logger.error(f"결과 저장 실패: {e}")
            return -1
    
    def get_history(
        self,
        limit: Optional[int] = None,
        order_by: str = 'created_at',
        ascending: bool = False
    ) -> pd.DataFrame:
        """
        히스토리 조회
        
        Args:
            limit: 조회할 레코드 수
            order_by: 정렬 기준 컬럼
            ascending: 오름차순 여부
        
        Returns:
            pd.DataFrame: 히스토리 데이터
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                query = f"""
                    SELECT 
                        id, created_at, params_json, cagr, sharpe_ratio,
                        max_drawdown, total_return_pct, num_trades,
                        regime_stats_json, notes
                    FROM backtest_history
                    ORDER BY {order_by} {'ASC' if ascending else 'DESC'}
                """
                
                if limit:
                    query += f" LIMIT {limit}"
                
                df = pd.read_sql_query(query, conn)
                
                # JSON 파싱
                if not df.empty:
                    df['params'] = df['params_json'].apply(json.loads)
                    df['regime_stats'] = df['regime_stats_json'].apply(
                        lambda x: json.loads(x) if x else {}
                    )
                
                return df
                
        except Exception as e:
            logger.error(f"히스토리 조회 실패: {e}")
            return pd.DataFrame()
    
    def get_by_id(self, record_id: int) -> Optional[Dict]:
        """
        ID로 레코드 조회
        
        Args:
            record_id: 레코드 ID
        
        Returns:
            Optional[Dict]: 레코드 데이터
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT 
                        id, created_at, params_json, cagr, sharpe_ratio,
                        max_drawdown, total_return_pct, num_trades,
                        regime_stats_json, notes
                    FROM backtest_history
                    WHERE id = ?
                """, (record_id,))
                
                row = cursor.fetchone()
                if not row:
                    return None
                
                return {
                    'id': row[0],
                    'created_at': row[1],
                    'params': json.loads(row[2]),
                    'cagr': row[3],
                    'sharpe_ratio': row[4],
                    'max_drawdown': row[5],
                    'total_return_pct': row[6],
                    'num_trades': row[7],
                    'regime_stats': json.loads(row[8]) if row[8] else {},
                    'notes': row[9]
                }
                
        except Exception as e:
            logger.error(f"레코드 조회 실패: {e}")
            return None
    
    def compare_results(self, ids: List[int]) -> pd.DataFrame:
        """
        여러 결과 비교
        
        Args:
            ids: 비교할 레코드 ID 리스트
        
        Returns:
            pd.DataFrame: 비교 데이터
        """
        try:
            records = []
            for record_id in ids:
                record = self.get_by_id(record_id)
                if record:
                    records.append(record)
            
            if not records:
                return pd.DataFrame()
            
            # DataFrame 생성
            df = pd.DataFrame(records)
            
            return df
            
        except Exception as e:
            logger.error(f"결과 비교 실패: {e}")
            return pd.DataFrame()
    
    def get_best_result(self, metric: str = 'sharpe_ratio') -> Optional[Dict]:
        """
        최고 성과 조회
        
        Args:
            metric: 평가 지표 (cagr, sharpe_ratio, max_drawdown)
        
        Returns:
            Optional[Dict]: 최고 성과 레코드
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # MDD는 최소값이 좋음
                order = 'ASC' if metric == 'max_drawdown' else 'DESC'
                
                cursor.execute(f"""
                    SELECT 
                        id, created_at, params_json, cagr, sharpe_ratio,
                        max_drawdown, total_return_pct, num_trades,
                        regime_stats_json, notes
                    FROM backtest_history
                    WHERE {metric} IS NOT NULL
                    ORDER BY {metric} {order}
                    LIMIT 1
                """)
                
                row = cursor.fetchone()
                if not row:
                    return None
                
                return {
                    'id': row[0],
                    'created_at': row[1],
                    'params': json.loads(row[2]),
                    'cagr': row[3],
                    'sharpe_ratio': row[4],
                    'max_drawdown': row[5],
                    'total_return_pct': row[6],
                    'num_trades': row[7],
                    'regime_stats': json.loads(row[8]) if row[8] else {},
                    'notes': row[9]
                }
                
        except Exception as e:
            logger.error(f"최고 성과 조회 실패: {e}")
            return None
