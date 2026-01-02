"""Unit tests for market data functionality"""
import pytest
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta

@pytest.fixture(scope="session")
def mock_etf_data():
    """테스트용 ETF 데이터 (단위 테스트용)"""
    return [
        {'code': '069500', 'name': 'KODEX 200'},
        {'code': '114800', 'name': 'KODEX 인버스'}
    ]

@pytest.fixture
def mock_krx_client(monkeypatch, mock_etf_data):
    """Mock KRX 클라이언트 (단위 테스트용)"""
    class MockStock:
        _cached_data = {}

        def get_etf_ticker_list(self):
            return [etf['code'] for etf in mock_etf_data]
        
        def get_etf_ticker_name(self, ticker):
            for etf in mock_etf_data:
                if etf['code'] == ticker:
                    return etf['name']
            return ''
        
        def get_etf_ohlcv_by_date(self, fromdate, todate, ticker):
            start = pd.to_datetime(fromdate)
            end = pd.to_datetime(todate)
            
            dates = pd.date_range(start=start, end=end, freq='B')
            data = pd.DataFrame({
                'date': dates,
                'close': pd.Series([10000.0 + i for i in range(len(dates))], dtype=float),
                'open': pd.Series([10000.0 + i for i in range(len(dates))], dtype=float),
                'high': pd.Series([10100.0 + i for i in range(len(dates))], dtype=float),
                'low': pd.Series([9900.0 + i for i in range(len(dates))], dtype=float),
                'volume': pd.Series([100000 + i for i in range(len(dates))], dtype=float),
                'value': pd.Series([1000000000 + i for i in range(len(dates))], dtype=float),
                'market_cap': pd.Series([100000000000 + i for i in range(len(dates))], dtype=float)
            })
            
            # pykrx의 실제 동작과 동일하게 날짜를 인덱스로 설정
            df = data.set_index('date')
            
            # 모든 숫자형 컬럼을 float으로 변환
            for col in df.columns:
                df[col] = df[col].astype(float)
                
            return df

    # Mock 객체 설정
    monkeypatch.setattr("pykrx.stock", MockStock())

    monkeypatch.setattr("pykrx.stock", MockStock())

@pytest.mark.unit
@pytest.mark.timeout(2)
def test_load_market_data_basic(mock_krx_client, tmp_path):
    """기본 마켓 데이터 로드 테스트"""
    from infra.data.loader import load_market_data
    
    cache_dir = tmp_path / "data/cache/ohlcv"
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    end_date = pd.Timestamp('2023-10-26')
    start_date = end_date - pd.Timedelta(days=1)
    
    df = load_market_data('KOR_ETF_CORE', end_date, start_date)
    
    # 기본 검증
    assert isinstance(df, pd.DataFrame), "반환값이 DataFrame이어야 함"
    assert len(df) > 0, "DataFrame이 비어있지 않아야 함"
    
    # 인덱스 구조 검증
    assert isinstance(df.index, pd.MultiIndex), "MultiIndex를 사용해야 함"
    assert df.index.names == ['code', 'date'], "인덱스 이름이 ['code', 'date']여야 함"
    
    # 데이터 구조 검증
    assert 'close' in df.columns, "'close' 컬럼이 존재해야 함"
    assert pd.api.types.is_numeric_dtype(df['close']), "종가는 숫자 타입이어야 함"
    assert (df['close'] > 0).all(), "종가는 양수여야 함"

@pytest.mark.unit
@pytest.mark.timeout(2)
def test_market_data_filtering(mock_krx_client, tmp_path):
    """ETF 필터링 테스트"""
    from infra.data.loader import load_market_data
    
    cache_dir = tmp_path / "data/cache/ohlcv"
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    end_date = pd.Timestamp('2023-10-26')
    df = load_market_data('KOR_ETF_CORE', end_date)
    
    # 필터링 검증
    codes = df.index.get_level_values('code').unique()
    assert '114800' not in codes, "인버스 ETF는 제외되어야 함"
    assert '069500' in codes, "일반 ETF는 포함되어야 함"

@pytest.mark.unit
@pytest.mark.timeout(2)
def test_market_data_cache(mock_krx_client, tmp_path):
    """캐시 기능 테스트"""
    from infra.data.loader import load_market_data
    import time
    
    # 임시 캐시 디렉토리 설정
    cache_dir = tmp_path / "data/cache/ohlcv"
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    end_date = pd.Timestamp('2023-10-26')
    cache_file = cache_dir / f"{end_date:%Y%m%d}.parquet"
    
    # 첫 번째 로드 - 캐시 생성
    start_time = time.time()
    df1 = load_market_data('KOR_ETF_CORE', end_date, cache_dir=cache_dir)
    first_load_time = time.time() - start_time
    
    # 캐시 파일 생성 확인
    assert cache_file.exists(), "캐시 파일이 생성되어야 함"
    
    # 두 번째 로드 - 캐시 사용
    start_time = time.time()
    df2 = load_market_data('KOR_ETF_CORE', end_date, cache_dir=cache_dir)
    second_load_time = time.time() - start_time
    
    # 검증
    assert df1.equals(df2), "캐시된 데이터가 일치해야 함"
    assert second_load_time < first_load_time, "캐시된 데이터 로드가 더 빨라야 함"