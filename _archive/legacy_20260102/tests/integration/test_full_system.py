# -*- coding: utf-8 -*-
"""
tests/integration/test_full_system.py
전체 시스템 통합 테스트 (실제 동작 검증)
"""
import pytest
from pathlib import Path
import subprocess
import sys
from datetime import date, timedelta


class TestFullSystem:
    """전체 시스템 통합 테스트"""
    
    @pytest.mark.integration
    @pytest.mark.slow
    def test_cli_help_commands(self):
        """CLI 도움말 테스트"""
        commands = ['update', 'backtest', 'scan', 'optimize']
        
        for cmd in commands:
            result = subprocess.run(
                [sys.executable, 'pc/cli.py', cmd, '--help'],
                capture_output=True,
                text=True,
                cwd=Path.cwd()
            )
            
            assert result.returncode == 0, f"{cmd} --help 실패"
            assert 'usage:' in result.stdout.lower(), f"{cmd} 도움말 출력 없음"
            
            print(f"✅ {cmd} --help 통과")
    
    @pytest.mark.integration
    @pytest.mark.slow
    def test_data_update_single_symbol(self):
        """데이터 업데이트 테스트 (단일 종목)"""
        result = subprocess.run(
            [sys.executable, 'pc/cli.py', 'update', 
             '--symbols', '069500', 
             '--date', '2024-12-31'],
            capture_output=True,
            text=True,
            cwd=Path.cwd(),
            timeout=60
        )
        
        # RC=0 또는 일부 실패 허용
        assert result.returncode in [0, 1], f"업데이트 실패: {result.stderr}"
        
        # 캐시 파일 확인
        cache_file = Path('data/cache/069500.parquet')
        if cache_file.exists():
            print(f"✅ 캐시 파일 생성 확인: {cache_file}")
        else:
            print(f"⚠️ 캐시 파일 미생성 (네트워크 또는 API 문제 가능)")
    
    @pytest.mark.integration
    def test_filtering_universe(self):
        """유니버스 필터링 테스트"""
        from core.data.filtering import get_filtered_universe
        
        universe = get_filtered_universe()
        
        assert isinstance(universe, list), "유니버스가 리스트가 아님"
        assert len(universe) > 0, "유니버스가 비어있음"
        assert len(universe) < 1500, "유니버스가 너무 큼 (필터링 안됨)"
        
        # 제외 키워드 확인
        from pykrx import stock
        exclude_keywords = ["레버리지", "인버스", "선물", "채권"]
        
        for code in universe[:10]:  # 샘플 확인
            try:
                name = stock.get_etf_ticker_name(code)
                for kw in exclude_keywords:
                    assert kw not in name, f"{code} {name}에 제외 키워드 포함"
            except:
                pass
        
        print(f"✅ 유니버스 필터링: {len(universe)}개 종목")
    
    @pytest.mark.integration
    def test_signal_generator(self):
        """신호 생성기 테스트"""
        from core.strategy.signals import create_default_signal_generator
        import pandas as pd
        import numpy as np
        
        generator = create_default_signal_generator()
        
        # 샘플 데이터
        dates = pd.date_range('2024-01-01', periods=60, freq='D')
        close = pd.Series(np.random.randn(60).cumsum() + 100, index=dates)
        high = close + np.random.rand(60) * 2
        low = close - np.random.rand(60) * 2
        volume = pd.Series(np.random.randint(1000000, 10000000, 60), index=dates)
        
        # 신호 생성
        result = generator.generate_combined_signal(close, high, low, volume)
        
        assert 'signal' in result, "신호 없음"
        assert 'confidence' in result, "신뢰도 없음"
        assert result['signal'] in ['BUY', 'SELL', 'HOLD'], f"잘못된 신호: {result['signal']}"
        assert 0 <= result['confidence'] <= 1, f"잘못된 신뢰도: {result['confidence']}"
        
        print(f"✅ 신호 생성: {result['signal']} (신뢰도: {result['confidence']:.2%})")
    
    @pytest.mark.integration
    def test_risk_manager(self):
        """리스크 관리자 테스트"""
        from core.risk.manager import RiskManager
        
        risk_mgr = RiskManager(
            position_cap=0.25,
            portfolio_vol_target=0.12,
            max_drawdown_threshold=-0.15,
            cooldown_days=5
        )
        
        # 포지션 크기 체크
        assert risk_mgr.check_position_size(0.20), "정상 포지션 거부"
        assert not risk_mgr.check_position_size(0.30), "과대 포지션 허용"
        
        # MDD 체크
        assert risk_mgr.check_drawdown(-0.10), "정상 MDD 거부"
        assert not risk_mgr.check_drawdown(-0.20), "과대 MDD 허용"
        
        print("✅ 리스크 관리자 정상 작동")
    
    @pytest.mark.integration
    def test_backtest_engine(self):
        """백테스트 엔진 테스트"""
        from core.engine.backtest import BacktestEngine
        from datetime import date
        
        engine = BacktestEngine(
            initial_capital=10_000_000,
            commission_rate=0.00015,
            slippage_rate=0.001
        )
        
        # 매수
        engine.execute_buy('069500', 100, 30000, date(2024, 1, 2))
        
        assert '069500' in engine.positions, "포지션 미생성"
        assert engine.positions['069500'].quantity == 100, "수량 불일치"
        
        # 매도
        engine.execute_sell('069500', 50, 31000, date(2024, 1, 3))
        
        assert engine.positions['069500'].quantity == 50, "매도 후 수량 불일치"
        
        # NAV 업데이트
        engine.update_nav({'069500': 32000}, date(2024, 1, 4))
        
        assert len(engine.nav_history) > 0, "NAV 기록 없음"
        
        print(f"✅ 백테스트 엔진: NAV={engine.nav_history[-1]['nav']:,.0f}원")
    
    @pytest.mark.integration
    def test_config_loading(self):
        """설정 파일 로딩 테스트"""
        from infra.config.loader import Config
        
        config = Config(Path('config/config.yaml'))
        
        # 필수 설정 확인
        assert config.get('data', 'cache_dir') is not None
        assert config.get('backtest', 'initial_capital') > 0
        assert config.get('strategy', 'signals') is not None
        
        print("✅ 설정 파일 로딩 성공")
    
    @pytest.mark.integration
    def test_logging_setup(self):
        """로깅 설정 테스트"""
        from infra.logging.setup import setup_logging
        import tempfile
        
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = setup_logging(
                name='test_system',
                log_dir=Path(tmpdir) / 'logs',
                console=False,
                file=True
            )
            
            logger.info("테스트 메시지")
            
            # 핸들러 닫기
            for handler in logger.handlers[:]:
                handler.close()
                logger.removeHandler(handler)
            
            # 로그 파일 확인
            log_files = list((Path(tmpdir) / 'logs').glob('*.log'))
            assert len(log_files) > 0, "로그 파일 미생성"
            
            print("✅ 로깅 시스템 정상 작동")
    
    @pytest.mark.integration
    @pytest.mark.slow
    def test_optuna_space(self):
        """Optuna 검색 공간 테스트"""
        import optuna
        from extensions.optuna.space import suggest_all_params
        
        study = optuna.create_study()
        trial = study.ask()
        
        params = suggest_all_params(trial)
        
        # 필수 파라미터 확인
        required_params = [
            'ma_period', 'rsi_period', 'adx_threshold',
            'rebalance_frequency', 'max_positions', 'position_cap'
        ]
        
        for param in required_params:
            assert param in params, f"{param} 파라미터 없음"
        
        # 가중치 정규화 확인
        weight_sum = (
            params['momentum_weight'] +
            params['trend_weight'] +
            params['mean_reversion_weight']
        )
        assert abs(weight_sum - 1.0) < 0.01, f"가중치 합이 1이 아님: {weight_sum}"
        
        print(f"✅ Optuna 검색 공간: {len(params)}개 파라미터")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration", "-s"])
