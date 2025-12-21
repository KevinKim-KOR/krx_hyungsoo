# -*- coding: utf-8 -*-
"""
tests/tuning/test_mini_tuning.py
미니 튜닝 테스트 - 파이프라인 정상 동작 확인

실행: python -m tests.tuning.test_mini_tuning
"""
import logging
import random
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    import optuna

    optuna.logging.set_verbosity(optuna.logging.WARNING)
except ImportError:
    print("❌ optuna 패키지가 필요합니다: pip install optuna")
    sys.exit(1)

from extensions.tuning import (
    BacktestMetrics,
    BacktestRunResult,
    GuardrailChecks,
    LogicChecks,
    Period,
    SplitConfig,
    CostConfig,
    DataConfig,
    DEFAULT_COSTS,
    TuningObjective,
    check_guardrails,
    check_anomalies,
    has_critical_anomaly,
    clear_global_cache,
    create_manifest,
    save_manifest,
    MANIFEST_SCHEMA_VERSION,
)

# 로깅 설정
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


def generate_mock_trading_calendar(start: date, end: date) -> list:
    """테스트용 거래일 캘린더 생성 (주말 제외)"""
    calendar = []
    current = start
    while current <= end:
        if current.weekday() < 5:
            calendar.append(current)
        current += timedelta(days=1)
    return calendar


def compute_universe_hash(universe_codes: list) -> str:
    """유니버스 코드 리스트를 정렬 후 해시로 변환 (순서 영향 제거)"""
    import hashlib

    if not universe_codes:
        return "default"
    sorted_codes = sorted(universe_codes)
    combined = ",".join(sorted_codes)
    return hashlib.sha256(combined.encode()).hexdigest()[:16]


def compute_deterministic_seed(
    random_seed: int,
    params_hash: str,
    period_signature: str,
) -> int:
    """
    완전 결정론적 seed 계산 - 최소 입력

    seed_input = (random_seed, params_hash, period_signature)

    run과 replay가 동일한 함수를 사용하여 결정론 보장

    Note:
    - lookback_months는 period_signature에 이미 반영됨 (train/val 구간이 달라짐)
    - universe_hash와 data_version은 캐시 키에서 관리하므로 seed에서 제외
    """
    import hashlib

    # 최소 입력 결합 (원본과 replay가 동일한 결과를 보장)
    combined = f"{random_seed}|{params_hash}|{period_signature}"
    hash_bytes = hashlib.sha256(combined.encode()).digest()

    # 해시의 처음 8바이트를 정수로 변환
    return int.from_bytes(hash_bytes[:8], byteorder="big")


def compute_params_hash_for_seed(params: dict) -> str:
    """params를 정렬된 해시로 변환"""
    import hashlib

    params_str = str(sorted(params.items()))
    return hashlib.sha256(params_str.encode()).hexdigest()[:16]


def compute_period_signature(start_date: date, end_date: date) -> str:
    """period를 시그니처 문자열로 변환"""
    return f"{start_date.isoformat()}~{end_date.isoformat()}"


class MockBacktestService:
    """
    테스트용 백테스트 서비스 Mock

    완전 결정론적: 동일 입력 → 동일 결과
    전역 상태 사용 금지
    """

    def __init__(self, seed: int = 42, data_version: str = "mock_v1"):
        self.base_seed = seed
        self.data_version = data_version

    def run(
        self,
        params: dict,
        start_date: date,
        end_date: date,
        universe_codes: list = None,
    ) -> BacktestMetrics:
        """
        결정론적 백테스트 결과 생성

        seed_input = (random_seed, params_hash, period_signature)
        전역 상태(call_count) 사용하지 않음

        Note: lookback_months는 period_signature에 이미 반영됨 (train/val 구간이 달라짐)
        """
        # 표준화된 입력으로 결정론적 seed 계산
        params_hash = compute_params_hash_for_seed(params)
        period_signature = compute_period_signature(start_date, end_date)

        deterministic_seed = compute_deterministic_seed(
            random_seed=self.base_seed,
            params_hash=params_hash,
            period_signature=period_signature,
        )
        rng = random.Random(deterministic_seed)

        # 파라미터에 따라 성능 변화 (튜닝 효과 시뮬레이션)
        ma_period = params.get("ma_period", 60)
        rsi_period = params.get("rsi_period", 14)

        # 특정 파라미터 조합에서 더 좋은 성능
        base_sharpe = 0.8
        if 40 <= ma_period <= 80:
            base_sharpe += 0.5
        if 10 <= rsi_period <= 20:
            base_sharpe += 0.3

        sharpe = base_sharpe + rng.uniform(-0.5, 0.5)
        cagr = 0.10 + sharpe * 0.05 + rng.uniform(-0.05, 0.05)
        mdd = -0.08 - rng.uniform(0, 0.15)

        # 가드레일 테스트용: 일부 trial은 가드레일 실패하도록
        if rng.random() < 0.2:  # 20% 확률로 가드레일 실패
            num_trades = rng.randint(10, 25)  # 30 미만
            exposure_ratio = rng.uniform(0.1, 0.25)  # 0.3 미만
        else:
            num_trades = rng.randint(35, 80)
            exposure_ratio = rng.uniform(0.4, 0.8)

        annual_turnover = rng.uniform(5, 20)

        return BacktestMetrics(
            sharpe=sharpe,
            cagr=cagr,
            mdd=mdd,
            total_return=cagr * 1.5,
            volatility=abs(cagr / sharpe) if sharpe != 0 else 0.1,
            num_trades=num_trades,
            win_rate=rng.uniform(0.4, 0.6),
            exposure_ratio=exposure_ratio,
            annual_turnover=annual_turnover,
        )


# 전역 Mock 서비스 (base_seed 저장용)
_mock_service = None


def get_mock_service(seed: int = 42) -> MockBacktestService:
    """Mock 서비스 인스턴스 반환 (매번 새로 생성하여 상태 격리)"""
    global _mock_service
    # 항상 새로 생성하여 상태 격리 보장
    _mock_service = MockBacktestService(seed)
    return _mock_service


def mock_run_single_backtest(
    params: dict,
    start_date: date,
    end_date: date,
    costs: CostConfig,
    trading_calendar: list,
    universe_codes: list = None,
) -> BacktestMetrics:
    """Mock 백테스트 실행 - 완전 결정론적"""
    global _mock_service
    if _mock_service is None:
        _mock_service = MockBacktestService(42)
    return _mock_service.run(params, start_date, end_date, universe_codes)


def run_mini_tuning_test(n_trials: int = 15, seed: int = 42):
    """
    미니 튜닝 테스트 실행

    목표: 성능이 아니라 파이프라인이 정상인지 확인
    - 가드레일에 걸리는 trial이 적당히 나오나?
    - 이상치 레이더가 말이 되는 경고를 띄우나?
    - manifest(stage=tuning)에 test=null로 저장되나?
    """
    print("\n" + "#" * 60)
    print(f"# 미니 튜닝 테스트 (n_trials={n_trials}, seed={seed})")
    print("#" * 60)

    # Mock 함수로 패치
    import extensions.tuning.runner as runner_module

    original_func = runner_module._run_single_backtest
    runner_module._run_single_backtest = mock_run_single_backtest

    # 전역 Mock 서비스 초기화
    global _mock_service
    _mock_service = MockBacktestService(seed)

    # 캐시 초기화
    clear_global_cache()

    try:
        # 설정
        end_date = date(2024, 6, 30)
        start_date = date(2020, 1, 1)
        trading_calendar = generate_mock_trading_calendar(start_date, end_date)

        lookbacks = [3, 6, 12]

        param_ranges = {
            "ma_period": {"min": 20, "max": 100, "step": 10, "type": "int"},
            "rsi_period": {"min": 5, "max": 25, "step": 5, "type": "int"},
        }

        # TuningObjective 생성
        objective = TuningObjective(
            start_date=start_date,
            end_date=end_date,
            trading_calendar=trading_calendar,
            lookbacks=lookbacks,
            param_ranges=param_ranges,
        )

        # Optuna Study 생성
        sampler = optuna.samplers.TPESampler(seed=seed)
        study = optuna.create_study(direction="maximize", sampler=sampler)

        print(f"\n[설정]")
        print(f"  기간: {start_date} ~ {end_date}")
        print(f"  룩백: {lookbacks}")
        print(f"  파라미터: {list(param_ranges.keys())}")
        print(f"  시행 횟수: {n_trials}")

        # 튜닝 실행
        print(f"\n[튜닝 실행 중...]")
        study.optimize(objective, n_trials=n_trials, show_progress_bar=True)

        # 결과 분석
        print(f"\n[결과 분석]")

        # 1. 가드레일 실패 통계
        stats = objective.get_stats()
        guardrail_failures = stats["guardrail_failures"]
        guardrail_rate = stats["guardrail_failure_rate"]

        print(f"\n  1) 가드레일 통계:")
        print(f"     - 전체 시행: {stats['trial_count']}")
        print(f"     - 가드레일 실패: {guardrail_failures} ({guardrail_rate:.1%})")
        print(f"     - 이상치 경고: {stats['anomaly_warnings']}")

        if 0.1 <= guardrail_rate <= 0.4:
            print(f"     ✅ 가드레일 실패율 적정 (10~40%)")
        else:
            print(f"     ⚠️ 가드레일 실패율 비정상 (기대: 10~40%)")

        # 1-1. 가드레일 실패 사유 히스토그램
        fail_reasons = stats.get("guardrail_fail_reasons", {})
        fail_reason_pct = stats.get("guardrail_fail_reason_pct", {})

        if fail_reasons:
            print(f"\n  1-1) 실패 사유 Top3:")
            for i, (reason, count) in enumerate(list(fail_reasons.items())[:3]):
                pct = fail_reason_pct.get(reason, 0)
                print(f"       {i + 1}. {reason}: {count}건 ({pct:.0%})")

        # 1-2. 중복 파라미터 통계
        unique_count = stats.get("unique_params_count", 0)
        dup_count = stats.get("duplicate_params_count", 0)
        print(f"\n  1-2) 파라미터 중복:")
        print(f"       - 고유 파라미터: {unique_count}")
        print(f"       - 중복 파라미터: {dup_count}")

        # 2. 완료된 Trial 분석
        completed_trials = [
            t for t in study.trials if t.state == optuna.trial.TrialState.COMPLETE
        ]
        pruned_trials = [
            t for t in study.trials if t.state == optuna.trial.TrialState.PRUNED
        ]

        print(f"\n  2) Trial 상태:")
        print(f"     - 완료: {len(completed_trials)}")
        print(f"     - Pruned (가드레일/이상치): {len(pruned_trials)}")

        # 3. 최적 Trial
        if completed_trials:
            best_trial = study.best_trial
            print(f"\n  3) 최적 Trial:")
            print(f"     - Trial #{best_trial.number}")
            print(f"     - 점수: {best_trial.value:.4f}")
            print(f"     - 파라미터: {best_trial.params}")

            if "val_sharpe" in best_trial.user_attrs:
                print(f"     - Val Sharpe: {best_trial.user_attrs['val_sharpe']:.4f}")
                print(
                    f"     - Val CAGR: {best_trial.user_attrs.get('val_cagr', 0):.2%}"
                )
                print(f"     - Val MDD: {best_trial.user_attrs.get('val_mdd', 0):.2%}")

        # 4. 룩백별 debug 필드 검증
        print(f"\n  4) 룩백별 debug 필드 검증:")

        from extensions.tuning.runner import run_backtest_for_tuning

        test_params = {"ma_period": 60, "rsi_period": 14}
        debug_by_lookback = {}

        for lb in lookbacks:
            result = run_backtest_for_tuning(
                params=test_params,
                start_date=start_date,
                end_date=end_date,
                lookback_months=lb,
                trading_calendar=trading_calendar,
                use_cache=False,
            )
            if result.debug:
                debug_by_lookback[lb] = {
                    "lookback_months": result.debug.lookback_months,
                    "params_hash": result.debug.params_hash[:8],
                    "cache_key": (
                        result.debug.cache_key[:20] if result.debug.cache_key else ""
                    ),
                    "period_signature": (
                        result.debug.period_signature[:40]
                        if result.debug.period_signature
                        else ""
                    ),
                }

        # 룩백별로 다른 값인지 확인
        lookback_values = [d["lookback_months"] for d in debug_by_lookback.values()]
        all_different = len(set(lookback_values)) == len(lookbacks)

        for lb, debug in debug_by_lookback.items():
            print(
                f"       lb={lb}: lookback_months={debug['lookback_months']}, "
                f"params_hash={debug['params_hash']}..., cache_key={debug['cache_key']}..."
            )

        if all_different:
            print(f"     ✅ 룩백별 debug.lookback_months 구분 정상 ({lookback_values})")
        else:
            print(f"     ❌ 룩백별 debug.lookback_months 동일! ({lookback_values})")

        # 5. Manifest 저장 테스트
        print(f"\n  5) Manifest 저장 테스트:")

        split_config = SplitConfig()
        data_config = DataConfig(
            data_version="mock_v1", universe_version="mock_universe_v1"
        )

        # 최적 결과로 manifest 생성
        if completed_trials:
            best_params = best_trial.params
            best_result = run_backtest_for_tuning(
                params=best_params,
                start_date=start_date,
                end_date=end_date,
                lookback_months=12,
                trading_calendar=trading_calendar,
                use_cache=False,
            )

            manifest = create_manifest(
                stage="tuning",
                start_date=start_date,
                end_date=end_date,
                lookbacks=lookbacks,
                trials=n_trials,
                split_config=split_config,
                costs=DEFAULT_COSTS,
                data_config=data_config,
                param_ranges=param_ranges,
                best_result=best_result,
                all_trials_count=len(study.trials),
                random_seed=seed,
            )

            # Test가 null인지 확인
            manifest_dict = manifest.to_dict()
            results = manifest_dict.get("results", {})
            best_trial_data = results.get("best_trial", {})
            metrics = best_trial_data.get("metrics", {})

            test_value = metrics.get("test")

            print(f"     - run_id: {manifest.run_id}")
            print(f"     - stage: {manifest.stage}")
            print(f"     - schema_version: {manifest.schema_version}")
            print(f"     - test 값: {test_value}")

            if test_value is None:
                print(f"     ✅ test=null 확인 (Test 봉인 정상)")
            else:
                print(f"     ❌ test가 null이 아님! (Test 봉인 실패)")

            # 파일 저장
            output_dir = Path(__file__).parent.parent.parent / "data" / "tuning_test"
            filepath = save_manifest(manifest, output_dir)
            print(f"     - 저장 경로: {filepath}")

        print("\n" + "=" * 60)
        print("미니 튜닝 테스트 완료")
        print("=" * 60)

        return True

    finally:
        # 원래 함수 복원
        runner_module._run_single_backtest = original_func


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="미니 튜닝 테스트")
    parser.add_argument("--trials", type=int, default=15, help="시행 횟수 (기본: 15)")
    parser.add_argument("--seed", type=int, default=42, help="랜덤 시드 (기본: 42)")

    args = parser.parse_args()

    success = run_mini_tuning_test(n_trials=args.trials, seed=args.seed)
    sys.exit(0 if success else 1)
