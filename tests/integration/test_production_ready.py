# -*- coding: utf-8 -*-
"""
tests/integration/test_production_ready.py
실전 운영 준비 통합 테스트
"""
import pytest
from pathlib import Path
import tempfile
import shutil

from infra.config.loader import Config
from infra.logging.setup import setup_logging, LogContext


class TestProductionReady:
    """실전 운영 준비 테스트"""
    
    @pytest.mark.integration
    def test_config_loading(self):
        """설정 파일 로딩 테스트"""
        config_path = Path('config/config.yaml')
        
        assert config_path.exists(), "설정 파일이 없습니다"
        
        config = Config(config_path)
        
        # 데이터 설정
        data_config = config.get_data_config()
        assert 'cache_dir' in data_config
        assert 'db_path' in data_config
        
        # 백테스트 설정
        backtest_config = config.get_backtest_config()
        assert 'initial_capital' in backtest_config
        assert 'commission_rate' in backtest_config
        
        # 전략 설정
        strategy_config = config.get_strategy_config()
        assert 'signals' in strategy_config
        assert 'risk' in strategy_config
        
        print("Config loading test: PASSED")
    
    @pytest.mark.integration
    def test_logging_setup(self):
        """로깅 설정 테스트"""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / 'logs'
            
            logger = setup_logging(
                name='test_logger',
                log_dir=log_dir,
                console=False,
                file=True
            )
            
            # 로그 기록
            logger.info("테스트 로그 메시지")
            logger.warning("경고 메시지")
            logger.error("오류 메시지")
            
            # 핸들러 닫기
            for handler in logger.handlers[:]:
                handler.close()
                logger.removeHandler(handler)
            
            # 로그 파일 확인
            log_files = list(log_dir.glob('*.log'))
            assert len(log_files) > 0, "로그 파일이 생성되지 않았습니다"
            
            # 로그 내용 확인
            with open(log_files[0], 'r', encoding='utf-8') as f:
                content = f.read()
                assert '테스트 로그 메시지' in content
                assert '경고 메시지' in content
                assert '오류 메시지' in content
        
        print("Logging setup test: PASSED")
    
    @pytest.mark.integration
    def test_log_context(self):
        """로그 컨텍스트 테스트"""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / 'logs'
            
            logger = setup_logging(
                name='test_context',
                log_dir=log_dir,
                console=False,
                file=True
            )
            
            # 컨텍스트 사용
            with LogContext(logger, "작업 A"):
                logger.info("작업 진행 중...")
            
            # 핸들러 닫기
            for handler in logger.handlers[:]:
                handler.close()
                logger.removeHandler(handler)
            
            # 로그 파일 확인
            log_files = list(log_dir.glob('*.log'))
            with open(log_files[0], 'r', encoding='utf-8') as f:
                content = f.read()
                assert '작업 A 시작' in content
                assert '작업 A 완료' in content
        
        print("Log context test: PASSED")
    
    @pytest.mark.integration
    def test_cli_help(self):
        """CLI 도움말 테스트"""
        import subprocess
        
        result = subprocess.run(
            ['python', 'pc/cli.py', '--help'],
            capture_output=True,
            text=True,
            cwd=Path.cwd()
        )
        
        assert result.returncode == 0
        assert 'update' in result.stdout
        assert 'backtest' in result.stdout
        assert 'scan' in result.stdout
        
        print("CLI help test: PASSED")
    
    @pytest.mark.integration
    def test_directory_structure(self):
        """디렉토리 구조 테스트"""
        required_dirs = [
            'core',
            'core/data',
            'core/strategy',
            'core/risk',
            'core/engine',
            'extensions',
            'extensions/backtest',
            'infra',
            'infra/data',
            'infra/logging',
            'infra/config',
            'pc',
            'tests',
            'tests/integration',
            'config'
        ]
        
        for dir_path in required_dirs:
            assert Path(dir_path).exists(), f"디렉토리가 없습니다: {dir_path}"
        
        print("Directory structure test: PASSED")
    
    @pytest.mark.integration
    def test_required_files(self):
        """필수 파일 존재 테스트"""
        required_files = [
            'config/config.yaml',
            'pc/cli.py',
            'core/indicators.py',
            'core/strategy/signals.py',
            'core/risk/manager.py',
            'core/engine/backtest.py',
            'extensions/backtest/runner.py',
            'extensions/backtest/report.py',
            'infra/config/loader.py',
            'infra/logging/setup.py'
        ]
        
        for file_path in required_files:
            assert Path(file_path).exists(), f"파일이 없습니다: {file_path}"
        
        print("Required files test: PASSED")
    
    @pytest.mark.integration
    def test_config_values(self):
        """설정 값 검증 테스트"""
        config = Config(Path('config/config.yaml'))
        
        # 백테스트 설정 검증
        initial_capital = config.get('backtest', 'initial_capital')
        assert initial_capital > 0
        assert isinstance(initial_capital, int)
        
        commission_rate = config.get('backtest', 'commission_rate')
        assert 0 < commission_rate < 0.01
        
        # 리스크 설정 검증
        position_cap = config.get('strategy', 'risk', 'position_cap')
        assert 0 < position_cap <= 1.0
        
        max_drawdown = config.get('strategy', 'risk', 'max_drawdown_threshold')
        assert max_drawdown < 0
        
        print("Config values test: PASSED")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])
