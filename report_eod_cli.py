# report_eod_cli.py
import argparse
from reporting_eod import generate_and_send_report_eod

def main():
    p = argparse.ArgumentParser(description="KRX EOD Report CLI")
    p.add_argument("--date", default="auto", help="YYYY-MM-DD 또는 auto")
    p.add_argument("--no-expect-today", action="store_true",
                   help="평일이라도 오늘 데이터 기대하지 않음(지연시 재시도 트리거 해제)")
    args = p.parse_args()
    expect_today = not args.no_expect_today
    raise SystemExit(generate_and_send_report_eod(args.date, expect_today=expect_today))

if __name__ == "__main__":
    main()