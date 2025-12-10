# -*- coding: utf-8 -*-
"""
app/services/tuning_service.py
튜닝 서비스 (단일 책임: Optuna 기반 파라미터 최적화)
"""
import logging
import threading
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

import optuna

from app.services.backtest_service import (
    BacktestParams,
    BacktestService,
    ConfigLoader,
)

logger = logging.getLogger(__name__)


@dataclass
class TuningParams:
    """튜닝 파라미터 (필수값만, default 없음)"""

    trials: int
    start_date: date
    end_date: date
    lookback_months: List[int]
    optimization_metric: str  # sharpe, cagr, calmar


@dataclass
class TuningState:
    """튜닝 상태"""

    is_running: bool = False
    current_trial: int = 0
    total_trials: int = 0
    best_sharpe: float = 0.0
    best_params: Optional[Dict] = None
    trials: List[Dict] = field(default_factory=list)
    stop_requested: bool = False
    lookback_results: Dict[int, Dict] = field(default_factory=dict)


class TuningService:
    """튜닝 서비스"""

    def __init__(self):
        self._state = TuningState()
        self._lock = threading.Lock()
        self._session_id: Optional[str] = None

        # 백테스트 서비스 (튜닝 중에는 개별 저장하지 않음)
        self._backtest_service = BacktestService(save_history=False)

        # 히스토리 서비스
        from app.services.history_service import HistoryService

        self._history_service = HistoryService()

    @property
    def state(self) -> TuningState:
        with self._lock:
            return self._state

    def _get_lookback_weights(self) -> Dict[int, float]:
        """설정에서 룩백 가중치 로드"""
        return ConfigLoader.get("tuning", "lookback_weights")

    def _get_param_ranges(self) -> Dict:
        """설정에서 파라미터 범위 로드 (기존 config.yaml 방식)"""
        return ConfigLoader.get("tuning", "param_ranges")

    def _get_tuning_variables(self) -> Dict:
        """backtest.yaml에서 활성화된 튜닝 변수 로드"""
        return ConfigLoader.get_tuning_variables()

    def start(self, params: TuningParams) -> None:
        """
        튜닝 시작 (백그라운드)

        Args:
            params: 튜닝 파라미터 (모든 필드 필수)

        Raises:
            RuntimeError: 이미 실행 중인 경우
        """
        with self._lock:
            if self._state.is_running:
                raise RuntimeError("튜닝이 이미 실행 중입니다")

        thread = threading.Thread(target=self._run_tuning, args=(params,))
        thread.daemon = True
        thread.start()

    def stop(self) -> None:
        """튜닝 중지 요청"""
        with self._lock:
            self._state.stop_requested = True

    def _run_tuning(self, params: TuningParams) -> None:
        """튜닝 실행 (내부)"""
        import uuid
        from pathlib import Path
        import pandas as pd

        self._session_id = str(uuid.uuid4())[:8]

        # 캐시 데이터 범위 확인 및 end_date 조정
        cache_dir = Path("data/cache")
        sample_file = cache_dir / "069500.parquet"  # KODEX 200
        actual_end_date = params.end_date

        if sample_file.exists():
            try:
                sample_df = pd.read_parquet(sample_file)
                cache_end = sample_df.index.max().date()
                if params.end_date > cache_end:
                    logger.warning(
                        f"end_date({params.end_date})가 캐시 범위({cache_end})를 초과. "
                        f"캐시 마지막 날짜로 조정"
                    )
                    actual_end_date = cache_end
            except Exception as e:
                logger.warning(f"캐시 날짜 확인 실패: {e}")

        with self._lock:
            self._state = TuningState(
                is_running=True,
                total_trials=params.trials,
            )

        # 튜닝 세션 생성
        self._history_service.create_tuning_session(
            session_id=self._session_id,
            total_trials=params.trials,
            lookback_months=params.lookback_months,
            optimization_metric=params.optimization_metric,
        )

        try:
            all_results = []
            # backtest.yaml의 tuning_variables 사용 (활성화된 변수만)
            tuning_vars = self._get_tuning_variables()
            # 기존 config.yaml의 param_ranges (fallback용)
            legacy_ranges = self._get_param_ranges()

            # 활성화된 변수 로깅
            logger.info(f"활성화된 튜닝 변수: {list(tuning_vars.keys())}")

            for lookback in params.lookback_months:
                start_date = actual_end_date - timedelta(days=lookback * 30)

                logger.info(f"룩백 {lookback}개월 최적화 시작: {start_date} ~ {actual_end_date}")

                def objective(trial: optuna.Trial) -> float:
                    with self._lock:
                        if self._state.stop_requested:
                            raise optuna.TrialPruned()

                    # 파라미터 샘플링 (tuning_variables 우선, 없으면 legacy 사용)
                    def get_range(name: str) -> Dict:
                        if name in tuning_vars:
                            return tuning_vars[name]
                        elif name in legacy_ranges:
                            return legacy_ranges[name]
                        else:
                            raise KeyError(f"변수 '{name}' 설정 없음")

                    ma_range = get_range("ma_period")
                    rsi_range = get_range("rsi_period")
                    stop_range = get_range("stop_loss")
                    # max_positions는 legacy에서만 사용 (tuning_variables에 없음)
                    pos_range = legacy_ranges.get("max_positions", {"min": 5, "max": 15, "step": 5})

                    bt_params = BacktestParams(
                        start_date=start_date,
                        end_date=actual_end_date,
                        ma_period=trial.suggest_int(
                            "ma_period",
                            ma_range["min"],
                            ma_range["max"],
                            step=ma_range.get("step", 10),
                        ),
                        rsi_period=trial.suggest_int(
                            "rsi_period",
                            rsi_range["min"],
                            rsi_range["max"],
                            step=rsi_range.get("step", 1),
                        ),
                        stop_loss=trial.suggest_int(
                            "stop_loss",
                            stop_range["min"],
                            stop_range["max"],
                            step=stop_range.get("step", 1),
                        ),
                        max_positions=trial.suggest_int(
                            "max_positions",
                            pos_range["min"],
                            pos_range["max"],
                            step=pos_range.get("step", 5),
                        ),
                        initial_capital=ConfigLoader.get("backtest", "initial_capital"),
                        enable_defense=True,
                    )

                    try:
                        # Train/Val/Test 분할 백테스트 실행
                        ext_result = self._backtest_service.run_with_split(bt_params)
                        result = ext_result.metrics
                    except Exception as e:
                        logger.warning(f"Trial {trial.number} 실패: {e}")
                        raise optuna.TrialPruned()

                    # 결과 저장 (Train/Val/Test 포함)
                    trial_data = {
                        "trial_number": trial.number + 1,
                        "lookback_months": lookback,
                        "params": {
                            "start_date": start_date.isoformat(),
                            "end_date": actual_end_date.isoformat(),
                            "ma_period": bt_params.ma_period,
                            "rsi_period": bt_params.rsi_period,
                            "stop_loss": bt_params.stop_loss,
                            "max_positions": bt_params.max_positions,
                        },
                        "result": {
                            "cagr": result.cagr,
                            "sharpe_ratio": result.sharpe_ratio,
                            "max_drawdown": result.max_drawdown,
                            "total_return": result.total_return,
                            "num_trades": result.num_trades,
                            "win_rate": result.win_rate,
                            "calmar_ratio": result.calmar_ratio,
                        },
                        # Train/Val/Test 분할 성과
                        "train": {
                            "cagr": ext_result.train_metrics.cagr,
                            "sharpe_ratio": ext_result.train_metrics.sharpe_ratio,
                            "max_drawdown": ext_result.train_metrics.max_drawdown,
                            "num_trades": ext_result.train_metrics.num_trades,
                        } if ext_result.train_metrics else None,
                        "val": {
                            "cagr": ext_result.val_metrics.cagr,
                            "sharpe_ratio": ext_result.val_metrics.sharpe_ratio,
                            "max_drawdown": ext_result.val_metrics.max_drawdown,
                            "num_trades": ext_result.val_metrics.num_trades,
                        } if ext_result.val_metrics else None,
                        "test": {
                            "cagr": ext_result.test_metrics.cagr,
                            "sharpe_ratio": ext_result.test_metrics.sharpe_ratio,
                            "max_drawdown": ext_result.test_metrics.max_drawdown,
                            "num_trades": ext_result.test_metrics.num_trades,
                        } if ext_result.test_metrics else None,
                        # 엔진 헬스체크
                        "engine_health": ext_result.engine_health,
                        "warnings": ext_result.warnings,
                        "timestamp": datetime.now().isoformat(),
                    }

                    # DB에 trial 저장 (Train/Val/Test 포함)
                    self._history_service.save_backtest(
                        params={
                            "start_date": start_date.isoformat(),
                            "end_date": actual_end_date.isoformat(),
                            "ma_period": bt_params.ma_period,
                            "rsi_period": bt_params.rsi_period,
                            "stop_loss": bt_params.stop_loss,
                            "max_positions": bt_params.max_positions,
                            "initial_capital": bt_params.initial_capital,
                            "enable_defense": bt_params.enable_defense,
                        },
                        result={
                            "cagr": result.cagr,
                            "sharpe_ratio": result.sharpe_ratio,
                            "max_drawdown": result.max_drawdown,
                            "total_return": result.total_return,
                            "num_trades": result.num_trades,
                            "win_rate": result.win_rate,
                            "volatility": result.volatility,
                            "calmar_ratio": result.calmar_ratio,
                        },
                        run_type="tuning",
                        tuning_session_id=self._session_id,
                        lookback_months=lookback,
                        train_metrics=trial_data.get("train"),
                        val_metrics=trial_data.get("val"),
                        test_metrics=trial_data.get("test"),
                        engine_health=trial_data.get("engine_health"),
                        warnings=trial_data.get("warnings"),
                    )

                    with self._lock:
                        self._state.current_trial += 1
                        self._state.trials.append(trial_data)

                        if result.sharpe_ratio > self._state.best_sharpe:
                            self._state.best_sharpe = result.sharpe_ratio
                            self._state.best_params = trial_data["params"]

                        # Sharpe 기준 정렬
                        self._state.trials.sort(
                            key=lambda x: x["result"]["sharpe_ratio"],
                            reverse=True,
                        )

                        # 세션 업데이트
                        self._history_service.update_tuning_session(
                            session_id=self._session_id,
                            completed_trials=self._state.current_trial,
                            best_sharpe=self._state.best_sharpe,
                            best_params=self._state.best_params,
                        )

                    # 목적 함수 값 반환
                    if params.optimization_metric == "cagr":
                        return result.cagr
                    elif params.optimization_metric == "calmar":
                        return result.calmar_ratio
                    else:
                        return result.sharpe_ratio

                # Optuna Study 생성
                study = optuna.create_study(
                    direction="maximize",
                    sampler=optuna.samplers.TPESampler(seed=42),
                )

                trials_per_lookback = params.trials // len(params.lookback_months)

                try:
                    study.optimize(
                        objective,
                        n_trials=trials_per_lookback,
                        show_progress_bar=False,
                        catch=(Exception,),
                    )

                    with self._lock:
                        self._state.lookback_results[lookback] = {
                            "best_params": study.best_params,
                            "best_value": study.best_value,
                            "n_trials": len(study.trials),
                        }

                    all_results.append(
                        {
                            "lookback": lookback,
                            "best_params": study.best_params,
                            "best_value": study.best_value,
                        }
                    )

                except Exception as e:
                    logger.error(f"룩백 {lookback}개월 최적화 실패: {e}")

            # 앙상블 파라미터 계산
            if all_results:
                ensemble_params = self._calculate_ensemble(all_results)
                with self._lock:
                    self._state.best_params = ensemble_params

                # 최종 세션 업데이트
                self._history_service.update_tuning_session(
                    session_id=self._session_id,
                    ensemble_params=ensemble_params,
                    lookback_results=self._state.lookback_results,
                    status="completed",
                )

        except Exception as e:
            logger.error(f"튜닝 실패: {e}")
            self._history_service.update_tuning_session(
                session_id=self._session_id,
                status="failed",
            )

        finally:
            with self._lock:
                self._state.is_running = False

        logger.info("Optuna 튜닝 완료")

    def _calculate_ensemble(self, results: List[Dict]) -> Dict:
        """룩백 기간별 결과를 앙상블하여 최종 파라미터 계산"""
        if not results:
            return {}

        weights = self._get_lookback_weights()
        ensemble = {}
        param_keys = ["ma_period", "rsi_period", "stop_loss", "max_positions"]

        for key in param_keys:
            weighted_sum = 0.0
            total_weight = 0.0

            for r in results:
                lookback = r["lookback"]
                w = weights.get(lookback, 0.2)
                value = r["best_params"].get(key, 0)

                weighted_sum += w * value
                total_weight += w

            if total_weight > 0:
                ensemble[key] = int(round(weighted_sum / total_weight))

        ensemble["initial_capital"] = ConfigLoader.get("backtest", "initial_capital")
        ensemble["enable_defense"] = True

        return ensemble
