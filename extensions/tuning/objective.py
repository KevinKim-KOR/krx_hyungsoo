# -*- coding: utf-8 -*-
"""
extensions/tuning/objective.py
튜닝/검증 체계 v2.1 - Optuna 목적함수

문서 참조: docs/tuning/02_objective_gates.md 6절
"""
import logging
from datetime import date
from typing import Dict, List, Optional, Any

import optuna

from extensions.tuning.types import (
    BacktestRunResult,
    CostConfig,
    DataConfig,
    SplitConfig,
    DEFAULT_COSTS,
    compute_params_hash,
)
from extensions.tuning.runner import run_backtest_for_tuning
from extensions.tuning.guardrails import (
    check_guardrails,
    check_anomalies,
    has_critical_anomaly,
)

logger = logging.getLogger(__name__)


def calculate_score(result: BacktestRunResult, mdd_threshold: float = 0.15) -> float:
    """
    Val 기반 점수 계산 (MDD 페널티 포함)

    문서 참조: docs/tuning/02_objective_gates.md 6.3절

    Args:
        result: 백테스트 결과
        mdd_threshold: MDD 페널티 임계값 (기본 15%)

    Returns:
        점수 (Val Sharpe - MDD 페널티)
    """
    val = result.metrics.get("val")
    if val is None:
        return -999.0

    # MDD 페널티: 15% 초과 시
    mdd_penalty = max(0, abs(val.mdd) - mdd_threshold) * 10

    return val.sharpe - mdd_penalty


class TuningObjective:
    """
    Optuna 목적함수 클래스

    문서 참조: docs/tuning/02_objective_gates.md 6.1절

    ⚠️ 절대 규칙:
    - objective에서는 Test를 계산하지 않는다.
    - 반드시 run_backtest_for_tuning()만 호출한다.
    """

    def __init__(
        self,
        start_date: date,
        end_date: date,
        trading_calendar: List[date],
        lookbacks: List[int] = None,
        lookback_combination: str = "min",
        split_config: Optional[SplitConfig] = None,
        costs: Optional[CostConfig] = None,
        data_config: Optional[DataConfig] = None,
        param_ranges: Optional[Dict[str, Dict]] = None,
        universe_codes: Optional[List[str]] = None,
    ):
        """
        Args:
            start_date: 전체 시작일
            end_date: 전체 종료일
            trading_calendar: 거래일 리스트
            lookbacks: 룩백 기간 리스트 (기본 [3, 6, 12])
            lookback_combination: 멀티 룩백 결합 방식 ('min' or 'mean_std')
            split_config: Split 설정
            costs: 비용 설정 (기본값 적용)
            data_config: 데이터 설정
            param_ranges: 파라미터 범위 설정
            universe_codes: 유니버스 코드 리스트 (필수)
        """
        self.start_date = start_date
        self.end_date = end_date
        self.trading_calendar = trading_calendar
        self.lookbacks = lookbacks or [3, 6, 12]
        self.lookback_combination = lookback_combination
        self.split_config = split_config or SplitConfig()
        self.costs = costs or DEFAULT_COSTS
        self.data_config = data_config or DataConfig()
        self.universe_codes = universe_codes

        # 파라미터 범위 (기본값)
        # stop_loss_pct: 양수 소수 (0.03~0.10 = 3%~10%)
        # unit: "decimal_positive" (예: 0.05 = 5% 손절)
        self.param_ranges = param_ranges or {
            "ma_period": {"min": 20, "max": 200, "step": 10, "type": "int"},
            "rsi_period": {"min": 5, "max": 30, "step": 1, "type": "int"},
            "stop_loss_pct": {
                "min": 0.03,
                "max": 0.15,
                "step": 0.01,
                "type": "float",
                "unit": "decimal_positive",
            },
        }

        # 통계
        self.trial_count = 0
        self.guardrail_failures = 0
        self.anomaly_warnings = 0

        # 가드레일 실패 사유 히스토그램
        self.guardrail_fail_reasons: Dict[str, int] = {}

        # 중복 후보 추적
        self.params_hash_seen: Dict[str, int] = {}  # params_hash -> trial_number

    def _suggest_params(self, trial: optuna.Trial) -> Dict[str, Any]:
        """파라미터 샘플링"""
        params = {}

        for name, config in self.param_ranges.items():
            if config["type"] == "int":
                params[name] = trial.suggest_int(
                    name, config["min"], config["max"], step=config.get("step", 1)
                )
            elif config["type"] == "float":
                params[name] = trial.suggest_float(
                    name, config["min"], config["max"], step=config.get("step", 0.01)
                )

        return params

    def _combine_scores(self, scores: List[float]) -> float:
        """
        멀티 룩백 점수 결합

        문서 참조: docs/tuning/01_metrics_guardrails.md 5.3절
        """
        if not scores:
            return -999.0

        if self.lookback_combination == "min":
            # Option A: 최솟값 (강력한 안정성 지향) — 기본값
            return min(scores)
        else:
            # Option B: 평균 - k*표준편차 (균형형)
            import numpy as np

            return float(np.mean(scores) - 1.0 * np.std(scores))

    def __call__(self, trial: optuna.Trial) -> float:
        """
        목적 함수 실행

        ⚠️ v2.1 절대 규칙:
        - objective에서는 Test를 계산하지 않는다.
        - 반드시 run_backtest_for_tuning()만 호출한다.
        - period는 run_backtest_for_tuning 내부에서 룩백별로 계산된다.

        Args:
            trial: Optuna trial

        Returns:
            목적함수 값 (min(scores) 또는 mean-std)
        """
        self.trial_count += 1

        # 파라미터 샘플링
        params = self._suggest_params(trial)

        # 중복 후보 추적
        params_hash = compute_params_hash(params)
        if params_hash in self.params_hash_seen:
            dup_trial = self.params_hash_seen[params_hash]
            trial.set_user_attr("dup_of", dup_trial)
            trial.set_user_attr("params_hash", params_hash)
            logger.info(
                f"Trial #{trial.number}: 중복 파라미터 (dup_of=#{dup_trial}) - Pruned"
            )
            # 중복이면 TrialPruned로 시간 절약
            raise optuna.TrialPruned(f"중복 파라미터 (dup_of=#{dup_trial})")
        else:
            self.params_hash_seen[params_hash] = trial.number

        # 파라미터 해시 저장
        trial.set_user_attr("params_hash", params_hash)

        scores = []
        all_results = []

        for lb in self.lookbacks:
            # ✅ period는 내부에서 룩백별로 계산됨
            result = run_backtest_for_tuning(
                params=params,
                start_date=self.start_date,
                end_date=self.end_date,
                lookback_months=lb,
                trading_calendar=self.trading_calendar,
                split_config=self.split_config,
                costs=self.costs,
                data_config=self.data_config,
                universe_codes=self.universe_codes,
            )

            all_results.append(result)

            # 가드레일 체크
            if not check_guardrails(result):
                self.guardrail_failures += 1
                # 실패 사유 수집
                if result.guardrail_checks:
                    for reason in result.guardrail_checks.failures:
                        # 사유 정규화 (예: "num_trades(14) < 30" -> "LOW_TRADES")
                        if "num_trades" in reason:
                            key = "LOW_TRADES"
                        elif "exposure_ratio" in reason:
                            key = "LOW_EXPOSURE"
                        elif "annual_turnover" in reason:
                            key = "HIGH_TURNOVER"
                        else:
                            key = "OTHER"
                        self.guardrail_fail_reasons[key] = (
                            self.guardrail_fail_reasons.get(key, 0) + 1
                        )
                return -999.0

            # 이상치 감지
            anomalies = check_anomalies(result, stage="tuning")
            if has_critical_anomaly(anomalies):
                self.anomaly_warnings += 1
                # 🔴 경고가 있으면 탈락
                return -999.0

            # 점수 계산
            score = calculate_score(result)
            scores.append(score)

        # 멀티 룩백 결합
        final_score = self._combine_scores(scores)

        # Trial 메타데이터 저장
        trial.set_user_attr("params", params)
        trial.set_user_attr("scores_by_lookback", dict(zip(self.lookbacks, scores)))
        trial.set_user_attr("final_score", final_score)

        # Val 지표 저장 (첫 번째 룩백 기준)
        if all_results and all_results[0].val:
            val = all_results[0].val
            trial.set_user_attr("val_sharpe", val.sharpe)
            trial.set_user_attr("val_cagr", val.cagr)
            trial.set_user_attr("val_mdd", val.mdd)

        return final_score

    def get_stats(self) -> Dict[str, Any]:
        """목적함수 통계"""
        # 실패 사유 히스토그램 정렬 (빈도 내림차순)
        sorted_reasons = sorted(
            self.guardrail_fail_reasons.items(), key=lambda x: x[1], reverse=True
        )

        # 실패 사유 비율 계산
        total_failures = sum(self.guardrail_fail_reasons.values())
        fail_reason_pct = {
            k: v / total_failures if total_failures > 0 else 0.0
            for k, v in sorted_reasons
        }

        return {
            "trial_count": self.trial_count,
            "guardrail_failures": self.guardrail_failures,
            "anomaly_warnings": self.anomaly_warnings,
            "guardrail_failure_rate": (
                self.guardrail_failures / self.trial_count
                if self.trial_count > 0
                else 0.0
            ),
            "guardrail_fail_reasons": dict(sorted_reasons),
            "guardrail_fail_reason_pct": fail_reason_pct,
            "unique_params_count": len(self.params_hash_seen),
            "duplicate_params_count": self.trial_count - len(self.params_hash_seen),
        }


def create_tuning_objective(
    start_date: date,
    end_date: date,
    trading_calendar: List[date],
    lookbacks: List[int] = None,
    param_ranges: Optional[Dict] = None,
) -> TuningObjective:
    """
    튜닝 목적함수 생성 헬퍼

    Args:
        start_date: 시작일
        end_date: 종료일
        trading_calendar: 거래일 리스트
        lookbacks: 룩백 기간 리스트
        param_ranges: 파라미터 범위

    Returns:
        TuningObjective 인스턴스
    """
    return TuningObjective(
        start_date=start_date,
        end_date=end_date,
        trading_calendar=trading_calendar,
        lookbacks=lookbacks,
        param_ranges=param_ranges,
    )
