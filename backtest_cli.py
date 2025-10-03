#!/usr/bin/env python
# Robust Minimal backtest CLI v1 (KR cache schema tolerant)

import argparse, os, glob
from typing import List, Tuple, Optional
import pandas as pd
import numpy as np

CACHE_BASE = os.path.join("data", "cache", "kr")

# --- helpers -----------------------------------------------------------------

CANDIDATE_CLOSE_COLS = [
    "close", "Close", "CLOSE",
    "adj_close", "Adj Close", "adjClose", "AdjClose",
    "close_price", "ClosePrice", "종가",
]

def _to_dtindex(df: pd.DataFrame) -> pd.DataFrame:
    """Accepts (a) DatetimeIndex already, or (b) has 'date'/'Date' column."""
    if isinstance(df.index, pd.DatetimeIndex):
        return df.sort_index()
    for c in ["date", "Date", "DATE"]:
        if c in df.columns:
            d = df.copy()
            d[c] = pd.to_datetime(d[c])
            d = d.set_index(c)
            return d.sort_index()
    # last resort: try to parse any index to datetime (errors ignore)
    try:
        d = df.copy()
        d.index = pd.to_datetime(d.index, errors="coerce")
        d = d[~d.index.isna()]
        return d.sort_index()
    except Exception:
        return df

def _extract_close(df: pd.DataFrame) -> Optional[pd.Series]:
    """Find a reasonable 'close' series; tolerate common schema variants."""
    for c in CANDIDATE_CLOSE_COLS:
        if c in df.columns:
            s = df[c].astype(float)
            # some caches may store split-adjusted vs raw; either is fine
            return s
    # common nested schema: columns like ('close', 'price') or multiindex
    if isinstance(df.columns, pd.MultiIndex):
        # try level search
        for lvl in range(df.columns.nlevels):
            mask = df.columns.get_level_values(lvl).str.lower().str.contains("close", na=False)
            if mask.any():
                col = df.columns[mask][0]
                s = df[col].astype(float)
                return s
    return None

def load_universe(cache_base: str) -> List[Tuple[str, pd.DataFrame]]:
    files = sorted(glob.glob(os.path.join(cache_base, "*.pkl")))
    uni: List[Tuple[str, pd.DataFrame]] = []
    for fp in files:
        # skip known non-symbol files
        base = os.path.basename(fp)
        if base.lower().startswith("trading_days"):
            continue
        try:
            obj = pd.read_pickle(fp)
            if isinstance(obj, pd.Series):
                df = obj.to_frame(name="close")
            elif isinstance(obj, pd.DataFrame):
                df = obj
            elif isinstance(obj, dict):
                # tolerate dict-like payloads
                if "df" in obj and isinstance(obj["df"], (pd.DataFrame, pd.Series)):
                    df = obj["df"] if isinstance(obj["df"], pd.DataFrame) else obj["df"].to_frame("close")
                else:
                    # try any first DataFrame-like value
                    df = None
                    for v in obj.values():
                        if isinstance(v, pd.DataFrame):
                            df = v; break
                    if df is None:
                        continue
            else:
                continue

            df = _to_dtindex(df)
            s = _extract_close(df)
            if s is None:
                continue

            # clean
            s = s.replace([np.inf, -np.inf], np.nan).dropna()
            if s.empty:
                continue

            code = base.replace(".pkl", "")
            uni.append((code, s.to_frame("close")))
        except Exception:
            # ignore malformed file
            continue
    return uni

def weekly_rebalance_dates(idx: pd.DatetimeIndex) -> pd.DatetimeIndex:
    df = pd.DataFrame(index=idx)
    df["w"] = df.index.to_period("W-MON")
    firsts = df.groupby("w").apply(lambda x: x.index.min())
    return pd.DatetimeIndex(firsts.values)

# --- core --------------------------------------------------------------------

def backtest(start: str, end: str, mode: str, wl: int, top: int) -> pd.DataFrame:
    uni = load_universe(CACHE_BASE)
    if not uni:
        raise RuntimeError(
            f"No usable cache under {CACHE_BASE}. "
            f"Check .pkl schema (must include a close price column)."
        )

    # align on union of dates; we only use actual trading days
    frames = []
    for code, df in uni:
        d = df[(df.index >= start) & (df.index <= end)]
        if not d.empty:
            frames.append(d["close"].rename(code))
    if not frames:
        raise RuntimeError("No overlapping data in the selected range.")

    px = pd.concat(frames, axis=1, join="outer").sort_index()
    rets = px.pct_change().fillna(0.0)

    # momentum signal (wl-day return)
    sigs = px.pct_change(periods=wl)

    # weekly rebalance on first trading day of each W-MON period
    rb_days = weekly_rebalance_dates(px.index)
    rb_days = rb_days[(rb_days >= pd.to_datetime(start)) & (rb_days <= pd.to_datetime(end))]
    if len(rb_days) == 0:
        raise RuntimeError("No rebalance dates (check period).")

    nav = 1.0
    rows = []
    w = None

    for day in px.index:
        if day in rb_days:
            sig_today = sigs.loc[:day].iloc[-1]
            sig_today = sig_today.replace([np.inf, -np.inf], np.nan).dropna()
            if not sig_today.empty:
                picks = sig_today.sort_values(ascending=False).head(top).index
                w = pd.Series(1.0 / len(picks), index=picks)
            else:
                w = None

        r = 0.0 if w is None else rets.loc[day, w.index].fillna(0.0).dot(w.values)
        nav *= (1.0 + r)
        rows.append((day, nav, r))

    out = pd.DataFrame(rows, columns=["date", "nav", "ret"]).set_index("date")
    return out

def main():
    ap = argparse.ArgumentParser(description="Robust backtest runner (weekly rebalance, TopN equal-weight)")
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--mode", choices=["score_abs", "rank"], default="score_abs")
    ap.add_argument("--wl", type=int, default=63, help="lookback days (e.g., 63~126)")
    ap.add_argument("--top", type=int, default=5, help="Top N")
    ap.add_argument("--out", type=str, required=True, help="output CSV path")
    args = ap.parse_args()

    df = backtest(args.start, args.end, args.mode, args.wl, args.top)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    df.to_csv(args.out, index=True, date_format="%Y-%m-%d")
    print(f"[OK] saved: {args.out} rows={len(df)}")

if __name__ == "__main__":
    main()
