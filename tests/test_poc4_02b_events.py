"""POC4-02B 사건 · 분류 · 경보 run · RANDOM_NULL · 판정 (PLAN §5 · §7 · 확정 B1·B5~B8·B12).

순수 함수만 — DB 를 열지 않는다. 난수는 seed 고정.
"""

from __future__ import annotations

import random
from datetime import date, timedelta

import pytest

from app import ml_ew_events as ev
from app import ml_ew_report as rp
from app import ml_ew_signals as sg


def _chain_one_event(n: int = 40) -> list[float]:
    chain = [100.0] * n
    chain[11], chain[12], chain[13], chain[14] = 103.0, 101.0, 97.0, 96.0
    return chain


def _weekdays(n: int, start: date) -> list[str]:
    out, d = [], start
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


# --- label · 사건 ----------------------------------------------------------------------


def test_dd10_uses_legacy_function_and_label_days():
    chain = _chain_one_event()
    dd = ev.future_drawdowns([f"d{i}" for i in range(40)], chain)
    assert dd[-10:] == [None] * 10 and dd[29] is not None
    assert ev.last_computable(dd) == 29
    assert dd[4] == pytest.approx(96.0 / 103.0 - 1.0)
    assert dd[12] == pytest.approx(96.0 / 101.0 - 1.0)  # −4.95% → label 아님
    assert ev.label_days(dd) == list(range(3, 12))


def test_grouping_gap_9_merges_and_gap_10_splits():
    assert ev.group_label_days([10, 19]) == [[10, 19]]
    assert ev.group_label_days([10, 20]) == [[10], [20]]
    assert ev.group_label_days([1, 2, 12, 30, 39, 49]) == [[1, 2], [12], [30, 39], [49]]


def test_event_p_t_b_depth():
    chain = _chain_one_event()
    dd = ev.future_drawdowns([f"d{i}" for i in range(40)], chain)
    (e,) = ev.build_events(chain, dd, d0=0)
    assert (e["first"], e["last"], e["label_days"]) == (3, 11, 9)
    assert (e["peak"], e["trough"], e["breach"]) == (11, 14, 13)
    assert e["depth"] == pytest.approx(96.0 / 103.0 - 1.0)
    assert e["status"] == ev.EVALUABLE


def test_trough_and_peak_ties_take_earliest():
    chain = [100.0] * 40
    chain[5] = chain[6] = 110.0
    chain[8] = chain[10] = 95.0
    chain[9] = 96.0
    dd = ev.future_drawdowns([f"d{i}" for i in range(40)], chain)
    assert dd[7] == -0.05  # 경계 포함 (≤ −5%)
    (e,) = ev.build_events(chain, dd, d0=0)
    assert (e["first"], e["last"]) == (0, 7)
    assert e["peak"] == 5  # 같은 최고가 두 날(5·6) → 이른 날
    assert e["trough"] == 8  # 같은 최저가 두 날(8·10) → 이른 날
    assert e["breach"] == 7  # 100 ≤ 0.95 × 110


def test_breach_none_when_window_low_comes_first():
    # [F, Last+10] 의 최저가 앞쪽이면 T 가 앞에 오고 B 가 없을 수 있다(계약 §5 그대로).
    chain = [100.0] * 13 + [115.0] * 27
    chain[3], chain[10], chain[11], chain[12] = 99.0, 120.0, 118.0, 113.0
    dd = ev.future_drawdowns([f"d{i}" for i in range(40)], chain)
    (e,) = ev.build_events(chain, dd, d0=0)
    assert (e["first"], e["last"], e["trough"], e["peak"]) == (2, 10, 3, 2)
    assert e["breach"] is None and e["depth"] == pytest.approx(-0.01)


def test_right_censored_and_pre_window_unavailable():
    chain = _chain_one_event()
    dd = ev.future_drawdowns([f"d{i}" for i in range(40)], chain)
    (e,) = ev.build_events(chain, dd, d0=2)
    assert e["status"] == ev.PRE_WINDOW_UNAVAILABLE  # P−10 = 1 < D_0 = 2
    assert ev.build_events(chain, dd, d0=1)[0]["status"] == ev.EVALUABLE
    assert ev.build_events(chain, dd, d0=None)[0]["status"] == ev.PRE_WINDOW_UNAVAILABLE
    tail = [100.0] * 40
    tail[25], tail[28] = 104.0, 97.0  # label 일이 끝(29)까지 · Last + 9 > 29
    ddt = ev.future_drawdowns([f"d{i}" for i in range(40)], tail)
    (c,) = ev.build_events(tail, ddt, d0=0)
    assert c["last"] + ev.MERGE_GAP > ev.last_computable(ddt)
    assert c["status"] == ev.RIGHT_CENSORED_EVENT and c["right_censored"]
    # 잘린 사건은 관측 구간 전체 [F−10, 구간 끝] 를 제외 창으로 쓴다 (판정 §8)
    assert c["first"] < c["peak"]
    assert ev.event_window(c, 29) == (c["first"] - 10, 29)
    assert ev.event_window(e, 29) == (1, 14)


# --- 분류 -------------------------------------------------------------------------------


EVENT = {"event_id": 1, "peak": 20, "trough": 25, "breach": 23, "depth": -0.1}


@pytest.mark.parametrize(
    "alert_at, cls, lead, lead_b",
    [
        (12, ev.PRE, 8, 11),
        (10, ev.PRE, 10, 13),
        (19, ev.PRE, 1, 4),
        (20, ev.POST, 0, 3),
        (25, ev.POST, -5, -2),
        (9, ev.MISSED, None, None),
        (26, ev.MISSED, None, None),
    ],
)
def test_classification_and_lead(alert_at, cls, lead, lead_b):
    alerts = [False] * 40
    alerts[alert_at] = True
    got = ev.classify_event(alerts, EVENT)
    assert (got["class"], got["lead"], got["lead_vs_b"]) == (cls, lead, lead_b)


def test_event_summary_counts_median_share_severe():
    events = [
        {
            "event_id": i,
            "peak": 20 + 30 * i,
            "trough": 25 + 30 * i,
            "breach": None,
            "depth": d,
        }
        for i, d in enumerate([-0.05, -0.20, -0.08, -0.30], start=0)
    ]
    alerts = [False] * 200
    alerts[15] = True  # 사건 0 사전 (lead 5)
    alerts[52] = True  # 사건 1 시작 후 (lead −2)
    alerts[73] = True  # 사건 2 사전 (lead 7)
    got = ev.event_summary(alerts, events)
    assert (got["pre_capture"], got["post_only"], got["missed"]) == (2, 1, 1)
    assert got["captured"] == 3 and got["lead_median"] == 5.0
    assert got["pre_share"] == pytest.approx(2 / 3)
    # 깊이 25% 분위(선형) = −0.30×0.25 + −0.20×0.75 = −0.225 · 이하 = 사건 3(−0.30)
    assert got["severe_threshold_depth"] == pytest.approx(-0.225)
    assert got["severe_events"] == [3] and got["severe_missed"] == 1
    empty = ev.event_summary(alerts, [])
    assert empty["lead_median"] is None and empty["pre_share"] is None
    assert empty["severe_missed"] == 0


# --- 경보 run ---------------------------------------------------------------------------


def test_runs_true_excluded_false_precision_and_false_alarm_rate():
    n = 40
    alerts = [False] * n
    for i in (5, 6, 9, 10, 11, 28, 29, 30, 31, 37):
        alerts[i] = True
    eval_mask = ev.window_mask(n, [(10, 20)])
    excl_mask = ev.window_mask(n, [(30, 35)])
    got = ev.run_summary(alerts, eval_mask, excl_mask)
    assert ev.alert_runs(alerts) == [(5, 6), (9, 11), (28, 31), (37, 37)]
    assert (got["runs_true"], got["runs_false"], got["runs_excluded"]) == (1, 2, 1)
    assert got["run_precision"] == pytest.approx(1 / 3)
    assert got["alert_days_in_counted_runs"] == 6
    assert got["fa_runs_per_100_alerts"] == pytest.approx(2 / 6 * 100)
    days = ("alert_days_true", "alert_days_excluded", "false_alarm_days")
    assert [got[k] for k in days] == [2, 2, 6]
    assert got["day_precision"] == pytest.approx(2 / 8)
    none = ev.run_summary([False] * n, eval_mask, excl_mask)
    assert none["run_precision"] is None and none["fa_runs_per_100_alerts"] is None


def test_window_mask_clips_to_series():
    assert ev.window_mask(5, [(-3, 1), (4, 9)]) == [True, True, False, False, True]


# --- RANDOM_NULL ------------------------------------------------------------------------


def _null_inputs(seed: int = 4):
    dates = _weekdays(620, date(2014, 1, 1))
    rng = random.Random(seed)
    alerts, i = [False] * len(dates), 0
    while i < len(dates):
        if rng.random() < 0.15:
            length = rng.randint(1, 6)
            for j in range(i, min(i + length, len(dates))):
                alerts[j] = True
            i += length + 1
        else:
            i += 1
    eval_mask = ev.window_mask(len(dates), [(100, 130), (300, 320), (500, 540)])
    excl_mask = ev.window_mask(len(dates), [(590, 619)])
    return dates, alerts, eval_mask, excl_mask


def test_rotation_offsets_preserve_yearly_run_lengths():
    dates, alerts, _em, _xm = _null_inputs()
    segments = ev.year_segments(dates, 20, 610)
    assert [dates[s[0]][:4] for s in segments] == ["2014", "2015", "2016"]
    assert sum(len(s) for s in segments) == 591
    rng = random.Random(ev.NULL_SEED)
    for _ in range(50):
        shifted, _fallbacks = ev.shift_once(rng, alerts, segments)
        for seg in segments:
            before = ev.run_lengths([alerts[i] for i in seg])
            after = ev.run_lengths([shifted[i] for i in seg])
            assert before == after
        assert not any(shifted[i] for i in range(20)) and not any(shifted[611:])
    bits = [True, False, True, True, False, False]
    ok = ev.acceptable_offsets(bits)
    assert 0 in ok
    assert all(ev.run_lengths(ev.rotate(bits, o)) == [1, 2] for o in ok)
    assert ev.rotate([1, 2, 3, 4], 1) == [4, 1, 2, 3]


def test_draw_offset_falls_back_to_zero():
    rng = random.Random(1)
    assert ev.draw_offset(rng, 10, frozenset(), max_draws=5) == (0, True)
    off, fell = ev.draw_offset(random.Random(1), 10, frozenset(range(10)))
    assert not fell and 0 <= off < 10


def test_random_null_is_seed_reproducible_and_uses_same_windows():
    dates, alerts, em, xm = _null_inputs()
    a = ev.random_null(alerts, dates, 20, 610, em, xm, repeats=200)
    b = ev.random_null(alerts, dates, 20, 610, em, xm, repeats=200)
    assert a == b and a["seed"] == 20260925 and a["repeats"] == 200
    c = ev.random_null(alerts, dates, 20, 610, em, xm, repeats=200, seed=1)
    assert c["mean"] != a["mean"]
    # 같은 seed · 같은 이동으로 다시 계산한 분포의 95% 분위와 같다
    rng = random.Random(ev.NULL_SEED)
    segs = ev.year_segments(dates, 20, 610)
    precisions = []
    for _ in range(200):
        shifted, _f = ev.shift_once(rng, alerts, segs)
        precisions.append(ev.run_summary(shifted, em, xm)["run_precision"])
    assert a["p95"] == sg.bracketed_percentile(precisions, 95.0)
    empty = ev.random_null(alerts, dates, None, None, em, xm, repeats=3)
    assert empty["p95"] is None and empty["none_count"] == 3


# --- 판정 ---------------------------------------------------------------------------------


def _metrics(lead, pre, severe_missed, share, precision, fa, evaluable=5):
    return {
        "events": {
            "evaluable_events": evaluable,
            "lead_median": lead,
            "pre_capture": pre,
            "severe_missed": severe_missed,
            "pre_share": share,
        },
        "runs": {"run_precision": precision, "fa_runs_per_100_alerts": fa},
    }


def test_criteria_1_7_values():
    early = _metrics(3.0, 4, 0, 0.8, 0.5, 2.0)
    reactive = _metrics(1.0, 4, 1, 0.5, 0.4, 3.0)
    got = rp.criteria_1_7(early, reactive, {"p95": 0.45})
    assert [got[k]["value"] for k in "1234567"] == [True] * 7
    worse = rp.criteria_1_7(_metrics(1.0, 3, 2, 0.5, 0.4, 3.0), reactive, {"p95": 0.45})
    assert [worse[k]["value"] for k in "1234567"] == [False] * 7
    none = rp.criteria_1_7(
        _metrics(None, 0, 0, None, None, None, evaluable=0),
        _metrics(None, 0, 0, None, None, None, evaluable=0),
        {"p95": None},
    )
    assert [none[k]["value"] for k in "1234567"] == [None] * 7


def test_verdict_mapping_reject_vs_inconclusive():
    assert rp.verdict([True] * 10) == rp.PENDING
    assert rp.verdict([True] * 9 + [None]) == rp.INCONCLUSIVE
    assert rp.verdict([None] * 9 + [False]) == rp.REJECT
    assert rp.all_of([True, None]) is None and rp.all_of([None, False]) is False
    assert rp.all_of([]) is None and rp.all_of([True, True]) is True
    assert rp.final_verdict(rp.PENDING, True) == rp.PASS_CANDIDATE
    assert rp.final_verdict(rp.PENDING, False) == rp.REJECT
    assert rp.final_verdict(rp.INCONCLUSIVE, True) == rp.INCONCLUSIVE
    assert rp.final_verdict(rp.REJECT, True) == rp.REJECT


def test_variant_context_drops_event_window_to_excluded_and_year_days():
    dates = _weekdays(120, date(2025, 11, 3))
    events = [
        {"event_id": 1, "status": ev.EVALUABLE, "peak": 30, "trough": 35},
        {"event_id": 2, "status": ev.EVALUABLE, "peak": 80, "trough": 85},
        {"event_id": 3, "status": ev.RIGHT_CENSORED_EVENT, "peak": 105, "trough": 108},
    ]
    alerts = [False] * 120
    for i in (72, 73, 20):
        alerts[i] = True

    def runs(ctx):
        masked = rp.masked(alerts, ctx["included"])
        return ev.run_summary(masked, ctx["eval_mask"], ctx["excl_mask"])

    base = rp.context(events, dates, 5, 110)
    assert runs(base)["runs_true"] == 2
    loo = rp.context(events, dates, 5, 110, drop_events=frozenset({2}))
    got = runs(loo)
    assert (got["runs_true"], got["runs_excluded"], got["runs_false"]) == (1, 1, 0)
    assert [e["event_id"] for e in loo["evaluable"]] == [1]
    # 잘린 사건 창은 구간 끝까지 EXCLUDED
    assert base["excl_mask"][95] and base["excl_mask"][110]
    y = rp.context(events, dates, 5, 110, drop_year="2026")
    assert all(
        not inc for i, inc in enumerate(y["included"]) if dates[i].startswith("2026")
    )
    assert sum(y["included"]) == sum(1 for d in dates[5:111] if d.startswith("2025"))


def test_variants_exclude_2026_and_leave_one_out():
    dates = _weekdays(200, date(2025, 6, 2))
    events = [
        {
            "event_id": 1,
            "status": ev.EVALUABLE,
            "peak": 40,
            "trough": 45,
            "breach": None,
            "depth": -0.06,
        },
        {
            "event_id": 2,
            "status": ev.EVALUABLE,
            "peak": 170,
            "trough": 175,
            "breach": None,
            "depth": -0.09,
        },
    ]
    assert dates[170].startswith("2026") and dates[40].startswith("2025")
    early = [None] * 5 + [False] * 195
    react = [None] * 5 + [False] * 195
    early[35] = early[165] = True  # 두 사건 모두 사전
    react[42] = react[172] = True  # 두 사건 모두 시작 후
    got = rp.variants({sg.EARLY_PIT: early, sg.REACTIVE: react}, events, dates, 5, 189)
    ex = got["exclude_2026"]
    assert ex["dropped_events"] == [2] and ex["dropped_year"] == "2026"
    assert ex[sg.EARLY_PIT]["evaluable_events"] == 1
    # 2026 경보일이 빠져 두 신호 모두 run precision 1.0 → 조건 5(>) 는 false
    assert ex["core"] == {"1": True, "2": True, "5": False}
    assert ex["core_holds"] is False
    assert [v["dropped_events"] for v in got["leave_one_event_out"]] == [[1], [2]]
    assert [v["dropped_year"] for v in got["leave_one_year_out"]] == ["2025", "2026"]
    assert all(v["core"]["2"] is True for v in got["leave_one_event_out"])
