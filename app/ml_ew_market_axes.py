"""POC4-02B — 봉인 KRX → 시장일 위험 축 13개 (PLAN §6 · 확정 B4·B10 · 구현 정의 6).

기존 `app/ml_feature_builder.py`(:188-434)의 시장 위험 축 정의를 그대로 옮긴다. 다른 점은 입력뿐이다.

- 가격 = 069500 `KRX_BASEPRICE_CHAIN`(분배 중립 연결 계열 · 공용 reader) · 단위 %(수익률·낙폭·일간 변동) ·
  변동성 = 일간 % 수익률의 `statistics.stdev`. 069500 축은 기존 `app/ml_feature_primitives` 함수를
  연결 계열로 만든 `PriceSeries` 에 **그대로** 불러 계산한다(재구현하지 않는다).
- 거래량 = `ACC_TRDVOL` · NAV 괴리 = 같은 날 |(TDD_CLSPRC − NAV) / NAV| × 100.
- universe(날짜 t) = t 에 행이 있고 자기 계열에서 앞 행도 있는 ETF(기존 builder 의 "idx < 1 이면 건너뜀") ·
  069500 포함. 변형 — PIT(주): t 행 ISU_NM 으로 인버스·레버리지(2X·2배)·합성·선물 제외 /
  FS: PIT 중 봉인 최종일에도 행이 있는 ETF / ALL: 이름 필터 없음(legacy 진단 전용).
- ETF 일간 변동 = reader 의 `daily_return × 100`(FLUC_RT 검증 통과 · 같은 연결 구간일 때만) ·
  5일 수익률 = 같은 구간 안 연결값 5행 전 대비.

하지 않는 것 — 봉인 DB 쓰기 · 운영 DB 접근 · 보간·이월 · 새 factor.
"""

from __future__ import annotations

import statistics
from typing import Optional

from app.krx_sealed_reader import BENCHMARK_CODE, CLOSE_OK, CodeSeries, SealedPanel
from app.market_topn_helpers import classify_etf_tags
from app.ml_baseline_risk import RISK_COMPOSITE_AXES
from app.ml_feature_primitives import (
    WINDOW_5,
    WINDOW_20,
    PriceSeries,
    build_series,
    daily_returns,
    distance_from_20d_high,
    drawdown_20d,
    return_pct,
    volatility_20d,
    volume_ratio_20d,
)
from app.ml_score_validity_eval import is_filter_universe

# 기존 합성 점수의 13축(순서 그대로) — legacy 진단 입력.
LEGACY_AXES = tuple(axis for axis, _ in RISK_COMPOSITE_AXES)
UNIVERSE_AXES = (
    "etf_universe_down_ratio",
    "breadth_deterioration_proxy",
    "etf_universe_median_return_5d",
    "nav_discount_abs_avg",
)
KODEX_AXES = tuple(a for a in LEGACY_AXES if a not in UNIVERSE_AXES)

VARIANT_PIT = "PIT"
VARIANT_FS = "FS"
VARIANT_ALL = "ALL"
VARIANTS = (VARIANT_PIT, VARIANT_FS, VARIANT_ALL)

# app/ml_feature_builder.SHORT_WEAKNESS_WINDOW 과 같은 값 (builder 는 운영 DB 모듈을 import 하므로
# 여기서 import 하지 않는다).
SHORT_WEAKNESS_WINDOW = 3
FIVE_DAY_WINDOW = 5


class AxesError(RuntimeError):
    """축을 만들 수 없는 입력 — 069500 이 모든 거래일을 덮지 않거나 연결 계열이 끊김."""


# --- 069500 축 ------------------------------------------------------------------


def benchmark_chain(panel: SealedPanel) -> CodeSeries:
    """069500 계열 — 모든 거래일에 행이 있고 연결 계열이 한 구간이어야 한다."""
    bench = panel.benchmark()
    if bench.dates != panel.dates:
        raise AxesError(
            f"{BENCHMARK_CODE} 가 모든 거래일을 덮지 않는다: "
            f"{len(bench.dates)} / {len(panel.dates)}"
        )
    if any(c is None for c in bench.chain) or len(set(bench.segment)) != 1:
        raise AxesError(
            f"{BENCHMARK_CODE} 연결 계열이 끊겼다 (구간 {len(set(bench.segment))})"
        )
    return bench


def _kodex_row(series: PriceSeries, k: int) -> dict[str, Optional[float]]:
    """기존 builder 의 KODEX200 축 계산을 그대로 옮긴 것 (k = 거래일 index)."""
    closes = series.closes
    change = (
        (closes[k] / closes[k - 1] - 1.0) * 100.0
        if k >= 1 and closes[k - 1] > 0
        else None
    )
    rets20 = daily_returns(series, k, WINDOW_20)
    vol20 = volatility_20d(series, k)
    rets5 = daily_returns(series, k, WINDOW_5)
    vol5 = statistics.stdev(rets5) if len(rets5) >= 2 else None
    kvr = volume_ratio_20d(series, k)
    is_down = change is not None and change < 0
    recent = daily_returns(series, k, SHORT_WEAKNESS_WINDOW)
    if len(recent) == SHORT_WEAKNESS_WINDOW and all(r < 0 for r in recent):
        weak: Optional[float] = sum(recent)
    else:
        weak = 0.0 if recent else None
    return {
        "kodex200_return_5d": return_pct(series, k, WINDOW_5),
        "kodex200_return_20d": return_pct(series, k, WINDOW_20),
        "volatility_20d_market_proxy": (
            statistics.stdev(rets20) if len(rets20) >= 2 else None
        ),
        "drawdown_20d_market_proxy": drawdown_20d(series, k),
        "distance_from_20d_high": distance_from_20d_high(series, k),
        "volatility_expansion_20d": (
            vol5 / vol20
            if (vol5 is not None and vol20 is not None and vol20 > 0)
            else None
        ),
        "down_day_volume_ratio": kvr if is_down else None,
        "large_negative_day_proxy": (
            abs(change) * kvr if is_down and kvr is not None else None
        ),
        "short_term_weakness_proxy": weak,
    }


def kodex_axes(
    dates: list[str], chain: list[float], volume: list[Optional[float]]
) -> dict[str, list[Optional[float]]]:
    series = build_series(BENCHMARK_CODE, list(zip(dates, chain, volume)))
    out: dict[str, list[Optional[float]]] = {a: [] for a in KODEX_AXES}
    for k in range(len(dates)):
        row = _kodex_row(series, k)
        for axis in KODEX_AXES:
            out[axis].append(row[axis])
    return out


# --- universe 축 ----------------------------------------------------------------


class _Acc:
    """하루 · 한 universe 변형의 집계 — 기존 builder 의 breadth · 중앙 수익률 · NAV 분포와 같다."""

    __slots__ = ("size", "up", "down", "flat", "five", "nav_abs")

    def __init__(self) -> None:
        self.size = 0
        self.up = self.down = self.flat = 0
        self.five: list[float] = []
        self.nav_abs: list[float] = []

    def add(
        self, daily: Optional[float], five: Optional[float], nav_abs: Optional[float]
    ) -> None:
        self.size += 1
        if daily is not None:
            if daily > 0.0:
                self.up += 1
            elif daily < 0.0:
                self.down += 1
            else:
                self.flat += 1
        if five is not None:
            self.five.append(five)
        if nav_abs is not None:
            self.nav_abs.append(nav_abs)

    def axes(self) -> dict[str, Optional[float]]:
        total = self.up + self.down + self.flat
        up_ratio = self.up / total if total > 0 else None
        down_ratio = self.down / total if total > 0 else None
        return {
            "etf_universe_down_ratio": down_ratio,
            "breadth_deterioration_proxy": (
                down_ratio - up_ratio
                if (down_ratio is not None and up_ratio is not None)
                else None
            ),
            "etf_universe_median_return_5d": (
                statistics.median(self.five) if self.five else None
            ),
            "nav_discount_abs_avg": (
                statistics.fmean(self.nav_abs) if self.nav_abs else None
            ),
        }


def _row_values(
    s: CodeSeries, i: int
) -> tuple[Optional[float], Optional[float], Optional[float]]:
    """(일간 %, 5일 %, |NAV 괴리| %) — 연결 구간을 넘는 값은 만들지 않는다."""
    daily = None
    if s.daily_return[i] is not None and s.segment[i] == s.segment[i - 1]:
        daily = s.daily_return[i] * 100.0
    five = None
    j = i - FIVE_DAY_WINDOW
    if j >= 0 and s.segment[j] == s.segment[i]:
        base, cur = s.chain[j], s.chain[i]
        if base is not None and cur is not None and base > 0:
            five = (cur / base - 1.0) * 100.0
    nav_abs = None
    nav, close = s.nav[i], s.close[i]
    if nav is not None and nav > 0 and s.close_status[i] == CLOSE_OK:
        nav_abs = abs((close - nav) / nav * 100.0)
    return daily, five, nav_abs


def universe_axes(panel: SealedPanel) -> tuple[dict, dict]:
    """변형별 universe 축 4개와 날짜별 universe 크기·일간 변동을 센 종목 수."""
    final_codes = panel.present(panel.final_date)
    passes: dict[str, bool] = {}
    values = {v: {a: [] for a in UNIVERSE_AXES} for v in VARIANTS}
    sizes = {v: {"universe": [], "daily_counted": []} for v in VARIANTS}
    for date in panel.dates:
        acc = {v: _Acc() for v in VARIANTS}
        for code in sorted(panel.present(date)):
            s = panel.series[code]
            i = s.index[date]
            if i < 1:
                continue
            name = s.name[i]
            if name not in passes:
                passes[name] = is_filter_universe(classify_etf_tags(name))
            row = _row_values(s, i)
            acc[VARIANT_ALL].add(*row)
            if passes[name]:
                acc[VARIANT_PIT].add(*row)
                if code in final_codes:
                    acc[VARIANT_FS].add(*row)
        for v in VARIANTS:
            for axis, val in acc[v].axes().items():
                values[v][axis].append(val)
            sizes[v]["universe"].append(acc[v].size)
            sizes[v]["daily_counted"].append(acc[v].up + acc[v].down + acc[v].flat)
    return values, sizes


# --- 조립 -----------------------------------------------------------------------


def build_market_axes(panel: SealedPanel) -> dict:
    """축 단계 출력(JSON 그대로 저장 가능) — 날짜 · 연결 계열 · 069500 축 · 변형별 universe 축."""
    bench = benchmark_chain(panel)
    universe, sizes = universe_axes(panel)
    return {
        "dates": list(panel.dates),
        "chain": list(bench.chain),
        "kodex": kodex_axes(list(panel.dates), list(bench.chain), list(bench.volume)),
        "universe": universe,
        "universe_size": sizes,
    }


def axes_for(axes: dict, variant: str) -> dict[str, list[Optional[float]]]:
    """한 universe 변형의 13축 (069500 축 + 그 변형의 universe 축)."""
    merged = dict(axes["kodex"])
    merged.update(axes["universe"][variant])
    return {a: merged[a] for a in LEGACY_AXES}


def pit_minus_fs(axes: dict) -> dict:
    """universe 축 4개의 PIT − FS 차이 (둘 다 값이 있는 날만)."""
    out: dict = {}
    for axis in UNIVERSE_AXES:
        pit = axes["universe"][VARIANT_PIT][axis]
        fs = axes["universe"][VARIANT_FS][axis]
        diffs = [p - f for p, f in zip(pit, fs) if p is not None and f is not None]
        absd = [abs(d) for d in diffs]
        out[axis] = {
            "days_compared": len(diffs),
            "mean_diff": statistics.fmean(diffs) if diffs else None,
            "mean_abs_diff": statistics.fmean(absd) if absd else None,
            "median_abs_diff": statistics.median(absd) if absd else None,
            "max_abs_diff": max(absd) if absd else None,
        }
    return out


def config() -> dict:
    return {
        "legacy_axes": list(LEGACY_AXES),
        "universe_axes": list(UNIVERSE_AXES),
        "kodex_axes": list(KODEX_AXES),
        "variants": list(VARIANTS),
        "short_weakness_window": SHORT_WEAKNESS_WINDOW,
        "five_day_window": FIVE_DAY_WINDOW,
        "name_filter": "classify_etf_tags + is_filter_universe (t 행 ISU_NM)",
    }
