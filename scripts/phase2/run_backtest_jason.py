#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Phase 2 재테스트 - 3-1단계: Jason 엔진 백테스트
Week 1 Day 3-4: Jason 어댑터 통합 테스트
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
logger = create_logger("3_1_run_backtest_jason", PROJECT_ROOT)

logger.info("Phase 2 재테스트 - 3-1단계: Jason 엔진 백테스트")
logger.info("Week 1 Day 3-4: Jason 어댑터 통합 테스트")

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

# 3. Jason 어댑터 초기화
logger.section("3. Jason 어댑터 초기화")

from core.engine.jason_adapter import JasonBacktestAdapter
from extensions.strategy.signal_generator import SignalGenerator

# 백테스트 설정
backtest_config = {
    'initial_capital': 10_000_000,
    'commission_rate': 0.00015,
    'slippage_rate': 0.001,
    'max_positions': 10,
    'country_code': 'kor'
}

logger.info("백테스트 설정:")
for key, value in backtest_config.items():
    logger.info(f"  {key}: {value}")

# Jason 어댑터 생성
adapter = JasonBacktestAdapter(**backtest_config)
logger.success("Jason 어댑터 초기화 완료")

# 4. 전략 설정
logger.section("4. 전략 설정")

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

# 5. 백테스트 실행
logger.section("5. Jason 백테스트 실행")

logger.info("백테스트 실행 중...")
logger.info("(Jason 어댑터를 통한 실행)")

try:
    results = adapter.run(
        price_data=price_data,
        strategy=strategy,
        start_date=start_date,
        end_date=end_date
    )
    
    logger.success("백테스트 완료!")
    
    # 6. 결과 출력
    logger.section("6. 백테스트 결과")
    
    logger.info(f"초기 자본: {backtest_config['initial_capital']:,.0f}원")
    logger.info(f"최종 자산: {results['final_value']:,.0f}원")
    logger.info(f"총 수익: {results['total_return']:,.0f}원")
    logger.info(f"수익률: {results['total_return_pct']:.2f}%")
    logger.info(f"CAGR: {results['cagr']:.2f}%")
    logger.info(f"Sharpe Ratio: {results['sharpe_ratio']:.2f}")
    logger.info(f"Max Drawdown: {results['max_drawdown']:.2f}%")
    logger.info(f"거래 수: {results['num_trades']}회")
    
    # 7. 결과 저장
    logger.section("7. 결과 저장")
    
    output_dir = PROJECT_ROOT / 'data' / 'output' / 'phase2'
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 결과 요약 저장
    summary_file = output_dir / 'backtest_jason_summary.json'
    summary = {
        'config': backtest_config,
        'params': params,
        'results': {
            'initial_capital': backtest_config['initial_capital'],
            'final_value': results['final_value'],
            'total_return': results['total_return'],
            'total_return_pct': results['total_return_pct'],
            'cagr': results['cagr'],
            'sharpe_ratio': results['sharpe_ratio'],
            'max_drawdown': results['max_drawdown'],
            'num_trades': results['num_trades']
        }
    }
    
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    logger.success(f"결과 요약 저장: {summary_file}")
    
    # 거래 내역 저장
    if results['trades']:
        trades_file = output_dir / 'backtest_jason_trades.csv'
        trades_df = pd.DataFrame(results['trades'])
        trades_df.to_csv(trades_file, index=False, encoding='utf-8-sig')
        logger.success(f"거래 내역 저장: {trades_file}")
    
    # 일별 평가액 저장
    if results['daily_values']:
        daily_file = output_dir / 'backtest_jason_daily.csv'
        daily_df = pd.DataFrame(results['daily_values'], columns=['date', 'value'])
        daily_df.to_csv(daily_file, index=False, encoding='utf-8-sig')
        logger.success(f"일별 평가액 저장: {daily_file}")
    
    # 8. 비교 분석
    logger.section("8. 기존 결과와 비교")
    
    # 기존 임시 결과 (run_backtest.py)
    logger.info("기존 임시 결과:")
    logger.info("  수익률: 15.0%")
    logger.info("  CAGR: 3.7%")
    logger.info("  Sharpe: N/A")
    logger.info("  MDD: N/A")
    
    logger.info("\nJason 엔진 결과:")
    logger.info(f"  수익률: {results['total_return_pct']:.2f}%")
    logger.info(f"  CAGR: {results['cagr']:.2f}%")
    logger.info(f"  Sharpe: {results['sharpe_ratio']:.2f}")
    logger.info(f"  MDD: {results['max_drawdown']:.2f}%")
    
    logger.info("\n✅ Jason 엔진을 통해 정확한 성과 지표를 계산했습니다!")
    
except Exception as e:
    logger.fail(f"백테스트 실패: {e}")
    import traceback
    traceback.print_exc()
    logger.finish()
    sys.exit(1)

logger.finish()
logger.info("\n" + "="*60)
logger.info("Week 1 Day 3-4 완료!")
logger.info("다음 단계: Week 2 - 방어 시스템 구현")
logger.info("="*60)
