# -*- coding: utf-8 -*-
"""
NAS 전용 경량 CLI
- ingest-eod: 데이터 수집
- scanner: 스캐너 실행
- notify: 텔레그램 알림
"""

import argparse
import sys
import os

# core 모듈 import 경로 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.db import init_db
from core.fetchers import ingest_eod
from core.calendar_kr import is_trading_day, load_trading_days
from nas.scanner_nas import run_scanner_nas
from core.notifications import send_notify
import pandas as pd

def cmd_init(args):
    """DB 초기화"""
    init_db()
    print("✅ DB 초기화 완료")

def cmd_ingest_eod(args):
    """EOD 데이터 수집"""
    asof = pd.to_datetime(pd.Timestamp.today().date() if args.date == "auto" else args.date)
    load_trading_days(asof)
    
    if not is_trading_day(asof):
        print(f"[SKIP] 휴장일 {asof.date()} — ingest 생략")
        return
    
    ingest_eod(asof.strftime("%Y-%m-%d"))
    print(f"✅ EOD 데이터 수집 완료: {asof.date()}")

def cmd_scanner(args):
    """스캐너 실행"""
    asof = pd.to_datetime(args.date if args.date else pd.Timestamp.today().date())
    load_trading_days(asof)
    
    if not is_trading_day(asof):
        print(f"[SKIP] 휴장일 {asof.date()} — scanner 생략")
        return
    
    run_scanner_nas(asof)
    print(f"✅ 스캐너 실행 완료: {asof.date()}")

def cmd_notify(args):
    """텔레그램 알림 전송"""
    send_notify(args.message, channel="telegram")
    print("✅ 알림 전송 완료")

def main():
    parser = argparse.ArgumentParser(description="KRX Alertor NAS CLI")
    subparsers = parser.add_subparsers(dest="command", help="명령어")
    
    # init
    parser_init = subparsers.add_parser("init", help="DB 초기화")
    parser_init.set_defaults(func=cmd_init)
    
    # ingest-eod
    parser_ingest = subparsers.add_parser("ingest-eod", help="EOD 데이터 수집")
    parser_ingest.add_argument("--date", default="auto", help="날짜 (YYYY-MM-DD 또는 auto)")
    parser_ingest.set_defaults(func=cmd_ingest_eod)
    
    # scanner
    parser_scanner = subparsers.add_parser("scanner", help="스캐너 실행")
    parser_scanner.add_argument("--date", help="날짜 (YYYY-MM-DD)")
    parser_scanner.set_defaults(func=cmd_scanner)
    
    # notify
    parser_notify = subparsers.add_parser("notify", help="알림 전송")
    parser_notify.add_argument("message", help="메시지 내용")
    parser_notify.set_defaults(func=cmd_notify)
    
    args = parser.parse_args()
    
    if not hasattr(args, 'func'):
        parser.print_help()
        return
    
    args.func(args)

if __name__ == "__main__":
    main()
