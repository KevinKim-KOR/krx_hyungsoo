"""POC4-02B 시점 기준 점수·경보 · 교정 3건 · 진단 (PLAN §6 · 확정 B2·B3·B9).

순수 함수만 — DB 를 열지 않는다. 난수는 seed 고정.
"""

from __future__ import annotations

import random

import pytest

from app import ml_ew_signals as sg
from app.ml_baseline_risk import (
    RISK_COMPOSITE_AXES,
    _compute_composite_scores,
    _RiskAsofRow,
)
from app.ml_ew_market_axes import LEGACY_AXES
from app.ml_score_validity_metrics import percentile

EARLY_NAMES = [a for a, _ in sg.EARLY_AXES]


def _random_axes(n: int, seed: int = 7, none_rate: float = 0.1) -> dict:
    rng = random.Random(seed)
    out = {}
    for axis in LEGACY_AXES:
        out[axis] = [
            None if rng.random() < none_rate else round(rng.gauss(0, 1), 3)
            for _ in range(n)
        ]
    return out


# --- 위험 percentile -------------------------------------------------------------------


def test_percentile_needs_60_prior_non_null_values():
    values = [None, None] + [float(i) for i in range(70)]
    got = sg.risk_percentiles(values, True)
    # 앞 None 2개 + 과거값 60개 미만인 날 60개는 None · 61번째 값(과거 60개)부터 계산
    assert all(v is None for v in got[:62])
    assert got[62] == pytest.approx(1.0)  # 60 이 과거 0..59 보다 커서 가장 위험
    assert got[-1] == pytest.approx(1.0)


def test_percentile_counts_ties_half_and_excludes_self():
    values = [1.0] * 60 + [1.0]
    got = sg.risk_percentiles(values, True)
    assert got[60] == pytest.approx(0.5)  # 같은 값 60개 → 0.5 · 자기 자신은 과거에 없음


def test_percentile_direction():
    values = [float(i) for i in range(60)] + [-5.0]
    # 클수록 위험 → 가장 작은 값은 안전 · 작을수록 위험 → 가장 위험
    assert sg.risk_percentiles(values, True)[60] == 0.0
    assert sg.risk_percentiles(values, False)[60] == 1.0


def test_scores_and_alerts_do_not_use_future_values():
    axes = _random_axes(260)
    base_scores = sg.composite_scores(axes)
    base_alerts = sg.point_in_time_alerts(base_scores)
    t = 200
    changed = {
        a: v[: t + 1]
        + [99.0 if x is not None else 5.0 for x in v[t + 1 :]]  # noqa: E203
        for a, v in axes.items()
    }
    new_scores = sg.composite_scores(changed)
    new_alerts = sg.point_in_time_alerts(new_scores)
    assert new_scores[: t + 1] == base_scores[: t + 1]
    assert new_alerts[: t + 1] == base_alerts[: t + 1]
    assert new_scores[t + 1 :] != base_scores[t + 1 :]  # noqa: E203
    react = sg.reactive_scores(axes)
    assert sg.reactive_scores(changed)[: t + 1] == react[: t + 1]


def test_early_score_needs_three_axes():
    axes = {a: [None] * 70 for a in LEGACY_AXES}
    axes["kodex200_return_5d"] = [float(i) for i in range(70)]
    axes["kodex200_return_20d"] = [float(i) for i in range(70)]
    assert all(s is None for s in sg.composite_scores(axes))
    axes["volatility_20d_market_proxy"] = [float(i) for i in range(70)]
    got = sg.composite_scores(axes)
    assert got[59] is None and got[60] is not None


# --- 경보 -----------------------------------------------------------------------------


def test_alert_needs_60_prior_scores():
    scores = [0.5] * 59 + [0.9, 0.9]
    got = sg.point_in_time_alerts(scores)
    assert all(a is None for a in got[:60])
    assert got[60] is True


def test_alert_ties_at_threshold_alert_even_with_float_interpolation():
    # 0.013 × 60 의 66.67 선형보간은 부동소수로 0.013 보다 조금 크다 — 경계 동점은 그래도 경보.
    assert percentile([0.013] * 60, 66.67) > 0.013
    got = sg.point_in_time_alerts([0.013] * 61)
    assert got[60] is True
    assert sg.bracketed_percentile([0.013] * 60, 66.67) == 0.013


def test_alert_threshold_is_prior_percentile():
    rng = random.Random(3)
    scores = [rng.random() for _ in range(120)]
    alerts = sg.point_in_time_alerts(scores)
    for t in (60, 90, 119):
        thr = percentile(scores[:t], sg.ALERT_PERCENTILE)
        assert alerts[t] == (scores[t] >= thr)


def test_none_score_is_undefined_alert_and_not_in_history():
    scores = [0.1] * 60 + [None, 0.2]
    got = sg.point_in_time_alerts(scores)
    assert got[60] is None and got[61] is True


# --- 교정 3건 (B3) -------------------------------------------------------------------


def test_correction_duplicate_drawdown_axis_removed():
    assert sg.DROPPED_DUPLICATE_AXIS not in EARLY_NAMES
    assert "drawdown_20d_market_proxy" in EARLY_NAMES
    assert len(sg.EARLY_AXES) == 12 and len(LEGACY_AXES) == 13
    axes = _random_axes(150)
    before = sg.composite_scores(axes)
    axes["distance_from_20d_high"] = [9.9] * 150
    assert sg.composite_scores(axes) == before


def test_correction_short_term_weakness_direction():
    legacy = dict(RISK_COMPOSITE_AXES)
    early = dict(sg.EARLY_AXES)
    assert legacy["short_term_weakness_proxy"] is True  # 기존 결함 — 음수 합이 안전 쪽
    assert early["short_term_weakness_proxy"] is False  # 교정 — 작을수록 위험
    hist = [0.0] * 60
    got = sg.risk_percentiles(hist + [-3.0], early["short_term_weakness_proxy"])
    assert got[60] == 1.0  # 3일 연속 하락(음수 합)이 가장 위험


def test_correction_normalization_sparse_axis_does_not_shift_score():
    rng = random.Random(11)
    n = 201
    dense = (
        "volatility_20d_market_proxy",
        "volatility_expansion_20d",
        "nav_discount_abs_avg",
    )
    sparse = "down_day_volume_ratio"
    axes = {a: [None] * n for a in LEGACY_AXES}
    for a in dense:
        vals = [float(v) for v in range(200)]
        rng.shuffle(vals)
        axes[a] = vals + [99.5]  # 마지막 날 = 과거 200개의 정확한 중간(percentile 0.5)
    sp = [float(v) for v in range(100)]
    rng.shuffle(sp)
    axes[sparse] = [sp[i // 2] if i % 2 == 0 else None for i in range(200)] + [49.5]
    with_sparse = sg.composite_scores(axes)[200]
    without = dict(axes)
    without[sparse] = axes[sparse][:200] + [None]
    assert with_sparse == 0.5 and sg.composite_scores(without)[200] == 0.5

    def legacy_last(ax):
        rows = [
            _RiskAsofRow(asof=f"d{i:03d}", values={a: ax[a][i] for a in LEGACY_AXES})
            for i in range(n)
        ]
        _compute_composite_scores(rows)
        return rows[-1].composite_score

    # 기존 합성은 값 있는 날이 적은 축이 있으면 위험 쪽으로 밀린다(순위 51 대 101).
    assert legacy_last(axes) > legacy_last(without)


# --- 진단 -----------------------------------------------------------------------------


def test_exact_k_top_third_ties_earliest_first():
    scores = [None, 0.9, 0.5, 0.9, 0.1, 0.9, 0.2, 0.3, 0.4, 0.6]
    alerts, k = sg.exact_k_alerts(scores, 1, 9)
    assert k == 3
    assert [i for i, a in enumerate(alerts) if a] == [1, 3, 5]
    alerts, k = sg.exact_k_alerts([0.7, 0.7, 0.7, 0.7, 0.7, 0.7], 0, 5)
    assert k == 2 and alerts == [True, True, False, False, False, False]
    assert sg.exact_k_alerts([0.1], None, None) == ([False], 0)


def test_legacy_top_third_uses_original_composite():
    axes = _random_axes(90, seed=5, none_rate=0.0)
    dates = [f"2014-01-{i:03d}" for i in range(90)]
    comp = sg.legacy_composite(dates, axes)
    rows = [
        _RiskAsofRow(asof=d, values={a: axes[a][i] for a in LEGACY_AXES})
        for i, d in enumerate(dates)
    ]
    _compute_composite_scores(rows)
    assert comp == [r.composite_score for r in rows]
    alerts, k = sg.legacy_top_third_alerts(comp, 30, 89)
    assert k == 20 and sum(alerts) == 20
    ranked = sorted(range(30, 90), key=lambda i: comp[i], reverse=True)
    chosen = ranked[:20]
    assert {i for i, a in enumerate(alerts) if a} == set(chosen)


def test_first_defined_needs_both_signals():
    a = [None, None, True, False]
    b = [None, False, None, True]
    assert sg.first_defined(a, b) == 3
    assert sg.first_defined([None], [None]) is None
