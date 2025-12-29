"""
app/cli/alerts.py
전략 스캐너 및 알림 CLI
"""
import argparse
import datetime as dt
import sys
from pathlib import Path
import yaml
import pandas as pd

from core.engine.scanner import MarketScanner
from core.strategy.rules import StrategyRules
from infra.notify.telegram import send_alerts  # slack에서 telegram으로 변경
from infra.data.loader import load_market_data
from core.risk.position import Position

def load_config(config_path: Path) -> dict:
    """설정 파일 로드"""
    with open(config_path) as f:
        return yaml.safe_load(f)

def run(argv=None):
    parser = argparse.ArgumentParser(prog="app.cli.alerts", description="전략 스캐너 및 알림")
    sp = parser.add_subparsers(dest="cmd", required=True)

    # 스캐너 실행 
    sp_scan = sp.add_parser("scan", help="전략 스캐너 실행")
    sp_scan.add_argument("--config", type=Path, required=True, help="전략 설정 파일")
    sp_scan.add_argument("--date", type=str, default="auto", help="날짜 (auto=오늘)")
    sp_scan.add_argument("--strategy", type=str, choices=['legacy', 'phase9'], default='legacy', help="전략 엔진 선택")
    
    # 알림 전송
    sp_notify = sp.add_parser("notify", help="알림 전송")
    sp_notify.add_argument("--signal-file", type=Path, required=True, help="신호 파일")
    sp_notify.add_argument("--template", type=str, default="default_v1", help="알림 템플릿")

    args = parser.parse_args(argv)

    try:
        if args.cmd == "scan":
            # 1. 설정 로드
            cfg = load_config(args.config)
            date = pd.Timestamp.now() if args.date == "auto" else pd.Timestamp(args.date)
            
            signals = []
            
            if args.strategy == 'phase9':
                # Phase 9: Crisis Alpha Executor
                from core.engine.phase9_executor import Phase9Executor
                print(f"[CLI] Phase 9 Strategy Selected. Date: {date.date()}")
                executor = Phase9Executor()
                signals = executor.execute(date.date())
                
            else:
                # Legacy Logic
                # 2. 데이터 로드
                prices = load_market_data(cfg["universe"], end_date=date)
                
                # 3. 현재 포지션 로드 (TODO: DB 연동)
                positions = []  # 현재는 빈 리스트, 향후 DB에서 로드
                
                # 4. 스캐너 실행
                rules = StrategyRules(
                    core_holdings=cfg.get("core_holdings", []),
                    lookbacks=cfg.get("lookbacks", [21, 63, 126]),
                    weights=cfg.get("weights", [0.5, 0.3, 0.2]),
                    top_n=cfg.get("top_n", 5)
                )
                scanner = MarketScanner(rules, prices, positions)
                signals = scanner.generate_signals()
            
            # 5. 결과 저장
            
            # 5. 결과 저장
            output_file = Path(f"reports/signals_{date:%Y%m%d}.yaml")
            output_file.parent.mkdir(parents=True, exist_ok=True)
            # Signal 객체를 dict로 변환
            # Signal 객체를 dict로 변환 (Legacy 호환성)
            signal_dicts = []
            for s in signals:
                if isinstance(s, dict):
                     # Phase 9 (Already Dict)
                     signal_dicts.append(s)
                else:
                     # Legacy (Object)
                    signal_dict = {
                        'code': s.code,
                        'signal_type': s.signal_type.value,  # enum의 값을 저장
                        'score': float(s.score),  # numpy.float를 파이썬 float로 변환
                        'reason': s.reason,
                        'timestamp': s.timestamp.isoformat()  # 타임스탬프를 문자열로 변환
                    }
                    signal_dicts.append(signal_dict)
            
            with open(output_file, "w", encoding='utf-8') as f:
                yaml.safe_dump(signal_dicts, f, allow_unicode=True)
            print(f"신호 생성 완료: {len(signals)}건 -> {output_file}")
            
        elif args.cmd == "notify":
            # 알림 전송
            with open(args.signal_file, encoding='utf-8') as f:
                signals = yaml.safe_load(f)
            send_alerts(signals, template=args.template)
            print(f"알림 전송 완료: {len(signals)}건")

        return 0

    except Exception as e:
        print(f"[ERROR] alerts runner failed: {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(run())
