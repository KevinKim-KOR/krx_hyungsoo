# -*- coding: utf-8 -*-
"""
Phase 5: 분석 로그 통합 테스트

목적:
- 실제 백테스트에서 분석 로그 생성 확인
- 일자별/트레이드별 로그 저장
- 레짐 변경 및 방어 이벤트 기록
"""
import sys
from pathlib import Path
from datetime import date
import json

# 프로젝트 루트
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
from scripts.dev.phase2.utils.logger import create_logger

logger = create_logger("phase5_analysis_logs", PROJECT_ROOT)

logger.info("=" * 70)
logger.info("Phase 5: 분석 로그 통합 테스트")
logger.info("=" * 70)

# 1. 데이터 로드
logger.section("1. 데이터 로드")

universe_file = PROJECT_ROOT / 'data' / 'universe' / 'etf_universe.csv'
universe_df = pd.read_csv(universe_file, encoding='utf-8-sig')
tickers = universe_df['ticker'].tolist()

if '069500' not in tickers:
    tickers.append('069500')

logger.info(f"유니버스: {len(tickers)}개")

start_date = date(2024, 1, 1)  # 짧은 기간으로 테스트
end_date = date(2024, 6, 30)

from infra.data.loader import load_price_data

price_data = load_price_data(tickers, start_date, end_date)
logger.success(f"데이터 로드 완료: {price_data.shape}")

# 2. 전략 설정
logger.section("2. 전략 설정")

from extensions.strategy.signal_generator import SignalGenerator

strategy = SignalGenerator(
    ma_period=60,
    rsi_period=14,
    rsi_overbought=70,
    maps_buy_threshold=0.0,
    maps_sell_threshold=-5.0
)
logger.success("전략 초기화 완료")

# 3. 어댑터 생성 (분석 로그 활성화)
logger.section("3. 어댑터 생성")

from core.engine.krx_maps_adapter import KRXMAPSAdapter

adapter = KRXMAPSAdapter(
    initial_capital=10_000_000,
    commission_rate=0.00015,
    slippage_rate=0.001,
    max_positions=10,
    country_code='kor',
    instrument_type='etf',
    enable_defense=True
)

# 분석 로그 활성화 확인
logger.info(f"분석 로그 활성화: {adapter.enable_analysis_logging}")
logger.success("어댑터 생성 완료")

# 4. 백테스트 실행
logger.section("4. 백테스트 실행")

results = adapter.run(
    price_data=price_data,
    strategy=strategy,
    start_date=start_date,
    end_date=end_date
)

logger.success("백테스트 완료")
logger.info(f"  수익률: {results.get('total_return_pct', 0):.2f}%")
logger.info(f"  거래 수: {results.get('num_trades', 0)}회")

# 5. 분석 로그 확인
logger.section("5. 분석 로그 확인")

analysis_logs = adapter.get_analysis_logs()

# 일자별 로그
daily_df = analysis_logs['daily']
logger.info(f"일자별 로그: {len(daily_df)}행")
if not daily_df.empty:
    logger.info(f"  컬럼: {list(daily_df.columns)}")
    logger.info(f"  첫 날: {daily_df.index[0]}")
    logger.info(f"  마지막 날: {daily_df.index[-1]}")

# 트레이드 로그
trade_df = analysis_logs['trades']
logger.info(f"트레이드 로그: {len(trade_df)}행")
if not trade_df.empty:
    buy_count = len(trade_df[trade_df['side'] == 'BUY'])
    sell_count = len(trade_df[trade_df['side'] == 'SELL'])
    logger.info(f"  매수: {buy_count}건")
    logger.info(f"  매도: {sell_count}건")

# 레짐 변경 로그
regime_df = analysis_logs['regime_changes']
logger.info(f"레짐 변경 로그: {len(regime_df)}행")

# 방어 이벤트 로그
defense_df = analysis_logs['defense_events']
logger.info(f"방어 이벤트 로그: {len(defense_df)}행")

# 요약
summary = analysis_logs['summary']
logger.info(f"\n요약 통계:")
logger.info(f"  총 거래일: {summary.get('total_days', 0)}일")
logger.info(f"  총 거래: {summary.get('total_trades', 0)}건")
logger.info(f"  레짐 변경: {summary.get('regime_changes', 0)}회")
logger.info(f"  방어 이벤트: {summary.get('defense_events', 0)}회")

if 'regime_distribution' in summary:
    logger.info("  레짐 분포:")
    for regime, stats in summary['regime_distribution'].items():
        logger.info(f"    - {regime}: {stats['days']}일 ({stats['pct']:.1f}%)")

# 6. 분석 로그 저장
logger.section("6. 분석 로그 저장")

output_dir = PROJECT_ROOT / 'data' / 'output' / 'analysis_logs'
adapter.save_analysis_logs(output_dir, prefix='backtest_2024h1')

logger.success(f"분석 로그 저장 완료: {output_dir}")

# 저장된 파일 확인
for f in output_dir.glob('backtest_2024h1_*'):
    logger.info(f"  - {f.name}")

# 7. 요약
logger.section("7. 요약")

logger.info("=" * 70)
logger.info("Phase 5: 분석 로그 통합 테스트 완료")
logger.info("=" * 70)
logger.info("\n✅ 생성된 로그:")
logger.info(f"  - 일자별 로그: {len(daily_df)}행")
logger.info(f"  - 트레이드 로그: {len(trade_df)}행")
logger.info(f"  - 레짐 변경 로그: {len(regime_df)}행")
logger.info(f"  - 방어 이벤트 로그: {len(defense_df)}행")
logger.info(f"\n✅ 저장 위치: {output_dir}")
logger.info("=" * 70)

logger.finish()
