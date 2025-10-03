# backtest_cli.py
# -*- coding: utf-8 -*-
import argparse, json, time, os
from pathlib import Path
from signals.service import compute_daily_signals

def run_once(start:str, end:str, mode:str, use_watchlist:bool):
    # signals.service가 내부적으로 동일 규칙(휴장/캐시/거래일)을 따르므로,
    # 동일 엔진을 사용해 점수/신호를 생성하고 간단 집계 예시를 리턴합니다.
    payload = compute_daily_signals(overrides={"mode": mode, "use_watchlist": use_watchlist})
    rows = payload.get("signals", [])
    buys = [r for r in rows if r.get("signal")=="BUY"]
    sells= [r for r in rows if r.get("signal")=="SELL"]
    return {"n": len(rows), "buys": len(buys), "sells": len(sells)}

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--start", required=True)
    p.add_argument("--end", required=True)
    p.add_argument("--mode", choices=["score_abs","rank"], default="score_abs")
    p.add_argument("--wl", type=int, default=1)
    args = p.parse_args()

    res = run_once(args.start, args.end, args.mode, bool(args.wl))
    ts  = time.strftime("%Y%m%d-%H%M%S")
    out = Path("reports/backtests"); out.mkdir(parents=True, exist_ok=True)
    with open(out/f"summary-{ts}.json","w",encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    print(res)

if __name__ == "__main__":
    raise SystemExit(main())
