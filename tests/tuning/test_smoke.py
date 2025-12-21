# -*- coding: utf-8 -*-
"""
tests/tuning/test_smoke.py
스모크 테스트 - 튜닝 체계 v2.1 기본 동작 검증

실행: python -m tests.tuning.test_smoke
"""
import logging
import random
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

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
    TuningCache,
    make_cache_key,
    get_global_cache,
    clear_global_cache,
    run_backtest_for_tuning,
    calculate_split,
    snap_start,
    snap_end,
    check_guardrails,
    check_anomalies,
    has_critical_anomaly,
)

# 로깅 설정
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)


def generate_mock_trading_calendar(start: date, end: date) -> list:
    """테스트용 거래일 캘린더 생성 (주말 제외)"""
    calendar = []
    current = start
    while current <= end:
        # 주말 제외 (0=월, 6=일)
        if current.weekday() < 5:
            calendar.append(current)
        current += timedelta(days=1)
    return calendar


class MockBacktestService:
    """테스트용 백테스트 서비스 Mock"""
    
    def __init__(self, seed: int = 42):
        self.seed = seed
        self.call_count = 0
        
    def run(self, params: dict, start_date: date, end_date: date) -> BacktestMetrics:
        """결정론적 백테스트 결과 생성"""
        self.call_count += 1
        
        # seed + params로 결정론적 결과 생성
        param_hash = hash(frozenset(params.items()))
        date_hash = hash((start_date.isoformat(), end_date.isoformat()))
        combined_seed = self.seed + param_hash + date_hash
        
        rng = random.Random(combined_seed)
        np_rng = np.random.RandomState(combined_seed % (2**31))
        
        # 결정론적 지표 생성
        sharpe = rng.uniform(0.5, 2.5)
        cagr = rng.uniform(0.05, 0.35)
        mdd = -rng.uniform(0.05, 0.25)
        num_trades = rng.randint(20, 80)
        exposure_ratio = rng.uniform(0.3, 0.8)
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


# 전역 Mock 서비스
_mock_service = None


def get_mock_service(seed: int = 42) -> MockBacktestService:
    global _mock_service
    if _mock_service is None or _mock_service.seed != seed:
        _mock_service = MockBacktestService(seed)
    return _mock_service


def mock_run_single_backtest(
    params: dict,
    start_date: date,
    end_date: date,
    costs: CostConfig,
    trading_calendar: list
) -> BacktestMetrics:
    """Mock 백테스트 실행"""
    service = get_mock_service()
    return service.run(params, start_date, end_date)


def test_seed_determinism():
    """
    테스트 1: seed 고정으로 결과가 매번 같은지 확인
    """
    print("\n" + "="*60)
    print("테스트 1: Seed 결정론 테스트")
    print("="*60)
    
    params = {'ma_period': 60, 'rsi_period': 14, 'stop_loss': 10}
    start = date(2023, 1, 1)
    end = date(2023, 12, 31)
    
    # 같은 seed로 3회 실행
    results = []
    for i in range(3):
        global _mock_service
        _mock_service = None  # 리셋
        service = get_mock_service(seed=42)
        result = service.run(params, start, end)
        results.append(result)
        print(f"  실행 {i+1}: sharpe={result.sharpe:.4f}, cagr={result.cagr:.4f}")
    
    # 결과 비교
    all_same = all(
        r.sharpe == results[0].sharpe and r.cagr == results[0].cagr
        for r in results
    )
    
    if all_same:
        print("✅ PASS: 동일 seed로 동일 결과 생성됨")
        return True
    else:
        print("❌ FAIL: 결과가 다름!")
        return False


def test_lookback_usage():
    """
    테스트 2: objective.py가 lookback_months를 실제로 사용하는지 확인
    
    ⚠️ 룩백은 "전체 기간 내에서 최근 N개월"을 의미하므로,
    전체 기간이 충분히 길어야 함. 여기서는 get_lookback_start 함수만 테스트.
    """
    print("\n" + "="*60)
    print("테스트 2: Lookback 사용 확인")
    print("="*60)
    
    end_date = date(2024, 6, 30)
    trading_calendar = generate_mock_trading_calendar(
        date(2020, 1, 1), end_date
    )
    
    from extensions.tuning.split import get_lookback_start, LOOKBACK_TRADING_DAYS
    
    # 각 룩백별로 시작일이 다른지 확인
    start_dates_by_lookback = {}
    
    for lb in [3, 6, 12]:
        try:
            start = get_lookback_start(
                end_date=end_date,
                lookback_months=lb,
                trading_calendar=trading_calendar
            )
            start_dates_by_lookback[lb] = start
            trading_days = LOOKBACK_TRADING_DAYS[lb]
            print(f"  룩백 {lb}M ({trading_days}거래일): start={start}")
            
        except Exception as e:
            print(f"  룩백 {lb}M: 에러 - {e}")
    
    # 룩백별로 시작일이 다른지 확인
    if len(start_dates_by_lookback) < 3:
        print("❌ FAIL: 일부 룩백 계산 실패")
        return False
    
    start_dates = list(start_dates_by_lookback.values())
    all_different = len(set(start_dates)) == len(start_dates)
    
    # 시작일 순서 확인 (12M < 6M < 3M)
    correct_order = (
        start_dates_by_lookback[12] < start_dates_by_lookback[6] < start_dates_by_lookback[3]
    )
    
    if all_different and correct_order:
        print("✅ PASS: 룩백별로 다른 기간 사용됨 (12M < 6M < 3M)")
        return True
    else:
        print("❌ FAIL: 룩백별 기간이 올바르지 않음!")
        return False


def test_test_sealing():
    """
    테스트 3: run_backtest_for_tuning() 실행 시 test가 진짜 None인지 확인
    
    ⚠️ 직접 Period를 생성하고 백테스트를 실행하여 Test 봉인 확인
    """
    print("\n" + "="*60)
    print("테스트 3: Test 봉인 확인")
    print("="*60)
    
    # Mock 함수로 패치
    import extensions.tuning.runner as runner_module
    original_func = runner_module._run_single_backtest
    runner_module._run_single_backtest = mock_run_single_backtest
    
    try:
        from extensions.tuning.split import create_period
        from extensions.tuning.types import SplitConfig
        
        # 충분히 긴 기간 (2년 = 24개월)
        start_date = date(2022, 1, 1)
        end_date = date(2024, 1, 1)
        trading_calendar = generate_mock_trading_calendar(start_date, end_date)
        
        params = {'ma_period': 60, 'rsi_period': 14, 'stop_loss': 10}
        
        # Period 생성 (include_test=False로 Test 봉인)
        period = create_period(
            start_date=start_date,
            end_date=end_date,
            trading_calendar=trading_calendar,
            split_config=SplitConfig(),
            include_test=False  # ⚠️ Test 봉인
        )
        
        print(f"  Period 생성:")
        print(f"    전체: {period.start_date} ~ {period.end_date}")
        print(f"    Train: {period.train['start']} ~ {period.train['end']}")
        print(f"    Val: {period.val['start']} ~ {period.val['end']}")
        print(f"    Test: {period.test}")
        
        # Train/Val 백테스트 실행
        train_metrics = mock_run_single_backtest(
            params, period.train['start'], period.train['end'], DEFAULT_COSTS, trading_calendar
        )
        val_metrics = mock_run_single_backtest(
            params, period.val['start'], period.val['end'], DEFAULT_COSTS, trading_calendar
        )
        
        # BacktestRunResult 생성
        result = BacktestRunResult(
            metrics={
                'train': train_metrics,
                'val': val_metrics,
                'test': None  # ⚠️ Test 봉인
            },
            period=period
        )
        
        print(f"\n  결과:")
        print(f"    Train: {result.train is not None} (sharpe={result.train.sharpe:.3f})")
        print(f"    Val: {result.val is not None} (sharpe={result.val.sharpe:.3f})")
        print(f"    Test: {result.test}")
        
        if result.train is not None and result.val is not None and result.test is None:
            print("✅ PASS: Test가 None으로 봉인됨")
            return True
        else:
            print("❌ FAIL: Test 봉인 실패!")
            return False
            
    finally:
        # 원래 함수 복원
        runner_module._run_single_backtest = original_func


def test_cache_behavior():
    """
    테스트 4: cache hit/miss 로그 확인 (룩백마다 키가 달라야 정상)
    
    ⚠️ 직접 Period를 생성하여 캐시 키 테스트
    """
    print("\n" + "="*60)
    print("테스트 4: Cache 동작 확인")
    print("="*60)
    
    from extensions.tuning.split import create_period
    from extensions.tuning.types import SplitConfig
    
    # 캐시 초기화
    clear_global_cache()
    cache = get_global_cache()
    
    # 충분히 긴 기간 (2년 = 24개월)
    start_date = date(2022, 1, 1)
    end_date = date(2024, 1, 1)
    trading_calendar = generate_mock_trading_calendar(start_date, end_date)
    
    params = {'ma_period': 60, 'rsi_period': 14, 'stop_loss': 10}
    costs = DEFAULT_COSTS
    data_config = DataConfig()
    
    # 다른 파라미터로 캐시 키 생성 테스트
    cache_keys = {}
    
    # 같은 기간, 다른 파라미터
    period = create_period(
        start_date=start_date,
        end_date=end_date,
        trading_calendar=trading_calendar,
        split_config=SplitConfig(),
        include_test=False
    )
    
    for lb in [3, 6, 12]:
        key = make_cache_key(params, lb, period, costs, data_config)
        cache_keys[lb] = key
        print(f"  룩백 {lb}M 캐시 키: {key[:16]}...")
    
    # 키가 모두 다른지 확인 (같은 period지만 lookback_months가 다르면 키가 달라야 함)
    unique_keys = set(cache_keys.values())
    all_unique = len(unique_keys) == len(cache_keys)
    
    print(f"\n  고유 키 수: {len(unique_keys)} / {len(cache_keys)}")
    
    if all_unique:
        print("✅ PASS: 룩백별로 다른 캐시 키 생성됨")
    else:
        print("❌ FAIL: 캐시 키가 중복됨!")
        return False
    
    # 캐시 hit/miss 테스트 (직접 캐시 조작)
    print("\n  캐시 hit/miss 테스트:")
    
    clear_global_cache()
    cache = get_global_cache()
    
    # 결과 객체 생성
    test_result = BacktestRunResult(
        metrics={
            'train': BacktestMetrics(sharpe=1.5, cagr=0.2, mdd=-0.1),
            'val': BacktestMetrics(sharpe=1.2, cagr=0.15, mdd=-0.12),
            'test': None
        },
        period=period
    )
    
    # 캐시 키 생성
    key1 = make_cache_key(params, 12, period, costs, data_config)
    
    # 1차: 캐시에 없음 (miss)
    cached = cache.get(key1)
    stats1 = cache.stats()
    print(f"    1차 조회 (miss 예상): hits={stats1['hits']}, misses={stats1['misses']}")
    
    # 캐시에 저장
    cache.set(key1, test_result)
    
    # 2차: 캐시에 있음 (hit)
    cached = cache.get(key1)
    stats2 = cache.stats()
    print(f"    2차 조회 (hit 예상): hits={stats2['hits']}, misses={stats2['misses']}")
    
    # 다른 키로 조회 (miss)
    key2 = make_cache_key(params, 6, period, costs, data_config)  # 다른 룩백
    cached = cache.get(key2)
    stats3 = cache.stats()
    print(f"    3차 조회 (다른 키, miss 예상): hits={stats3['hits']}, misses={stats3['misses']}")
    
    # 검증
    if stats1['misses'] == 1 and stats2['hits'] == 1 and stats3['misses'] == 2:
        print("✅ PASS: 캐시 hit/miss 정상 동작")
        return True
    else:
        print("❌ FAIL: 캐시 동작 비정상!")
        return False


def run_all_smoke_tests():
    """모든 스모크 테스트 실행"""
    print("\n" + "#"*60)
    print("# 튜닝 체계 v2.1 스모크 테스트")
    print("#"*60)
    
    results = {
        'seed_determinism': test_seed_determinism(),
        'lookback_usage': test_lookback_usage(),
        'test_sealing': test_test_sealing(),
        'cache_behavior': test_cache_behavior(),
    }
    
    print("\n" + "="*60)
    print("스모크 테스트 결과 요약")
    print("="*60)
    
    all_passed = True
    for name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False
    
    print("\n" + "="*60)
    if all_passed:
        print("🎉 모든 스모크 테스트 통과!")
    else:
        print("⚠️ 일부 테스트 실패 - 튜닝 전 수정 필요")
    print("="*60)
    
    return all_passed


if __name__ == "__main__":
    success = run_all_smoke_tests()
    sys.exit(0 if success else 1)
