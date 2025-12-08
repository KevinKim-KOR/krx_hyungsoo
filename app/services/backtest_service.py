# -*- coding: utf-8 -*-
"""
app/services/backtest_service.py
백테스트 서비스 (단일 책임: 백테스트 실행)
"""
import logging
from dataclasses import dataclass
from datetime import date
from typing import Dict, Optional

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

        # 목표 비중 계산 (동일 가중)
        top_n = min(params.max_positions, len(universe))
        weight = 1.0 / top_n
        target_weights = {code: weight for code in universe[:top_n]}

        # 백테스트 실행
        result = runner.run(
            price_data=price_data,
            target_weights=target_weights,
            start_date=params.start_date,
            end_date=params.end_date,
            market_index_data=market_data,
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
