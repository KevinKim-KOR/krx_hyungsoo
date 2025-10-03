# tools/bootstrap_cache_pc.py
# -*- coding: utf-8 -*-
"""
KR 코드(예: 005930)를 받아 야후(코드.KS)에서 종가를 가져와
data/cache/kr/<code>.pkl 로 저장합니다.
"""
import os, sys, argparse, datetime as dt
import pandas as pd

def guess_symbol(code: str) -> str:
    # 숫자 6자리면 .KS 붙이기
    c = code.strip()
    return c if not c.isdigit() else f"{c}.KS"

def fetch_close(symbol: str, start="2018-01-01"):
    import yfinance as yf
    df = yf.download(symbol, start=start, progress=False, auto_adjust=True, threads=False)
    if df is None or df.empty:
        return None
    out = pd.DataFrame({"date": df.index.tz_localize(None).date, "close": df["Close"].astype(float).values})
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--codes", default="005930,000660,069500,091160,133690,305720")
    ap.add_argument("--start", default="2018-01-01")
    args = ap.parse_args()

    os.makedirs(os.path.join("data","cache","kr"), exist_ok=True)
    codes = [c.strip() for c in args.codes.split(",") if c.strip()]
    ok, fail = 0, []
    for code in codes:
        sym = guess_symbol(code)
        df = fetch_close(sym, start=args.start)
        if df is None or df.empty:
            fail.append(code); continue
        pkl = os.path.join("data","cache","kr", f"{code}.pkl")
        df.to_pickle(pkl)
        print(f"[OK] {code} <- {sym} rows={len(df)} -> {pkl}")
        ok += 1
    if fail:
        print("[WARN] 실패:", ",".join(fail))
    print(f"DONE ok={ok} fail={len(fail)}")

if __name__ == "__main__":
    raise SystemExit(main())
