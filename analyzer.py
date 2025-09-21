import datetime as dt
from typing import Optional, Dict
import pandas as pd
from sqlalchemy import select
from tabulate import tabulate
from db import SessionLocal, PriceDaily, Security, Position
from fetchers import ensure_yahoo_ticker, fetch_eod_yf
from config import DEFAULT_BENCHMARK

def load_prices(session, start: Optional[dt.date], end: Optional[dt.date]) -> pd.DataFrame:
    q = select(PriceDaily)
    if start:
        q = q.where(PriceDaily.date >= start)
    if end:
        q = q.where(PriceDaily.date <= end)
    rows = session.execute(q).scalars().all()
    if not rows:
        return pd.DataFrame(columns=["code","date","close"])
    df = pd.DataFrame([{"code": r.code, "date": r.date, "close": r.close} for r in rows])
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values(["code","date"])

def calc_cumulative_return(nav: pd.Series) -> float:
    if nav.empty:
        return 0.0
    return float(nav.iloc[-1] / nav.iloc[0] - 1.0)

def portfolio_nav(prices: pd.DataFrame, weights: Dict[str,float]) -> pd.Series:
    wide = prices.pivot(index="date", columns="code", values="close").dropna(how="all").ffill()
    cols = [c for c in weights.keys() if c in wide.columns]
    if not cols:
        return pd.Series(dtype=float)
    norm = wide[cols] / wide[cols].iloc[0]
    wvec = pd.Series({c: weights[c] for c in cols})
    nav = (norm * wvec).sum(axis=1)
    return nav

def benchmark_series(session, benchmark_code: str, start: dt.date, end: dt.date) -> pd.Series:
    sec = session.execute(select(Security).where(Security.code==benchmark_code)).scalar_one_or_none()
    ticker = (sec.yahoo_ticker if sec and sec.yahoo_ticker else ensure_yahoo_ticker(benchmark_code, sec.market if sec else "KS"))
    df = fetch_eod_yf(ticker, start, end)
    if df.empty:
        return pd.Series(dtype=float)
    s = df.set_index(pd.to_datetime(df["date"]))["close"].dropna()
    s = s / s.iloc[0]
    return s

def report(start: Optional[str], end: Optional[str], benchmark: Optional[str], weights: Optional[Dict[str,float]]=None):
    start_d = pd.to_datetime(start).date() if start else None
    end_d = pd.to_datetime(end).date() if end else None

    with SessionLocal() as session:
        prices = load_prices(session, start_d, end_d)
        if prices.empty:
            print("가격 데이터가 없습니다. 먼저 app.py ingest-eod 를 실행하세요.")
            return

        if weights is None:
            poss = session.execute(select(Position)).scalars().all()
            weights = {p.code: float(p.weight) for p in poss} if poss else {}

        if not weights:
            codes = prices["code"].unique().tolist()
            if not codes:
                print("사용 가능한 종목이 없습니다.")
                return
            w = 1.0 / len(codes)
            weights = {c: w for c in codes}

        nav = portfolio_nav(prices, weights)
        port_cum = calc_cumulative_return(nav)

        bench_code = benchmark or DEFAULT_BENCHMARK
        bench = benchmark_series(session, bench_code, nav.index[0].date(), nav.index[-1].date()) if not nav.empty else pd.Series(dtype=float)
        bench = bench.reindex(nav.index).ffill()
        bench_cum = calc_cumulative_return(bench)

        rows = [
            ["기간", f"{nav.index[0].date()} ~ {nav.index[-1].date()}"] if not nav.empty else ["기간","-"],
            ["포트폴리오 누적수익률", f"{port_cum*100:.2f}%"],
            [f"벤치마크({bench_code}) 누적수익률", f"{bench_cum*100:.2f}%"],
            ["초과수익(포트 - 벤치)", f"{(port_cum-bench_cum)*100:.2f}%"]
        ]
        print(tabulate(rows, tablefmt="plain"))
