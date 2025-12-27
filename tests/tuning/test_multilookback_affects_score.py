# -*- coding: utf-8 -*-
"""
tests/tuning/test_multilookback_affects_score.py

검증 목표:
lb=3, 6, 12개월 실행 시 score 또는 val_sharpe_trailing 또는 val_bars_used_trailing 중 
최소 1개가 반드시 달라져야 한다.

이전에는 룩백이 캐시 키에만 영향을 주고, 실제 백테스트 기간은 동일(Start~End)하여
결과가 똑같이 나오는 문제가 있었다 (가짜 멀티룩백).
v2.2에서는 "평가 윈도우"로서의 룩백을 검증한다.
"""
import pytest
from datetime import date
from extensions.tuning.runner import run_backtest_for_tuning
from extensions.tuning.types import BacktestRunResult

# Mock 데이터 생성을 위한 임시 설정 (Val 기간 확보를 위해 5년 설정)
START_DATE = date(2020, 1, 1)
END_DATE = date(2024, 12, 31)
PARAMS = {
    "ma_period": 60,
    "rsi_period": 14,
    "stop_loss_pct": 0.05,
}

@pytest.fixture
def mock_calendar():
    """주말 제외한 간단한 거래일 캘린더"""
    from datetime import timedelta
    calendar = []
    curr = START_DATE
    while curr <= END_DATE:
        if curr.weekday() < 5:
            calendar.append(curr)
        curr += timedelta(days=1)
    return calendar

@pytest.fixture
def mock_universe():
    return ["005930", "000660"]

def test_multilookback_results_differ(mock_calendar, mock_universe):
    """
    동일 파라미터로 lookback만 다르게 실행했을 때,
    결과(bars_used, sharpe 등)가 달라져야 한다.
    """
    # 1. 실행 (lb=3, 6, 12)
    # 실제 데이터나 Mock 서비스 동작에 의존하므로, 여기서는
    # runner 로직이 'trailing'을 반영하는지 확인하는 것이 핵심.
    # 단, 현재 MockBacktestService는 기간에 상관없이 랜덤/고정 값을 리턴할 수 있으므로
    # runner.py가 'bars_used'를 계산하는 방식이 변경되었는지 확인하는 것이 더 확실할 수 있다.
    # 하지만 통합 테스트 관점에서 실행 결과 비교를 시도한다.
    
    # ⚠️ 주의: 이 테스트는 runner 수정 전에는 실패해야 정상이다 (현재는 똑같음)
    
    results = {}
    lookbacks = [3, 6, 12]
    
    for lb in lookbacks:
        result: BacktestRunResult = run_backtest_for_tuning(
            params=PARAMS,
            start_date=START_DATE,
            end_date=END_DATE,
            lookback_months=lb,
            trading_calendar=mock_calendar,
            universe_codes=mock_universe,
            use_cache=False # 공정한 비교를 위해 캐시 끔
        )
        
        # v2.2 요구사항: val 결과가 trailing 기준이어야 함
        # bars_used는 val 기간의 거래일 수인데, v2.2에서는 lb에 따라 달라져야 함
        val_metrics = result.val
        debug = result.debug
        
        print(f"\n[LB={lb}]")
        if debug:
            print(f"  effective_eval_start: {debug.effective_eval_start}")
            print(f"  bars_used: {debug.bars_used}")
            
        results[lb] = {
            "sharpe": val_metrics.sharpe if val_metrics else 0.0,
            "bars_used": debug.bars_used if debug else 0,
            "effective_start": debug.effective_eval_start if debug else None
        }

    # 2. 검증: bars_used나 sharpe가 서로 달라야 함
    # 특히 bars_used는 물리적으로 달라야 함 (3개월 vs 6개월 vs 12개월)
    
    # LB=3 vs LB=6
    assert results[3]["bars_used"] != results[6]["bars_used"], \
        f"LB=3({results[3]['bars_used']})과 LB=6({results[6]['bars_used']})의 bars_used가 동일합니다. Trailing 평가가 적용되지 않았습니다."
        
    # LB=6 vs LB=12
    assert results[6]["bars_used"] != results[12]["bars_used"], \
        f"LB=6({results[6]['bars_used']})과 LB=12({results[12]['bars_used']})의 bars_used가 동일합니다."
        
    print("\n✅ 멀티 룩백 검증 통과: 룩백별로 평가 기간(bars_used)이 다릅니다.")
