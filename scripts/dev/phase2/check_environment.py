#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Phase 2 재테스트 - 1단계: 환경 확인
예상 시간: 5분
"""
import sys
import os
from pathlib import Path
import importlib.util

# 프로젝트 루트
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

# 로거 생성
from scripts.phase2.utils.logger import create_logger
logger = create_logger("1_check_environment", PROJECT_ROOT)

logger.info("Phase 2 재테스트 - 1단계: 환경 확인")
logger.info("예상 시간: 5분")

# 1. Python 버전 확인
logger.section("1. Python 환경")
logger.info(f"Python 버전: {sys.version}")
logger.info(f"Python 경로: {sys.executable}")

# 2. 필수 패키지 확인
logger.section("2. 필수 패키지 확인")

required_packages = {
    'pandas': '2.0.0',
    'numpy': '1.24.0',
    'optuna': '3.0.0',
    'pykrx': '1.0.0',
    'FinanceDataReader': '0.9.0',
    'yfinance': '0.2.0',
    'pyarrow': '10.0.0',
    'tqdm': '4.60.0',
    'matplotlib': '3.5.0',
    'seaborn': '0.12.0'
}

missing_packages = []
installed_packages = {}

for package, min_version in required_packages.items():
    try:
        if package == 'FinanceDataReader':
            import FinanceDataReader as fdr
            version = fdr.__version__ if hasattr(fdr, '__version__') else 'unknown'
        else:
            mod = importlib.import_module(package)
            version = mod.__version__ if hasattr(mod, '__version__') else 'unknown'
        
        installed_packages[package] = version
        logger.success(f"{package:25s} {version}")
    except ImportError:
        missing_packages.append(package)
        logger.fail(f"{package:25s} (미설치)")

if missing_packages:
    logger.warn("누락된 패키지:")
    logger.info(f"   pip install {' '.join(missing_packages)}")

# 3. 디스크 공간 확인
logger.section("3. 디스크 공간 확인")

import shutil
total, used, free = shutil.disk_usage(PROJECT_ROOT)

logger.info(f"전체: {total // (2**30):,} GB")
logger.info(f"사용: {used // (2**30):,} GB")
logger.info(f"여유: {free // (2**30):,} GB")

if free < 5 * (2**30):  # 5GB
    logger.warn("디스크 공간이 부족합니다 (최소 5GB 필요)")
else:
    logger.success("디스크 공간 충분")

# 4. 디렉토리 구조 확인
logger.section("4. 디렉토리 구조 확인")

required_dirs = [
    'data/cache/ohlcv',
    'data/universe',
    'backtests/phase2_retest',
    'scripts/phase2',
    'logs'
]

for dir_path in required_dirs:
    full_path = PROJECT_ROOT / dir_path
    if full_path.exists():
        logger.success(dir_path)
    else:
        logger.warn(f"{dir_path} (생성 필요)")
        full_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"   → 생성 완료")

# 5. 기존 데이터 확인
logger.section("5. 기존 캐시 데이터 확인")

cache_dir = PROJECT_ROOT / 'data' / 'cache' / 'ohlcv'
parquet_files = list(cache_dir.glob('*.parquet'))

# 날짜 파일 제외
stock_files = [f for f in parquet_files if not f.stem.isdigit() or len(f.stem) != 8]

logger.info(f"캐시된 종목 수: {len(stock_files)}개")

if stock_files:
    logger.info(f"예시 종목:")
    for f in stock_files[:5]:
        size_kb = f.stat().st_size / 1024
        logger.info(f"  - {f.name:20s} ({size_kb:6.1f} KB)")

# 6. 기존 백테스트 결과 확인
logger.section("6. 기존 백테스트 결과 확인")

backtest_dir = PROJECT_ROOT / 'backtests'
if backtest_dir.exists():
    csv_files = list(backtest_dir.rglob('*.csv'))
    json_files = list(backtest_dir.rglob('*.json'))
    
    logger.info(f"CSV 파일: {len(csv_files)}개")
    logger.info(f"JSON 파일: {len(json_files)}개")
    
    # best_params.json 확인
    best_params = PROJECT_ROOT / 'best_params.json'
    if best_params.exists():
        logger.success("best_params.json 존재")
        import json
        with open(best_params, 'r') as f:
            params = json.load(f)
        logger.info(f"   현재 파라미터:")
        for key, value in params.items():
            logger.info(f"     - {key}: {value}")
    else:
        logger.warn("best_params.json 없음 (최적화 필요)")
else:
    logger.warn("backtests 디렉토리 없음")

# 7. 요약
logger.section("환경 확인 요약")

issues = []

if missing_packages:
    issues.append(f"누락된 패키지: {len(missing_packages)}개")

if free < 5 * (2**30):
    issues.append("디스크 공간 부족")

if len(stock_files) < 50:
    issues.append(f"캐시된 종목 부족 ({len(stock_files)}개 < 50개)")

if issues:
    logger.warn("해결 필요한 항목:")
    for issue in issues:
        logger.info(f"   - {issue}")
    logger.info("")
    logger.info("다음 단계로 진행하기 전에 위 항목을 해결하세요.")
else:
    logger.success("모든 환경 준비 완료!")
    logger.info("")
    logger.info("다음 단계: 데이터 준비")
    logger.info("  python scripts/phase2/prepare_data.py")

logger.finish()
logger.info(f"\n로그 파일: {logger.log_file}")
