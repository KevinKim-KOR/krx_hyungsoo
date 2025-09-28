# signals_cli.py
# -*- coding: utf-8 -*-
import argparse, sys
from signals.service import compute_daily_signals, send_signals_to_telegram

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=["score_abs","rank"], default=None)
    p.add_argument("--wl", type=int, default=1, help="1=watchlist 사용, 0=전체")
    p.add_argument("--top", type=int, default=5)
    args = p.parse_args()

    overrides = {}
    if args.mode:
        overrides["mode"] = args.mode
    overrides["use_watchlist"] = bool(args.wl)

    payload = compute_daily_signals(overrides=overrides)
    ok = send_signals_to_telegram(payload, top=args.top)
    return 0 if ok else 1

if __name__ == "__main__":
    sys.exit(main())
