# -*- coding: utf-8 -*-
"""
Phase 5: 분석 로그 테스트

목적:
- AnalysisLogger 기능 검증
- 일자별/트레이드별 로그 생성
- 저장 및 로드 테스트
"""
import sys
from pathlib import Path
from datetime import date, timedelta

# 프로젝트 루트
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.dev.phase2.utils.logger import create_logger
logger = create_logger("phase5_analysis_test", PROJECT_ROOT)

logger.info("=" * 70)
logger.info("Phase 5: 분석 로그 테스트")
logger.info("=" * 70)

# 1. 분석 로거 생성
logger.section("1. 분석 로거 생성")

from core.engine.analysis_logger import AnalysisLogger, create_analysis_logger

analysis_logger = create_analysis_logger()
logger.success("분석 로거 생성 완료")

# 2. 일자별 로그 기록
logger.section("2. 일자별 로그 기록")

# 샘플 데이터 생성
start_date = date(2024, 1, 1)
portfolio_value = 10_000_000
regimes = ['bull', 'bull', 'neutral', 'bear', 'bear', 'neutral', 'bull']

for i in range(7):
    current_date = start_date + timedelta(days=i)
    regime = regimes[i]
    
    # 레짐에 따른 수익률 시뮬레이션
    if regime == 'bull':
        daily_return = 0.01
        regime_ratio = 1.0
    elif regime == 'bear':
        daily_return = -0.02
        regime_ratio = 0.5
    else:
        daily_return = 0.005
        regime_ratio = 0.8
    
    portfolio_value *= (1 + daily_return)
    cash = portfolio_value * (1 - regime_ratio * 0.8)
    holdings = portfolio_value - cash
    
    analysis_logger.log_daily(
        date=current_date,
        portfolio_value=portfolio_value,
        cash=cash,
        holdings_value=holdings,
        regime=regime,
        regime_confidence=0.7,
        regime_ratio=regime_ratio,
        num_positions=5,
        daily_return=daily_return,
        cumulative_return=(portfolio_value / 10_000_000 - 1)
    )

logger.success(f"일자별 로그 기록 완료: {len(analysis_logger.daily_logs)}건")

# 3. 트레이드 로그 기록
logger.section("3. 트레이드 로그 기록")

# 샘플 거래 데이터
trades = [
    {'date': date(2024, 1, 1), 'ticker': '069500', 'side': 'BUY', 'qty': 100, 'price': 50000, 'reason': 'rebalance'},
    {'date': date(2024, 1, 2), 'ticker': '102110', 'side': 'BUY', 'qty': 50, 'price': 30000, 'reason': 'rebalance'},
    {'date': date(2024, 1, 4), 'ticker': '069500', 'side': 'SELL', 'qty': 50, 'price': 49000, 'reason': 'regime_reduce_bear_50%'},
    {'date': date(2024, 1, 5), 'ticker': '102110', 'side': 'SELL', 'qty': 50, 'price': 28000, 'reason': 'stop_loss'},
]

for trade in trades:
    commission = trade['qty'] * trade['price'] * 0.00015
    tax = trade['qty'] * trade['price'] * 0.0023 if trade['side'] == 'SELL' else 0
    slippage = trade['qty'] * trade['price'] * 0.001
    
    analysis_logger.log_trade(
        date=trade['date'],
        ticker=trade['ticker'],
        side=trade['side'],
        qty=trade['qty'],
        price=trade['price'],
        commission=commission,
        tax=tax,
        slippage=slippage,
        reason=trade['reason']
    )

logger.success(f"트레이드 로그 기록 완료: {len(analysis_logger.trade_logs)}건")

# 4. 레짐 변경 로그
logger.section("4. 레짐 변경 로그")

analysis_logger.log_regime_change(
    date=date(2024, 1, 3),
    from_regime='bull',
    to_regime='neutral',
    confidence=0.65,
    action_taken='포지션 80%로 축소'
)

analysis_logger.log_regime_change(
    date=date(2024, 1, 4),
    from_regime='neutral',
    to_regime='bear',
    confidence=0.85,
    action_taken='포지션 50%로 축소, 매수 스킵'
)

logger.success(f"레짐 변경 로그 기록 완료: {len(analysis_logger.regime_changes)}건")

# 5. 방어 이벤트 로그
logger.section("5. 방어 이벤트 로그")

analysis_logger.log_defense_event(
    date=date(2024, 1, 4),
    event_type='regime_reduce',
    details='하락장 진입으로 포지션 50% 축소',
    impact=-0.02
)

analysis_logger.log_defense_event(
    date=date(2024, 1, 5),
    event_type='individual_stop',
    details='102110 개별 손절 (-10%)',
    impact=-0.10
)

logger.success(f"방어 이벤트 로그 기록 완료: {len(analysis_logger.defense_events)}건")

# 6. DataFrame 변환
logger.section("6. DataFrame 변환")

daily_df = analysis_logger.get_daily_logs()
trade_df = analysis_logger.get_trade_logs()
regime_df = analysis_logger.get_regime_changes()
defense_df = analysis_logger.get_defense_events()

logger.info(f"일자별 로그: {len(daily_df)}행")
logger.info(f"  컬럼: {list(daily_df.columns)[:5]}...")
logger.info(f"트레이드 로그: {len(trade_df)}행")
logger.info(f"  컬럼: {list(trade_df.columns)[:5]}...")
logger.info(f"레짐 변경 로그: {len(regime_df)}행")
logger.info(f"방어 이벤트 로그: {len(defense_df)}행")

# 7. 요약 통계
logger.section("7. 요약 통계")

summary = analysis_logger.get_summary()
logger.info(f"총 거래일: {summary['total_days']}일")
logger.info(f"총 거래: {summary['total_trades']}건")
logger.info(f"레짐 변경: {summary['regime_changes']}회")
logger.info(f"방어 이벤트: {summary['defense_events']}회")

if 'regime_distribution' in summary:
    logger.info("레짐 분포:")
    for regime, stats in summary['regime_distribution'].items():
        logger.info(f"  - {regime}: {stats['days']}일 ({stats['pct']:.1f}%)")

if 'trade_stats' in summary:
    ts = summary['trade_stats']
    logger.info("거래 통계:")
    logger.info(f"  - 매수: {ts['buy_count']}건")
    logger.info(f"  - 매도: {ts['sell_count']}건")
    logger.info(f"  - 총 비용: {ts['total_costs']:,.0f}원")

# 8. 저장 테스트
logger.section("8. 저장 테스트")

output_dir = PROJECT_ROOT / 'data' / 'output' / 'analysis_logs'
analysis_logger.save_logs(output_dir, prefix='test')
logger.success(f"로그 저장 완료: {output_dir}")

# 9. 요약
logger.section("9. 요약")

logger.info("=" * 70)
logger.info("Phase 5: 분석 로그 테스트 완료")
logger.info("=" * 70)
logger.info("\n✅ 구현 완료:")
logger.info("  - log_daily(): 일자별 포트폴리오 상태 기록")
logger.info("  - log_trade(): 개별 거래 기록")
logger.info("  - log_regime_change(): 레짐 변경 기록")
logger.info("  - log_defense_event(): 방어 이벤트 기록")
logger.info("  - get_summary(): 요약 통계 생성")
logger.info("  - save_logs(): CSV/JSON 저장")
logger.info("=" * 70)

logger.finish()
