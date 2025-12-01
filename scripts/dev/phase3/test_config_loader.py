# -*- coding: utf-8 -*-
"""
Phase 4: Config 연결 테스트

목적:
- Config 로드 검증
- 팩토리 함수 테스트
- 하위 호환성 확인
"""
import sys
from pathlib import Path

# 프로젝트 루트
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.dev.phase2.utils.logger import create_logger
logger = create_logger("phase4_config_test", PROJECT_ROOT)

logger.info("=" * 70)
logger.info("Phase 4: Config 연결 테스트")
logger.info("=" * 70)

# 1. Config 로드 테스트
logger.section("1. Config 로드 테스트")

from core.engine.config_loader import (
    load_backtest_config,
    create_maps_adapter_from_config,
    get_split_config,
    get_regime_scaling_config,
    quick_backtest_config
)

# 한국 설정 로드
config_kr = load_backtest_config(country='korea')
logger.success("한국 설정 로드 완료")
logger.info(f"  초기 자본: {config_kr['initial_capital']:,}원")
logger.info(f"  최대 포지션: {config_kr['max_positions']}개")
logger.info(f"  수수료율: {config_kr['commission_rate']*100:.3f}%")
logger.info(f"  슬리피지: {config_kr['slippage_rate']*100:.2f}%")
logger.info(f"  세율 (주식): {config_kr['tax_rates'].get('stock', 0)*100:.2f}%")
logger.info(f"  세율 (ETF): {config_kr['tax_rates'].get('etf', 0)*100:.2f}%")

# 2. 레짐 스케일링 설정
logger.section("2. 레짐 스케일링 설정")

regime_config = get_regime_scaling_config()
logger.info(f"  활성화: {regime_config.get('enabled', False)}")
logger.info(f"  포지션 비율:")
for regime, ratio in regime_config.get('position_ratios', {}).items():
    logger.info(f"    - {regime}: {ratio*100:.0f}%")
logger.info(f"  기존 포지션 축소: {regime_config.get('reduce_existing_positions', False)}")

# 3. 분할 설정
logger.section("3. 분할 설정")

split_config = get_split_config()
logger.info(f"  Train: {split_config.get('train_ratio', 0)*100:.0f}%")
logger.info(f"  Val: {split_config.get('val_ratio', 0)*100:.0f}%")
logger.info(f"  Test: {split_config.get('test_ratio', 0)*100:.0f}%")

# 4. 어댑터 생성 테스트
logger.section("4. 어댑터 생성 테스트")

# Config에서 어댑터 생성
adapter = create_maps_adapter_from_config(
    instrument_type='etf',
    country='korea'
)
logger.success("어댑터 생성 완료 (Config 기반)")
logger.info(f"  초기 자본: {adapter.initial_capital:,}원")
logger.info(f"  최대 포지션: {adapter.max_positions}개")
logger.info(f"  방어 시스템: {adapter.enable_defense}")

# 5. 하위 호환성 테스트 (기존 방식)
logger.section("5. 하위 호환성 테스트")

from core.engine.krx_maps_adapter import KRXMAPSAdapter

# 기존 방식 (하드코딩)
adapter_old = KRXMAPSAdapter(
    initial_capital=10_000_000,
    commission_rate=0.00015,
    slippage_rate=0.001,
    max_positions=10,
    country_code='kor',
    instrument_type='etf',
    enable_defense=True
)
logger.success("기존 방식 어댑터 생성 완료")

# 비교
if adapter.initial_capital == adapter_old.initial_capital:
    logger.success("✅ 하위 호환성 유지됨")
else:
    logger.fail("❌ 하위 호환성 문제")

# 6. 빠른 설정 테스트
logger.section("6. 빠른 설정 테스트")

quick_config = quick_backtest_config(
    capital=50_000_000,
    instrument='stock',
    defense=False
)
logger.info(f"  초기 자본: {quick_config['initial_capital']:,}원")
logger.info(f"  상품 유형: {quick_config['instrument_type']}")
logger.info(f"  방어 시스템: {quick_config['enable_defense']}")

# 7. 요약
logger.section("7. 요약")

logger.info("=" * 70)
logger.info("Phase 4: Config 연결 테스트 완료")
logger.info("=" * 70)
logger.info("\n✅ 구현 완료:")
logger.info("  - load_backtest_config(): YAML에서 설정 로드")
logger.info("  - create_maps_adapter_from_config(): Config 기반 어댑터 생성")
logger.info("  - get_split_config(): 분할 설정 조회")
logger.info("  - get_regime_scaling_config(): 레짐 스케일링 설정 조회")
logger.info("  - quick_backtest_config(): 빠른 설정 생성")
logger.info("\n✅ 하위 호환성: 기존 하드코딩 방식도 계속 사용 가능")
logger.info("=" * 70)

logger.finish()
