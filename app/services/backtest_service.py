# -*- coding: utf-8 -*-
"""
app/services/backtest_service.py
백테스트 서비스 (단일 책임: 백테스트 실행)
"""
import logging
from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Optional

import yaml
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class BacktestParams:
    """백테스트 파라미터 (필수값만, default 없음)"""

    start_date: date
    end_date: date
    ma_period: int
    rsi_period: int
    stop_loss: float
    initial_capital: int
    max_positions: int
    enable_defense: bool


@dataclass
class BacktestResult:
    """백테스트 결과"""

    cagr: float
    sharpe_ratio: float
    max_drawdown: float
    total_return: float
    num_trades: int
    win_rate: float
    volatility: float
    calmar_ratio: float
    # 엔진 정합성 검증용 추가 필드
    sell_trades: int = 0
    total_costs: float = 0.0
    total_realized_pnl: float = 0.0


@dataclass
class SplitMetrics:
    """Train/Val/Test 분할 성과"""
    cagr: float
    sharpe_ratio: float
    max_drawdown: float
    num_trades: int


@dataclass
class ExtendedBacktestResult:
    """확장된 백테스트 결과 (Train/Val/Test + engine_health + daily_logs)"""

    # 전체 성과
    metrics: BacktestResult
    
    # Train/Val/Test 분할 성과
    train_metrics: Optional[SplitMetrics] = None
    val_metrics: Optional[SplitMetrics] = None
    test_metrics: Optional[SplitMetrics] = None
    
    # 엔진 헬스체크
    engine_health: Optional[Dict] = None
    
    # 일별 비중 로그 (최근 N개만)
    daily_logs: Optional[List[Dict]] = None
    
    # 경고 메시지
    warnings: Optional[List[str]] = None


class ConfigLoader:
    """설정 파일 로더"""

    _config: Optional[Dict] = None
    _backtest_config: Optional[Dict] = None

    @classmethod
    def load(cls) -> Dict:
        if cls._config is None:
            config_path = Path(__file__).parent.parent.parent / "config" / "config.yaml"
            if not config_path.exists():
                raise FileNotFoundError(f"설정 파일 없음: {config_path}")
            with open(config_path, "r", encoding="utf-8") as f:
                cls._config = yaml.safe_load(f)
        return cls._config

    @classmethod
    def load_backtest_config(cls) -> Dict:
        """backtest.yaml 로드"""
        if cls._backtest_config is None:
            config_path = Path(__file__).parent.parent.parent / "config" / "backtest.yaml"
            if not config_path.exists():
                raise FileNotFoundError(f"설정 파일 없음: {config_path}")
            with open(config_path, "r", encoding="utf-8") as f:
                cls._backtest_config = yaml.safe_load(f)
        return cls._backtest_config

    @classmethod
    def get(cls, *keys, required: bool = True):
        """중첩 키로 설정값 조회"""
        config = cls.load()
        value = config
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                if required:
                    raise KeyError(f"필수 설정값 누락: {'.'.join(keys)}")
                return None
        return value

    @classmethod
    def get_tuning_variables(cls) -> Dict:
        """활성화된 튜닝 변수 목록 반환"""
        config = cls.load_backtest_config()
        variables = config.get("tuning_variables", {})

        enabled_vars = {}
        for name, var_config in variables.items():
            if var_config.get("enabled", False):
                enabled_vars[name] = {
                    "min": var_config["range"][0],
                    "max": var_config["range"][1],
                    "default": var_config.get("default"),
                    "step": var_config.get("step", 1),
                    "description": var_config.get("description", ""),
                    "category": var_config.get("category", "other"),
                }
        return enabled_vars

    @classmethod
    def get_all_tuning_variables(cls) -> Dict:
        """모든 튜닝 변수 목록 반환 (활성화 여부 포함)"""
        config = cls.load_backtest_config()
        return config.get("tuning_variables", {})


class BacktestService:
    """백테스트 서비스"""

    def __init__(self, save_history: bool = True):
        self._save_history = save_history
        self._history_service = None
        self._validate_dependencies()

        if self._save_history:
            from app.services.history_service import HistoryService

            self._history_service = HistoryService()

    def _validate_dependencies(self):
        """의존성 검증"""
        try:
            from extensions.backtest.runner import BacktestRunner

            self._runner_class = BacktestRunner
        except ImportError as e:
            raise ImportError(f"BacktestRunner import 실패: {e}")

        try:
            from infra.data.loader import load_price_data
            from core.data.filtering import get_filtered_universe

            self._load_price_data = load_price_data
            self._get_universe = get_filtered_universe
        except ImportError as e:
            raise ImportError(f"데이터 로더 import 실패: {e}")

    def _load_market_index(self, start_date: date, end_date: date):
        """시장 지수 데이터 로드"""
        from pykrx import stock
        import pandas as pd

        kospi_code = ConfigLoader.get("market_index", "kospi_code")

        df = stock.get_index_ohlcv_by_date(
            start_date.strftime("%Y%m%d"),
            end_date.strftime("%Y%m%d"),
            kospi_code,
        )
        df.index = pd.to_datetime(df.index)

        # 컬럼명 변환 (한글 → 영문)
        column_map = {
            "시가": "Open",
            "고가": "High",
            "저가": "Low",
            "종가": "Close",
            "거래량": "Volume",
            "거래대금": "Amount",
        }
        df = df.rename(columns=column_map)

        return df

    def run(self, params: BacktestParams) -> BacktestResult:
        """
        백테스트 실행

        Args:
            params: 백테스트 파라미터 (모든 필드 필수)

        Returns:
            BacktestResult

        Raises:
            ValueError: 데이터 부족 또는 결과 없음
        """
        from datetime import timedelta

        # 데이터 로드
        universe = self._get_universe()
        if not universe:
            raise ValueError("유니버스가 비어있음")

        # 모멘텀 스코어 계산을 위해 룩백 기간(90일) 추가하여 데이터 로드
        lookback_buffer = timedelta(days=90)
        data_start_date = params.start_date - lookback_buffer

        price_data = self._load_price_data(universe, data_start_date, params.end_date)
        if price_data is None or price_data.empty:
            raise ValueError("가격 데이터 로드 실패")

        market_data = self._load_market_index(data_start_date, params.end_date)

        # 백테스트 러너 생성
        runner = self._runner_class(
            initial_capital=params.initial_capital,
            max_positions=params.max_positions,
            enable_defense=params.enable_defense,
        )

        # 유니버스 전체를 target_weights로 전달 (runner가 모멘텀 스코어로 Top N 선정)
        # 비중은 runner 내부에서 동적으로 계산됨
        target_weights = {code: 1.0 / params.max_positions for code in universe}

        # 백테스트 실행 (모든 튜닝 파라미터 전달)
        result = runner.run(
            price_data=price_data,
            target_weights=target_weights,
            start_date=params.start_date,
            end_date=params.end_date,
            market_index_data=market_data,
            ma_period=params.ma_period,
            rsi_period=params.rsi_period,
            stop_loss=params.stop_loss / 100.0,  # % → 소수 변환 (예: -10 → -0.10)
        )

        metrics = result.get("metrics", {})
        trades = result.get("trades", [])

        # 결과 검증 (모두 0이면 경고)
        annual_return = metrics.get("annual_return", 0)
        sharpe = metrics.get("sharpe_ratio", 0)
        mdd = metrics.get("max_drawdown", 0)

        if annual_return == 0 and sharpe == 0 and mdd == 0:
            logger.warning(
                f"백테스트 결과가 비어있음 - 거래 없음 또는 데이터 부족 "
                f"(기간: {params.start_date} ~ {params.end_date})"
            )

        # 엔진에서 이미 퍼센트로 반환하므로 변환 불필요
        # win_rate는 엔진에서 일별 수익률 기준으로 계산됨 (이미 %)
        result_obj = BacktestResult(
            cagr=annual_return,  # 이미 %
            sharpe_ratio=sharpe,
            max_drawdown=mdd,  # 이미 %
            total_return=metrics.get("total_return", 0),  # 이미 %
            num_trades=len(trades),
            win_rate=metrics.get("win_rate", 0),  # 엔진에서 계산된 값 사용 (이미 %)
            volatility=metrics.get("volatility", 0),  # 이미 %
            calmar_ratio=metrics.get("calmar_ratio", 0),
        )

        # 히스토리 저장
        if self._save_history and self._history_service:
            self._history_service.save_backtest(
                params={
                    "start_date": params.start_date.isoformat(),
                    "end_date": params.end_date.isoformat(),
                    "ma_period": params.ma_period,
                    "rsi_period": params.rsi_period,
                    "stop_loss": params.stop_loss,
                    "max_positions": params.max_positions,
                    "initial_capital": params.initial_capital,
                    "enable_defense": params.enable_defense,
                },
                result={
                    "cagr": result_obj.cagr,
                    "sharpe_ratio": result_obj.sharpe_ratio,
                    "max_drawdown": result_obj.max_drawdown,
                    "total_return": result_obj.total_return,
                    "num_trades": result_obj.num_trades,
                    "win_rate": result_obj.win_rate,
                    "volatility": result_obj.volatility,
                    "calmar_ratio": result_obj.calmar_ratio,
                },
                run_type="single",
            )

        return result_obj

    def run_with_split(
        self, 
        params: BacktestParams,
        train_ratio: float = 0.70,
        val_ratio: float = 0.15,
        test_ratio: float = 0.15,
        daily_log_limit: int = 30,
    ) -> ExtendedBacktestResult:
        """
        Train/Val/Test 분할 백테스트 실행
        
        Args:
            params: 백테스트 파라미터
            train_ratio: Train 비율 (기본 70%)
            val_ratio: Validation 비율 (기본 15%)
            test_ratio: Test 비율 (기본 15%)
            daily_log_limit: 반환할 daily_log 개수 (기본 30)
        
        Returns:
            ExtendedBacktestResult (전체 + Train/Val/Test + engine_health + daily_logs)
        """
        from datetime import timedelta
        
        # 데이터 로드
        universe = self._get_universe()
        if not universe:
            raise ValueError("유니버스가 비어있음")
        
        lookback_buffer = timedelta(days=90)
        data_start_date = params.start_date - lookback_buffer
        
        price_data = self._load_price_data(universe, data_start_date, params.end_date)
        if price_data is None or price_data.empty:
            raise ValueError("가격 데이터 로드 실패")
        
        market_data = self._load_market_index(data_start_date, params.end_date)
        
        # 기간 분할 계산
        total_days = (params.end_date - params.start_date).days
        train_days = int(total_days * train_ratio)
        val_days = int(total_days * val_ratio)
        
        train_end = params.start_date + timedelta(days=train_days)
        val_end = train_end + timedelta(days=val_days)
        
        periods = {
            "train": (params.start_date, train_end),
            "val": (train_end + timedelta(days=1), val_end),
            "test": (val_end + timedelta(days=1), params.end_date),
        }
        
        logger.info(f"기간 분할: Train {periods['train']}, Val {periods['val']}, Test {periods['test']}")
        
        # 러너 생성
        runner = self._runner_class(
            initial_capital=params.initial_capital,
            max_positions=params.max_positions,
            enable_defense=params.enable_defense,
        )
        
        target_weights = {code: 1.0 / params.max_positions for code in universe}
        
        # 전체 기간 백테스트
        full_result = runner.run(
            price_data=price_data,
            target_weights=target_weights,
            start_date=params.start_date,
            end_date=params.end_date,
            market_index_data=market_data,
            ma_period=params.ma_period,
            rsi_period=params.rsi_period,
            stop_loss=params.stop_loss / 100.0,
        )
        
        full_metrics = full_result.get("metrics", {})
        engine_health = full_metrics.get("engine_health", {})
        daily_logs = full_result.get("daily_logs", [])
        
        # 전체 성과 객체 (엔진 정합성 검증용 필드 포함)
        overall = BacktestResult(
            cagr=full_metrics.get("annual_return", 0),
            sharpe_ratio=full_metrics.get("sharpe_ratio", 0),
            max_drawdown=full_metrics.get("max_drawdown", 0),
            total_return=full_metrics.get("total_return", 0),
            num_trades=len(full_result.get("trades", [])),
            win_rate=full_metrics.get("win_rate", 0),
            volatility=full_metrics.get("volatility", 0),
            calmar_ratio=full_metrics.get("calmar_ratio", 0),
            # 엔진 정합성 검증용
            sell_trades=full_metrics.get("sell_trades", 0),
            total_costs=full_metrics.get("total_costs", 0.0),
            total_realized_pnl=full_metrics.get("total_realized_pnl", 0.0),
        )
        
        # 각 구간별 백테스트
        split_results = {}
        for split_name, (split_start, split_end) in periods.items():
            if split_start >= split_end:
                continue
            try:
                split_runner = self._runner_class(
                    initial_capital=params.initial_capital,
                    max_positions=params.max_positions,
                    enable_defense=params.enable_defense,
                )
                split_result = split_runner.run(
                    price_data=price_data,
                    target_weights=target_weights,
                    start_date=split_start,
                    end_date=split_end,
                    market_index_data=market_data,
                    ma_period=params.ma_period,
                    rsi_period=params.rsi_period,
                    stop_loss=params.stop_loss / 100.0,
                )
                split_metrics = split_result.get("metrics", {})
                split_results[split_name] = SplitMetrics(
                    cagr=split_metrics.get("annual_return", 0),
                    sharpe_ratio=split_metrics.get("sharpe_ratio", 0),
                    max_drawdown=split_metrics.get("max_drawdown", 0),
                    num_trades=len(split_result.get("trades", [])),
                )
            except Exception as e:
                logger.warning(f"{split_name} 구간 백테스트 실패: {e}")
                split_results[split_name] = None
        
        # 경고 생성
        warnings = engine_health.get("warnings", []) if engine_health else []
        
        # 과적합 경고 추가
        if split_results.get("train") and split_results.get("test"):
            train_sharpe = split_results["train"].sharpe_ratio
            test_sharpe = split_results["test"].sharpe_ratio
            if train_sharpe > 0 and test_sharpe > 0:
                degradation = (train_sharpe - test_sharpe) / train_sharpe
                if degradation > 0.3:  # 30% 이상 성능 저하
                    warnings.append(f"overfit_warning: Train→Test Sharpe 저하 {degradation*100:.1f}%")
        
        return ExtendedBacktestResult(
            metrics=overall,
            train_metrics=split_results.get("train"),
            val_metrics=split_results.get("val"),
            test_metrics=split_results.get("test"),
            engine_health=engine_health,
            daily_logs=daily_logs[-daily_log_limit:] if daily_logs else None,
            warnings=warnings if warnings else None,
        )
