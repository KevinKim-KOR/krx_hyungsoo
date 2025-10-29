# -*- coding: utf-8 -*-
"""
pc/cli.py
PC용 CLI 인터페이스 (실전 운영)
"""
import argparse
import sys
from pathlib import Path
from datetime import date, datetime, timedelta
import logging

# 프로젝트 루트를 sys.path에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from infra.data.updater import DataUpdater
from core.data.filtering import ETFFilter
from extensions.backtest.runner import create_momentum_runner
from extensions.backtest.report import create_report

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def cmd_update_data(args):
    """데이터 업데이트 명령"""
    logger.info("=" * 60)
    logger.info("데이터 업데이트 시작")
    logger.info("=" * 60)
    
    # 날짜 파싱
    if args.date == 'auto':
        end_date = date.today()
    else:
        end_date = datetime.strptime(args.date, '%Y-%m-%d').date()
    
    # 시작일 (기본: 1년 전)
    start_date = end_date - timedelta(days=365)
    
    # 유니버스 필터링
    etf_filter = ETFFilter()
    universe = etf_filter.get_filtered_universe()
    
    logger.info(f"유니버스: {len(universe)}개 종목")
    logger.info(f"기간: {start_date} ~ {end_date}")
    
    # 데이터 업데이트
    updater = DataUpdater()
    
    if args.symbols:
        # 특정 종목만
        symbols = args.symbols.split(',')
        for symbol in symbols:
            updater.update_single(symbol.strip(), start_date, end_date, force=args.force)
    else:
        # 전체 유니버스
        updater.update_universe(universe, start_date, end_date, force=args.force)
    
    logger.info("=" * 60)
    logger.info("데이터 업데이트 완료")
    logger.info("=" * 60)
    
    return 0


def cmd_backtest(args):
    """백테스트 명령"""
    logger.info("=" * 60)
    logger.info("백테스트 시작")
    logger.info("=" * 60)
    
    # 날짜 파싱
    start_date = datetime.strptime(args.start, '%Y-%m-%d').date()
    
    if args.end == 'today':
        end_date = date.today()
    else:
        end_date = datetime.strptime(args.end, '%Y-%m-%d').date()
    
    logger.info(f"기간: {start_date} ~ {end_date}")
    logger.info(f"초기 자본: {args.capital:,}원")
    logger.info(f"최대 보유 종목: {args.max_positions}개")
    logger.info(f"리밸런싱: {args.rebalance}")
    
    # 유니버스
    if args.universe:
        universe = args.universe.split(',')
    else:
        etf_filter = ETFFilter()
        universe = etf_filter.get_filtered_universe()
    
    logger.info(f"유니버스: {len(universe)}개 종목")
    
    # 가격 데이터 로드
    from infra.data.loader import load_price_data
    price_data = load_price_data(universe, start_date, end_date)
    
    if price_data.empty:
        logger.error("가격 데이터가 없습니다. 먼저 데이터를 업데이트하세요.")
        return 1
    
    # 백테스트 실행
    runner = create_momentum_runner(
        initial_capital=args.capital,
        max_positions=args.max_positions
    )
    
    result = runner.run(
        price_data=price_data,
        start_date=start_date,
        end_date=end_date,
        universe=universe,
        rebalance_frequency=args.rebalance
    )
    
    # 리포트 생성
    report = create_report(result)
    
    # 콘솔 출력
    print("\n" + report.generate_summary())
    
    # 파일 저장
    if args.output:
        output_dir = Path(args.output)
        report.save_to_file(output_dir)
        logger.info(f"리포트 저장: {output_dir}")
    
    logger.info("=" * 60)
    logger.info("백테스트 완료")
    logger.info("=" * 60)
    
    return 0


def cmd_scan(args):
    """스캔 명령 (매매 신호 생성)"""
    logger.info("=" * 60)
    logger.info("매매 신호 스캔 시작")
    logger.info("=" * 60)
    
    # 날짜 파싱
    if args.date == 'auto':
        scan_date = date.today()
    else:
        scan_date = datetime.strptime(args.date, '%Y-%m-%d').date()
    
    logger.info(f"스캔 날짜: {scan_date}")
    
    # 유니버스
    etf_filter = ETFFilter()
    universe = etf_filter.get_filtered_universe()
    
    logger.info(f"유니버스: {len(universe)}개 종목")
    
    # 신호 생성
    from core.strategy.signals import create_default_signal_generator
    from infra.data.loader import load_price_data
    
    signal_generator = create_default_signal_generator()
    
    # 최근 60일 데이터
    start_date = scan_date - timedelta(days=120)
    price_data = load_price_data(universe, start_date, scan_date)
    
    if price_data.empty:
        logger.error("가격 데이터가 없습니다.")
        return 1
    
    # 종목별 신호 생성
    signals = []
    
    for symbol in universe:
        try:
            if symbol not in price_data.index.get_level_values('code'):
                continue
            
            symbol_data = price_data.loc[symbol]
            symbol_data = symbol_data[symbol_data.index <= scan_date]
            
            if len(symbol_data) < 60:
                continue
            
            recent_data = symbol_data.tail(60)
            
            result = signal_generator.generate_combined_signal(
                close=recent_data['close'],
                high=recent_data.get('high'),
                low=recent_data.get('low'),
                volume=recent_data.get('volume')
            )
            
            if result['signal'] == 'BUY' and result['confidence'] >= args.min_confidence:
                signals.append({
                    'symbol': symbol,
                    'signal': result['signal'],
                    'confidence': result['confidence'],
                    'price': recent_data['close'].iloc[-1]
                })
        
        except Exception as e:
            logger.debug(f"신호 생성 실패 ({symbol}): {e}")
    
    # 신뢰도 순 정렬
    signals.sort(key=lambda x: x['confidence'], reverse=True)
    
    # 상위 N개
    top_signals = signals[:args.top_n]
    
    # 출력
    print("\n" + "=" * 60)
    print(f"매매 신호 ({len(top_signals)}개)")
    print("=" * 60)
    
    for i, sig in enumerate(top_signals, 1):
        print(f"{i}. {sig['symbol']}: {sig['signal']} "
              f"(신뢰도: {sig['confidence']:.2%}, 가격: {sig['price']:,.0f})")
    
    print("=" * 60)
    
    # 파일 저장
    if args.output:
        import pandas as pd
        df = pd.DataFrame(top_signals)
        output_file = Path(args.output)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_file, index=False, encoding='utf-8-sig')
        logger.info(f"신호 저장: {output_file}")
    
    logger.info("=" * 60)
    logger.info("스캔 완료")
    logger.info("=" * 60)
    
    return 0


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(
        description='KRX Alertor - PC CLI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  # 데이터 업데이트
  python pc/cli.py update --date auto
  
  # 백테스트 실행
  python pc/cli.py backtest --start 2024-01-01 --output reports/backtest_2024
  
  # 매매 신호 스캔
  python pc/cli.py scan --date auto --top-n 10
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='명령')
    
    # update 명령
    parser_update = subparsers.add_parser('update', help='데이터 업데이트')
    parser_update.add_argument('--date', default='auto', help='종료일 (YYYY-MM-DD 또는 auto)')
    parser_update.add_argument('--symbols', help='특정 종목만 (쉼표 구분)')
    parser_update.add_argument('--force', action='store_true', help='강제 업데이트')
    parser_update.set_defaults(func=cmd_update_data)
    
    # backtest 명령
    parser_backtest = subparsers.add_parser('backtest', help='백테스트 실행')
    parser_backtest.add_argument('--start', required=True, help='시작일 (YYYY-MM-DD)')
    parser_backtest.add_argument('--end', default='today', help='종료일 (YYYY-MM-DD 또는 today)')
    parser_backtest.add_argument('--capital', type=int, default=10000000, help='초기 자본 (기본: 1천만원)')
    parser_backtest.add_argument('--max-positions', type=int, default=10, help='최대 보유 종목 수')
    parser_backtest.add_argument('--rebalance', default='monthly', choices=['daily', 'weekly', 'monthly'], help='리밸런싱 주기')
    parser_backtest.add_argument('--universe', help='유니버스 (쉼표 구분, 미지정시 자동 필터링)')
    parser_backtest.add_argument('--output', help='리포트 저장 경로')
    parser_backtest.set_defaults(func=cmd_backtest)
    
    # scan 명령
    parser_scan = subparsers.add_parser('scan', help='매매 신호 스캔')
    parser_scan.add_argument('--date', default='auto', help='스캔 날짜 (YYYY-MM-DD 또는 auto)')
    parser_scan.add_argument('--min-confidence', type=float, default=0.6, help='최소 신뢰도 (기본: 0.6)')
    parser_scan.add_argument('--top-n', type=int, default=10, help='상위 N개 (기본: 10)')
    parser_scan.add_argument('--output', help='신호 저장 경로 (CSV)')
    parser_scan.set_defaults(func=cmd_scan)
    
    # 파싱
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # 명령 실행
    try:
        return args.func(args)
    except Exception as e:
        logger.error(f"오류 발생: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
