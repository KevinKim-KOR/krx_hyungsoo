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
from core.data.filtering import ETFFilter, get_filtered_universe
from extensions.backtest.runner import create_default_runner, create_momentum_runner
from extensions.backtest.report import create_report
from extensions.optuna.objective import create_objective

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
    universe = get_filtered_universe()
    
    logger.info(f"유니버스: {len(universe)}개 종목")
    logger.info(f"기간: {start_date} ~ {end_date}")
    
    # 데이터 업데이트
    updater = DataUpdater()
    
    if args.symbols:
        # 특정 종목만
        symbols = args.symbols.split(',')
        for symbol in symbols:
            updater.update_symbol(symbol.strip(), end_date, force=args.force)
    else:
        # 전체 유니버스
        updater.update_universe(universe, end_date, force=args.force)
    
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
        universe = get_filtered_universe()
    
    logger.info(f"유니버스: {len(universe)}개 종목")
    
    # 가격 데이터 로드 (lookback 고려하여 더 많은 데이터 로드)
    from infra.data.loader import load_price_data
    lookback_days = 120  # 60일 lookback + 여유
    data_start_date = start_date - timedelta(days=lookback_days)
    price_data = load_price_data(universe, data_start_date, end_date)
    
    if price_data.empty:
        logger.error("가격 데이터가 없습니다. 먼저 데이터를 업데이트하세요.")
        return 1
    
    # 백테스트 실행 (MAPS 전략)
    runner = create_default_runner(
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
    universe = get_filtered_universe()
    
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
                    'price': recent_data['close'].iloc[-1],
                    'components': result.get('components', {})
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
    
    # 텔레그램 알림
    if args.notify:
        try:
            from infra.notify.telegram import send_to_telegram
            
            message = f"*[장마감] 매매 신호 알림*\n\n"
            message += f"📅 날짜: {scan_date}\n"
            message += f"📊 신호 수: {len(top_signals)}개\n\n"
            
            for i, sig in enumerate(top_signals, 1):
                message += f"{i}. `{sig['symbol']}`: *{sig['signal']}*\n"
                message += f"   신뢰도: {sig['confidence']:.1%} | 가격: {sig['price']:,.0f}원\n"
            
            send_to_telegram(message)
            logger.info("텔레그램 알림 전송 완료")
        except Exception as e:
            logger.error(f"텔레그램 알림 실패: {e}")
    
    logger.info("=" * 60)
    logger.info("스캔 완료")
    logger.info("=" * 60)
    
    return 0


def cmd_optimize(args):
    """파라미터 최적화 명령 (Optuna)"""
    logger.info("=" * 60)
    logger.info("파라미터 최적화 시작 (Optuna)")
    logger.info("=" * 60)
    
    import optuna
    import yaml
    from datetime import datetime
    
    # 날짜 파싱
    start_date = datetime.strptime(args.start, '%Y-%m-%d').date()
    
    if args.end == 'today':
        end_date = date.today()
    else:
        end_date = datetime.strptime(args.end, '%Y-%m-%d').date()
    
    logger.info(f"최적화 기간: {start_date} ~ {end_date}")
    logger.info(f"Trials: {args.trials}, Timeout: {args.timeout}초")
    logger.info(f"목적함수: 연율화 수익률 - {args.mdd_lambda} × MDD")
    
    # 출력 디렉토리
    if args.output:
        output_dir = Path(args.output)
    else:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_dir = Path(f'reports/optuna/study_{timestamp}')
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Optuna study 생성
    study_name = f"krx_alertor_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    storage_path = output_dir / 'study.db'
    
    study = optuna.create_study(
        study_name=study_name,
        storage=f'sqlite:///{storage_path}',
        direction='maximize',
        load_if_exists=True,
        sampler=optuna.samplers.TPESampler(seed=args.seed) if args.seed else None
    )
    
    # 목적 함수 생성
    objective = create_objective(
        start_date=start_date,
        end_date=end_date,
        initial_capital=args.capital,
        mdd_penalty_lambda=args.mdd_lambda,
        seed=args.seed
    )
    
    # 최적화 실행
    logger.info("최적화 실행 중...")
    
    try:
        study.optimize(
            objective,
            n_trials=args.trials,
            timeout=args.timeout,
            show_progress_bar=True
        )
    except KeyboardInterrupt:
        logger.warning("사용자에 의해 중단됨")
    
    # 결과 저장
    logger.info("=" * 60)
    logger.info("최적화 완료")
    logger.info("=" * 60)
    
    # 최적 파라미터
    best_params = study.best_params
    best_value = study.best_value
    
    logger.info(f"최적 목적함수 값: {best_value:.4f}")
    logger.info(f"최적 파라미터: {best_params}")
    
    # 최적 파라미터 저장
    params_file = output_dir / 'best_params.yaml'
    with open(params_file, 'w', encoding='utf-8') as f:
        yaml.dump(best_params, f, allow_unicode=True)
    
    logger.info(f"최적 파라미터 저장: {params_file}")
    
    # 리포트 생성
    report_file = output_dir / 'study_report.md'
    
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(f"# Optuna 최적화 리포트\n\n")
        f.write(f"## 설정\n\n")
        f.write(f"- 기간: {start_date} ~ {end_date}\n")
        f.write(f"- Trials: {len(study.trials)}\n")
        f.write(f"- 목적함수: 연율화 수익률 - {args.mdd_lambda} × MDD\n")
        f.write(f"- 초기 자본: {args.capital:,}원\n\n")
        
        f.write(f"## 최적 결과\n\n")
        f.write(f"- 목적함수 값: {best_value:.4f}\n")
        
        # 최적 trial의 메트릭
        best_trial = study.best_trial
        if best_trial.user_attrs:
            f.write(f"- 연율화 수익률: {best_trial.user_attrs.get('annual_return', 0):.2%}\n")
            f.write(f"- MDD: {best_trial.user_attrs.get('mdd', 0):.2%}\n")
            f.write(f"- Sharpe: {best_trial.user_attrs.get('sharpe', 0):.2f}\n")
            f.write(f"- 총 수익률: {best_trial.user_attrs.get('total_return', 0):.2%}\n")
            f.write(f"- 변동성: {best_trial.user_attrs.get('volatility', 0):.2%}\n")
            f.write(f"- 승률: {best_trial.user_attrs.get('win_rate', 0):.2%}\n")
        
        f.write(f"\n## 최적 파라미터\n\n")
        f.write(f"```yaml\n")
        f.write(yaml.dump(best_params, allow_unicode=True))
        f.write(f"```\n")
    
    logger.info(f"리포트 저장: {report_file}")
    logger.info(f"Study DB: {storage_path}")
    
    # 시각화 (선택)
    if args.plot:
        try:
            import optuna.visualization as vis
            import plotly
            
            # Optimization history
            fig = vis.plot_optimization_history(study)
            plotly.offline.plot(fig, filename=str(output_dir / 'optimization_history.html'), auto_open=False)
            
            # Parameter importances
            fig = vis.plot_param_importances(study)
            plotly.offline.plot(fig, filename=str(output_dir / 'param_importances.html'), auto_open=False)
            
            logger.info(f"시각화 저장: {output_dir}")
        except Exception as e:
            logger.warning(f"시각화 생성 실패: {e}")
    
    logger.info("=" * 60)
    logger.info("최적화 완료")
    logger.info("=" * 60)
    
    return 0


def cmd_walk_forward(args):
    """워크포워드 분석 명령"""
    from datetime import datetime
    from pathlib import Path
    from extensions.optuna.walk_forward import run_walk_forward
    
    logger.info("=" * 60)
    logger.info("워크포워드 분석 시작")
    logger.info("=" * 60)
    
    # 날짜 파싱
    start_date = datetime.strptime(args.start, '%Y-%m-%d').date()
    end_date = datetime.strptime(args.end, '%Y-%m-%d').date()
    
    # 출력 디렉토리
    if args.output:
        output_dir = Path(args.output)
    else:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_dir = Path(f'reports/walk_forward/{args.window_type}_{timestamp}')
    
    # 실행
    results = run_walk_forward(
        start_date=start_date,
        end_date=end_date,
        train_months=args.train_months,
        test_months=args.test_months,
        window_type=args.window_type,
        n_trials=args.trials,
        output_dir=output_dir,
        seed=args.seed
    )
    
    logger.info("=" * 60)
    logger.info("워크포워드 분석 완료")
    logger.info("=" * 60)
    
    return 0


def cmd_robustness(args):
    """로버스트니스 테스트 명령"""
    from datetime import datetime
    from pathlib import Path
    import json
    from extensions.optuna.robustness import run_robustness_tests
    
    logger.info("=" * 60)
    logger.info("로버스트니스 테스트 시작")
    logger.info("=" * 60)
    
    # 날짜 파싱
    start_date = datetime.strptime(args.start, '%Y-%m-%d').date()
    end_date = datetime.strptime(args.end, '%Y-%m-%d').date()
    
    # 파라미터 로드
    params_file = Path(args.params)
    if not params_file.exists():
        logger.error(f"파라미터 파일 없음: {params_file}")
        return 1
    
    with open(params_file, 'r', encoding='utf-8') as f:
        base_params = json.load(f)
    
    logger.info(f"기본 파라미터: {base_params}")
    
    # 출력 디렉토리
    if args.output:
        output_dir = Path(args.output)
    else:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_dir = Path(f'reports/robustness/{timestamp}')
    
    # 실행
    results = run_robustness_tests(
        base_params=base_params,
        start_date=start_date,
        end_date=end_date,
        n_iterations=args.iterations,
        output_dir=output_dir,
        seed=args.seed
    )
    
    logger.info("=" * 60)
    logger.info("로버스트니스 테스트 완료")
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
    parser_scan.add_argument('--notify', action='store_true', help='텔레그램 알림 전송')
    parser_scan.set_defaults(func=cmd_scan)
    
    # optimize 명령
    parser_optimize = subparsers.add_parser('optimize', help='파라미터 최적화 (Optuna)')
    parser_optimize.add_argument('--start', required=True, help='시작일 (YYYY-MM-DD)')
    parser_optimize.add_argument('--end', default='today', help='종료일 (YYYY-MM-DD 또는 today)')
    parser_optimize.add_argument('--capital', type=int, default=10000000, help='초기 자본 (기본: 1천만원)')
    parser_optimize.add_argument('--trials', type=int, default=100, help='Trial 수 (기본: 100)')
    parser_optimize.add_argument('--timeout', type=int, help='타임아웃 (초)')
    parser_optimize.add_argument('--mdd-lambda', type=float, default=2.0, help='MDD 패널티 계수 (기본: 2.0)')
    parser_optimize.add_argument('--seed', type=int, default=42, help='랜덤 시드 (재현성)')
    parser_optimize.add_argument('--output', help='결과 저장 경로')
    parser_optimize.add_argument('--plot', action='store_true', help='시각화 생성')
    parser_optimize.set_defaults(func=cmd_optimize)
    
    # walk-forward 명령
    parser_wf = subparsers.add_parser('walk-forward', help='워크포워드 분석')
    parser_wf.add_argument('--start', required=True, help='시작일 (YYYY-MM-DD)')
    parser_wf.add_argument('--end', required=True, help='종료일 (YYYY-MM-DD)')
    parser_wf.add_argument('--train-months', type=int, default=12, help='학습 기간 (개월)')
    parser_wf.add_argument('--test-months', type=int, default=3, help='검증 기간 (개월)')
    parser_wf.add_argument('--window-type', choices=['sliding', 'expanding'], default='sliding', help='윈도우 타입')
    parser_wf.add_argument('--trials', type=int, default=50, help='각 윈도우당 Optuna trials')
    parser_wf.add_argument('--seed', type=int, default=42, help='랜덤 시드')
    parser_wf.add_argument('--output', help='출력 디렉토리')
    parser_wf.set_defaults(func=cmd_walk_forward)
    
    # robustness 명령
    parser_robust = subparsers.add_parser('robustness', help='로버스트니스 테스트')
    parser_robust.add_argument('--start', required=True, help='시작일 (YYYY-MM-DD)')
    parser_robust.add_argument('--end', required=True, help='종료일 (YYYY-MM-DD)')
    parser_robust.add_argument('--params', required=True, help='파라미터 JSON 파일 경로')
    parser_robust.add_argument('--iterations', type=int, default=30, help='반복 횟수')
    parser_robust.add_argument('--seed', type=int, default=42, help='랜덤 시드')
    parser_robust.add_argument('--output', help='출력 디렉토리')
    parser_robust.set_defaults(func=cmd_robustness)
    
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
