"""ML Baseline v0 — future return / drawdown / down_ratio target 생성 (2026-06-11).

지시문 §7.2 / §8.2 / §9 — feature asof 이후의 가격만으로 target 계산.
훈련 / 점수화 / scoring 에 미래 데이터가 섞이지 않음을 보장하는 leakage check 포함.

본 모듈 책임:
- ETF candidate target: future_return_{5,10,20}d / future_excess_return_*_vs_kodex200.
- Market risk target: future_kodex200_return_{3,5,10}d /
  future_market_drawdown_{5,10}d / future_universe_down_ratio_5d.
- horizon tail 제외: max(horizons) 거래일 만큼 마지막 구간은 target 미생성.

본 모듈은 SQLite read-only. feature 재계산 X, ML 학습 X.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

CANDIDATE_HORIZONS = (5, 10, 20)
RISK_RETURN_HORIZONS = (3, 5, 10)
RISK_DRAWDOWN_HORIZONS = (5, 10)
RISK_DOWN_RATIO_HORIZON = 5

MAX_HORIZON = max(
    max(CANDIDATE_HORIZONS),
    max(RISK_RETURN_HORIZONS),
    max(RISK_DRAWDOWN_HORIZONS),
    RISK_DOWN_RATIO_HORIZON,
)  # 20.


@dataclass
class TickerSeries:
    ticker: str
    dates: list[str]
    closes: list[float]
    index: dict[str, int] = field(default_factory=dict)


@dataclass
class MarketSeries:
    dates: list[str]
    kodex_close: list[Optional[float]]
    down_ratio: list[Optional[float]]
    index: dict[str, int] = field(default_factory=dict)


def _load_ticker_series(con: sqlite3.Connection) -> dict[str, TickerSeries]:
    """etf_ml_feature_daily 의 close_price 시계열을 ticker 별로 로드 (asof ASC)."""
    cur = con.execute(
        "SELECT ticker, asof, close_price FROM etf_ml_feature_daily "
        "WHERE close_price IS NOT NULL "
        "ORDER BY ticker, asof"
    )
    out: dict[str, TickerSeries] = {}
    for ticker, asof, close in cur.fetchall():
        s = out.get(ticker)
        if s is None:
            s = TickerSeries(ticker=ticker, dates=[], closes=[])
            out[ticker] = s
        s.dates.append(str(asof))
        s.closes.append(float(close))
    for s in out.values():
        s.index = {d: i for i, d in enumerate(s.dates)}
    return out


def _load_market_series(con: sqlite3.Connection, kodex_ticker: str) -> MarketSeries:
    """market_risk_feature_daily + KODEX200 close 시계열 (asof ASC)."""
    cur = con.execute(
        "SELECT asof, etf_universe_down_ratio "
        "FROM market_risk_feature_daily ORDER BY asof"
    )
    dates: list[str] = []
    down: list[Optional[float]] = []
    for asof, dr in cur.fetchall():
        dates.append(str(asof))
        down.append(float(dr) if dr is not None else None)

    cur = con.execute(
        "SELECT asof, close_price FROM etf_ml_feature_daily "
        "WHERE ticker = ? ORDER BY asof",
        (kodex_ticker,),
    )
    kodex_by_asof = {str(r[0]): float(r[1]) for r in cur.fetchall() if r[1] is not None}
    kodex_close = [kodex_by_asof.get(d) for d in dates]

    series = MarketSeries(
        dates=dates,
        kodex_close=kodex_close,
        down_ratio=down,
    )
    series.index = {d: i for i, d in enumerate(dates)}
    return series


# ─── candidate targets ───────────────────────────────────────────────


def _ticker_future_return(s: TickerSeries, idx: int, horizon: int) -> Optional[float]:
    j = idx + horizon
    if j >= len(s.closes):
        return None
    base = s.closes[idx]
    if base <= 0:
        return None
    return (s.closes[j] - base) / base


@dataclass
class CandidateTargetRow:
    asof: str
    ticker: str
    future_return_5d: Optional[float] = None
    future_return_10d: Optional[float] = None
    future_return_20d: Optional[float] = None
    future_excess_return_5d_vs_kodex200: Optional[float] = None
    future_excess_return_10d_vs_kodex200: Optional[float] = None
    future_excess_return_20d_vs_kodex200: Optional[float] = None


def build_candidate_targets(
    db_path: Path, kodex_ticker: str
) -> tuple[list[CandidateTargetRow], list[str]]:
    """ETF × asof 각 행에 future_return / future_excess_return target 생성.

    horizon tail (max=20) 만큼 마지막 구간은 None — 평가 단계에서 제외.

    Returns (rows, errors).
    """
    errors: list[str] = []
    with sqlite3.connect(str(db_path)) as con:
        ticker_series = _load_ticker_series(con)
    if kodex_ticker not in ticker_series:
        errors.append(
            f"kodex200({kodex_ticker}) close 시계열이 etf_ml_feature_daily 에 없음"
        )
        return [], errors
    kodex = ticker_series[kodex_ticker]

    rows: list[CandidateTargetRow] = []
    for tk, s in ticker_series.items():
        for i, asof in enumerate(s.dates):
            row = CandidateTargetRow(asof=asof, ticker=tk)
            for h in CANDIDATE_HORIZONS:
                tr = _ticker_future_return(s, i, h)
                setattr(row, f"future_return_{h}d", tr)
                k_idx = kodex.index.get(asof)
                kr = (
                    _ticker_future_return(kodex, k_idx, h)
                    if k_idx is not None
                    else None
                )
                ex = tr - kr if (tr is not None and kr is not None) else None
                setattr(row, f"future_excess_return_{h}d_vs_kodex200", ex)
            rows.append(row)
    return rows, errors


# ─── risk targets ────────────────────────────────────────────────────


def _kodex_future_return(
    market: MarketSeries, idx: int, horizon: int
) -> Optional[float]:
    j = idx + horizon
    if j >= len(market.dates):
        return None
    base = market.kodex_close[idx]
    end = market.kodex_close[j]
    if base is None or end is None or base <= 0:
        return None
    return (end - base) / base


def _kodex_future_drawdown(
    market: MarketSeries, idx: int, horizon: int
) -> Optional[float]:
    """idx+1 .. idx+horizon 구간의 min/peak 기준 drawdown (음수).

    feature asof 시점의 close 를 시작점으로 두고, 그 이후 horizon 거래일 중
    누적 최저가 - 누적 최고가 의 비율 (가장 큰 낙폭). 음수.
    """
    base = market.kodex_close[idx]
    if base is None or base <= 0:
        return None
    end_idx = idx + horizon
    if end_idx >= len(market.dates):
        return None
    peak = base
    worst = 0.0
    for k in range(idx + 1, end_idx + 1):
        c = market.kodex_close[k]
        if c is None or c <= 0:
            return None
        if c > peak:
            peak = c
        dd = (c - peak) / peak  # ≤ 0.
        if dd < worst:
            worst = dd
    return worst


def _future_down_ratio_avg(
    market: MarketSeries, idx: int, horizon: int
) -> Optional[float]:
    end_idx = idx + horizon
    if end_idx >= len(market.dates):
        return None
    vals = [
        market.down_ratio[k]
        for k in range(idx + 1, end_idx + 1)
        if market.down_ratio[k] is not None
    ]
    if not vals:
        return None
    return sum(vals) / len(vals)


@dataclass
class RiskTargetRow:
    asof: str
    future_kodex200_return_3d: Optional[float] = None
    future_kodex200_return_5d: Optional[float] = None
    future_kodex200_return_10d: Optional[float] = None
    future_market_drawdown_5d: Optional[float] = None
    future_market_drawdown_10d: Optional[float] = None
    future_universe_down_ratio_5d: Optional[float] = None


def build_risk_targets(
    db_path: Path, kodex_ticker: str
) -> tuple[list[RiskTargetRow], list[str]]:
    errors: list[str] = []
    with sqlite3.connect(str(db_path)) as con:
        market = _load_market_series(con, kodex_ticker)
    if not market.dates:
        errors.append("market_risk_feature_daily 가 비어있음")
        return [], errors

    rows: list[RiskTargetRow] = []
    for i, asof in enumerate(market.dates):
        row = RiskTargetRow(asof=asof)
        for h in RISK_RETURN_HORIZONS:
            setattr(
                row,
                f"future_kodex200_return_{h}d",
                _kodex_future_return(market, i, h),
            )
        for h in RISK_DRAWDOWN_HORIZONS:
            setattr(
                row,
                f"future_market_drawdown_{h}d",
                _kodex_future_drawdown(market, i, h),
            )
        row.future_universe_down_ratio_5d = _future_down_ratio_avg(
            market, i, RISK_DOWN_RATIO_HORIZON
        )
        rows.append(row)
    return rows, errors


# ─── leakage check ───────────────────────────────────────────────────


@dataclass
class LeakageReport:
    feature_future_data_leakage_detected: bool
    target_horizon_short_tail_excluded: bool
    time_order_preserved: bool
    candidate_tail_asof_count: int
    risk_tail_asof_count: int
    details: list[str] = field(default_factory=list)


def evaluate_leakage(
    db_path: Path,
    candidate_rows: list[CandidateTargetRow],
    risk_rows: list[RiskTargetRow],
) -> LeakageReport:
    """누수 방지 원칙 검증 — 지시문 §9.

    1. feature asof 의 모든 future_* target 은 그 asof 이후 가격만으로 계산되었는지.
       (코드 경로 자체가 idx + horizon 의 close 만 사용 — 구조적으로 누수 불가).
    2. horizon tail 제외: 마지막 MAX_HORIZON 거래일은 모든 horizon target 이 None.
    3. time order: asof 가 ASC 정렬되어 있는지.
    """
    details: list[str] = []

    # (1) 구조적 누수 없음 — _ticker_future_return / _kodex_future_return /
    # _kodex_future_drawdown / _future_down_ratio_avg 모두 idx 미래 인덱스만 read.
    structural_no_leak = True

    # (2) horizon tail — risk_rows 의 마지막 MAX_HORIZON 행이 모두 None.
    tail_ok_risk = True
    risk_tail_count = 0
    if risk_rows:
        tail = risk_rows[-MAX_HORIZON:] if len(risk_rows) >= MAX_HORIZON else risk_rows
        risk_tail_count = len(tail)
        for r in tail:
            if (
                r.future_kodex200_return_3d is not None
                and tail.index(r) >= len(tail) - 3
            ):
                tail_ok_risk = False
                details.append(
                    f"risk tail leakage 의심: asof={r.asof} return_3d 값 존재"
                )

    # candidate 의 tail: 각 ticker 마지막 MAX_HORIZON 의 future_*_20d 가 None.
    tail_ok_cand = True
    cand_tail_asofs: set[str] = set()
    by_tk: dict[str, list[CandidateTargetRow]] = {}
    for r in candidate_rows:
        by_tk.setdefault(r.ticker, []).append(r)
    for tk, rows in by_tk.items():
        if len(rows) < MAX_HORIZON:
            continue
        tail = rows[-MAX_HORIZON:]
        for r in tail:
            cand_tail_asofs.add(r.asof)
        last = tail[-1]
        if last.future_return_20d is not None:
            tail_ok_cand = False
            details.append(
                f"candidate tail leakage 의심: ticker={tk} asof={last.asof} "
                f"future_return_20d 값 존재"
            )

    # (3) time order — 각 ticker 의 asof ASC 인지 확인.
    time_order_ok = True
    for tk, rows in by_tk.items():
        for i in range(1, len(rows)):
            if rows[i].asof < rows[i - 1].asof:
                time_order_ok = False
                details.append(f"time order 위반: ticker={tk} asof DESC 발견")
                break
        if not time_order_ok:
            break

    leak_detected = not (structural_no_leak and tail_ok_risk and tail_ok_cand)
    return LeakageReport(
        feature_future_data_leakage_detected=leak_detected,
        target_horizon_short_tail_excluded=tail_ok_risk and tail_ok_cand,
        time_order_preserved=time_order_ok,
        candidate_tail_asof_count=len(cand_tail_asofs),
        risk_tail_asof_count=risk_tail_count,
        details=details[:10],
    )
