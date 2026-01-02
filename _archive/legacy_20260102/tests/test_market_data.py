import pytest
import numpy as np
import pandas as pd
from pathlib import Path
from infra.data.loader import load_market_data

@pytest.fixture(scope="session")
def sample_etf_data():
    """테스트용 ETF 데이터 - 세션 레벨 캐싱 (최소 샘플)"""
    return [
        {'code': '069500', 'name': 'KODEX 200'},
        {'code': '114800', 'name': 'KODEX 인버스'},
    ]

@pytest.fixture
def mock_pykrx(monkeypatch, sample_etf_data):
    """pykrx 모킹 (캐시된 응답 사용)"""
    class MockStock:
        _cached_data = {}  # 클래스 레벨 캐시
        
        def get_etf_ticker_list(self):
            return [etf['code'] for etf in sample_etf_data]
        
        def get_etf_ticker_name(self, ticker):
            for etf in sample_etf_data:
                if etf['code'] == ticker:
                    return etf['name']
            return ''
        
        def get_etf_ohlcv_by_date(self, fromdate, todate, ticker):
            # 캐시 키 생성
            cache_key = f"{ticker}_{fromdate}_{todate}"
            
            # 캐시된 데이터가 있으면 반환
            if cache_key in self._cached_data:
                return self._cached_data[cache_key]
            
            # 최소한의 테스트 데이터 생성 (1-2일치)
            dates = pd.date_range(fromdate, todate, freq='B', periods=2)
            data = {
                '종가': [10000, 10100],
                '거래량': [100000, 110000],
                '거래대금': [1000000000, 1100000000]
            }
            df = pd.DataFrame(data, index=dates)
            
            # 캐시에 저장
            self._cached_data[cache_key] = df
            return df
    
    monkeypatch.setattr("pykrx.stock", MockStock())

@pytest.mark.timeout(2)  # 2초 타임아웃 설정
def test_load_market_data(mock_pykrx, tmp_path):
    """마켓 데이터 로드 테스트"""
    # 임시 캐시 디렉토리 설정
    cache_dir = tmp_path / "data/cache/ohlcv"
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    end_date = pd.Timestamp('2023-10-26')
    start_date = end_date - pd.Timedelta(days=1)  # 1일 데이터만 테스트
    
    df = load_market_data('KOR_ETF_CORE', end_date, start_date)
    
    # 기본 검증
    assert isinstance(df, pd.DataFrame)
    assert len(df) > 0
    
    # 인덱스 구조 검증
    assert isinstance(df.index, pd.MultiIndex)
    assert df.index.names == ['code', 'date']
    
    # 데이터 타입 검증
    assert 'close' in df.columns
    assert df['close'].dtype == float
    
    # 데이터 정합성 검증
    assert df['close'].notna().all()  # 종가에 결측치가 없어야 함
    assert (df['close'] > 0).all()    # 종가는 양수여야 함
    
    # 필터링 검증 (인버스 ETF 제외)
    codes = df.index.get_level_values('code').unique()
    assert '114800' not in codes  # 인버스 ETF는 제외되어야 함

def test_market_data_cache(mock_pykrx, tmp_path):
    """캐시 기능 테스트"""
    import shutil
    
    # 임시 캐시 디렉토리 설정
    cache_dir = tmp_path / "data/cache/ohlcv"
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    end_date = pd.Timestamp('2023-10-26')
    cache_file = cache_dir / f"{end_date:%Y%m%d}.parquet"
    
    # 첫 번째 로드 - 캐시 생성
    df1 = load_market_data('KOR_ETF_CORE', end_date)
    df1.to_parquet(cache_file)  # 캐시 파일 생성
    
    # 두 번째 로드 - 캐시에서 읽기
    df2 = load_market_data('KOR_ETF_CORE', end_date)
    assert df1.equals(df2)

if __name__ == '__main__':
    pytest.main([__file__, '-v'])