"""POC4-02B — 시점 기준 위험 점수 · 경보 (PLAN §6 · 확정 B2·B3·B9 · 구현 정의 2).

- 위험 percentile(축 · 날짜 t) = (t **이전** 날짜 값 중 현재보다 덜 위험한 수 + 0.5 × 같은 값 수) / 과거값 수.
  과거값(결측 제외) 60개 이상일 때만 · 0~1. t 의 값은 계산 뒤에 과거 목록에 넣는다(자기 자신 제외).
- EARLY_WARNING(주 평가 · B3 교정) — 축 12개(`distance_from_20d_high` 는 `drawdown_20d_market_proxy` 와 같은
  함수라 뺀다) · `short_term_weakness_proxy` 는 작을수록 위험(교정) · 있는 축 percentile 의 평균 · 축 3개 이상.
- REACTIVE_BASELINE — `drawdown_20d_market_proxy` 하나의 같은 percentile.
- 경보(B9) — 현재 점수 ≥ t 이전 점수들의 66.67 percentile(선형보간 · 과거 점수 60개 이상) · 경계 동점은 경보.
- 진단(LOOKAHEAD=true · 판정 미사용) — EXACT_K(구간 상위 int(일수/3)) · LEGACY_FULL_SAMPLE(기존
  `_compute_composite_scores` 를 수정 없이 호출 · 13축 · 전 종목 universe · 상위 1/3).

학습·threshold fit 없음 → purge·embargo `NOT_APPLICABLE_TO_NO_FIT_RULE`(B13).
"""

from __future__ import annotations

import bisect
import math
from typing import Optional, Sequence

from app.ml_baseline_risk import RISK_TERCILE, _compute_composite_scores, _RiskAsofRow
from app.ml_ew_market_axes import (
    LEGACY_AXES,
    VARIANT_ALL,
    VARIANT_FS,
    VARIANT_PIT,
    axes_for,
)
from app.ml_score_validity_metrics import mean, percentile

MIN_HISTORY = 60
MIN_AXES = 3
ALERT_PERCENTILE = 66.67
MIN_PRIOR_SCORES = 60

# (축, 클수록 위험) — PLAN §6 EARLY 12축.
EARLY_AXES = (
    ("volatility_20d_market_proxy", True),
    ("volatility_expansion_20d", True),
    ("down_day_volume_ratio", True),
    ("nav_discount_abs_avg", True),
    ("etf_universe_down_ratio", True),
    ("large_negative_day_proxy", True),
    ("breadth_deterioration_proxy", True),
    ("kodex200_return_5d", False),
    ("kodex200_return_20d", False),
    ("etf_universe_median_return_5d", False),
    ("drawdown_20d_market_proxy", False),
    ("short_term_weakness_proxy", False),
)
REACTIVE_AXIS = ("drawdown_20d_market_proxy", False)
DROPPED_DUPLICATE_AXIS = "distance_from_20d_high"

EARLY_PIT = "EARLY_PIT"
EARLY_FS = "EARLY_FS"
REACTIVE = "REACTIVE"
SIGNALS = (EARLY_PIT, EARLY_FS, REACTIVE)
PURGE_EMBARGO = "NOT_APPLICABLE_TO_NO_FIT_RULE"


def bracketed_percentile(values: Sequence[float], pct: float) -> Optional[float]:
    """`percentile`(선형보간 · numpy 기본) 값을 이웃 두 순서값 사이로 고정한다.

    이웃 두 값이 같으면 결과는 정확히 그 값이다 — 부동소수 보간 오차 때문에 경계 동점이
    경보·severe 에서 빠지지 않게 한다(수학적 값은 바뀌지 않는다).
    """
    got = percentile(values, pct)
    if got is None or len(values) < 2:
        return got
    ordered = sorted(values)
    pos = (len(ordered) - 1) * (pct / 100.0)
    lo, hi = ordered[math.floor(pos)], ordered[math.ceil(pos)]
    return min(max(got, lo), hi)


def risk_percentiles(
    values: Sequence[Optional[float]],
    higher_is_riskier: bool,
    min_history: int = MIN_HISTORY,
) -> list[Optional[float]]:
    """날짜별 시점 기준 위험 percentile (t 이전 결측 제외 값만)."""
    prior: list[float] = []
    out: list[Optional[float]] = []
    for v in values:
        if v is None:
            out.append(None)
            continue
        n = len(prior)
        if n >= min_history:
            left = bisect.bisect_left(prior, v)
            right = bisect.bisect_right(prior, v)
            less_risky = left if higher_is_riskier else n - right
            out.append((less_risky + 0.5 * (right - left)) / n)
        else:
            out.append(None)
        bisect.insort(prior, v)
    return out


def composite_scores(
    axes: dict[str, list[Optional[float]]],
    spec: Sequence[tuple[str, bool]] = EARLY_AXES,
    min_axes: int = MIN_AXES,
) -> list[Optional[float]]:
    """축별 percentile 의 평균 — 있는 축이 `min_axes` 개 이상일 때만."""
    per_axis = [risk_percentiles(axes[a], hi) for a, hi in spec]
    n = len(next(iter(axes.values()))) if axes else 0
    out: list[Optional[float]] = []
    for k in range(n):
        got = [p[k] for p in per_axis if p[k] is not None]
        out.append(mean(got) if len(got) >= min_axes else None)
    return out


def reactive_scores(axes: dict[str, list[Optional[float]]]) -> list[Optional[float]]:
    axis, higher = REACTIVE_AXIS
    return risk_percentiles(axes[axis], higher)


def point_in_time_alerts(
    scores: Sequence[Optional[float]],
    pct: float = ALERT_PERCENTILE,
    min_prior: int = MIN_PRIOR_SCORES,
) -> list[Optional[bool]]:
    """현재 점수 ≥ t 이전 점수의 pct 분위 → 경보. 점수 없음·과거 부족 → None(판정 불가)."""
    prior: list[float] = []
    out: list[Optional[bool]] = []
    for s in scores:
        if s is None:
            out.append(None)
            continue
        if len(prior) >= min_prior:
            out.append(s >= bracketed_percentile(prior, pct))
        else:
            out.append(None)
        bisect.insort(prior, s)
    return out


def exact_k_alerts(
    scores: Sequence[Optional[float]], lo: Optional[int], hi: Optional[int]
) -> tuple[list[bool], int]:
    """EXACT_K_DIAGNOSTIC — 구간 [lo, hi] 점수 상위 k = int(일수/3) 일 (동점은 이른 날 · LOOKAHEAD)."""
    alerts = [False] * len(scores)
    if lo is None or hi is None or hi < lo:
        return alerts, 0
    k = int((hi - lo + 1) / 3)
    cands = [i for i in range(lo, hi + 1) if scores[i] is not None]
    cands.sort(key=lambda i: (-scores[i], i))
    for i in cands[:k]:
        alerts[i] = True
    return alerts, k


def legacy_composite(dates: list[str], axes_all: dict) -> list[Optional[float]]:
    """기존 합성 점수 — `_compute_composite_scores` 를 수정 없이 호출(결함 그대로 · 전체 기간 순위)."""
    rows = [
        _RiskAsofRow(asof=d, values={a: axes_all[a][k] for a in LEGACY_AXES})
        for k, d in enumerate(dates)
    ]
    _compute_composite_scores(rows)
    return [r.composite_score for r in rows]


def legacy_top_third_alerts(
    composite: Sequence[Optional[float]], lo: Optional[int], hi: Optional[int]
) -> tuple[list[bool], int]:
    """LEGACY_FULL_SAMPLE_DIAGNOSTIC — 구간 안 합성 점수 상위 1/3 (기존과 같은 내림차순 안정 정렬 · k 식)."""
    alerts = [False] * len(composite)
    if lo is None or hi is None or hi < lo:
        return alerts, 0
    cands = [i for i in range(lo, hi + 1) if composite[i] is not None]
    if not cands:
        return alerts, 0
    ranked = sorted(cands, key=lambda i: composite[i], reverse=True)
    k = max(1, int(len(ranked) * RISK_TERCILE))
    for i in ranked[:k]:
        alerts[i] = True
    return alerts, k


def build_signals(axes: dict) -> dict:
    """신호 단계 출력 — 신호별 점수·경보 + legacy 합성 점수 (JSON 그대로 저장 가능)."""
    pit = axes_for(axes, VARIANT_PIT)
    fs = axes_for(axes, VARIANT_FS)
    scores = {
        EARLY_PIT: composite_scores(pit),
        EARLY_FS: composite_scores(fs),
        REACTIVE: reactive_scores(pit),
    }
    return {
        "scores": scores,
        "alerts": {name: point_in_time_alerts(s) for name, s in scores.items()},
        "legacy_composite": legacy_composite(
            axes["dates"], axes_for(axes, VARIANT_ALL)
        ),
    }


def first_defined(*alert_series: Sequence[Optional[bool]]) -> Optional[int]:
    """모든 신호의 경보 판정이 가능한 첫 index (D_0)."""
    n = min(len(a) for a in alert_series)
    for k in range(n):
        if all(a[k] is not None for a in alert_series):
            return k
    return None


def config() -> dict:
    return {
        "min_history": MIN_HISTORY,
        "min_axes": MIN_AXES,
        "alert_percentile": ALERT_PERCENTILE,
        "min_prior_scores": MIN_PRIOR_SCORES,
        "early_axes": [list(x) for x in EARLY_AXES],
        "reactive_axis": list(REACTIVE_AXIS),
        "dropped_duplicate_axis": DROPPED_DUPLICATE_AXIS,
        "legacy_tercile": RISK_TERCILE,
        "purge_embargo": PURGE_EMBARGO,
    }
