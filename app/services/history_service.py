# -*- coding: utf-8 -*-
"""
app/services/history_service.py
히스토리 서비스 (단일 책임: 백테스트/튜닝 히스토리 저장 및 조회)
"""
import json
import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from app.services.backtest_service import ConfigLoader

logger = logging.getLogger(__name__)


@dataclass
class BacktestHistoryRecord:
    """백테스트 히스토리 레코드"""

    id: int
    created_at: str
    run_type: str  # 'single' or 'tuning'
    tuning_session_id: Optional[str]
    lookback_months: Optional[int]
    start_date: str
    end_date: str
    ma_period: int
    rsi_period: int
    stop_loss: float
    max_positions: int
    initial_capital: int
    enable_defense: bool
    cagr: float
    sharpe_ratio: float
    max_drawdown: float
    total_return: float
    num_trades: int
    win_rate: float
    volatility: float
    calmar_ratio: float


@dataclass
class TuningSessionRecord:
    """튜닝 세션 레코드"""

    id: str
    created_at: str
    total_trials: int
    completed_trials: int
    lookback_months: List[int]
    optimization_metric: str
    best_sharpe: float
    best_params: Dict
    ensemble_params: Dict
    lookback_results: Dict
    status: str  # 'running', 'completed', 'stopped', 'failed'


class HistoryService:
    """히스토리 서비스"""

    def __init__(self):
        db_path = ConfigLoader.get("data", "db_path")
        self._db_path = Path(db_path).parent / "backtest_history.db"
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()

    def _init_database(self):
        """데이터베이스 초기화"""
        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.cursor()

            # 백테스트 히스토리 테이블
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS backtest_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TIMESTAMP DEFAULT (DATETIME('now', 'localtime')),
                    run_type TEXT NOT NULL,
                    tuning_session_id TEXT,
                    lookback_months INTEGER,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    ma_period INTEGER NOT NULL,
                    rsi_period INTEGER NOT NULL,
                    stop_loss REAL NOT NULL,
                    max_positions INTEGER NOT NULL,
                    initial_capital INTEGER NOT NULL,
                    enable_defense INTEGER NOT NULL,
                    cagr REAL NOT NULL,
                    sharpe_ratio REAL NOT NULL,
                    max_drawdown REAL NOT NULL,
                    total_return REAL NOT NULL,
                    num_trades INTEGER NOT NULL,
                    win_rate REAL NOT NULL,
                    volatility REAL NOT NULL,
                    calmar_ratio REAL NOT NULL,
                    -- Train/Val/Test 분할 성과 (JSON)
                    train_metrics_json TEXT,
                    val_metrics_json TEXT,
                    test_metrics_json TEXT,
                    -- 엔진 헬스체크 (JSON)
                    engine_health_json TEXT,
                    -- 경고 메시지 (JSON)
                    warnings_json TEXT
                )
            """
            )

            # 튜닝 세션 테이블
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS tuning_sessions (
                    id TEXT PRIMARY KEY,
                    created_at TIMESTAMP DEFAULT (DATETIME('now', 'localtime')),
                    total_trials INTEGER NOT NULL,
                    completed_trials INTEGER NOT NULL,
                    lookback_months_json TEXT NOT NULL,
                    optimization_metric TEXT NOT NULL,
                    best_sharpe REAL,
                    best_params_json TEXT,
                    ensemble_params_json TEXT,
                    lookback_results_json TEXT,
                    status TEXT NOT NULL
                )
            """
            )

            # 인덱스 생성
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_backtest_created_at
                ON backtest_history(created_at DESC)
            """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_backtest_sharpe
                ON backtest_history(sharpe_ratio DESC)
            """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_backtest_session
                ON backtest_history(tuning_session_id)
            """
            )

            # 기존 테이블에 새 컬럼 추가 (마이그레이션)
            new_columns = [
                ("train_metrics_json", "TEXT"),
                ("val_metrics_json", "TEXT"),
                ("test_metrics_json", "TEXT"),
                ("engine_health_json", "TEXT"),
                ("warnings_json", "TEXT"),
            ]
            for col_name, col_type in new_columns:
                try:
                    cursor.execute(
                        f"ALTER TABLE backtest_history ADD COLUMN {col_name} {col_type}"
                    )
                except sqlite3.OperationalError:
                    pass  # 컬럼이 이미 존재함

            conn.commit()

        logger.info(f"히스토리 DB 초기화 완료: {self._db_path}")

    def save_backtest(
        self,
        params: Dict,
        result: Dict,
        run_type: str = "single",
        tuning_session_id: Optional[str] = None,
        lookback_months: Optional[int] = None,
        train_metrics: Optional[Dict] = None,
        val_metrics: Optional[Dict] = None,
        test_metrics: Optional[Dict] = None,
        engine_health: Optional[Dict] = None,
        warnings: Optional[List[str]] = None,
    ) -> int:
        """
        백테스트 결과 저장

        Args:
            params: 백테스트 파라미터
            result: 백테스트 결과
            run_type: 실행 유형 ('single' or 'tuning')
            tuning_session_id: 튜닝 세션 ID (튜닝 시)
            lookback_months: 룩백 기간 (튜닝 시)
            train_metrics: Train 구간 성과 (선택)
            val_metrics: Validation 구간 성과 (선택)
            test_metrics: Test 구간 성과 (선택)
            engine_health: 엔진 헬스체크 결과 (선택)
            warnings: 경고 메시지 목록 (선택)

        Returns:
            저장된 레코드 ID

        Raises:
            ValueError: 저장 실패 시
        """
        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO backtest_history (
                    run_type, tuning_session_id, lookback_months,
                    start_date, end_date, ma_period, rsi_period,
                    stop_loss, max_positions, initial_capital, enable_defense,
                    cagr, sharpe_ratio, max_drawdown, total_return,
                    num_trades, win_rate, volatility, calmar_ratio,
                    train_metrics_json, val_metrics_json, test_metrics_json,
                    engine_health_json, warnings_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    run_type,
                    tuning_session_id,
                    lookback_months,
                    params["start_date"],
                    params["end_date"],
                    params["ma_period"],
                    params["rsi_period"],
                    params["stop_loss"],
                    params["max_positions"],
                    params["initial_capital"],
                    1 if params.get("enable_defense", True) else 0,
                    result["cagr"],
                    result["sharpe_ratio"],
                    result["max_drawdown"],
                    result["total_return"],
                    result["num_trades"],
                    result["win_rate"],
                    result["volatility"],
                    result["calmar_ratio"],
                    json.dumps(train_metrics) if train_metrics else None,
                    json.dumps(val_metrics) if val_metrics else None,
                    json.dumps(test_metrics) if test_metrics else None,
                    json.dumps(engine_health) if engine_health else None,
                    json.dumps(warnings) if warnings else None,
                ),
            )

            conn.commit()
            record_id = cursor.lastrowid

        logger.info(
            f"백테스트 히스토리 저장: ID={record_id}, Sharpe={result['sharpe_ratio']:.2f}"
        )
        return record_id

    def create_tuning_session(
        self,
        session_id: str,
        total_trials: int,
        lookback_months: List[int],
        optimization_metric: str,
    ) -> None:
        """
        튜닝 세션 생성

        Args:
            session_id: 세션 ID
            total_trials: 총 trial 수
            lookback_months: 룩백 기간 목록
            optimization_metric: 최적화 지표
        """
        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO tuning_sessions (
                    id, total_trials, completed_trials,
                    lookback_months_json, optimization_metric,
                    best_sharpe, best_params_json, ensemble_params_json,
                    lookback_results_json, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    session_id,
                    total_trials,
                    0,
                    json.dumps(lookback_months),
                    optimization_metric,
                    0.0,
                    "{}",
                    "{}",
                    "{}",
                    "running",
                ),
            )

            conn.commit()

        logger.info(f"튜닝 세션 생성: {session_id}")

    def update_tuning_session(
        self,
        session_id: str,
        completed_trials: Optional[int] = None,
        best_sharpe: Optional[float] = None,
        best_params: Optional[Dict] = None,
        ensemble_params: Optional[Dict] = None,
        lookback_results: Optional[Dict] = None,
        status: Optional[str] = None,
    ) -> None:
        """
        튜닝 세션 업데이트

        Args:
            session_id: 세션 ID
            completed_trials: 완료된 trial 수
            best_sharpe: 최고 Sharpe
            best_params: 최적 파라미터
            ensemble_params: 앙상블 파라미터
            lookback_results: 룩백별 결과
            status: 상태
        """
        updates = []
        values = []

        if completed_trials is not None:
            updates.append("completed_trials = ?")
            values.append(completed_trials)
        if best_sharpe is not None:
            updates.append("best_sharpe = ?")
            values.append(best_sharpe)
        if best_params is not None:
            updates.append("best_params_json = ?")
            values.append(json.dumps(best_params))
        if ensemble_params is not None:
            updates.append("ensemble_params_json = ?")
            values.append(json.dumps(ensemble_params))
        if lookback_results is not None:
            updates.append("lookback_results_json = ?")
            values.append(json.dumps(lookback_results))
        if status is not None:
            updates.append("status = ?")
            values.append(status)

        if not updates:
            return

        values.append(session_id)

        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"UPDATE tuning_sessions SET {', '.join(updates)} WHERE id = ?",
                values,
            )
            conn.commit()

    def get_backtest_history(
        self,
        limit: int = 100,
        run_type: Optional[str] = None,
        order_by: str = "created_at",
        ascending: bool = False,
    ) -> List[Dict]:
        """
        백테스트 히스토리 조회

        Args:
            limit: 조회 개수
            run_type: 실행 유형 필터 ('single' or 'tuning')
            order_by: 정렬 기준
            ascending: 오름차순 여부

        Returns:
            히스토리 목록
        """
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            where_clause = ""
            params = []
            if run_type:
                where_clause = "WHERE run_type = ?"
                params.append(run_type)

            order = "ASC" if ascending else "DESC"
            query = f"""
                SELECT * FROM backtest_history
                {where_clause}
                ORDER BY {order_by} {order}
                LIMIT ?
            """
            params.append(limit)

            cursor.execute(query, params)
            rows = cursor.fetchall()

        return [dict(row) for row in rows]

    def get_tuning_sessions(
        self,
        limit: int = 20,
        status: Optional[str] = None,
    ) -> List[Dict]:
        """
        튜닝 세션 목록 조회

        Args:
            limit: 조회 개수
            status: 상태 필터

        Returns:
            세션 목록
        """
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            where_clause = ""
            params = []
            if status:
                where_clause = "WHERE status = ?"
                params.append(status)

            query = f"""
                SELECT * FROM tuning_sessions
                {where_clause}
                ORDER BY created_at DESC
                LIMIT ?
            """
            params.append(limit)

            cursor.execute(query, params)
            rows = cursor.fetchall()

        result = []
        for row in rows:
            record = dict(row)
            record["lookback_months"] = json.loads(record["lookback_months_json"])
            record["best_params"] = json.loads(record["best_params_json"])
            record["ensemble_params"] = json.loads(record["ensemble_params_json"])
            record["lookback_results"] = json.loads(record["lookback_results_json"])
            del record["lookback_months_json"]
            del record["best_params_json"]
            del record["ensemble_params_json"]
            del record["lookback_results_json"]
            result.append(record)

        return result

    def get_tuning_session(self, session_id: str) -> Optional[Dict]:
        """
        튜닝 세션 조회

        Args:
            session_id: 세션 ID

        Returns:
            세션 정보
        """
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM tuning_sessions WHERE id = ?", (session_id,))
            row = cursor.fetchone()

        if not row:
            return None

        record = dict(row)
        record["lookback_months"] = json.loads(record["lookback_months_json"])
        record["best_params"] = json.loads(record["best_params_json"])
        record["ensemble_params"] = json.loads(record["ensemble_params_json"])
        record["lookback_results"] = json.loads(record["lookback_results_json"])
        del record["lookback_months_json"]
        del record["best_params_json"]
        del record["ensemble_params_json"]
        del record["lookback_results_json"]

        return record

    def get_best_backtest(self, metric: str = "sharpe_ratio") -> Optional[Dict]:
        """
        최고 성과 백테스트 조회

        Args:
            metric: 평가 지표 (sharpe_ratio, cagr, calmar_ratio)

        Returns:
            최고 성과 레코드
        """
        valid_metrics = ["sharpe_ratio", "cagr", "calmar_ratio", "max_drawdown"]
        if metric not in valid_metrics:
            raise ValueError(f"metric은 {valid_metrics} 중 하나여야 합니다")

        order = "ASC" if metric == "max_drawdown" else "DESC"

        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(
                f"""
                SELECT * FROM backtest_history
                WHERE {metric} IS NOT NULL
                ORDER BY {metric} {order}
                LIMIT 1
            """
            )
            row = cursor.fetchone()

        return dict(row) if row else None

    def get_session_trials(self, session_id: str) -> List[Dict]:
        """
        튜닝 세션의 모든 trial 조회

        Args:
            session_id: 세션 ID

        Returns:
            trial 목록
        """
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT * FROM backtest_history
                WHERE tuning_session_id = ?
                ORDER BY sharpe_ratio DESC
            """,
                (session_id,),
            )
            rows = cursor.fetchall()

        return [dict(row) for row in rows]

    def get_statistics(self) -> Dict:
        """
        전체 통계 조회

        Returns:
            통계 정보
        """
        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.cursor()

            # 백테스트 통계
            cursor.execute(
                """
                SELECT
                    COUNT(*) as total_backtests,
                    AVG(sharpe_ratio) as avg_sharpe,
                    MAX(sharpe_ratio) as max_sharpe,
                    AVG(cagr) as avg_cagr,
                    MAX(cagr) as max_cagr,
                    AVG(max_drawdown) as avg_mdd,
                    MIN(max_drawdown) as min_mdd
                FROM backtest_history
            """
            )
            bt_stats = cursor.fetchone()

            # 튜닝 세션 통계
            cursor.execute(
                """
                SELECT
                    COUNT(*) as total_sessions,
                    SUM(completed_trials) as total_trials,
                    MAX(best_sharpe) as best_sharpe
                FROM tuning_sessions
            """
            )
            tuning_stats = cursor.fetchone()

        return {
            "backtest": {
                "total": bt_stats[0] or 0,
                "avg_sharpe": bt_stats[1] or 0,
                "max_sharpe": bt_stats[2] or 0,
                "avg_cagr": bt_stats[3] or 0,
                "max_cagr": bt_stats[4] or 0,
                "avg_mdd": bt_stats[5] or 0,
                "min_mdd": bt_stats[6] or 0,
            },
            "tuning": {
                "total_sessions": tuning_stats[0] or 0,
                "total_trials": tuning_stats[1] or 0,
                "best_sharpe": tuning_stats[2] or 0,
            },
        }
