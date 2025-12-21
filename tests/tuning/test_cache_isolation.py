# -*- coding: utf-8 -*-
"""
tests/tuning/test_cache_isolation.py
Cache isolation 단위테스트 - 캐시 오염 방지 검증

목표: 캐시가 파라미터/룩백/유니버스/데이터버전 변경에 대해 오염되지 않는지 증명

테스트 항목:
(A) 동일 입력 2회: 2회차 HIT 증가 확인
(B) params 중 1개만 변경(ma_period +10 등): cache_key 달라지고 MISS 발생 확인
(C) universe_codes 1개만 변경: cache_key 달라지고 MISS 확인
(D) data_version(mock_v1 vs real_v1) 변경: cache_key 달라지고 MISS 확인

실행: python -m tests.tuning.test_cache_isolation
"""
import logging
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from extensions.tuning import (
    clear_global_cache,
    get_global_cache,
    run_backtest_for_tuning,
    SplitConfig,
    DataConfig,
)
from extensions.tuning.cache import make_cache_key
from extensions.tuning.split import create_period

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


class TestCacheIsolation:
    """Cache isolation 테스트"""

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

    def test_same_input_cache_hit(self):
        """
        (A) 동일 입력 2회: 2회차 HIT 증가 확인
        """
        params = {"ma_period": 60, "rsi_period": 14}
        split_config = SplitConfig()
        data_config = DataConfig(
            data_version="mock_v1",
            universe_hash="test_hash_A",
            universe_count=5,
        )
        universe_codes = [f"TEST{i:03d}" for i in range(5)]

        clear_global_cache()
        cache = get_global_cache()

        # 첫 번째 실행 (MISS)
        initial_hits = cache.stats().get("hits", 0)
        initial_misses = cache.stats().get("misses", 0)

        result1 = run_backtest_for_tuning(
            params=params,
            start_date=self.start_date,
            end_date=self.end_date,
            lookback_months=3,
            trading_calendar=self.trading_calendar,
            split_config=split_config,
            data_config=data_config,
            use_cache=True,
            universe_codes=universe_codes,
        )

        after_first_hits = cache.stats().get("hits", 0)
        after_first_misses = cache.stats().get("misses", 0)

        # 두 번째 실행 (HIT 예상)
        result2 = run_backtest_for_tuning(
            params=params,
            start_date=self.start_date,
            end_date=self.end_date,
            lookback_months=3,
            trading_calendar=self.trading_calendar,
            split_config=split_config,
            data_config=data_config,
            use_cache=True,
            universe_codes=universe_codes,
        )

        after_second_hits = cache.stats().get("hits", 0)

        # 검증: 두 번째 실행에서 HIT 증가
        assert (
            after_second_hits > after_first_hits
        ), f"2회차에서 HIT 증가해야 함: first={after_first_hits}, second={after_second_hits}"

        # 결과도 동일해야 함
        assert (
            result1.val.sharpe == result2.val.sharpe
        ), f"동일 입력인데 결과가 다름: {result1.val.sharpe} != {result2.val.sharpe}"

        logger.info(
            f"✅ 동일 입력 캐시 HIT 테스트 PASS: hits {after_first_hits} -> {after_second_hits}"
        )

    def test_params_change_cache_miss(self):
        """
        (B) params 중 1개만 변경(ma_period +10 등): cache_key 달라지고 MISS 발생 확인
        """
        base_params = {"ma_period": 60, "rsi_period": 14}
        changed_params = {"ma_period": 70, "rsi_period": 14}  # ma_period만 변경

        split_config = SplitConfig()
        data_config = DataConfig(
            data_version="mock_v1",
            universe_hash="test_hash_B",
            universe_count=5,
        )
        universe_codes = [f"TEST{i:03d}" for i in range(5)]

        clear_global_cache()

        # 첫 번째 실행 (base_params)
        result1 = run_backtest_for_tuning(
            params=base_params,
            start_date=self.start_date,
            end_date=self.end_date,
            lookback_months=3,
            trading_calendar=self.trading_calendar,
            split_config=split_config,
            data_config=data_config,
            use_cache=True,
            universe_codes=universe_codes,
        )
        cache_key1 = result1.debug.cache_key

        # 두 번째 실행 (changed_params)
        result2 = run_backtest_for_tuning(
            params=changed_params,
            start_date=self.start_date,
            end_date=self.end_date,
            lookback_months=3,
            trading_calendar=self.trading_calendar,
            split_config=split_config,
            data_config=data_config,
            use_cache=True,
            universe_codes=universe_codes,
        )
        cache_key2 = result2.debug.cache_key

        # 검증: cache_key가 달라야 함
        assert (
            cache_key1 != cache_key2
        ), f"params 변경 시 cache_key가 달라야 함: {cache_key1[:8]} == {cache_key2[:8]}"

        # 결과도 달라야 함 (다른 params이므로)
        # Note: Mock에서는 params가 결과에 영향을 미침
        logger.info(
            f"✅ params 변경 캐시 MISS 테스트 PASS: "
            f"key1={cache_key1[:8]}, key2={cache_key2[:8]}"
        )

    def test_lookback_change_cache_miss(self):
        """
        (C-1) lookback_months 변경: cache_key 달라지고 MISS 확인
        """
        params = {"ma_period": 60, "rsi_period": 14}
        split_config = SplitConfig()
        data_config = DataConfig(
            data_version="mock_v1",
            universe_hash="test_hash_C1",
            universe_count=5,
        )
        universe_codes = [f"TEST{i:03d}" for i in range(5)]

        clear_global_cache()

        lookbacks = [3, 6, 12]
        cache_keys = []

        for lb in lookbacks:
            result = run_backtest_for_tuning(
                params=params,
                start_date=self.start_date,
                end_date=self.end_date,
                lookback_months=lb,
                trading_calendar=self.trading_calendar,
                split_config=split_config,
                data_config=data_config,
                use_cache=True,
                universe_codes=universe_codes,
            )
            cache_keys.append(result.debug.cache_key)

        # 검증: 모든 cache_key가 달라야 함
        unique_keys = set(cache_keys)
        assert len(unique_keys) == len(
            lookbacks
        ), f"lookback 변경 시 cache_key가 모두 달라야 함: {[k[:8] for k in cache_keys]}"

        logger.info(
            f"✅ lookback 변경 캐시 MISS 테스트 PASS: {[k[:8] for k in cache_keys]}"
        )

    def test_universe_change_cache_miss(self):
        """
        (C-2) universe_codes 1개만 변경: cache_key 달라지고 MISS 확인

        Note: 현재 캐시 키는 data_config.universe_hash를 사용하므로,
        universe_codes가 달라지면 universe_hash도 달라져야 함
        """
        params = {"ma_period": 60, "rsi_period": 14}
        split_config = SplitConfig()

        universe_codes1 = ["TEST001", "TEST002", "TEST003"]
        universe_codes2 = ["TEST001", "TEST002", "TEST004"]  # TEST003 -> TEST004

        # universe_hash 계산
        import hashlib

        hash1 = hashlib.sha256(",".join(sorted(universe_codes1)).encode()).hexdigest()[
            :16
        ]
        hash2 = hashlib.sha256(",".join(sorted(universe_codes2)).encode()).hexdigest()[
            :16
        ]

        data_config1 = DataConfig(
            data_version="mock_v1",
            universe_hash=hash1,
            universe_count=len(universe_codes1),
        )
        data_config2 = DataConfig(
            data_version="mock_v1",
            universe_hash=hash2,
            universe_count=len(universe_codes2),
        )

        clear_global_cache()

        # 첫 번째 실행
        result1 = run_backtest_for_tuning(
            params=params,
            start_date=self.start_date,
            end_date=self.end_date,
            lookback_months=3,
            trading_calendar=self.trading_calendar,
            split_config=split_config,
            data_config=data_config1,
            use_cache=True,
            universe_codes=universe_codes1,
        )
        cache_key1 = result1.debug.cache_key

        # 두 번째 실행 (universe 변경)
        result2 = run_backtest_for_tuning(
            params=params,
            start_date=self.start_date,
            end_date=self.end_date,
            lookback_months=3,
            trading_calendar=self.trading_calendar,
            split_config=split_config,
            data_config=data_config2,
            use_cache=True,
            universe_codes=universe_codes2,
        )
        cache_key2 = result2.debug.cache_key

        # 검증: cache_key가 달라야 함
        assert (
            cache_key1 != cache_key2
        ), f"universe 변경 시 cache_key가 달라야 함: {cache_key1[:8]} == {cache_key2[:8]}"

        logger.info(
            f"✅ universe 변경 캐시 MISS 테스트 PASS: "
            f"key1={cache_key1[:8]}, key2={cache_key2[:8]}"
        )

    def test_data_version_change_cache_miss(self):
        """
        (D) data_version(mock_v1 vs real_v1) 변경: cache_key 달라지고 MISS 확인
        """
        params = {"ma_period": 60, "rsi_period": 14}
        split_config = SplitConfig()
        universe_codes = [f"TEST{i:03d}" for i in range(5)]

        data_config_mock = DataConfig(
            data_version="mock_v1",
            universe_hash="test_hash_D",
            universe_count=5,
        )
        data_config_real = DataConfig(
            data_version="real_v1",
            universe_hash="test_hash_D",
            universe_count=5,
        )

        clear_global_cache()

        # 첫 번째 실행 (mock_v1)
        result1 = run_backtest_for_tuning(
            params=params,
            start_date=self.start_date,
            end_date=self.end_date,
            lookback_months=3,
            trading_calendar=self.trading_calendar,
            split_config=split_config,
            data_config=data_config_mock,
            use_cache=True,
            universe_codes=universe_codes,
        )
        cache_key1 = result1.debug.cache_key

        # 두 번째 실행 (real_v1)
        result2 = run_backtest_for_tuning(
            params=params,
            start_date=self.start_date,
            end_date=self.end_date,
            lookback_months=3,
            trading_calendar=self.trading_calendar,
            split_config=split_config,
            data_config=data_config_real,
            use_cache=True,
            universe_codes=universe_codes,
        )
        cache_key2 = result2.debug.cache_key

        # 검증: cache_key가 달라야 함
        assert (
            cache_key1 != cache_key2
        ), f"data_version 변경 시 cache_key가 달라야 함: {cache_key1[:8]} == {cache_key2[:8]}"

        logger.info(
            f"✅ data_version 변경 캐시 MISS 테스트 PASS: "
            f"key1={cache_key1[:8]}, key2={cache_key2[:8]}"
        )


def run_cache_isolation_test():
    """
    Cache isolation 테스트 실행 (pytest 없이 직접 실행)
    """
    print("\n" + "=" * 60)
    print("Cache Isolation 테스트")
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
        # (A) 동일 입력 2회 테스트
        print("\n[A] 동일 입력 2회 - 캐시 HIT 테스트...")
        params = {"ma_period": 60, "rsi_period": 14}
        split_config = SplitConfig()
        data_config = DataConfig(
            data_version="mock_v1",
            universe_hash="test_hash_A",
            universe_count=5,
        )
        universe_codes = [f"TEST{i:03d}" for i in range(5)]

        clear_global_cache()
        cache = get_global_cache()

        result1 = run_backtest_for_tuning(
            params=params,
            start_date=start_date,
            end_date=end_date,
            lookback_months=3,
            trading_calendar=trading_calendar,
            split_config=split_config,
            data_config=data_config,
            use_cache=True,
            universe_codes=universe_codes,
        )
        hits_after_first = cache.stats().get("hits", 0)

        result2 = run_backtest_for_tuning(
            params=params,
            start_date=start_date,
            end_date=end_date,
            lookback_months=3,
            trading_calendar=trading_calendar,
            split_config=split_config,
            data_config=data_config,
            use_cache=True,
            universe_codes=universe_codes,
        )
        hits_after_second = cache.stats().get("hits", 0)

        if hits_after_second > hits_after_first:
            print(f"   ✅ PASS: hits {hits_after_first} -> {hits_after_second}")
        else:
            print(f"   ❌ FAIL: HIT 증가 없음")
            return False

        # (B) params 변경 테스트
        print("\n[B] params 변경 - 캐시 MISS 테스트...")
        clear_global_cache()

        result1 = run_backtest_for_tuning(
            params={"ma_period": 60, "rsi_period": 14},
            start_date=start_date,
            end_date=end_date,
            lookback_months=3,
            trading_calendar=trading_calendar,
            split_config=split_config,
            data_config=data_config,
            use_cache=True,
            universe_codes=universe_codes,
        )
        key1 = result1.debug.cache_key

        result2 = run_backtest_for_tuning(
            params={"ma_period": 70, "rsi_period": 14},  # ma_period 변경
            start_date=start_date,
            end_date=end_date,
            lookback_months=3,
            trading_calendar=trading_calendar,
            split_config=split_config,
            data_config=data_config,
            use_cache=True,
            universe_codes=universe_codes,
        )
        key2 = result2.debug.cache_key

        if key1 != key2:
            print(f"   ✅ PASS: key1={key1[:8]}, key2={key2[:8]}")
        else:
            print(f"   ❌ FAIL: cache_key 동일")
            return False

        # (C) lookback 변경 테스트
        print("\n[C] lookback 변경 - 캐시 MISS 테스트...")
        clear_global_cache()

        keys = []
        for lb in [3, 6, 12]:
            result = run_backtest_for_tuning(
                params=params,
                start_date=start_date,
                end_date=end_date,
                lookback_months=lb,
                trading_calendar=trading_calendar,
                split_config=split_config,
                data_config=data_config,
                use_cache=True,
                universe_codes=universe_codes,
            )
            keys.append(result.debug.cache_key)

        if len(set(keys)) == 3:
            print(f"   ✅ PASS: {[k[:8] for k in keys]}")
        else:
            print(f"   ❌ FAIL: 중복 cache_key 발견")
            return False

        # (D) data_version 변경 테스트
        print("\n[D] data_version 변경 - 캐시 MISS 테스트...")
        clear_global_cache()

        data_config_mock = DataConfig(
            data_version="mock_v1",
            universe_hash="test_hash_D",
            universe_count=5,
        )
        data_config_real = DataConfig(
            data_version="real_v1",
            universe_hash="test_hash_D",
            universe_count=5,
        )

        result1 = run_backtest_for_tuning(
            params=params,
            start_date=start_date,
            end_date=end_date,
            lookback_months=3,
            trading_calendar=trading_calendar,
            split_config=split_config,
            data_config=data_config_mock,
            use_cache=True,
            universe_codes=universe_codes,
        )
        key1 = result1.debug.cache_key

        result2 = run_backtest_for_tuning(
            params=params,
            start_date=start_date,
            end_date=end_date,
            lookback_months=3,
            trading_calendar=trading_calendar,
            split_config=split_config,
            data_config=data_config_real,
            use_cache=True,
            universe_codes=universe_codes,
        )
        key2 = result2.debug.cache_key

        if key1 != key2:
            print(f"   ✅ PASS: key1={key1[:8]}, key2={key2[:8]}")
        else:
            print(f"   ❌ FAIL: cache_key 동일")
            return False

        print("\n" + "=" * 60)
        print("✅ 모든 Cache Isolation 테스트 PASS")
        print("=" * 60)
        return True

    finally:
        runner_module._run_single_backtest = original_func


if __name__ == "__main__":
    success = run_cache_isolation_test()
    sys.exit(0 if success else 1)
