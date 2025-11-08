#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Phase 2 재테스트 - Week 2 Day 3: 시장 급락 감지 백테스트
KRX MAPS 엔진 + MarketCrashDetector 통합 테스트
"""
import sys
from pathlib import Path
from datetime import date
import pandas as pd
import json

# 프로젝트 루트
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 로거 생성
from scripts.phase2.utils.logger import create_logger
logger = create_logger("week2_day3_crash", PROJECT_ROOT)

logger.info("Week 2 Day 3: 시장 급락 감지 백테스트")
logger.info("목표: 시장 급락 감지로 MDD 개선")

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

# 4. 백테스트 실행 (방어 시스템 없음)
logger.section("4. 백테스트 실행 (방어 시스템 없음)")

from core.engine.krx_maps_adapter import KRXMAPSAdapter

backtest_config = {
    'initial_capital': 10_000_000,
    'commission_rate': 0.00015,
    'slippage_rate': 0.001,
    'max_positions': 10,
    'country_code': 'kor'
}

logger.info("방어 시스템 비활성화 백테스트...")

adapter_no_defense = KRXMAPSAdapter(
    **backtest_config,
    enable_defense=False
)

try:
    results_no_defense = adapter_no_defense.run(
        price_data=price_data,
        strategy=strategy,
        start_date=start_date,
        end_date=end_date
    )
    
    logger.success("백테스트 완료 (방어 없음)!")
    logger.info(f"  수익률: {results_no_defense['total_return_pct']:.2f}%")
    logger.info(f"  CAGR: {results_no_defense['cagr']:.2f}%")
    logger.info(f"  Sharpe: {results_no_defense['sharpe_ratio']:.2f}")
    logger.info(f"  MDD: {results_no_defense['max_drawdown']:.2f}%")
    logger.info(f"  거래 수: {results_no_defense['num_trades']}회")

except Exception as e:
    logger.fail(f"백테스트 실패 (방어 없음): {e}")
    import traceback
    traceback.print_exc()
    logger.finish()
    sys.exit(1)

# 5. 백테스트 실행 (시장 급락 감지 있음)
logger.section("5. 백테스트 실행 (시장 급락 감지 있음)")

logger.info("시장 급락 감지 활성화 백테스트 (개선)")
logger.info("  단일 급락: -5% (당일 Low)")
logger.info("  단기 급락: -7% / 3일 (최저 Low)")
logger.info("  보유 종목 하락: 60% / -5%")
logger.info("  방어 모드 유지: 5일")
logger.info("  개별 손절: 비활성화")

adapter_with_crash = KRXMAPSAdapter(
    **backtest_config,
    enable_defense=True,
    fixed_stop_loss_pct=-100.0,  # 비활성화
    trailing_stop_pct=-100.0,  # 비활성화
    portfolio_stop_loss_pct=-100.0,  # 비활성화
    cooldown_days=0
)

try:
    results_with_crash = adapter_with_crash.run(
        price_data=price_data,
        strategy=strategy,
        start_date=start_date,
        end_date=end_date
    )
    
    logger.success("백테스트 완료 (시장 급락 감지)!")
    logger.info(f"  수익률: {results_with_crash['total_return_pct']:.2f}%")
    logger.info(f"  CAGR: {results_with_crash['cagr']:.2f}%")
    logger.info(f"  Sharpe: {results_with_crash['sharpe_ratio']:.2f}")
    logger.info(f"  MDD: {results_with_crash['max_drawdown']:.2f}%")
    logger.info(f"  거래 수: {results_with_crash['num_trades']}회")
    
    # 시장 급락 감지 통계
    if 'crash_stats' in results_with_crash:
        crash_stats = results_with_crash['crash_stats']
        logger.info("\n시장 급락 감지 통계:")
        logger.info(f"  시장 급락: {crash_stats['market_crash_count']}회")
        logger.info(f"  보유 종목 하락: {crash_stats['portfolio_decline_count']}회")
        logger.info(f"  방어 모드 일수: {crash_stats['defense_mode_days']}일")
        logger.info(f"  현재 방어 모드: {crash_stats['is_defense_mode']}")

except Exception as e:
    logger.fail(f"백테스트 실패 (시장 급락 감지): {e}")
    import traceback
    traceback.print_exc()
    logger.finish()
    sys.exit(1)

# 6. 결과 비교
logger.section("6. 결과 비교")

logger.info("=" * 60)
logger.info("백테스트 결과 비교")
logger.info("=" * 60)

# 비교 테이블
comparison = {
    '지표': ['수익률 (%)', 'CAGR (%)', 'Sharpe Ratio', 'MDD (%)', '거래 수'],
    '방어 없음': [
        f"{results_no_defense['total_return_pct']:.2f}",
        f"{results_no_defense['cagr']:.2f}",
        f"{results_no_defense['sharpe_ratio']:.2f}",
        f"{results_no_defense['max_drawdown']:.2f}",
        f"{results_no_defense['num_trades']}"
    ],
    '시장 급락 감지': [
        f"{results_with_crash['total_return_pct']:.2f}",
        f"{results_with_crash['cagr']:.2f}",
        f"{results_with_crash['sharpe_ratio']:.2f}",
        f"{results_with_crash['max_drawdown']:.2f}",
        f"{results_with_crash['num_trades']}"
    ]
}

comparison_df = pd.DataFrame(comparison)
logger.info("\n" + comparison_df.to_string(index=False))

# 개선율 계산
mdd_improvement = ((results_with_crash['max_drawdown'] - results_no_defense['max_drawdown']) 
                   / abs(results_no_defense['max_drawdown']) * 100)
cagr_change = results_with_crash['cagr'] - results_no_defense['cagr']

logger.info("\n개선 효과:")
logger.info(f"  MDD 개선: {mdd_improvement:.1f}% (목표: +50%)")
logger.info(f"  CAGR 변화: {cagr_change:+.2f}%p")

# 목표 달성 여부
logger.info("\n목표 달성 여부:")
if results_with_crash['max_drawdown'] > -12.0:
    logger.success(f"  ✅ MDD 목표 달성! ({results_with_crash['max_drawdown']:.2f}% > -12%)")
else:
    logger.warning(f"  ⚠️ MDD 목표 미달성 ({results_with_crash['max_drawdown']:.2f}% < -12%)")

if results_with_crash['cagr'] >= 30.0:
    logger.success(f"  ✅ CAGR 목표 달성! ({results_with_crash['cagr']:.2f}% >= 30%)")
else:
    logger.warning(f"  ⚠️ CAGR 목표 미달성 ({results_with_crash['cagr']:.2f}% < 30%)")

if results_with_crash['sharpe_ratio'] >= 1.5:
    logger.success(f"  ✅ Sharpe 목표 달성! ({results_with_crash['sharpe_ratio']:.2f} >= 1.5)")
else:
    logger.warning(f"  ⚠️ Sharpe 목표 미달성 ({results_with_crash['sharpe_ratio']:.2f} < 1.5)")

# 7. 결과 저장
logger.section("7. 결과 저장")

output_dir = PROJECT_ROOT / 'data' / 'output' / 'phase2'
output_dir.mkdir(parents=True, exist_ok=True)

# 비교 결과 저장
comparison_file = output_dir / 'crash_detection_comparison.json'
comparison_data = {
    'no_defense': {
        'total_return_pct': results_no_defense['total_return_pct'],
        'cagr': results_no_defense['cagr'],
        'sharpe_ratio': results_no_defense['sharpe_ratio'],
        'max_drawdown': results_no_defense['max_drawdown'],
        'num_trades': results_no_defense['num_trades']
    },
    'with_crash_detection': {
        'total_return_pct': results_with_crash['total_return_pct'],
        'cagr': results_with_crash['cagr'],
        'sharpe_ratio': results_with_crash['sharpe_ratio'],
        'max_drawdown': results_with_crash['max_drawdown'],
        'num_trades': results_with_crash['num_trades'],
        'crash_stats': results_with_crash.get('crash_stats', {})
    },
    'improvement': {
        'mdd_improvement_pct': mdd_improvement,
        'cagr_change': cagr_change
    }
}

with open(comparison_file, 'w', encoding='utf-8') as f:
    json.dump(comparison_data, f, indent=2, ensure_ascii=False)

logger.success(f"비교 결과 저장: {comparison_file}")

# 시장 급락 감지 결과 저장
crash_summary_file = output_dir / 'backtest_crash_detection_summary.json'
crash_summary = {
    'config': {
        **backtest_config,
        'enable_defense': True,
        'single_day_crash_threshold': -5.0,
        'short_term_crash_threshold': -7.0,
        'short_term_crash_period': 3,
        'portfolio_decline_threshold': 0.6,
        'portfolio_decline_pct': -5.0,
        'defense_mode_duration': 5
    },
    'params': params,
    'results': {
        'initial_capital': backtest_config['initial_capital'],
        'final_value': results_with_crash['final_value'],
        'total_return': results_with_crash['total_return'],
        'total_return_pct': results_with_crash['total_return_pct'],
        'cagr': results_with_crash['cagr'],
        'sharpe_ratio': results_with_crash['sharpe_ratio'],
        'max_drawdown': results_with_crash['max_drawdown'],
        'num_trades': results_with_crash['num_trades'],
        'crash_stats': results_with_crash.get('crash_stats', {})
    }
}

with open(crash_summary_file, 'w', encoding='utf-8') as f:
    json.dump(crash_summary, f, indent=2, ensure_ascii=False)

logger.success(f"시장 급락 감지 결과 저장: {crash_summary_file}")

logger.finish()
logger.info("\n" + "="*60)
logger.info("Week 2 Day 3 완료!")
logger.info("다음 단계: Day 4 - 변동성 관리")
logger.info("="*60)
