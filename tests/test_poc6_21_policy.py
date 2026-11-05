"""POC6-21 손계산 — 절대 정답 · 새 주간 규칙(문턱 · 최근 0/10/11거래일 · 이연 체결일 · 보호 우선 · 중복 취소 ·
비적격 보류) · 독립 감사 · 거래 · 묶음 · 회복 · 판정 축.

손으로 만든 작은 Panel 만 쓴다(봉인 DB · 라이브 DB · 학습 없음).
"""

from __future__ import annotations

import datetime as dt
import math

import numpy as np
import pytest

from app.trend_switch import audit as AU
from app.trend_switch import labels as LB
from app.trend_switch import policy as TP
from app.trend_switch import report as RP
from app.trend_switch import trades as TR
from app.weekly_selection import data as D
from app.weekly_selection import features as F
from app.weekly_selection import policy as PO

H = math.log(1.002 / 0.998)
C = 0.002


def _days(n: int) -> list[str]:
    d, out = dt.date(2024, 1, 1), []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += dt.timedelta(days=1)
    return out


def panel(closes: dict[str, list[float]], no_trade=(), no_row=()) -> D.Panel:
    codes = sorted(closes)
    I = np.array([closes[c] for c in codes], dtype=float)  # noqa: E741
    ok = np.ones(I.shape, dtype=bool)
    has = np.ones(I.shape, dtype=bool)
    for c, k in no_trade:
        ok[codes.index(c), k] = False
    for c, k in no_row:
        has[codes.index(c), k] = False
        I[codes.index(c), k] = np.nan
    return D.Panel(
        axis=_days(I.shape[1]),
        codes=codes,
        I=I,
        O=I.copy(),
        H=I.copy(),
        L=I.copy(),
        C=I.copy(),
        V=np.full(I.shape, 1000.0),
        raw_open=I.copy(),
        raw_high=I.copy(),
        raw_low=I.copy(),
        seg=np.zeros(I.shape, dtype=int),
        has_row=has,
        exec_ok=ok,
    )


def flat(codes: str, n: int = 40, **kw) -> D.Panel:
    return panel({c: [100.0] * n for c in codes}, **kw)


def plan(p, i, scores, cands=None, excluded=None) -> TP.Plan:
    ci = p.ci
    return TP.Plan(
        signal=i,
        scores={ci[c]: s for c, s in scores.items()},
        cands=[ci[c] for c in (cands if cands is not None else sorted(scores))],
        excluded={ci[c]: w for c, w in (excluded or {}).items()},
    )


def sim(p, plans, strengthen, end=None) -> dict:
    bk = TP.simulate(
        p,
        {pl.signal: pl for pl in plans},
        0,
        end or len(p.axis) - 1,
        C,
        "X",
        strengthen,
    )
    return PO.to_json(bk)


def audit(p, bk, plans, strengthen) -> list[str]:
    scores = {
        p.axis[pl.signal]: {p.codes[j]: s for j, s in pl.scores.items()} for pl in plans
    }
    cands = {p.axis[pl.signal]: [p.codes[j] for j in pl.cands] for pl in plans}
    outs = {
        p.axis[pl.signal]: {p.codes[j]: w for j, w in pl.excluded.items()}
        for pl in plans
    }
    return AU.audit_book(p, bk, scores, cands, outs, strengthen, 0, len(p.axis) - 1)


def fills(bk, side=None):
    return [
        (f["date"], f["ticker"], f["side"], f["reason"])
        for f in bk["fills"]
        if side in (None, f["side"])
    ]


# ── 문턱 ─────────────────────────────────────────────────────────────────────────


def test_threshold_h_is_log_round_trip_and_strong_is_twice():
    assert TP.H == pytest.approx(math.log(1.002) - math.log(0.998), abs=1e-15)
    assert TP.STRONG == 2 * TP.H and TP.RECENT_DAYS == 10
    assert TP.threshold(False, 0) == (TP.H, True, False)
    assert TP.threshold(True, 0) == (TP.STRONG, True, True)
    assert TP.threshold(True, 10) == (TP.STRONG, True, True)
    assert TP.threshold(True, 11) == (TP.H, False, False)
    assert TP.threshold(True, None) == (TP.H, False, False)


# ── 편입 · 이탈 ──────────────────────────────────────────────────────────────────


def test_first_plan_enters_up_to_five_at_h_then_one_per_week():
    p = flat("ABCDEFG")
    s0 = {"A": H, "B": 1.0, "C": 1.0, "D": 1.0, "E": H - 1e-9, "F": 1.0}
    pl = [
        plan(p, 0, s0, cands=list("ABCDE")),
        plan(
            p,
            5,
            {**dict.fromkeys("ABCD", 0.0), "E": 1.0, "F": 1.0, "G": 1.0},
            cands=list("EFG"),
        ),
    ]
    bk = sim(p, pl, strengthen=False)
    assert [t for d, t, s, r in fills(bk, "BUY") if d == p.axis[2]] == list("ABCD")
    assert bk["plans"][0]["limit"] == 5 and bk["plans"][0]["entries"] == list("ABCD")
    assert bk["plans"][1]["limit"] == 1 and bk["plans"][1]["entries"] == ["E"]
    assert [r["ticker"] for r in bk["plans"][1]["entry_reviews"]] == [
        "E"
    ]  # 한도 차면 검토 끝
    assert audit(p, bk, pl, False) == []


def test_exit_picks_lowest_score_once_and_between_bounds_holds():
    p = flat("ABCDE")
    pl = [plan(p, 0, dict.fromkeys("ABCDE", 1.0))]
    pl.append(plan(p, 20, {"A": -0.1, "B": -0.2, "C": -H, "D": 0.0, "E": -0.2}))
    pl.append(plan(p, 25, {"A": -0.1, "C": -H, "D": -H + 1e-9, "E": -0.2}))
    bk = sim(p, pl, strengthen=False)
    sells = fills(bk, "SELL")
    assert sells == [
        (p.axis[22], "B", "SELL", "EXIT"),
        (p.axis[27], "E", "SELL", "EXIT"),
    ]
    rv = {r["ticker"]: r["passed"] for r in bk["plans"][2]["exit_reviews"]}
    assert rv == {
        "A": True,
        "C": True,
        "D": False,
        "E": True,
    }  # −h 는 이탈 · −h 보다 큼 = 유지
    assert audit(p, bk, pl, False) == []


@pytest.mark.parametrize(
    "sig, strengthen, enters",
    [(16, True, False), (16, False, True), (17, True, True), (6, True, False)],
)
def test_recent_reentry_counts_from_actual_deferred_fill_day(sig, strengthen, enters):
    """매도 계획 실행일 5 는 거래 불가 → 6 에 체결. 판단일 16 = 체결 뒤 10거래일(강화) · 17 = 11(일반)."""
    p = flat("AB", no_trade=[("A", 5)])
    pl = [plan(p, 0, {"A": 1.0, "B": -1.0}), plan(p, 3, {"A": -1.0, "B": -1.0})]
    pl.append(plan(p, sig, {"A": 1.5 * H, "B": -1.0}))
    bk = sim(p, pl, strengthen)
    assert fills(bk, "SELL") == [(p.axis[6], "A", "SELL", "EXIT")]
    assert bk["intents"][1]["waited"] == [p.axis[5]]
    rev = bk["plans"][2]["entry_reviews"][0]
    assert rev["gap"] == sig - 6 and rev["recent"] == (sig - 6 <= 10)
    assert rev["strengthened"] == (strengthen and sig - 6 <= 10)
    assert bool(bk["plans"][2]["entries"]) == enters
    assert audit(p, bk, pl, strengthen) == []


@pytest.mark.parametrize(
    "sig, strengthen, exits", [(12, True, False), (12, False, True), (13, True, True)]
)
def test_recent_reexit_counts_from_entry_fill(sig, strengthen, exits):
    p = flat("A")
    pl = [plan(p, 0, {"A": 1.0}), plan(p, sig, {"A": -1.5 * H})]
    bk = sim(p, pl, strengthen)
    rev = bk["plans"][1]["exit_reviews"][0]
    assert rev["gap"] == sig - 2 and rev["strengthened"] == (
        strengthen and sig - 2 <= 10
    )
    assert bool(bk["plans"][1]["exits"]) == exits
    assert audit(p, bk, pl, strengthen) == []


def test_same_day_sell_fill_is_gap_zero_and_strengthened():
    p = flat("AB")
    pl = [
        plan(p, 0, {"A": 1.0, "B": -1}),
        plan(p, 3, {"A": -1.0, "B": -1}),
        plan(p, 5, {"A": 1.5 * H, "B": -1}),
    ]
    bk = sim(p, pl, strengthen=True)
    rev = bk["plans"][2]["entry_reviews"][0]
    assert (rev["gap"], rev["strengthened"], rev["passed"]) == (0, True, False)
    assert TR.reviews(bk)["entry"]["strengthened"] == 1


def test_capacity_full_means_no_entry_review():
    p = flat("ABCDEF")
    pl = [
        plan(p, 0, dict.fromkeys("ABCDE", 1.0)),
        plan(p, 5, {**dict.fromkeys("ABCDE", 0.0), "F": 1.0}, cands=["F"]),
    ]
    bk = sim(p, pl, strengthen=True)
    assert bk["plans"][1]["limit"] == 0 and bk["plans"][1]["entry_reviews"] == []


# ── 보호 · 중복 · 비적격 ──────────────────────────────────────────────────────────


def test_protect_at_signal_close_wins_and_no_duplicate_exit():
    c = [100.0] * 30
    c[10:] = [84.0] * 20
    p = panel({"A": c})
    pl = [plan(p, 0, {"A": 1.0}), plan(p, 10, {"A": -1.0})]
    bk = sim(p, pl, strengthen=True)
    assert [it["reason"] for it in bk["intents"] if it["side"] == "SELL"] == ["PROTECT"]
    assert (
        bk["plans"][1]["held_exiting"] == [["A", "PROTECT"]]
        and bk["plans"][1]["exits"] == []
    )
    assert fills(bk, "SELL") == [(p.axis[12], "A", "SELL", "PROTECT")]
    assert audit(p, bk, pl, True) == []


def test_live_exit_becomes_protect_when_condition_hits_one_trade():
    c = [100.0] * 30
    c[7:] = [84.0] * 23
    p = panel({"A": c}, no_trade=[("A", 7)])
    pl = [plan(p, 0, {"A": 1.0}), plan(p, 5, {"A": -1.0})]
    bk = sim(p, pl, strengthen=False)
    sells = [it for it in bk["intents"] if it["side"] == "SELL"]
    assert len(sells) == 1
    assert (sells[0]["reason"], sells[0]["planned_reason"], sells[0]["protect_at"]) == (
        "PROTECT",
        "EXIT",
        p.axis[7],
    )
    assert fills(bk, "SELL") == [(p.axis[8], "A", "SELL", "PROTECT")]
    assert audit(p, bk, pl, False) == []


def test_not_eligible_holding_is_held_recorded_and_still_protected():
    c = [100.0] * 30
    c[12:] = [80.0] * 18
    p = panel({"A": c, "B": [100.0] * 30})
    pl = [
        plan(p, 0, {"A": 1.0, "B": -1.0}),
        plan(p, 5, {"B": -1.0}, excluded={"A": "liquidity"}),
    ]
    bk = sim(p, pl, strengthen=True)
    assert bk["plans"][1]["held_not_eligible"] == [["A", "liquidity"]]
    assert bk["plans"][1]["exit_reviews"] == [] and bk["plans"][1]["exits"] == []
    assert fills(bk, "SELL") == [(p.axis[14], "A", "SELL", "PROTECT")]
    ho = TR.held_out(bk)
    assert (ho["pairs"], ho["dates"], ho["reasons"]) == (1, 1, {"liquidity": 1})
    assert ho["held_days"] == 14 - 5  # 계획일 5 ~ 13 종가(14 시가 매도)
    assert audit(p, bk, pl, True) == []


def test_holding_without_eligibility_or_reason_is_check_required():
    p = flat("AB")
    pl = {0: plan(p, 0, {"A": 1.0, "B": -1.0}), 5: plan(p, 5, {"B": -1.0})}
    with pytest.raises(D.CheckRequired):
        TP.simulate(p, pl, 0, len(p.axis) - 1, C, "X", True)


def test_unknown_close_of_holding_is_check_required_not_settled():
    p = flat("A", no_row=[("A", 9)])
    bk = sim(p, [plan(p, 0, {"A": 1.0})], strengthen=True)
    assert bk["status"] == "CHECK_REQUIRED" and bk["end"]["stopped_at"] == p.axis[9]


# ── 독립 감사가 잡는 것 ────────────────────────────────────────────────────────────


def _scenario():
    p = flat("AB", no_trade=[("A", 5)])
    pl = [
        plan(p, 0, {"A": 1.0, "B": -1.0}),
        plan(p, 3, {"A": -1.0, "B": -1.0}),
        plan(p, 16, {"A": 1.5 * H, "B": 2.0}),
    ]
    return p, pl, sim(p, pl, True)


def test_audit_catches_review_flag_entry_and_fill_tamper():
    p, pl, bk = _scenario()
    assert audit(p, bk, pl, True) == []
    bk["plans"][2]["entry_reviews"][0]["strengthened"] = False
    assert any("편입 검토 기록" in x for x in audit(p, bk, pl, True))
    p, pl, bk = _scenario()
    assert any(
        "편입" in x and "기대" in x for x in audit(p, bk, pl, False)
    )  # 강화 없는 기대와 다름
    p, pl, bk = _scenario()
    bk["fills"][0]["price"] = 101.0
    assert any("체결가" in x for x in audit(p, bk, pl, True))


def test_audit_catches_missing_protect_relabel():
    c = [100.0] * 30
    c[7:] = [84.0] * 23
    p = panel({"A": c}, no_trade=[("A", 7)])
    pl = [plan(p, 0, {"A": 1.0}), plan(p, 5, {"A": -1.0})]
    bk = sim(p, pl, strengthen=False)
    it = next(x for x in bk["intents"] if x["side"] == "SELL")
    it["reason"] = "EXIT"
    for k in ("planned_reason", "protect_at"):
        it.pop(k)
    assert any("EXIT 그대로" in x for x in audit(p, bk, pl, False))


def test_audit_recomputes_r_scores_and_candidates_from_prices():
    rng = np.random.default_rng(3)
    closes = {
        c: list(100 * np.cumprod(1 + rng.normal(0, 0.01, 130))) for c in "ABCDEFG"
    }
    p = panel(closes)
    members = {125: list(range(7))}
    r = AU.r_scores(p, members, [125])[p.axis[125]]
    assert r["A"] == pytest.approx(
        math.log(closes["A"][125] / closes["A"][65]), abs=1e-15
    )
    ret = {c: closes[c][125] / closes[c][5] - 1 for c in closes}
    assert (
        AU.candidates(p, members, [125])[p.axis[125]]
        == sorted(ret, key=lambda c: -ret[c])[:5]
    )


# ── 절대 정답 ────────────────────────────────────────────────────────────────────


def test_absolute_label_ignores_bench_rows_but_keeps_etf_checks():
    n = 70
    p = panel(
        {"069500": [100.0] * n, "A": [100.0 + k for k in range(n)]},
        no_row=[("069500", 61)],
    )
    j, b = p.ci["A"], p.ci["069500"]
    assert not F.label_ok(p, j, 0, b) and LB.label_ok(
        p, j, 0
    )  # 069500 미래 행 없어도 ETF 정답 있음
    p.O[j, 2] = 101.5  # 합성 시가 ≠ 종가
    assert LB.label(p, j, 0) == math.log(p.I[j, 61] / 101.5)
    p.seg[j, 61] = 1
    assert LB.label(p, j, 0) is None
    p.seg[j, 61] = 0
    p.raw_open[j, 2] = 0
    assert LB.label(p, j, 0) is None
    assert LB.label(p, j, n - 61) is None  # q 가 축 밖


def test_usable_date_rule_twenty_labels_and_95_percent():
    assert LB._usable(20, 20) and not LB._usable(20, 19) and not LB._usable(19, 19)
    assert LB._usable(21, 20) and not LB._usable(
        22, 20
    )  # 20/21 = 95.2% · 20/22 = 90.9%


# ── 거래 · 묶음 · 회복 ───────────────────────────────────────────────────────────


def test_trade_pnl_prior_and_bundle_link_within_ten_days():
    p = flat("AB")
    pl = [
        plan(p, 0, {"A": 1.0, "B": -1}),
        plan(p, 3, {"A": -1.0, "B": -1}),
        plan(p, 7, {"A": 1.0, "B": -1}),
    ]
    pl.append(plan(p, 30, {"A": -1.0, "B": -1}))
    bk = sim(p, pl, strengthen=False)
    rows = TR.trade_list(p, bk)
    budget = 20.0
    sell_cash = budget / (1 + C) * (1 - C)
    assert (
        rows[0]["pnl"] == pytest.approx(sell_cash - budget, abs=1e-12)
        and rows[0]["prior"] == "NONE"
    )
    assert (
        rows[1]["entry_kind"],
        rows[1]["prior"],
        rows[1]["fill_gap_from_prior_exit"],
    ) == ("SHORT_REENTRY", "LOSS", 4)
    b = TR.bundles(rows, {d: k for k, d in enumerate(p.axis)})
    assert (b["bundles"], b["trades_in_bundles"]) == (1, 2)
    assert b["pnl_closed"] == pytest.approx(rows[0]["pnl"] + rows[1]["pnl"], abs=1e-12)
    a = TR.analyze(p, bk, PO.START_VALUE)
    assert a["short_reentry_by_prior"]["LOSS"]["trades"] == 1
    assert a["costs_total"] == pytest.approx(sum(f["cost"] for f in bk["fills"]), abs=0)


def test_bundle_breaks_after_eleven_days():
    rows = [
        {
            "ticker": "A",
            "entry_date": "d0",
            "exit_date": "d2",
            "exit_kind": "EXIT",
            "pnl": 1.0,
            "costs": 0.1,
        },
        {
            "ticker": "A",
            "entry_date": "d13",
            "exit_date": "d20",
            "exit_kind": "EXIT",
            "pnl": 1.0,
            "costs": 0.1,
        },
    ]
    pos = {"d0": 0, "d2": 2, "d13": 13, "d20": 20}
    assert TR.bundles(rows, pos)["bundles"] == 0
    pos["d13"] = 12
    assert TR.bundles(rows, pos)["bundles"] == 1


def test_longest_underwater_counts_days_below_prior_peak_and_open_end():
    led = [
        {"date": f"d{k}", "value": v}
        for k, v in enumerate([99, 98, 101, 100, 100.5, 102, 101, 100, 99])
    ]
    u = TR.underwater(led, 100.0)
    assert (u["longest_days"], u["longest_start"], u["longest_end"]) == (3, "d6", "d8")
    assert u["underwater_at_end"] and u["days_at_end"] == 3 and u["longest_open_at_end"]
    assert TR.underwater(led[:6], 100.0)["underwater_at_end"] is False
    same = [{"date": f"e{k}", "value": v} for k, v in enumerate([100.0, 100.0, 99.0])]
    assert (
        TR.underwater(same, 100.0)["longest_days"] == 1
    )  # 고점과 같으면 밑돈 날이 아님


# ── 판정 축 ──────────────────────────────────────────────────────────────────────


def _c(cagr, mdd=-0.1, subs=(0.0, 0.0, 0.0), to=1.0):
    return {
        "status": "OK",
        "total": {"cagr": cagr, "mdd": mdd},
        "subperiods": [{"return": s} for s in subs],
        "turnover": {"annual": to},
    }


def _test(**kw):
    base = {f"{k}_{c}": _c(0.05) for k in RP.NAMES for c in ("20", "40")}
    base.update(kw)
    return base


GOOD = dict(
    M1_20=_c(0.10, subs=(0.1, 0.1, 0.0), to=2.0),
    M0_20=_c(0.09, to=3.0),
    M1_40=_c(0.09),
    M0_40=_c(0.08),
    R1_40=_c(0.05),
    K_40=_c(0.05),
)
BOOT = {"uncertain": True}


def test_candidate_needs_all_four_axes_and_strengthen_observed():
    j = RP.judge("OK", _test(**GOOD), BOOT, {"M1_20": 3, "R1_20": 2})
    assert (j["ml_gain"], j["strengthen_gain"], j["purpose_risk"], j["high_cost"]) == (
        "ML_GAIN_OBSERVED",
        "STRENGTHEN_GAIN_OBSERVED",
        "PURPOSE_RISK_MET",
        "HIGH_COST_MET",
    )
    assert (
        j["candidate"] == "FURTHER_REVIEW_CANDIDATE" and j["uncertainty"] == "UNCERTAIN"
    )


def test_no_m1_opportunity_is_not_judged_and_not_candidate():
    j = RP.judge("OK", _test(**GOOD), BOOT, {"M1_20": 0, "R1_20": 0})
    assert j["strengthen_gain"] == "NOT_JUDGED" and j["candidate"] == "NOT_CANDIDATE"
    assert {
        "STRENGTHEN_NOT_JUDGED_NO_OPPORTUNITY",
        "R1_NO_STRENGTHEN_OPPORTUNITY",
    } <= set(j["reasons"])


def test_strengthen_axis_uses_m1_opportunity_not_r1():
    j = RP.judge("OK", _test(**GOOD), BOOT, {"M1_20": 0, "R1_20": 4})
    assert j["strengthen_gain"] == "NOT_JUDGED"
    j = RP.judge("OK", _test(**GOOD), BOOT, {"M1_20": 4, "R1_20": 0})
    assert j["strengthen_gain"] == "STRENGTHEN_GAIN_OBSERVED"
    assert "R1_NO_STRENGTHEN_OPPORTUNITY" in j["reasons"]
    assert j["candidate"] == "FURTHER_REVIEW_CANDIDATE"


def test_same_result_with_opportunity_is_valid_unobserved():
    same = {**GOOD, "M0_20": _c(0.10, to=2.0), "M0_40": _c(0.09)}
    j = RP.judge("OK", _test(**same), BOOT, {"M1_20": 5, "R1_20": 5})
    assert (
        j["strengthen_gain"] == "STRENGTHEN_GAIN_NOT_SHOWN"
    )  # 회전율이 줄지 않음 = 미관측(판단 불가 아님)


def test_ml_gain_needs_one_point_and_two_of_three_subperiods():
    j = RP.judge(
        "OK",
        _test(**{**GOOD, "M1_20": _c(0.10, subs=(0.1, 0.0, 0.0), to=2.0)}),
        BOOT,
        {"M1_20": 3, "R1_20": 3},
    )
    assert j["ml_gain"] == "ML_GAIN_NOT_SHOWN" and j["values"]["sub_wins"] == 1
    j = RP.judge(
        "OK",
        _test(**{**GOOD, "M1_20": _c(0.0599, subs=(0.1, 0.1, 0.1), to=2.0)}),
        BOOT,
        {"M1_20": 3, "R1_20": 3},
    )
    assert j["ml_gain"] == "ML_GAIN_NOT_SHOWN"


def test_risk_turnover_and_cost_reasons():
    bad = {
        **GOOD,
        "M1_20": _c(0.10, mdd=-0.16, subs=(0.1, 0.1, 0.0), to=6.5),
        "M1_40": _c(0.04),
    }
    j = RP.judge("OK", _test(**bad), BOOT, {"M1_20": 3, "R1_20": 3})
    assert {
        "MDD_WORSE_THAN_R1",
        "MDD_WORSE_THAN_K",
        "TURNOVER_ABOVE_6",
        "COST_40BP_NOT_ABOVE_R1",
    } <= set(j["reasons"])
    assert (
        j["purpose_risk"] == "PURPOSE_RISK_NOT_MET"
        and j["high_cost"] == "HIGH_COST_NOT_MET"
    )


@pytest.mark.parametrize("validity", ["CHECK_REQUIRED", "DATA_SHORT", "BUDGET_STOP"])
def test_invalid_runs_are_not_judged(validity):
    j = RP.judge(validity, None, None, None)
    assert j["candidate"] == j["ml_gain"] == j["strengthen_gain"] == "NOT_JUDGED"
    assert j["OPERATION_ADOPTION"] == "NO" and j["TOTAL_RETURN_VALIDATED"] == "NO"


def test_audit_catches_missing_and_conditionless_protect():
    c = [100.0] * 30
    c[10:] = [84.0] * 20
    drop, still = panel({"A": c}), flat("A", n=30)
    pl = [plan(still, 0, {"A": 1.0})]
    assert any(
        "보호 이탈 누락" in x for x in audit(drop, sim(still, pl, True), pl, True)
    )
    assert any(
        "조건 없는 보호 이탈" in x for x in audit(still, sim(drop, pl, True), pl, True)
    )


def test_audit_requires_every_plan_day_and_intent_fields():
    p, pl, bk = _scenario()
    bk["plans"] = bk["plans"][:1] + bk["plans"][2:]  # 둘째 계획 기록 빠짐
    assert any(
        "계획 기록 2개 ≠ 공통 계획 신호 3개" in x for x in audit(p, bk, pl, True)
    )
    p, pl, bk = _scenario()
    it = next(x for x in bk["intents"] if x["side"] == "SELL")
    it["recent"] = False  # 거래 구분(단기 재이탈)의 근거 칸
    assert any("통상 이탈 의도 칸" in x for x in audit(p, bk, pl, True))
    p, pl, bk = _scenario()
    it = next(x for x in bk["intents"] if x["side"] == "BUY")
    it["cand_rank"] = 9
    assert any("편입 의도" in x and "후보 순위" in x for x in audit(p, bk, pl, True))


def test_exit_kind_dates_count_exit_fills_and_cash_summary():
    rows = [
        {
            "entry_date": "d1",
            "exit_date": "d5",
            "exit_kind": "PROTECT",
            "pnl": -1.0,
            "costs": 0.1,
        },
        {
            "entry_date": "d1",
            "exit_date": "d9",
            "exit_kind": "PROTECT",
            "pnl": -2.0,
            "costs": 0.1,
        },
    ]
    assert TR._group(rows, "exit_date")["dates"] == 2 and TR._group(rows)["dates"] == 1
    led = [
        {"date": "a", "cash": 100.0, "value": 100.0, "pos": {}},
        {"date": "b", "cash": 20.0, "value": 99.0, "pos": {"A": [1, 1]}},
    ]
    c = TR.cash(led)
    assert c["avg_cash_weight"] == pytest.approx((1.0 + 20 / 99) / 2, abs=1e-15)
    assert (c["full_cash_days"], c["end_cash_weight"]) == (1, 20 / 99)


def test_underwater_tie_points_to_latest_run():
    led = [{"date": f"d{k}", "value": v} for k, v in enumerate([99, 98, 101, 100, 99])]
    u = TR.underwater(led, 100.0)
    assert (u["longest_days"], u["longest_start"], u["longest_end"]) == (2, "d3", "d4")
    assert u["longest_open_at_end"]
    sub = TR.underwater_sub(led, [("d2", "d4")], 100.0)[0]
    assert sub["longest_days"] == 2 and sub["bounds"] == [
        "d2",
        "d4",
    ]  # 기준 = 구간 전 마지막 평가 98
