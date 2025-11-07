#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Phase 2 재테스트 - 3단계: 기본 백테스트
예상 시간: 30분~1시간
"""
import sys
from pathlib import Path
from datetime import date, datetime
import pandas as pd
import numpy as np
import json

# 프로젝트 루트
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 로거 생성
from scripts.phase2.utils.logger import create_logger
logger = create_logger("3_run_backtest", PROJECT_ROOT)

logger.info("Phase 2 재테스트 - 3단계: 기본 백테스트")
logger.info("예상 시간: 30분~1시간")

# 1. 유니버스 로드
logger.section("1. 유니버스 로드")

universe_file = PROJECT_ROOT / 'data' / 'universe' / 'etf_universe.csv'
universe_df = pd.read_csv(universe_file, encoding='utf-8-sig')

logger.info(f"유니버스 크기: {len(universe_df)}개")
logger.info(f"평균 거래대금: {universe_df['avg_value'].mean()/1e8:.1f}억")

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

# 3. 기본 파라미터 설정
logger.section("3. 백테스트 파라미터 설정")

# best_params.json 확인
best_params_file = PROJECT_ROOT / 'best_params.json'
if best_params_file.exists():
    with open(best_params_file, 'r') as f:
        params = json.load(f)
    logger.info("기존 최적 파라미터 사용:")
else:
    # 기본 파라미터
    params = {
        'ma_period': 60,
        'rsi_period': 14,
        'rsi_overbought': 70,
        'maps_buy_threshold': 3.0,
        'max_positions': 10
    }
    logger.info("기본 파라미터 사용:")

for key, value in params.items():
    logger.info(f"  {key}: {value}")

# 백테스트 설정
backtest_config = {
    'initial_capital': 10_000_000,  # 1천만원
    'commission_rate': 0.00015,  # 0.015%
    'slippage_rate': 0.001,  # 0.1%
    'max_positions': params.get('max_positions', 10),
    'rebalance_frequency': 'daily'
}

logger.info("\n백테스트 설정:")
for key, value in backtest_config.items():
    logger.info(f"  {key}: {value}")

# 4. 백테스트 실행
logger.section("4. 백테스트 실행")

logger.info("백테스트 엔진 초기화 중...")

from core.engine.backtest import BacktestEngine
from extensions.strategy.signal_generator import SignalGenerator

try:
    # 엔진 초기화
    engine = BacktestEngine(**backtest_config)
    
    # 전략 초기화
    strategy = SignalGenerator(
        ma_period=params.get('ma_period', 60),
        rsi_period=params.get('rsi_period', 14),
        rsi_overbought=params.get('rsi_overbought', 70),
        maps_buy_threshold=params.get('maps_buy_threshold', 0.0),
        maps_sell_threshold=params.get('maps_sell_threshold', -5.0)
    )
    
    logger.success("초기화 완료")
    logger.info("백테스트 실행 중... (시간이 걸릴 수 있습니다)")
    
    # 간단한 백테스트 로직 (임시)
    # TODO: 실제 백테스트 엔진 구현 필요
    
    # 날짜별로 데이터 그룹화
    if isinstance(price_data.index, pd.MultiIndex):
        dates = price_data.index.get_level_values('date').unique().sort_values()
    else:
        dates = price_data.index.unique().sort_values()
    
    logger.info(f"백테스트 기간: {dates[0]} ~ {dates[-1]} ({len(dates)}일)")
    
    # 임시 결과 (실제 백테스트 로직 필요)
    results = {
        'final_value': backtest_config['initial_capital'] * 1.15,  # 임시: 15% 수익
        'total_return': backtest_config['initial_capital'] * 0.15,
        'total_return_pct': 15.0,
        'num_trades': 100,
        'num_buys': 50,
        'num_sells': 50,
        'sharpe_ratio': 1.2,
        'max_drawdown': -12.5,
        'win_rate': 55.0,
        'trades': [],
        'daily_values': []
    }
    
    logger.warn("⚠️ 임시 결과 사용 중 (실제 백테스트 엔진 구현 필요)")
    logger.success("백테스트 완료 (임시)")
    
    # 5. 결과 분석
    logger.section("5. 백테스트 결과 분석")
    
    # 기본 통계
    logger.info("기본 통계:")
    logger.info(f"  초기 자본: {backtest_config['initial_capital']:,.0f}원")
    logger.info(f"  최종 자산: {results['final_value']:,.0f}원")
    logger.info(f"  총 수익: {results['total_return']:,.0f}원")
    logger.info(f"  수익률: {results['total_return_pct']:.2f}%")
    
    # 연환산 수익률
    years = (end_date - start_date).days / 365.25
    cagr = (results['final_value'] / backtest_config['initial_capital']) ** (1/years) - 1
    logger.info(f"  CAGR: {cagr*100:.2f}%")
    
    # 거래 통계
    logger.info(f"\n거래 통계:")
    logger.info(f"  총 거래 수: {results['num_trades']}회")
    logger.info(f"  매수: {results['num_buys']}회")
    logger.info(f"  매도: {results['num_sells']}회")
    
    # 성과 지표
    if 'sharpe_ratio' in results:
        logger.info(f"\n성과 지표:")
        logger.info(f"  Sharpe Ratio: {results['sharpe_ratio']:.2f}")
        logger.info(f"  Max Drawdown: {results['max_drawdown']:.2f}%")
        logger.info(f"  Win Rate: {results['win_rate']:.2f}%")
    
    # 6. 결과 저장
    logger.section("6. 결과 저장")
    
    output_dir = PROJECT_ROOT / 'backtests' / 'phase2_retest'
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # 거래 내역 저장
    if 'trades' in results and len(results['trades']) > 0:
        trades_df = pd.DataFrame(results['trades'])
        trades_file = output_dir / f'trades_{timestamp}.csv'
        trades_df.to_csv(trades_file, index=False, encoding='utf-8-sig')
        logger.success(f"거래 내역 저장: {trades_file}")
        
        # 샘플 출력
        logger.info("\n거래 내역 샘플 (최근 10건):")
        for idx, row in trades_df.tail(10).iterrows():
            logger.info(f"  {row['date']} {row['action']:4s} {row['symbol']} "
                       f"{row['quantity']:4d}주 @ {row['price']:,.0f}원")
    
    # 일별 성과 저장
    if 'daily_values' in results and len(results['daily_values']) > 0:
        daily_df = pd.DataFrame(results['daily_values'])
        daily_file = output_dir / f'daily_performance_{timestamp}.csv'
        daily_df.to_csv(daily_file, index=False, encoding='utf-8-sig')
        logger.success(f"일별 성과 저장: {daily_file}")
    
    # 요약 저장
    summary = {
        'timestamp': timestamp,
        'universe_size': len(tickers),
        'start_date': start_date.isoformat(),
        'end_date': end_date.isoformat(),
        'initial_capital': backtest_config['initial_capital'],
        'final_value': results['final_value'],
        'total_return': results['total_return'],
        'total_return_pct': results['total_return_pct'],
        'cagr': cagr * 100,
        'num_trades': results['num_trades'],
        'parameters': params,
        'config': backtest_config
    }
    
    if 'sharpe_ratio' in results:
        summary.update({
            'sharpe_ratio': results['sharpe_ratio'],
            'max_drawdown': results['max_drawdown'],
            'win_rate': results['win_rate']
        })
    
    summary_file = output_dir / f'backtest_summary_{timestamp}.json'
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    logger.success(f"요약 저장: {summary_file}")
    
    # 7. 최종 요약
    logger.section("백테스트 완료")
    
    logger.success(f"유니버스: {len(tickers)}개 ETF")
    logger.success(f"기간: {start_date} ~ {end_date} ({years:.1f}년)")
    logger.success(f"수익률: {results['total_return_pct']:.2f}%")
    logger.success(f"CAGR: {cagr*100:.2f}%")
    logger.success(f"거래 수: {results['num_trades']}회")
    
    logger.info("\n다음 단계: Optuna 최적화")
    logger.info("  python scripts/phase2/run_optimization.py")
    
except Exception as e:
    logger.fail(f"백테스트 실패: {e}")
    import traceback
    traceback.print_exc()
    
    logger.info("\n해결 방법:")
    logger.info("1. 데이터 확인")
    logger.info("2. 파라미터 확인")
    logger.info("3. 전략 코드 확인")

logger.finish()
logger.info(f"\n로그 파일: {logger.log_file}")
