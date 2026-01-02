# -*- coding: utf-8 -*-
"""
tests/integration/test_data_pipeline.py
데이터 파이프라인 통합 테스트
"""
import pytest
import pandas as pd
from datetime import date, timedelta
from pathlib import Path
import tempfile
import shutil

from infra.data.updater import DataUpdater
from core.data.filtering import ETFFilter


class TestDataPipeline:
    """데이터 파이프라인 통합 테스트"""
    
    @pytest.fixture
    def temp_cache_dir(self):
        """임시 캐시 디렉토리"""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def updater(self, temp_cache_dir):
        """데이터 업데이터"""
        return DataUpdater(cache_dir=temp_cache_dir)
    
    @pytest.fixture
    def etf_filter(self):
        """ETF 필터"""
        return ETFFilter(
            min_liquidity=1e8,
            min_price=1000
        )
    
    @pytest.mark.integration
    def test_update_single_symbol(self, updater):
        """단일 종목 업데이트 테스트"""
        symbol = "069500"
        end_date = date.today()
        
        success = updater.update_symbol(symbol, end_date)
        
        assert success
        cache_path = updater._get_cache_path(symbol)
        assert cache_path.exists()
        
        df = updater._read_cache(symbol)
        assert df is not None
        assert not df.empty
        assert 'close' in df.columns
        
        print(f"Update success: {symbol} ({len(df)} rows)")
    
    @pytest.mark.integration
    def test_full_pipeline(self, updater, etf_filter):
        """전체 파이프라인 테스트"""
        symbols = ["069500", "091160"]
        end_date = date.today()
        
        update_results = updater.update_universe(symbols, end_date)
        assert sum(update_results.values()) > 0
        
        etfs = [
            {'code': symbol, 'name': f'ETF_{symbol}', 'cat': 'TEST'}
            for symbol in symbols
            if update_results.get(symbol, False)
        ]
        
        dfs = []
        for symbol in symbols:
            df = updater._read_cache(symbol)
            if df is not None and not df.empty:
                df = df.copy()
                df['code'] = symbol
                df = df.reset_index()
                if 'index' in df.columns:
                    df = df.rename(columns={'index': 'date'})
                dfs.append(df)
        
        assert len(dfs) > 0
        
        price_data = pd.concat(dfs)
        if 'date' in price_data.columns:
            price_data.set_index(['code', 'date'], inplace=True)
        else:
            price_data['date'] = price_data.index
            price_data.set_index(['code', 'date'], inplace=True)
        
        filtered = etf_filter.apply_all_filters(
            etfs,
            price_data,
            lookback_days=20,
            max_per_category=2
        )
        
        assert len(filtered) > 0
        
        print(f"Pipeline success: {len(filtered)} ETFs")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])
