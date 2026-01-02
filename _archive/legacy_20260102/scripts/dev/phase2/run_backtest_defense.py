#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Phase 2 재테스트 - Week 2 Day 2: 방어 시스템 백테스트
KRX MAPS 엔진 + DefenseSystem 통합 테스트
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
logger = create_logger("week2_day2_defense", PROJECT_ROOT)

logger.info("Week 2 Day 2: 방어 시스템 백테스트")
logger.info("목표: MDD -23.5% → -10~12% 감소")

# 1. 유니버스 로드
logger.section("1. 유니버스 로드")

universe_file = PROJECT_ROOT / 'data' / 'universe' / 'etf_universe.csv'
universe_df = pd.read_csv(universe_file, encoding='utf-8-sig')

logger.info(f"유니버스 크기: {len(universe_df)}개")
tickers = universe_df['ticker'].tolist()
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

# 5. 백테스트 실행 (방어 시스템 있음)
logger.section("5. 백테스트 실행 (방어 시스템 있음)")

logger.info("방어 시스템 활성화 백테스트...")
logger.info("  고정 손절: -7%")
logger.info("  트레일링 스톱: -10%")
logger.info("  포트폴리오 손절: -15%")
logger.info("  쿨다운: 3일")

adapter_with_defense = KRXMAPSAdapter(
    **backtest_config,
    enable_defense=True,
    fixed_stop_loss_pct=-7.0,
    trailing_stop_pct=-10.0,
    portfolio_stop_loss_pct=-15.0,
    cooldown_days=3
)

try:
    results_with_defense = adapter_with_defense.run(
        price_data=price_data,
        strategy=strategy,
        start_date=start_date,
        end_date=end_date
    )
    
    logger.success("백테스트 완료 (방어 있음)!")
    logger.info(f"  수익률: {results_with_defense['total_return_pct']:.2f}%")
    logger.info(f"  CAGR: {results_with_defense['cagr']:.2f}%")
    logger.info(f"  Sharpe: {results_with_defense['sharpe_ratio']:.2f}")
    logger.info(f"  MDD: {results_with_defense['max_drawdown']:.2f}%")
    logger.info(f"  거래 수: {results_with_defense['num_trades']}회")
    
    # 방어 시스템 통계
    if 'defense_stats' in results_with_defense:
        defense_stats = results_with_defense['defense_stats']
        logger.info("\n방어 시스템 통계:")
        logger.info(f"  고정 손절: {defense_stats['fixed_stop_count']}회")
        logger.info(f"  트레일링 스톱: {defense_stats['trailing_stop_count']}회")
        logger.info(f"  포트폴리오 손절: {defense_stats['portfolio_stop_count']}회")
        logger.info(f"  쿨다운 중: {defense_stats['cooldown_count']}개 종목")

except Exception as e:
    logger.fail(f"백테스트 실패 (방어 있음): {e}")
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
    '방어 있음': [
        f"{results_with_defense['total_return_pct']:.2f}",
        f"{results_with_defense['cagr']:.2f}",
        f"{results_with_defense['sharpe_ratio']:.2f}",
        f"{results_with_defense['max_drawdown']:.2f}",
        f"{results_with_defense['num_trades']}"
    ]
}

comparison_df = pd.DataFrame(comparison)
logger.info("\n" + comparison_df.to_string(index=False))

# 개선율 계산
mdd_improvement = ((results_with_defense['max_drawdown'] - results_no_defense['max_drawdown']) 
                   / abs(results_no_defense['max_drawdown']) * 100)
cagr_change = results_with_defense['cagr'] - results_no_defense['cagr']

logger.info("\n개선 효과:")
logger.info(f"  MDD 개선: {mdd_improvement:.1f}% (목표: +50%)")
logger.info(f"  CAGR 변화: {cagr_change:+.2f}%p")

# 목표 달성 여부
logger.info("\n목표 달성 여부:")
if results_with_defense['max_drawdown'] > -12.0:
    logger.success(f"  ✅ MDD 목표 달성! ({results_with_defense['max_drawdown']:.2f}% > -12%)")
else:
    logger.warning(f"  ⚠️ MDD 목표 미달성 ({results_with_defense['max_drawdown']:.2f}% < -12%)")

if results_with_defense['cagr'] >= 30.0:
    logger.success(f"  ✅ CAGR 목표 달성! ({results_with_defense['cagr']:.2f}% >= 30%)")
else:
    logger.warning(f"  ⚠️ CAGR 목표 미달성 ({results_with_defense['cagr']:.2f}% < 30%)")

if results_with_defense['sharpe_ratio'] >= 1.5:
    logger.success(f"  ✅ Sharpe 목표 달성! ({results_with_defense['sharpe_ratio']:.2f} >= 1.5)")
else:
    logger.warning(f"  ⚠️ Sharpe 목표 미달성 ({results_with_defense['sharpe_ratio']:.2f} < 1.5)")

# 7. 결과 저장
logger.section("7. 결과 저장")

output_dir = PROJECT_ROOT / 'data' / 'output' / 'phase2'
output_dir.mkdir(parents=True, exist_ok=True)

# 비교 결과 저장
comparison_file = output_dir / 'defense_comparison.json'
comparison_data = {
    'no_defense': {
        'total_return_pct': results_no_defense['total_return_pct'],
        'cagr': results_no_defense['cagr'],
        'sharpe_ratio': results_no_defense['sharpe_ratio'],
        'max_drawdown': results_no_defense['max_drawdown'],
        'num_trades': results_no_defense['num_trades']
    },
    'with_defense': {
        'total_return_pct': results_with_defense['total_return_pct'],
        'cagr': results_with_defense['cagr'],
        'sharpe_ratio': results_with_defense['sharpe_ratio'],
        'max_drawdown': results_with_defense['max_drawdown'],
        'num_trades': results_with_defense['num_trades'],
        'defense_stats': results_with_defense.get('defense_stats', {})
    },
    'improvement': {
        'mdd_improvement_pct': mdd_improvement,
        'cagr_change': cagr_change
    }
}

with open(comparison_file, 'w', encoding='utf-8') as f:
    json.dump(comparison_data, f, indent=2, ensure_ascii=False)

logger.success(f"비교 결과 저장: {comparison_file}")

# 방어 있음 결과 저장
defense_summary_file = output_dir / 'backtest_defense_summary.json'
defense_summary = {
    'config': {
        **backtest_config,
        'enable_defense': True,
        'fixed_stop_loss_pct': -7.0,
        'trailing_stop_pct': -10.0,
        'portfolio_stop_loss_pct': -15.0,
        'cooldown_days': 3
    },
    'params': params,
    'results': {
        'initial_capital': backtest_config['initial_capital'],
        'final_value': results_with_defense['final_value'],
        'total_return': results_with_defense['total_return'],
        'total_return_pct': results_with_defense['total_return_pct'],
        'cagr': results_with_defense['cagr'],
        'sharpe_ratio': results_with_defense['sharpe_ratio'],
        'max_drawdown': results_with_defense['max_drawdown'],
        'num_trades': results_with_defense['num_trades'],
        'defense_stats': results_with_defense.get('defense_stats', {})
    }
}

with open(defense_summary_file, 'w', encoding='utf-8') as f:
    json.dump(defense_summary, f, indent=2, ensure_ascii=False)

logger.success(f"방어 시스템 결과 저장: {defense_summary_file}")

logger.finish()
logger.info("\n" + "="*60)
logger.info("Week 2 Day 2 완료!")
logger.info("다음 단계: Day 3 - 시장 급락 감지")
logger.info("="*60)
