"""Integration tests for market data functionality"""
import pytest
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

@pytest.mark.integration
@pytest.mark.skipif(
    "not config.getoption('--run-integration')",
    reason="Only run when --run-integration is given"
)
def test_real_market_data_load():
    """실제 API를 사용한 마켓 데이터 로드 테스트"""
    from infra.data.loader import load_market_data
    
    end_date = pd.Timestamp.now().floor('D')
    start_date = end_date - pd.Timedelta(days=5)
    
    df = load_market_data('KOR_ETF_CORE', end_date, start_date)
    
    assert isinstance(df, pd.DataFrame)
    assert len(df) > 0
    assert isinstance(df.index, pd.MultiIndex)
    assert df.index.names == ['code', 'date']
    assert 'close' in df.columns
    assert df['close'].dtype == float
    assert (df['close'] > 0).all()

@pytest.mark.integration
@pytest.mark.skipif(
    "not config.getoption('--run-integration')",
    reason="Only run when --run-integration is given"
)
def test_market_data_cache_integration():
    """실제 환경에서 캐시 기능 테스트"""
    from infra.data.loader import load_market_data
    import time
    
    end_date = pd.Timestamp.now().floor('D')
    
    # 첫 번째 로드 - 캐시 생성
    start_time = time.time()
    df1 = load_market_data('KOR_ETF_CORE', end_date)
    first_load_time = time.time() - start_time
    
    # 두 번째 로드 - 캐시 사용
    start_time = time.time()
    df2 = load_market_data('KOR_ETF_CORE', end_date)
    second_load_time = time.time() - start_time
    
    # 검증
    assert df1.equals(df2), "캐시된 데이터가 일치해야 함"
    assert second_load_time < first_load_time, "캐시된 데이터 로드가 더 빨라야 함"

def pytest_addoption(parser):
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="run integration tests"
    )