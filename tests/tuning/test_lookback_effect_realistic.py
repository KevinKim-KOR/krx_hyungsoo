# -*- coding: utf-8 -*-
"""
tests/tuning/test_lookback_effect_realistic.py
룩백이 진짜로 결과에 영향을 주는지 자동 증명 테스트 - Phase 1.6

같은 params, 같은 universe, 같은 period에서 lookback_months=3/6/12로 3번 실행했을 때:
1. result.debug.lookback_start_date가 달라야 함
2. cache_key_prefix(앞 8자리)가 달라야 함

둘 중 하나라도 동일하면 FAIL.
"""
import pytest
from datetime import date
from typing import List

from extensions.tuning.runner import run_backtest_for_tuning
from extensions.tuning.types import SplitConfig, CostConfig, DataConfig
from extensions.tuning.cache import clear_global_cache


def get_mock_trading_calendar(start_date: date, end_date: date) -> List[date]:
    """테스트용 거래일 생성 (주말 제외)"""
    from datetime import timedelta

    calendar = []
    current = start_date
    while current <= end_date:
        if current.weekday() < 5:  # 월~금
            calendar.append(current)
        current += timedelta(days=1)
    return calendar


@pytest.fixture
def mock_backtest_setup(monkeypatch):
    """Mock 백테스트 설정"""
    from extensions.tuning.types import BacktestMetrics

    call_count = {"count": 0}

    def mock_run_single_backtest(
        params, start_date, end_date, costs, trading_calendar, universe_codes=None
    ):
        call_count["count"] += 1
        # 룩백에 따라 다른 결과 반환 (실제 영향 시뮬레이션)
        return BacktestMetrics(
            sharpe=0.5 + call_count["count"] * 0.1,
            cagr=0.10,
            mdd=-0.15,
            num_trades=50,
            exposure_ratio=0.5,
        )

    import extensions.tuning.runner as runner_module

    monkeypatch.setattr(runner_module, "_run_single_backtest", mock_run_single_backtest)

    return call_count


class TestLookbackEffect:
    """룩백 효과 테스트"""

    def test_lookback_produces_different_lookback_start_dates(
        self, mock_backtest_setup
    ):
        """
        같은 params로 lookback_months=3/6/12 실행 시
        debug.lookback_start_date가 모두 달라야 함
        """
        clear_global_cache()

        params = {"ma_period": 60, "rsi_period": 14, "stop_loss": 0.08}
        start_date = date(2020, 1, 1)
        end_date = date(2024, 12, 31)
        trading_calendar = get_mock_trading_calendar(start_date, end_date)

        lookbacks = [3, 6, 12]
        lookback_start_dates = []

        for lb in lookbacks:
            result = run_backtest_for_tuning(
                params=params,
                start_date=start_date,
                end_date=end_date,
                lookback_months=lb,
                trading_calendar=trading_calendar,
                use_cache=False,  # 캐시 비활성화로 매번 실행
            )

            assert result.debug is not None, f"lookback={lb}: debug가 None"
            assert (
                result.debug.lookback_start_date is not None
            ), f"lookback={lb}: lookback_start_date가 None"

            lookback_start_dates.append(result.debug.lookback_start_date)

        # 모든 lookback_start_date가 달라야 함
        unique_dates = set(lookback_start_dates)
        assert len(unique_dates) == len(lookbacks), (
            f"lookback_start_date가 동일함! "
            f"dates={lookback_start_dates}, unique={len(unique_dates)}"
        )

    def test_lookback_produces_different_cache_keys(self, mock_backtest_setup):
        """
        같은 params로 lookback_months=3/6/12 실행 시
        cache_key 앞 8자리가 모두 달라야 함
        """
        clear_global_cache()

        params = {"ma_period": 60, "rsi_period": 14, "stop_loss": 0.08}
        start_date = date(2020, 1, 1)
        end_date = date(2024, 12, 31)
        trading_calendar = get_mock_trading_calendar(start_date, end_date)

        lookbacks = [3, 6, 12]
        cache_key_prefixes = []

        for lb in lookbacks:
            result = run_backtest_for_tuning(
                params=params,
                start_date=start_date,
                end_date=end_date,
                lookback_months=lb,
                trading_calendar=trading_calendar,
                use_cache=True,  # 캐시 활성화
            )

            assert result.debug is not None, f"lookback={lb}: debug가 None"
            assert result.debug.cache_key, f"lookback={lb}: cache_key가 비어있음"

            cache_key_prefix = result.debug.cache_key[:8]
            cache_key_prefixes.append(cache_key_prefix)

        # 모든 cache_key 앞 8자리가 달라야 함
        unique_prefixes = set(cache_key_prefixes)
        assert len(unique_prefixes) == len(lookbacks), (
            f"cache_key 앞 8자리가 동일함! "
            f"prefixes={cache_key_prefixes}, unique={len(unique_prefixes)}"
        )

    def test_lookback_both_conditions_must_differ(self, mock_backtest_setup):
        """
        통합 테스트: lookback_start_date와 cache_key 둘 다 달라야 함
        """
        clear_global_cache()

        params = {"ma_period": 60, "rsi_period": 14, "stop_loss": 0.08}
        start_date = date(2020, 1, 1)
        end_date = date(2024, 12, 31)
        trading_calendar = get_mock_trading_calendar(start_date, end_date)

        lookbacks = [3, 6, 12]
        results_by_lookback = {}

        for lb in lookbacks:
            result = run_backtest_for_tuning(
                params=params,
                start_date=start_date,
                end_date=end_date,
                lookback_months=lb,
                trading_calendar=trading_calendar,
                use_cache=True,
            )
            results_by_lookback[lb] = result

        # 검증 1: lookback_start_date가 모두 다름
        lookback_start_dates = [
            r.debug.lookback_start_date for r in results_by_lookback.values()
        ]
        assert len(set(lookback_start_dates)) == len(
            lookbacks
        ), f"lookback_start_date 중복! {lookback_start_dates}"

        # 검증 2: cache_key 앞 8자리가 모두 다름
        cache_key_prefixes = [
            r.debug.cache_key[:8] for r in results_by_lookback.values()
        ]
        assert len(set(cache_key_prefixes)) == len(
            lookbacks
        ), f"cache_key 앞 8자리 중복! {cache_key_prefixes}"

        # 검증 3: lookback_months가 올바르게 기록됨
        for lb, result in results_by_lookback.items():
            assert (
                result.debug.lookback_months == lb
            ), f"lookback_months 불일치: expected={lb}, actual={result.debug.lookback_months}"

        print("\n✅ 룩백 효과 검증 통과:")
        for lb, result in results_by_lookback.items():
            print(
                f"   lb={lb}M: start_date={result.debug.lookback_start_date}, "
                f"cache_key={result.debug.cache_key[:8]}..."
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
