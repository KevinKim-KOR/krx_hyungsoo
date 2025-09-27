# report_watchlist_cli.py
import argparse
from reporting_eod import generate_and_send_watchlist_report

def main():
    p = argparse.ArgumentParser(description="KRX Watchlist EOD Report CLI")
    p.add_argument("--date", default="auto", help="YYYY-MM-DD 또는 auto")
    p.add_argument("--watchlist", default="watchlist.yaml", help="watchlist yaml 경로")
    args = p.parse_args()
    raise SystemExit(generate_and_send_watchlist_report(args.date, args.watchlist))

if __name__ == "__main__":
    main()
