# report_eod_cli.py
import argparse
from reporting_eod import generate_and_send_report_eod

def main():
    p = argparse.ArgumentParser(description="KRX EOD Report CLI")
    p.add_argument("--date", default="auto", help="YYYY-MM-DD 또는 auto")
    args = p.parse_args()
    raise SystemExit(generate_and_send_report_eod(args.date))

if __name__ == "__main__":
    main()
