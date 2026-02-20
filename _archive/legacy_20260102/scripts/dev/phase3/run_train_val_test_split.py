# -*- coding: utf-8 -*-
"""
Phase 3: Train/Val/Test 3-way 분리 백테스트

목적:
- 과최적화 방지
- 실전 성과 예측
- 검증 신뢰도 측정

분할:
- Train: 70% (파라미터 탐색)
- Val: 15% (최적 파라미터 선택)
- Test: 15% (실전 성과 예측)

사용법:
    python run_train_val_test_split.py
    python run_train_val_test_split.py --start-date 2023-01-01 --end-date 2025-12-01
"""
import sys
import argparse
from pathlib import Path
from datetime import date, datetime
from datetime import timezone, timedelta
KST = timezone(timedelta(hours=9))
import json

# 프로젝트 루트 추가
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

# 명령줄 인자 파싱
parser = argparse.ArgumentParser(description='Train/Val/Test 3-way 분리 백테스트')
parser.add_argument('--start-date', type=str, default=None, help='시작일 (YYYY-MM-DD)')
parser.add_argument('--end-date', type=str, default=None, help='종료일 (YYYY-MM-DD)')
args = parser.parse_args()

# 로거 생성
from scripts.dev.phase2.utils.logger import create_logger
logger = create_logger("phase3_train_val_test", PROJECT_ROOT)

logger.info("=" * 70)
logger.info("Phase 3: Train/Val/Test 3-way 분리 백테스트")
logger.info("=" * 70)
logger.info("목적: 과최적화 방지 + 실전 성과 예측")

# 1. 유니버스 로드
logger.section("1. 유니버스 로드")

universe_file = PROJECT_ROOT / 'data' / 'universe' / 'etf_universe.csv'
universe_df = pd.read_csv(universe_file, encoding='utf-8-sig')

logger.info(f"유니버스 크기: {len(universe_df)}개")
tickers = universe_df['ticker'].tolist()

# KODEX 200 추가
if '069500' not in tickers:
    tickers.append('069500')
    logger.info("KODEX 200 (069500) 추가 - KOSPI 대표")

logger.info(f"종목 코드: {tickers[:10]}... (총 {len(tickers)}개)")

# 2. 가격 데이터 로드
logger.section("2. 가격 데이터 로드")

# 날짜 파라미터 처리
if args.start_date:
    start_date = datetime.strptime(args.start_date, '%Y-%m-%d').date()
else:
    start_date = date(2022, 1, 1)

if args.end_date:
    end_date = datetime.strptime(args.end_date, '%Y-%m-%d').date()
else:
    end_date = date.today()

logger.info(f"명령줄 인자: start_date={args.start_date}, end_date={args.end_date}")

logger.info(f"기간: {start_date} ~ {end_date}")
logger.info("데이터 로딩 중...")

from infra.data.loader import load_price_data

try:
    price_data = load_price_data(tickers, start_date, end_date)
    
    logger.success("데이터 로드 완료")
    logger.info(f"   Shape: {price_data.shape}")
    
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

# 4. Train/Val/Test 분리 백테스트
logger.section("4. Train/Val/Test 분리 백테스트")

from core.engine.krx_maps_adapter import KRXMAPSAdapter
from extensions.backtest.train_test_split import (
    get_three_way_split_periods,
    run_backtest_with_three_way_split,
    compare_three_way_results
)

# 백테스트 설정
backtest_config = {
    'initial_capital': 10_000_000,
    'commission_rate': 0.00015,
    'slippage_rate': 0.001,
    'max_positions': 10,
    'country_code': 'kor',
    'instrument_type': 'etf',
    'enable_defense': True,
}

# 4.1 기간 분리 확인
logger.info("\n4.1 기간 분리 확인 (70/15/15)")
logger.info("-" * 40)

periods = get_three_way_split_periods(
    start_date, end_date,
    train_ratio=0.70,
    val_ratio=0.15,
    test_ratio=0.15
)
logger.info(f"  {periods.train}")
logger.info(f"  {periods.val}")
logger.info(f"  {periods.test}")

# 4.2 어댑터 생성
logger.info("\n4.2 어댑터 생성")
logger.info("-" * 40)

adapter = KRXMAPSAdapter(**backtest_config)
logger.success("어댑터 생성 완료")

# 4.3 Train/Val/Test 분리 백테스트 실행
logger.info("\n4.3 Train/Val/Test 분리 백테스트 실행")
logger.info("-" * 40)

try:
    results = run_backtest_with_three_way_split(
        adapter=adapter,
        price_data=price_data,
        strategy=strategy,
        start_date=start_date,
        end_date=end_date,
        train_ratio=0.70,
        val_ratio=0.15,
        test_ratio=0.15
    )
    
    logger.success("Train/Val/Test 분리 백테스트 완료!")
    
except Exception as e:
    logger.fail(f"백테스트 실패: {e}")
    import traceback
    traceback.print_exc()
    logger.finish()
    sys.exit(1)

# 5. 결과 비교
logger.section("5. 결과 비교")

comparison = compare_three_way_results(results, verbose=True)

# 6. 상세 결과 출력
logger.section("6. 상세 결과")

train_results = results['train']
val_results = results['val']
test_results = results['test']

def print_period_results(name, period, result):
    logger.info(f"\n[{name} 결과]")
    logger.info(f"  기간: {period.start_date} ~ {period.end_date}")
    logger.info(f"  수익률: {result.get('total_return_pct', 0):.2f}%")
    logger.info(f"  CAGR: {result.get('cagr', 0):.2f}%")
    logger.info(f"  Sharpe: {result.get('sharpe_ratio', 0):.2f}")
    logger.info(f"  MDD: {result.get('max_drawdown', 0):.2f}%")
    logger.info(f"  거래 수: {result.get('num_trades', 0)}회")
    logger.info(f"  거래비용: {result.get('total_costs', 0):,.0f}원 ({result.get('cost_ratio', 0):.2f}%)")
    
    # 레짐 통계
    if 'regime_stats' in result:
        rs = result['regime_stats']
        logger.info(f"  레짐 통계:")
        logger.info(f"    - 상승장: {rs.get('bull_days', 0)}일 ({rs.get('bull_pct', 0):.1f}%)")
        logger.info(f"    - 하락장: {rs.get('bear_days', 0)}일 ({rs.get('bear_pct', 0):.1f}%)")
        logger.info(f"    - 중립장: {rs.get('neutral_days', 0)}일 ({rs.get('neutral_pct', 0):.1f}%)")

print_period_results("Train", periods.train, train_results)
print_period_results("Val", periods.val, val_results)
print_period_results("Test", periods.test, test_results)

# 7. 최종 판정
logger.section("7. 최종 판정")

status = comparison.get('status', '알 수 없음')
reliability = comparison.get('validation_reliability', 'unknown')
is_overfit = comparison.get('is_overfit', False)

if is_overfit:
    logger.fail(f"[X] {status}")
    logger.info("  파라미터 튜닝 시 주의가 필요합니다.")
else:
    logger.success(f"[O] {status}")
    logger.info(f"  검증 신뢰도: {reliability}")

# 경고 출력
if comparison.get('warnings'):
    logger.info("\n[!] 주의사항:")
    for warning in comparison['warnings']:
        logger.warning(f"  {warning}")

# 8. 결과 저장
logger.section("8. 결과 저장")

output_dir = PROJECT_ROOT / 'data' / 'output' / 'backtest'
output_dir.mkdir(parents=True, exist_ok=True)

# 결과 저장
result_file = output_dir / 'train_val_test_split_results.json'
save_results = {
    # 사용된 파라미터
    'strategy_params': params,
    'backtest_config': backtest_config,
    'periods': {
        'train': {
            'start': str(periods.train.start_date),
            'end': str(periods.train.end_date),
            'days': periods.train.days
        },
        'val': {
            'start': str(periods.val.start_date),
            'end': str(periods.val.end_date),
            'days': periods.val.days
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
        'cost_ratio': train_results.get('cost_ratio', 0),
    },
    'val': {
        'total_return_pct': val_results.get('total_return_pct', 0),
        'cagr': val_results.get('cagr', 0),
        'sharpe_ratio': val_results.get('sharpe_ratio', 0),
        'max_drawdown': val_results.get('max_drawdown', 0),
        'num_trades': val_results.get('num_trades', 0),
        'total_costs': val_results.get('total_costs', 0),
        'cost_ratio': val_results.get('cost_ratio', 0),
    },
    'test': {
        'total_return_pct': test_results.get('total_return_pct', 0),
        'cagr': test_results.get('cagr', 0),
        'sharpe_ratio': test_results.get('sharpe_ratio', 0),
        'max_drawdown': test_results.get('max_drawdown', 0),
        'num_trades': test_results.get('num_trades', 0),
        'total_costs': test_results.get('total_costs', 0),
        'cost_ratio': test_results.get('cost_ratio', 0),
    },
    'comparison': {
        'status': comparison.get('status', ''),
        'is_overfit': comparison.get('is_overfit', False),
        'validation_reliability': comparison.get('validation_reliability', ''),
        'degradation_pattern': comparison.get('degradation_pattern', ''),
        'warnings': comparison.get('warnings', [])
    }
}

with open(result_file, 'w', encoding='utf-8') as f:
    json.dump(save_results, f, indent=2, ensure_ascii=False)

logger.success(f"결과 저장: {result_file}")

# 히스토리에도 저장
from datetime import datetime
history_file = PROJECT_ROOT / 'data' / 'output' / 'backtest_history.json'
history = []
if history_file.exists():
    try:
        with open(history_file, 'r', encoding='utf-8') as f:
            history = json.load(f)
    except:
        pass

new_history_entry = {
    'id': str(int(datetime.now(KST).timestamp() * 1000)),
    'timestamp': datetime.now(KST).isoformat(),
    'parameters': {
        'start_date': str(periods.train.start_date),
        'end_date': str(periods.test.end_date),
        'initial_capital': 10000000,
        'split_type': '3-way (70/15/15)'
    },
    'metrics': {
        'cagr': test_results.get('cagr', 0),
        'sharpe': test_results.get('sharpe_ratio', 0),
        'mdd': test_results.get('max_drawdown', 0)
    },
    'train_metrics': {
        'cagr': train_results.get('cagr', 0),
        'sharpe': train_results.get('sharpe_ratio', 0),
        'mdd': train_results.get('max_drawdown', 0)
    },
    'val_metrics': {
        'cagr': val_results.get('cagr', 0),
        'sharpe': val_results.get('sharpe_ratio', 0),
        'mdd': val_results.get('max_drawdown', 0)
    },
    'status': 'success'
}
history.insert(0, new_history_entry)
history = history[:50]  # 최대 50개 유지

with open(history_file, 'w', encoding='utf-8') as f:
    json.dump(history, f, indent=2, ensure_ascii=False)

logger.success(f"히스토리 저장: {history_file}")

# 9. 요약
logger.section("9. 요약")

logger.info("=" * 70)
logger.info("Phase 3: Train/Val/Test 3-way 분리 백테스트 완료")
logger.info("=" * 70)
logger.info(f"\n[성과 비교]")
logger.info(f"  Train CAGR: {train_results.get('cagr', 0):.2f}%")
logger.info(f"  Val CAGR:   {val_results.get('cagr', 0):.2f}%")
logger.info(f"  Test CAGR:  {test_results.get('cagr', 0):.2f}%")
logger.info(f"\n[판정] {status}")
logger.info(f"   검증 신뢰도: {reliability}")
logger.info("=" * 70)

logger.finish()
