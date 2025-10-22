#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scanner.py 필터 로직 테스트

실행: pytest tests/test_scanner_filters.py -v
"""

import pytest
import pandas as pd
import numpy as np
from scanner import build_candidate_table, load_config_yaml


@pytest.fixture
def sample_config():
    """테스트용 설정"""
    return {
        "universe": {
            "type": "ETF",
            "market": "KS",
            "exclude_keywords": ["레버리지"],
            "min_avg_turnover": 0  # 테스트에서는 유동성 필터 비활성화
        },
        "scanner": {
            "adx_window": 14,
            "mfi_window": 14,
            "vol_z_window": 20,
            "thresholds": {
                "daily_jump_pct": 2.0,
                "adx_min": 20.0,
                "mfi_min": 50.0,
                "mfi_max": 80.0,
                "volz_min": 1.0
            }
        }
    }


@pytest.fixture
def sample_price_data():
    """테스트용 가격 데이터 생성"""
    dates = pd.date_range("2024-01-01", periods=250, freq="D")
    
    # 종목 A: 강한 상승 추세 (조건 충족)
    code_a = pd.DataFrame({
        "date": dates,
        "code": "A",
        "open": np.linspace(100, 150, 250),
        "high": np.linspace(102, 152, 250),
        "low": np.linspace(98, 148, 250),
        "close": np.linspace(100, 150, 250),
        "volume": [10000] * 250
    })
    
    # 종목 B: 약한 추세 (조건 불충족)
    code_b = pd.DataFrame({
        "date": dates,
        "code": "B",
        "open": [100] * 250,
        "high": [102] * 250,
        "low": [98] * 250,
        "close": [100] * 250,
        "volume": [5000] * 250
    })
    
    # 종목 C: 하락 추세 (조건 불충족)
    code_c = pd.DataFrame({
        "date": dates,
        "code": "C",
        "open": np.linspace(150, 100, 250),
        "high": np.linspace(152, 102, 250),
        "low": np.linspace(148, 98, 250),
        "close": np.linspace(150, 100, 250),
        "volume": [8000] * 250
    })
    
    return pd.concat([code_a, code_b, code_c], ignore_index=True)


class TestCandidateFiltering:
    """후보 필터링 테스트"""
    
    def test_build_candidate_table_structure(self, sample_price_data, sample_config):
        """후보 테이블 생성 및 컬럼 구조 검증"""
        asof = pd.Timestamp("2024-09-07")
        result = build_candidate_table(sample_price_data, asof, sample_config)
        
        # 필수 컬럼 존재 확인
        required_cols = [
            "code", "close", "ret1", "ret20", "ret60",
            "sma20", "sma50", "sma200", "slope20",
            "adx", "mfi", "volz",
            "trend_ok", "jump_ok", "strength_ok", "all_ok"
        ]
        for col in required_cols:
            assert col in result.columns, f"컬럼 누락: {col}"
    
    def test_trend_filter(self, sample_price_data, sample_config):
        """추세 필터 검증 (close > SMA50 & SMA200)"""
        asof = pd.Timestamp("2024-09-07")
        result = build_candidate_table(sample_price_data, asof, sample_config)
        
        # 종목 A(상승)는 trend_ok=True
        a_row = result[result["code"] == "A"]
        if not a_row.empty:
            assert a_row.iloc[0]["trend_ok"] == True
        
        # 종목 C(하락)는 trend_ok=False
        c_row = result[result["code"] == "C"]
        if not c_row.empty:
            assert c_row.iloc[0]["trend_ok"] == False
    
    def test_jump_filter_threshold(self, sample_config):
        """급등 필터 임계값 검증"""
        # 1일 수익률 3% 상승
        dates = pd.date_range("2024-09-01", periods=5)
        data = pd.DataFrame({
            "date": dates,
            "code": "TEST",
            "open": [100, 101, 102, 103, 106],
            "high": [101, 102, 103, 104, 107],
            "low": [99, 100, 101, 102, 105],
            "close": [100, 101, 102, 103, 106],  # 마지막 날 +2.9%
            "volume": [1000] * 5
        })
        
        asof = pd.Timestamp("2024-09-05")
        result = build_candidate_table(data, asof, sample_config)
        
        if not result.empty:
            # 2% 임계값이므로 2.9% 상승은 통과
            assert result.iloc[0]["jump_ok"] == True
    
    def test_empty_data_handling(self, sample_config):
        """빈 데이터 처리"""
        empty_df = pd.DataFrame(columns=["date", "code", "open", "high", "low", "close", "volume"])
        asof = pd.Timestamp("2024-09-07")
        result = build_candidate_table(empty_df, asof, sample_config)
        
        assert result.empty


class TestConfigLoading:
    """설정 파일 로딩 테스트"""
    
    def test_config_priority(self, tmp_path):
        """설정 파일 우선순위 검증"""
        # config/config.yaml 생성
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        config_file = config_dir / "config.yaml"
        config_file.write_text("test: value1")
        
        # 현재 디렉토리에 config.yaml 생성
        root_config = tmp_path / "config.yaml"
        root_config.write_text("test: value2")
        
        # config/config.yaml이 우선
        import os
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            cfg = load_config_yaml()
            assert cfg["test"] == "value1"
        finally:
            os.chdir(old_cwd)
    
    def test_config_not_found(self):
        """설정 파일 없을 때 예외 발생"""
        with pytest.raises(FileNotFoundError):
            load_config_yaml("nonexistent.yaml")


class TestThresholdAdjustment:
    """임계값 조정 효과 테스트"""
    
    def test_relaxed_thresholds(self, sample_price_data):
        """완화된 임계값으로 더 많은 후보 생성"""
        asof = pd.Timestamp("2024-09-07")
        
        # 엄격한 설정
        strict_cfg = {
            "universe": {"min_avg_turnover": 0},
            "scanner": {
                "adx_window": 14, "mfi_window": 14, "vol_z_window": 20,
                "thresholds": {
                    "daily_jump_pct": 3.0,  # 높음
                    "adx_min": 30.0,        # 높음
                    "mfi_min": 60.0,
                    "mfi_max": 70.0,
                    "volz_min": 2.0
                }
            }
        }
        
        # 완화된 설정
        relaxed_cfg = {
            "universe": {"min_avg_turnover": 0},
            "scanner": {
                "adx_window": 14, "mfi_window": 14, "vol_z_window": 20,
                "thresholds": {
                    "daily_jump_pct": 0.5,  # 낮음
                    "adx_min": 10.0,        # 낮음
                    "mfi_min": 30.0,
                    "mfi_max": 90.0,
                    "volz_min": 0.0
                }
            }
        }
        
        strict_result = build_candidate_table(sample_price_data, asof, strict_cfg)
        relaxed_result = build_candidate_table(sample_price_data, asof, relaxed_cfg)
        
        # 완화된 설정에서 더 많은 후보 (또는 같은 수)
        strict_pass = strict_result["all_ok"].sum() if not strict_result.empty else 0
        relaxed_pass = relaxed_result["all_ok"].sum() if not relaxed_result.empty else 0
        
        assert relaxed_pass >= strict_pass


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
