# -*- coding: utf-8 -*-
"""
tests/tuning/test_replay_determinism.py
Replay 재현성 자동화 테스트

목표: 같은 manifest를 replay 했을 때 Train/Val/WF(out) 핵심 지표가 동일해야 PASS

실행: python -m pytest tests/tuning/test_replay_determinism.py -v
"""
import json
import logging
import sys
import tempfile
from datetime import date
from pathlib import Path

import pytest

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from extensions.tuning import (
    clear_global_cache,
    create_manifest,
    save_manifest,
    DEFAULT_COSTS,
    SplitConfig,
    DataConfig,
)
from tools.replay_manifest import replay_manifest

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


class TestReplayDeterminism:
    """Replay 재현성 테스트"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """테스트 전 캐시 초기화"""
        clear_global_cache()

    def test_mock_replay_determinism(self):
        """
        Mock 모드에서 manifest 생성 후 replay 재현성 검증

        1. Mock 모드로 튜닝 실행하여 manifest 생성
        2. replay_manifest로 재실행
        3. Val sharpe, combined_score가 tolerance 이내인지 확인
        """
        # Mock 패치
        import extensions.tuning.runner as runner_module
        from tests.tuning.test_mini_tuning import (
            mock_run_single_backtest,
            MockBacktestService,
            generate_mock_trading_calendar,
        )
        import tests.tuning.test_mini_tuning as mini_tuning_module

        original_func = runner_module._run_single_backtest
        runner_module._run_single_backtest = mock_run_single_backtest

        seed = 42
        mini_tuning_module._mock_service = MockBacktestService(seed)

        try:
            # 설정
            start_date = date(2020, 1, 1)
            end_date = date(2024, 6, 30)
            trading_calendar = generate_mock_trading_calendar(start_date, end_date)
            lookbacks = [3, 6, 12]

            param_ranges = {
                "ma_period": {"min": 20, "max": 100, "step": 10, "type": "int"},
                "rsi_period": {"min": 5, "max": 25, "step": 5, "type": "int"},
                "stop_loss_pct": {
                    "min": 0.03,
                    "max": 0.10,
                    "step": 0.01,
                    "type": "float",
                },
            }

            split_config = SplitConfig()
            data_config = DataConfig(
                data_version="mock_v1",
                universe_hash="test_hash_123",
                universe_count=10,
            )

            # Optuna 튜닝 실행
            import optuna

            optuna.logging.set_verbosity(optuna.logging.WARNING)

            from extensions.tuning import TuningObjective, run_backtest_for_tuning
            from extensions.tuning.objective import calculate_score

            universe_codes = [f"TEST{i:03d}" for i in range(10)]

            objective = TuningObjective(
                start_date=start_date,
                end_date=end_date,
                trading_calendar=trading_calendar,
                lookbacks=lookbacks,
                param_ranges=param_ranges,
                split_config=split_config,
                data_config=data_config,
                universe_codes=universe_codes,
            )

            sampler = optuna.samplers.TPESampler(seed=seed)
            study = optuna.create_study(direction="maximize", sampler=sampler)
            study.optimize(objective, n_trials=10, show_progress_bar=False)

            # 최적 trial 선택
            best_trial = study.best_trial
            best_params = best_trial.user_attrs.get("params", {})

            # 멀티 룩백 결과 수집
            # replay_manifest와 동일한 score 계산 방식 사용: sharpe - 0.5 * abs(mdd)
            by_lookback = {}
            scores = []
            for lb in lookbacks:
                result = run_backtest_for_tuning(
                    params=best_params,
                    start_date=start_date,
                    end_date=end_date,
                    lookback_months=lb,
                    trading_calendar=trading_calendar,
                    split_config=split_config,
                    data_config=data_config,
                    use_cache=True,
                    universe_codes=universe_codes,
                )
                val_sharpe = result.val.sharpe if result.val else 0
                val_mdd = result.val.mdd if result.val else 0
                # replay_manifest와 동일한 score 계산
                score = val_sharpe - 0.5 * abs(val_mdd)
                scores.append(score)
                by_lookback[lb] = {
                    "val_sharpe": val_sharpe,
                    "score": score,
                }

            combined_score = min(scores)
            min_lookback_months = lookbacks[scores.index(combined_score)]

            # Manifest 생성
            manifest = create_manifest(
                stage="test",
                start_date=start_date,
                end_date=end_date,
                lookbacks=lookbacks,
                trials=10,
                split_config=split_config,
                costs=DEFAULT_COSTS,
                data_config=data_config,
                param_ranges=param_ranges,
                best_result=result,
                all_trials_count=10,
                random_seed=seed,
                by_lookback=by_lookback,
                combined_score=combined_score,
                min_lookback_months=min_lookback_months,
            )

            # 임시 파일에 저장
            with tempfile.TemporaryDirectory() as tmpdir:
                filepath = save_manifest(manifest, Path(tmpdir))

                # Replay 실행
                replay_result = replay_manifest(str(filepath), tolerance=1e-6)

                # 검증 (ReplayResult는 dataclass)
                assert replay_result.passed, f"Replay 실패: {replay_result.failures}"

                # 각 룩백의 sharpe 차이 확인
                for key, diff in replay_result.diffs.items():
                    assert diff <= 1e-6, f"{key} diff={diff} > 1e-6"

                logger.info(f"✅ Replay 재현성 테스트 PASS (tolerance=1e-6)")

        finally:
            # Mock 패치 복원
            runner_module._run_single_backtest = original_func

    def test_replay_with_different_seed_should_fail(self):
        """
        다른 seed로 replay하면 결과가 달라야 함 (음성 테스트)

        이 테스트는 seed가 실제로 결과에 영향을 미치는지 확인
        """
        # Mock 패치
        import extensions.tuning.runner as runner_module
        from tests.tuning.test_mini_tuning import (
            mock_run_single_backtest,
            MockBacktestService,
            generate_mock_trading_calendar,
        )
        import tests.tuning.test_mini_tuning as mini_tuning_module

        original_func = runner_module._run_single_backtest
        runner_module._run_single_backtest = mock_run_single_backtest

        try:
            # 설정
            start_date = date(2020, 1, 1)
            end_date = date(2024, 6, 30)
            trading_calendar = generate_mock_trading_calendar(start_date, end_date)
            lookbacks = [3]

            param_ranges = {
                "ma_period": {"min": 50, "max": 70, "step": 10, "type": "int"},
                "rsi_period": {"min": 10, "max": 20, "step": 5, "type": "int"},
            }

            split_config = SplitConfig()
            data_config = DataConfig(
                data_version="mock_v1",
                universe_hash="test_hash_456",
                universe_count=5,
            )

            universe_codes = [f"TEST{i:03d}" for i in range(5)]

            from extensions.tuning import run_backtest_for_tuning
            from extensions.tuning.objective import calculate_score

            params = {"ma_period": 60, "rsi_period": 15}

            # seed=42로 실행
            mini_tuning_module._mock_service = MockBacktestService(42)
            clear_global_cache()

            result_seed42 = run_backtest_for_tuning(
                params=params,
                start_date=start_date,
                end_date=end_date,
                lookback_months=3,
                trading_calendar=trading_calendar,
                split_config=split_config,
                data_config=data_config,
                use_cache=False,
                universe_codes=universe_codes,
            )
            sharpe_seed42 = result_seed42.val.sharpe if result_seed42.val else 0

            # seed=123으로 실행
            mini_tuning_module._mock_service = MockBacktestService(123)
            clear_global_cache()

            result_seed123 = run_backtest_for_tuning(
                params=params,
                start_date=start_date,
                end_date=end_date,
                lookback_months=3,
                trading_calendar=trading_calendar,
                split_config=split_config,
                data_config=data_config,
                use_cache=False,
                universe_codes=universe_codes,
            )
            sharpe_seed123 = result_seed123.val.sharpe if result_seed123.val else 0

            # 다른 seed면 결과가 달라야 함
            assert (
                sharpe_seed42 != sharpe_seed123
            ), f"다른 seed인데 결과가 같음: seed42={sharpe_seed42}, seed123={sharpe_seed123}"

            logger.info(
                f"✅ 음성 테스트 PASS: seed42={sharpe_seed42:.4f}, seed123={sharpe_seed123:.4f}"
            )

        finally:
            runner_module._run_single_backtest = original_func

    def test_replay_same_seed_same_result(self):
        """
        같은 seed로 두 번 실행하면 결과가 동일해야 함
        """
        # Mock 패치
        import extensions.tuning.runner as runner_module
        from tests.tuning.test_mini_tuning import (
            mock_run_single_backtest,
            MockBacktestService,
            generate_mock_trading_calendar,
        )
        import tests.tuning.test_mini_tuning as mini_tuning_module

        original_func = runner_module._run_single_backtest
        runner_module._run_single_backtest = mock_run_single_backtest

        try:
            start_date = date(2020, 1, 1)
            end_date = date(2024, 6, 30)
            trading_calendar = generate_mock_trading_calendar(start_date, end_date)

            split_config = SplitConfig()
            data_config = DataConfig(
                data_version="mock_v1",
                universe_hash="test_hash_789",
                universe_count=5,
            )

            universe_codes = [f"TEST{i:03d}" for i in range(5)]
            params = {"ma_period": 60, "rsi_period": 15}

            from extensions.tuning import run_backtest_for_tuning

            # 첫 번째 실행
            mini_tuning_module._mock_service = MockBacktestService(42)
            clear_global_cache()

            result1 = run_backtest_for_tuning(
                params=params,
                start_date=start_date,
                end_date=end_date,
                lookback_months=3,
                trading_calendar=trading_calendar,
                split_config=split_config,
                data_config=data_config,
                use_cache=False,
                universe_codes=universe_codes,
            )
            sharpe1 = result1.val.sharpe if result1.val else 0

            # 두 번째 실행 (같은 seed)
            mini_tuning_module._mock_service = MockBacktestService(42)
            clear_global_cache()

            result2 = run_backtest_for_tuning(
                params=params,
                start_date=start_date,
                end_date=end_date,
                lookback_months=3,
                trading_calendar=trading_calendar,
                split_config=split_config,
                data_config=data_config,
                use_cache=False,
                universe_codes=universe_codes,
            )
            sharpe2 = result2.val.sharpe if result2.val else 0

            # 같은 seed면 결과가 동일해야 함
            assert (
                sharpe1 == sharpe2
            ), f"같은 seed인데 결과가 다름: {sharpe1} != {sharpe2}"

            logger.info(f"✅ 동일 seed 테스트 PASS: sharpe={sharpe1:.6f}")

        finally:
            runner_module._run_single_backtest = original_func


def run_replay_determinism_test():
    """
    Replay 재현성 테스트 실행 (pytest 없이 직접 실행)
    """
    print("\n" + "=" * 60)
    print("Replay 재현성 테스트")
    print("=" * 60)

    test = TestReplayDeterminism()
    # fixture 대신 직접 캐시 초기화
    clear_global_cache()

    try:
        print("\n[1] Mock replay 재현성 테스트...")
        test.test_mock_replay_determinism()
        print("   ✅ PASS")
    except AssertionError as e:
        print(f"   ❌ FAIL: {e}")
        return False

    try:
        print("\n[2] 다른 seed 음성 테스트...")
        test.test_replay_with_different_seed_should_fail()
        print("   ✅ PASS")
    except AssertionError as e:
        print(f"   ❌ FAIL: {e}")
        return False

    try:
        print("\n[3] 같은 seed 동일 결과 테스트...")
        test.test_replay_same_seed_same_result()
        print("   ✅ PASS")
    except AssertionError as e:
        print(f"   ❌ FAIL: {e}")
        return False

    print("\n" + "=" * 60)
    print("✅ 모든 Replay 재현성 테스트 PASS")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = run_replay_determinism_test()
    sys.exit(0 if success else 1)
