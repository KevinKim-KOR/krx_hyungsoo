#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Phase 0: 검증 프레임워크 테스트
Train/Test 분리 백테스트 실행

목적:
- 모든 변경사항을 Train/Test 양쪽에서 검증
- 과적합 여부 확인
- 실전 성과 예측

사용법:
    python scripts/dev/phase3/run_train_test_split.py
"""
import sys
from pathlib import Path
from datetime import date
import pandas as pd
import json

# 프로젝트 루트
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 로거 생성
from scripts.dev.phase2.utils.logger import create_logger
logger = create_logger("phase0_train_test", PROJECT_ROOT)

logger.info("=" * 70)
logger.info("Phase 0: 검증 프레임워크 - Train/Test 분리 백테스트")
logger.info("=" * 70)
logger.info("목적: 모든 변경사항을 Train/Test 양쪽에서 검증")

# 1. 유니버스 로드
logger.section("1. 유니버스 로드")

universe_file = PROJECT_ROOT / 'data' / 'universe' / 'etf_universe.csv'
universe_df = pd.read_csv(universe_file, encoding='utf-8-sig')

logger.info(f"유니버스 크기: {len(universe_df)}개")
tickers = universe_df['ticker'].tolist()

# KODEX 200 추가 (KOSPI 대표)
if '069500' not in tickers:
    tickers.append('069500')
    logger.info("KODEX 200 (069500) 추가 - KOSPI 대표")

logger.info(f"종목 코드: {tickers[:10]}... (총 {len(tickers)}개)")

# 2. 가격 데이터 로드
logger.section("2. 가격 데이터 로드")

start_date = date(2022, 1, 1)
end_date = date.today()

logger.info(f"기간: {start_date} ~ {end_date}")
logger.info("데이터 로딩 중...")

from infra.data.loader import load_price_data

try:
    price_data = load_price_data(tickers, start_date, end_date)
    
    logger.success("데이터 로드 완료")
    logger.info(f"   Shape: {price_data.shape}")
    logger.info(f"   Index: {price_data.index.names}")
    logger.info(f"   Columns: {price_data.columns.tolist()}")
    
    # KODEX 200 데이터 확인
    if '069500' in price_data.index.get_level_values(0):
        kodex_data = price_data.xs('069500', level=0)
        logger.info(f"   KODEX 200 데이터: {len(kodex_data)}일")
    else:
        logger.warning("   KODEX 200 데이터 없음!")
    
    # 데이터 품질 확인
    if isinstance(price_data.index, pd.MultiIndex):
        ticker_counts = price_data.groupby(level=0).size()
        logger.info(f"\n종목별 데이터 수:")
        logger.info(f"  평균: {ticker_counts.mean():.0f}일")
        logger.info(f"  최소: {ticker_counts.min():.0f}일")
        logger.info(f"  최대: {ticker_counts.max():.0f}일")

except Exception as e:
    logger.fail(f"데이터 로드 실패: {e}")
    import traceback
    traceback.print_exc()
    logger.finish()
    sys.exit(1)

# 3. 전략 설정
logger.section("3. 전략 설정")

from extensions.strategy.signal_generator import SignalGenerator

# best_params.json 확인
best_params_file = PROJECT_ROOT / 'best_params.json'
if best_params_file.exists():
    with open(best_params_file, 'r') as f:
        params = json.load(f)
    logger.info("기존 최적 파라미터 사용:")
else:
    params = {
        'ma_period': 60,
        'rsi_period': 14,
        'rsi_overbought': 70,
        'maps_buy_threshold': 0.0,
        'maps_sell_threshold': -5.0
    }
    logger.info("기본 파라미터 사용:")

for key, value in params.items():
    logger.info(f"  {key}: {value}")

# 전략 생성
strategy = SignalGenerator(
    ma_period=params['ma_period'],
    rsi_period=params.get('rsi_period', 14),
    rsi_overbought=params.get('rsi_overbought', 70),
    maps_buy_threshold=params['maps_buy_threshold'],
    maps_sell_threshold=params['maps_sell_threshold']
)

logger.success("전략 초기화 완료")

# 4. Train/Test 분리 백테스트
logger.section("4. Train/Test 분리 백테스트")

from core.engine.krx_maps_adapter import KRXMAPSAdapter
from extensions.backtest.train_test_split import (
    simple_train_test_split,
    run_backtest_with_split,
    compare_train_test_results,
    validate_split_quality,
    get_split_periods
)

# 백테스트 설정
backtest_config = {
    'initial_capital': 10_000_000,
    'commission_rate': 0.00015,
    'slippage_rate': 0.001,
    'max_positions': 10,
    'country_code': 'kor',
    'instrument_type': 'etf',  # ETF: 거래세 면제
    'enable_defense': True,  # 방어 시스템 활성화 (레짐 스케일링 포함)
}

# 4.1 기간 분리 확인
logger.info("\n4.1 기간 분리 확인")
logger.info("-" * 40)

periods = get_split_periods(start_date, end_date, train_ratio=0.7)
logger.info(f"  {periods.train}")
logger.info(f"  {periods.test}")

# 4.2 분할 품질 검증
logger.info("\n4.2 분할 품질 검증")
logger.info("-" * 40)

validation = validate_split_quality(
    price_data=price_data,
    train_period=periods.train,
    test_period=periods.test,
    market_index='069500'
)

if validation.get('train'):
    logger.info(f"  Train 시장 수익률: {validation['train'].get('return', 0):.2f}%")
    logger.info(f"  Train 시장 변동성: {validation['train'].get('volatility', 0):.2f}%")

if validation.get('test'):
    logger.info(f"  Test 시장 수익률: {validation['test'].get('return', 0):.2f}%")
    logger.info(f"  Test 시장 변동성: {validation['test'].get('volatility', 0):.2f}%")

if validation.get('warnings'):
    for warning in validation['warnings']:
        logger.warning(f"  {warning}")

# 4.3 어댑터 생성
logger.info("\n4.3 어댑터 생성")
logger.info("-" * 40)

adapter = KRXMAPSAdapter(**backtest_config)
logger.success("어댑터 생성 완료")

# 4.4 Train/Test 분리 백테스트 실행
logger.info("\n4.4 Train/Test 분리 백테스트 실행")
logger.info("-" * 40)

try:
    results = run_backtest_with_split(
        adapter=adapter,
        price_data=price_data,
        strategy=strategy,
        start_date=start_date,
        end_date=end_date,
        train_ratio=0.7
    )
    
    logger.success("Train/Test 분리 백테스트 완료!")
    
except Exception as e:
    logger.fail(f"백테스트 실패: {e}")
    import traceback
    traceback.print_exc()
    logger.finish()
    sys.exit(1)

# 5. 결과 비교
logger.section("5. 결과 비교")

comparison = compare_train_test_results(results, verbose=True)

# 6. 상세 결과 출력
logger.section("6. 상세 결과")

train_results = results['train']
test_results = results['test']

logger.info("\n[Train 결과]")
logger.info(f"  기간: {periods.train.start_date} ~ {periods.train.end_date}")
logger.info(f"  수익률: {train_results.get('total_return_pct', 0):.2f}%")
logger.info(f"  CAGR: {train_results.get('cagr', 0):.2f}%")
logger.info(f"  Sharpe: {train_results.get('sharpe_ratio', 0):.2f}")
logger.info(f"  MDD: {train_results.get('max_drawdown', 0):.2f}%")
logger.info(f"  거래 수: {train_results.get('num_trades', 0)}회")
logger.info(f"  거래비용: {train_results.get('total_costs', 0):,.0f}원 ({train_results.get('cost_ratio', 0):.2f}%)")
logger.info(f"    - 수수료: {train_results.get('total_commission', 0):,.0f}원")
logger.info(f"    - 세금: {train_results.get('total_tax', 0):,.0f}원 (세율: {train_results.get('tax_rate', 0):.2f}%)")
logger.info(f"    - 슬리피지: {train_results.get('total_slippage', 0):,.0f}원")

# 레짐 통계 출력
if 'regime_stats' in train_results:
    rs = train_results['regime_stats']
    logger.info(f"  레짐 통계:")
    logger.info(f"    - 상승장: {rs.get('bull_days', 0)}일 ({rs.get('bull_pct', 0):.1f}%)")
    logger.info(f"    - 하락장: {rs.get('bear_days', 0)}일 ({rs.get('bear_pct', 0):.1f}%)")
    logger.info(f"    - 중립장: {rs.get('neutral_days', 0)}일 ({rs.get('neutral_pct', 0):.1f}%)")
    logger.info(f"    - 레짐 변경: {rs.get('regime_changes', 0)}회")

logger.info("\n[Test 결과]")
logger.info(f"  기간: {periods.test.start_date} ~ {periods.test.end_date}")
logger.info(f"  수익률: {test_results.get('total_return_pct', 0):.2f}%")
logger.info(f"  CAGR: {test_results.get('cagr', 0):.2f}%")
logger.info(f"  Sharpe: {test_results.get('sharpe_ratio', 0):.2f}")
logger.info(f"  MDD: {test_results.get('max_drawdown', 0):.2f}%")
logger.info(f"  거래 수: {test_results.get('num_trades', 0)}회")
logger.info(f"  거래비용: {test_results.get('total_costs', 0):,.0f}원 ({test_results.get('cost_ratio', 0):.2f}%)")
logger.info(f"    - 수수료: {test_results.get('total_commission', 0):,.0f}원")
logger.info(f"    - 세금: {test_results.get('total_tax', 0):,.0f}원 (세율: {test_results.get('tax_rate', 0):.2f}%)")
logger.info(f"    - 슬리피지: {test_results.get('total_slippage', 0):,.0f}원")

# 레짐 통계 출력
if 'regime_stats' in test_results:
    rs = test_results['regime_stats']
    logger.info(f"  레짐 통계:")
    logger.info(f"    - 상승장: {rs.get('bull_days', 0)}일 ({rs.get('bull_pct', 0):.1f}%)")
    logger.info(f"    - 하락장: {rs.get('bear_days', 0)}일 ({rs.get('bear_pct', 0):.1f}%)")
    logger.info(f"    - 중립장: {rs.get('neutral_days', 0)}일 ({rs.get('neutral_pct', 0):.1f}%)")
    logger.info(f"    - 레짐 변경: {rs.get('regime_changes', 0)}회")

# 7. 최종 판정
logger.section("7. 최종 판정")

if comparison.get('is_overfit'):
    logger.fail("❌ 과적합 의심!")
    logger.info("  Train과 Test 성과 차이가 너무 큽니다.")
    logger.info("  파라미터 튜닝 시 주의가 필요합니다.")
else:
    logger.success("✅ 정상 범위")
    logger.info("  Train과 Test 성과 차이가 허용 범위 내입니다.")

# 경고 출력
if comparison.get('warnings'):
    logger.info("\n⚠️ 주의사항:")
    for warning in comparison['warnings']:
        logger.warning(f"  {warning}")

# 8. 결과 저장
logger.section("8. 결과 저장")

output_dir = PROJECT_ROOT / 'data' / 'output' / 'backtest'
output_dir.mkdir(parents=True, exist_ok=True)

# 결과 저장
result_file = output_dir / 'train_test_split_results.json'
save_results = {
    'periods': {
        'train': {
            'start': str(periods.train.start_date),
            'end': str(periods.train.end_date),
            'days': periods.train.days
        },
        'test': {
            'start': str(periods.test.start_date),
            'end': str(periods.test.end_date),
            'days': periods.test.days
        }
    },
    'train': {
        'total_return_pct': train_results.get('total_return_pct', 0),
        'cagr': train_results.get('cagr', 0),
        'sharpe_ratio': train_results.get('sharpe_ratio', 0),
        'max_drawdown': train_results.get('max_drawdown', 0),
        'num_trades': train_results.get('num_trades', 0),
        'total_costs': train_results.get('total_costs', 0),
        'total_commission': train_results.get('total_commission', 0),
        'total_tax': train_results.get('total_tax', 0),
        'total_slippage': train_results.get('total_slippage', 0),
        'cost_ratio': train_results.get('cost_ratio', 0),
        'instrument_type': train_results.get('instrument_type', 'etf'),
        'tax_rate': train_results.get('tax_rate', 0)
    },
    'test': {
        'total_return_pct': test_results.get('total_return_pct', 0),
        'cagr': test_results.get('cagr', 0),
        'sharpe_ratio': test_results.get('sharpe_ratio', 0),
        'max_drawdown': test_results.get('max_drawdown', 0),
        'num_trades': test_results.get('num_trades', 0),
        'total_costs': test_results.get('total_costs', 0),
        'total_commission': test_results.get('total_commission', 0),
        'total_tax': test_results.get('total_tax', 0),
        'total_slippage': test_results.get('total_slippage', 0),
        'cost_ratio': test_results.get('cost_ratio', 0),
        'instrument_type': test_results.get('instrument_type', 'etf'),
        'tax_rate': test_results.get('tax_rate', 0)
    },
    'comparison': {
        'is_overfit': comparison.get('is_overfit', False),
        'status': comparison.get('status', ''),
        'warnings': comparison.get('warnings', [])
    },
    'validation': validation
}

with open(result_file, 'w', encoding='utf-8') as f:
    json.dump(save_results, f, indent=2, ensure_ascii=False)

logger.success(f"결과 저장: {result_file}")

# 9. 요약
logger.section("9. 요약")

logger.info("=" * 70)
logger.info("Phase 0: 검증 프레임워크 테스트 완료")
logger.info("=" * 70)
logger.info(f"\n📊 Train/Test 비교:")
logger.info(f"  Train CAGR: {train_results.get('cagr', 0):.2f}%")
logger.info(f"  Test CAGR:  {test_results.get('cagr', 0):.2f}%")
logger.info(f"  차이: {test_results.get('cagr', 0) - train_results.get('cagr', 0):+.2f}%")
logger.info(f"\n📋 판정: {comparison.get('status', '알 수 없음')}")
logger.info("=" * 70)

logger.finish()
