# -*- coding: utf-8 -*-
"""End-to-End tests for market data functionality"""
import pytest
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

@pytest.mark.e2e
@pytest.mark.skipif(
    "not config.getoption('--run-e2e')",
    reason="Only run when --run-e2e is given"
)
def test_full_market_data_workflow():
    """전체 마켓 데이터 워크플로우 테스트"""
    from infra.data.loader import load_market_data
    from core.indicators import calculate_momentum
    from core.engine.scanner import scan_market
    
    # 1. 데이터 로드
    end_date = pd.Timestamp.now().floor('D')
    start_date = end_date - pd.Timedelta(days=60)  # 실제 사용 기간
    
    market_data = load_market_data('KOR_ETF_CORE', end_date, start_date)
    assert not market_data.empty, "마켓 데이터가 로드되어야 함"
    
    # 2. 지표 계산
    momentum = calculate_momentum(market_data)
    assert not momentum.empty, "모멘텀 지표가 계산되어야 함"
    
    # 3. 스캐너 실행
    signals = scan_market(market_data, momentum)
    assert isinstance(signals, pd.DataFrame), "스캔 결과가 생성되어야 함"
    
    # 4. 결과 검증
    assert 'signal' in signals.columns, "신호 컬럼이 존재해야 함"
    assert not signals[signals['signal'] != 0].empty, "유효한 신호가 있어야 함"

def pytest_addoption(parser):
    parser.addoption(
        "--run-e2e",
        action="store_true",
        default=False,
        help="run end-to-end tests"
    )