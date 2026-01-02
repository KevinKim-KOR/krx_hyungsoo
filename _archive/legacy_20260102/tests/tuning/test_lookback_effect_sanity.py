# -*- coding: utf-8 -*-
"""
tests/tuning/test_lookback_effect_sanity.py
Lookback "의미 검증" 테스트

목표: 동일 params로 lb=3/6/12 실행했을 때,
      최소한 debug.indicator_warmup_days 또는 debug.lookback_effective_start_date가
      서로 달라야 PASS

설계 참고:
- 현재 시스템에서 lookback_months는 "캐시 키 구분"용으로만 사용됨
- 실제 Train/Val 구간은 전체 기간에서 split_config 비율로 계산됨
- 따라서 lookback_months가 달라도 period_signature는 동일할 수 있음
- 하지만 debug.lookback_start_date는 달라야 함 (end_date - lookback_months)

실행: python -m tests.tuning.test_lookback_effect_sanity
"""
import logging
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from extensions.tuning import (
    clear_global_cache,
    run_backtest_for_tuning,
    SplitConfig,
    DataConfig,
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


class TestLookbackEffectSanity:
    """Lookback 의미 검증 테스트"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """테스트 전 캐시 초기화 및 Mock 패치"""
        clear_global_cache()

        # Mock 패치
        import extensions.tuning.runner as runner_module
        from tests.tuning.test_mini_tuning import (
            mock_run_single_backtest,
            MockBacktestService,
            generate_mock_trading_calendar,
        )
        import tests.tuning.test_mini_tuning as mini_tuning_module

        self.original_func = runner_module._run_single_backtest
        runner_module._run_single_backtest = mock_run_single_backtest
        mini_tuning_module._mock_service = MockBacktestService(42)

        self.start_date = date(2020, 1, 1)
        self.end_date = date(2024, 6, 30)
        self.trading_calendar = generate_mock_trading_calendar(
            self.start_date, self.end_date
        )

        yield

        # Mock 패치 복원
        runner_module._run_single_backtest = self.original_func

    def test_lookback_start_date_differs_by_lookback(self):
        """
        동일 params로 lb=3/6/12 실행 시 debug.lookback_start_date가 달라야 함

        lookback_start_date = end_date - lookback_months
        따라서 lb=3/6/12면 각각 다른 날짜가 나와야 함
        """
        params = {"ma_period": 60, "rsi_period": 14}
        split_config = SplitConfig()
        data_config = DataConfig(
            data_version="mock_v1",
            universe_hash="test_hash",
            universe_count=5,
        )
        universe_codes = [f"TEST{i:03d}" for i in range(5)]

        lookbacks = [3, 6, 12]
        results = {}

        for lb in lookbacks:
            clear_global_cache()
            result = run_backtest_for_tuning(
                params=params,
                start_date=self.start_date,
                end_date=self.end_date,
                lookback_months=lb,
                trading_calendar=self.trading_calendar,
                split_config=split_config,
                data_config=data_config,
                use_cache=False,
                universe_codes=universe_codes,
            )
            results[lb] = result

            logger.info(
                f"lb={lb}M: lookback_start_date={result.debug.lookback_start_date}, "
                f"lookback_effective_start_date={result.debug.lookback_effective_start_date}, "
                f"indicator_warmup_days={result.debug.indicator_warmup_days}"
            )

        # 검증: lookback_start_date가 모두 달라야 함
        start_dates = [r.debug.lookback_start_date for r in results.values()]
        unique_dates = set(start_dates)

        assert len(unique_dates) == len(
            lookbacks
        ), f"lookback_start_date가 모두 달라야 함: {start_dates}"

        logger.info(f"✅ lookback_start_date 검증 PASS: {start_dates}")

    def test_lookback_months_stored_correctly(self):
        """
        debug.lookback_months가 입력값과 일치하는지 확인
        """
        params = {"ma_period": 60, "rsi_period": 14}
        split_config = SplitConfig()
        data_config = DataConfig(
            data_version="mock_v1",
            universe_hash="test_hash",
            universe_count=5,
        )
        universe_codes = [f"TEST{i:03d}" for i in range(5)]

        lookbacks = [3, 6, 12]

        for lb in lookbacks:
            clear_global_cache()
            result = run_backtest_for_tuning(
                params=params,
                start_date=self.start_date,
                end_date=self.end_date,
                lookback_months=lb,
                trading_calendar=self.trading_calendar,
                split_config=split_config,
                data_config=data_config,
                use_cache=False,
                universe_codes=universe_codes,
            )

            assert (
                result.debug.lookback_months == lb
            ), f"lookback_months 불일치: expected={lb}, got={result.debug.lookback_months}"

        logger.info(f"✅ lookback_months 저장 검증 PASS")

    def test_indicator_warmup_days_based_on_ma_period(self):
        """
        debug.indicator_warmup_days가 ma_period에 따라 설정되는지 확인
        """
        split_config = SplitConfig()
        data_config = DataConfig(
            data_version="mock_v1",
            universe_hash="test_hash",
            universe_count=5,
        )
        universe_codes = [f"TEST{i:03d}" for i in range(5)]

        ma_periods = [20, 60, 100]

        for ma_period in ma_periods:
            params = {"ma_period": ma_period, "rsi_period": 14}
            clear_global_cache()

            result = run_backtest_for_tuning(
                params=params,
                start_date=self.start_date,
                end_date=self.end_date,
                lookback_months=3,
                trading_calendar=self.trading_calendar,
                split_config=split_config,
                data_config=data_config,
                use_cache=False,
                universe_codes=universe_codes,
            )

            assert result.debug.indicator_warmup_days == ma_period, (
                f"indicator_warmup_days 불일치: expected={ma_period}, "
                f"got={result.debug.indicator_warmup_days}"
            )

            logger.info(
                f"  ma_period={ma_period} -> indicator_warmup_days={result.debug.indicator_warmup_days}"
            )

        logger.info(f"✅ indicator_warmup_days 검증 PASS")

    def test_lookback_effective_start_date_differs_by_ma_period(self):
        """
        ma_period가 다르면 lookback_effective_start_date도 달라야 함

        lookback_effective_start_date = train_start + indicator_warmup_days
        """
        split_config = SplitConfig()
        data_config = DataConfig(
            data_version="mock_v1",
            universe_hash="test_hash",
            universe_count=5,
        )
        universe_codes = [f"TEST{i:03d}" for i in range(5)]

        ma_periods = [20, 60, 100]
        effective_dates = []

        for ma_period in ma_periods:
            params = {"ma_period": ma_period, "rsi_period": 14}
            clear_global_cache()

            result = run_backtest_for_tuning(
                params=params,
                start_date=self.start_date,
                end_date=self.end_date,
                lookback_months=3,
                trading_calendar=self.trading_calendar,
                split_config=split_config,
                data_config=data_config,
                use_cache=False,
                universe_codes=universe_codes,
            )

            effective_dates.append(result.debug.lookback_effective_start_date)
            logger.info(
                f"  ma_period={ma_period} -> effective_start={result.debug.lookback_effective_start_date}"
            )

        # 검증: effective_start_date가 모두 달라야 함
        unique_dates = set(effective_dates)
        assert len(unique_dates) == len(
            ma_periods
        ), f"lookback_effective_start_date가 모두 달라야 함: {effective_dates}"

        logger.info(f"✅ lookback_effective_start_date 검증 PASS")


def run_lookback_sanity_test():
    """
    Lookback 의미 검증 테스트 실행 (pytest 없이 직접 실행)
    """
    print("\n" + "=" * 60)
    print("Lookback 의미 검증 테스트")
    print("=" * 60)

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
    mini_tuning_module._mock_service = MockBacktestService(42)

    start_date = date(2020, 1, 1)
    end_date = date(2024, 6, 30)
    trading_calendar = generate_mock_trading_calendar(start_date, end_date)

    try:
        print("\n[1] lookback_start_date 검증...")
        params = {"ma_period": 60, "rsi_period": 14}
        split_config = SplitConfig()
        data_config = DataConfig(
            data_version="mock_v1",
            universe_hash="test_hash",
            universe_count=5,
        )
        universe_codes = [f"TEST{i:03d}" for i in range(5)]

        lookbacks = [3, 6, 12]
        start_dates = []

        for lb in lookbacks:
            clear_global_cache()
            result = run_backtest_for_tuning(
                params=params,
                start_date=start_date,
                end_date=end_date,
                lookback_months=lb,
                trading_calendar=trading_calendar,
                split_config=split_config,
                data_config=data_config,
                use_cache=False,
                universe_codes=universe_codes,
            )
            start_dates.append(result.debug.lookback_start_date)
            print(
                f"    lb={lb}M: lookback_start_date={result.debug.lookback_start_date}"
            )

        if len(set(start_dates)) == len(lookbacks):
            print("   ✅ PASS")
        else:
            print(f"   ❌ FAIL: 중복 날짜 발견")
            return False

        print("\n[2] indicator_warmup_days 검증...")
        ma_periods = [20, 60, 100]
        for ma_period in ma_periods:
            params = {"ma_period": ma_period, "rsi_period": 14}
            clear_global_cache()
            result = run_backtest_for_tuning(
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
            if result.debug.indicator_warmup_days != ma_period:
                print(
                    f"   ❌ FAIL: ma_period={ma_period}, warmup={result.debug.indicator_warmup_days}"
                )
                return False
            print(
                f"    ma_period={ma_period} -> warmup={result.debug.indicator_warmup_days}"
            )
        print("   ✅ PASS")

        print("\n[3] lookback_effective_start_date 검증...")
        effective_dates = []
        for ma_period in ma_periods:
            params = {"ma_period": ma_period, "rsi_period": 14}
            clear_global_cache()
            result = run_backtest_for_tuning(
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
            effective_dates.append(result.debug.lookback_effective_start_date)
            print(
                f"    ma_period={ma_period} -> effective_start={result.debug.lookback_effective_start_date}"
            )

        if len(set(effective_dates)) == len(ma_periods):
            print("   ✅ PASS")
        else:
            print(f"   ❌ FAIL: 중복 날짜 발견")
            return False

        print("\n" + "=" * 60)
        print("✅ 모든 Lookback 의미 검증 테스트 PASS")
        print("=" * 60)
        return True

    finally:
        runner_module._run_single_backtest = original_func


if __name__ == "__main__":
    success = run_lookback_sanity_test()
    sys.exit(0 if success else 1)
