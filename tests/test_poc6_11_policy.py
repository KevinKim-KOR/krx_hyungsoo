"""POC6-11 공통 운용 정책 · 장부 · K · 독립 손검산 — 설계 §6 · §7 · §9 · 판정 §3 · §6.

직접 만든 작은 행렬만 쓴다(DB 없음). 기대값은 손으로 계산한다.
"""

from __future__ import annotations

import json
import math

import numpy as np
import pytest

from app.weekly_selection import data as D
from app.weekly_selection import policy as PO
from app.weekly_selection import audit as AU

C = 0.002


def _panel(closes: dict, *, opens=None, vols=None, n=None):
    codes = sorted(closes)
    n = n or len(next(iter(closes.values())))
    axis = [f"2021-{1 + k // 28:02d}-{1 + k % 28:02d}" for k in range(n)]
    I = np.array([closes[c] for c in codes], dtype=float)  # noqa: E741
    O = np.array(  # noqa: E741
        [opens[c] if opens and c in opens else closes[c] for c in codes], dtype=float
    )
    V = np.array(
        [vols[c] if vols and c in vols else [1000.0] * n for c in codes], dtype=float
    )
    has = np.isfinite(I)
    O = np.where(has, O, np.nan)  # noqa: E741
    return D.Panel(
        axis=axis,
        codes=codes,
        I=I,
        O=O,
        H=np.fmax(O, I),
        L=np.fmin(O, I),
        C=I.copy(),
        V=V,
        raw_open=np.nan_to_num(O),
        raw_high=np.fmax(O, I),
        raw_low=np.fmin(O, I),
        seg=np.zeros(I.shape, dtype=np.int32),
        has_row=has,
        exec_ok=has & (V > 0) & (np.nan_to_num(O) > 0),
    )


def _flat(codes, n, price=100.0):
    return {c: [price] * n for c in codes}


def _plan(p, i, order, trend=None):
    """order = 높은 점수 순 종목 코드(자격 집합 전체)."""
    sc = {p.ci[c]: float(len(order) - k) for k, c in enumerate(order)}
    tr = {p.ci[c] for c in (order if trend is None else trend)}
    return PO.Plan(signal=i, scores=sc, trend_ok=tr)


CODES = [f"A{k:02d}" for k in range(1, 16)]


def test_first_plan_fills_five_then_one_per_week_and_budget():
    n = 20
    p = _panel(_flat(CODES, n))
    plans = {0: _plan(p, 0, CODES), 5: _plan(p, 5, CODES[5:] + CODES[:5])}
    bk = PO.simulate(p, plans, 0, n - 1, C, "L", [0, 5])
    buys = [f for f in bk.fills if f["side"] == "BUY"]
    assert [f["ticker"] for f in buys[:5]] == CODES[:5] and all(
        f["date"] == p.axis[2] for f in buys[:5]
    )
    # 같은 시가 다섯 매수의 기준 자산은 한 번만(100) → 예산 = min(20, 남은 현금) = 20 · 명목 = 20/(1+c)
    assert all(f["notional"] == pytest.approx(20 / (1 + C)) for f in buys[:5])
    assert bk.ledger[2]["cash"] == pytest.approx(0.0, abs=1e-12)
    # 둘째 계획: 기존 다섯은 순위 11~15 → 통상 이탈은 1개(가장 낮은 A05) · 편입 1개
    sells = [f for f in bk.fills if f["side"] == "SELL"]
    assert [f["ticker"] for f in sells] == ["A05"] and sells[0]["date"] == p.axis[7]
    assert [f["ticker"] for f in buys[5:]] == ["A06"]
    assert bk.plans[1]["limit"] == 1


def test_keep_within_top10_and_unranked_is_lowest_and_ties():
    n = 20
    p = _panel(_flat(CODES, n))
    first = CODES[:5]
    plans = {0: _plan(p, 0, CODES)}
    # 둘째 계획: A01 = 10위(유지) · A02 = 11위 · A03 = 자격 밖(순위 없음 = 가장 낮음)
    order = [c for c in CODES if c not in first][:9] + ["A01", "A02", "A04", "A05"]
    plans[5] = _plan(p, 5, order)
    bk = PO.simulate(p, plans, 0, n - 1, C, "L", [0, 5])
    pl = bk.plans[1]
    assert pl["held_rank"]["A01"] == 10 and pl["held_rank"]["A03"] is None
    assert pl["exits"] == ["A03"]  # 11위 A02 보다 순위 없음이 먼저 · 한 계획에 하나
    # 완전 동점 = 기존 보유 우선 → ticker 오름차순
    sc = {p.ci["A09"]: 1.0, p.ci["A03"]: 1.0, p.ci["A07"]: 1.0}
    assert [p.codes[j] for j in PO.ranking(sc, {p.ci["A07"]}, p.codes)] == [
        "A07",
        "A03",
        "A09",
    ]


def test_entry_needs_top5_and_trend_and_not_held():
    n = 12
    p = _panel(_flat(CODES, n))
    plans = {0: _plan(p, 0, CODES, trend=["A03", "A06", "A07"])}
    bk = PO.simulate(p, plans, 0, n - 1, C, "L", [0])
    assert sorted(f["ticker"] for f in bk.fills) == ["A03"]  # A06 · A07 은 상위 5 밖


def test_protect_exit_threshold_peak_and_no_double_sell():
    n = 16
    px = [100.0] * n
    px[3:6] = [110.0, 120.0, 103.0]  # 103/120 − 1 = −14.2% → 아직
    px[6] = 102.0  # 102/120 − 1 = −15% → 보호 이탈(실행 = 8일)
    cl = _flat(CODES, n)
    cl["A01"] = px
    p = _panel(cl)
    plans = {
        0: _plan(p, 0, CODES),
        6: _plan(p, 6, CODES[5:] + CODES[:5]),
    }  # 6일 정기도 A01 을 이탈 후보로
    bk = PO.simulate(p, plans, 0, n - 1, C, "L", [0, 6])
    prot = [it for it in bk.intents if it["reason"] == "PROTECT"]
    assert [(it["ticker"], it["signal"], it["exec_date"]) for it in prot] == [
        ("A01", p.axis[6], p.axis[8])
    ]
    a01 = [f for f in bk.fills if f["ticker"] == "A01" and f["side"] == "SELL"]
    assert len(a01) == 1 and a01[0]["reason"] == "PROTECT"
    normal = [
        it
        for it in bk.intents
        if it["signal"] == p.axis[6] and it["reason"] == "RANK_OUT"
    ]
    assert [it["ticker"] for it in normal] == [
        "A05"
    ]  # 같은 날 보호 매도 중인 A01 은 통상 후보에서 빠짐


def test_cooldown_four_reviews_then_reentry():
    n = 40
    p = _panel(_flat(CODES, n))
    reviews = list(range(0, 40, 5))  # 0 · 5 · 10 · … · 35
    plans = {0: _plan(p, 0, CODES, trend=["A01"])}  # A01 만 편입
    plans[5] = _plan(
        p, 5, CODES[1:] + ["A01"], trend=[]
    )  # A01 15위 → 이탈(7일 시가 매도) · 편입 없음
    for i in (10, 15, 20, 25, 30):
        plans[i] = _plan(p, i, CODES, trend=["A01"])  # A01 1위 · 추세 충족
    bk = PO.simulate(p, plans, 0, n - 1, C, "L", reviews)
    sold = [f for f in bk.fills if f["ticker"] == "A01" and f["side"] == "SELL"][0]
    assert sold["date"] == p.axis[7]
    rebuy = [
        it
        for it in bk.intents
        if it["ticker"] == "A01" and it["side"] == "BUY" and it["signal"] > p.axis[5]
    ]
    # 매도 뒤 검토 10 · 15 · 20 · 25 = 4회 대기 → 30 에서 다시 후보
    assert [it["signal"] for it in rebuy] == [p.axis[30]]


def test_not_tradable_buy_cancel_sell_defer_and_slot_full():
    n = 20
    cl = _flat(CODES, n)
    vols = {"A02": [1000.0] * n, "A06": [1000.0] * n}
    vols["A02"][2] = 0.0  # 첫 매수일 A02 거래 없음 → 취소(다음 정기까지 대기)
    vols["A06"][7], vols["A06"][8] = 0.0, 0.0  # 이탈 매도 이연(7 · 8) → 9 시가 매도
    p = _panel(cl, vols=vols)
    order1 = ["A06"] + CODES[:5]
    plans = {0: _plan(p, 0, order1), 5: _plan(p, 5, CODES[6:] + CODES[:6])}
    bk = PO.simulate(p, plans, 0, n - 1, C, "L", [0, 5])
    st = {(it["ticker"], it["signal"]): it for it in bk.intents}
    assert st[("A02", p.axis[0])]["status"] == "CANCELED_NOT_TRADABLE"
    sell = st[("A06", p.axis[5])] if ("A06", p.axis[5]) in st else None
    assert (
        sell is not None
        and sell["status"] == "FILLED"
        and sell["filled_date"] == p.axis[9]
    )
    assert sell["waited"] == [p.axis[7], p.axis[8]]
    # 5일 계획의 편입(A07)은 7일 실행 — 매도가 이연돼 4 + 1 = 5 보유 … 자리 있음(첫 매수 4종목)
    buy7 = st[("A07", p.axis[5])]
    assert buy7["status"] == "FILLED"


def test_slot_full_when_sell_deferred():
    n = 20
    vols = {"A05": [1000.0] * n}
    vols["A05"][7] = 0.0
    p = _panel(_flat(CODES, n), vols=vols)
    plans = {0: _plan(p, 0, CODES), 5: _plan(p, 5, CODES[5:] + CODES[:5])}
    bk = PO.simulate(p, plans, 0, n - 1, C, "L", [0, 5])
    st = {(it["ticker"], it["signal"]): it for it in bk.intents}
    assert (
        st[("A06", p.axis[5])]["status"] == "CANCELED_SLOT_FULL"
    )  # 미매도 슬롯 · 현금 중복 사용 없음
    assert len(bk.ledger[7]["pos"]) == 5


def test_zero_volume_valid_close_is_valued_and_missing_row_is_check_required():
    n = 20
    cl = _flat(CODES, n)
    cl["A01"] = [100.0] * 9 + [120.0] * 2 + [math.nan] * (n - 11)  # 11일부터 행 없음
    vols = {"A01": [1000.0] * n}
    vols["A01"][9], vols["A01"][10] = (
        0.0,
        0.0,
    )  # 거래량 0 · 정상 종가 → 평가는 하고 매도는 못 함
    p = _panel(cl, vols=vols)
    plans = {
        0: _plan(p, 0, CODES),
        7: _plan(p, 7, CODES[5:] + ["A05", "A04", "A03", "A02", "A01"]),
    }
    bk = PO.simulate(p, plans, 0, n - 1, C, "L", [0, 7])
    assert bk.status == "CHECK_REQUIRED"
    assert (
        bk.ledger[-1]["date"] == p.axis[10] and bk.ledger[-1]["pos"]["A01"][1] == 120.0
    )
    assert (
        bk.unresolved["first_unresolved"] == p.axis[11]
        and len(bk.unresolved["items"]) == 1
    )
    u = bk.unresolved["items"][0]
    assert (u["ticker"], u["last_valid"], u["cause"]) == ("A01", p.axis[10], "NO_ROW")
    assert u["last_weight_diagnostic"] == pytest.approx(
        u["last_value_diagnostic"] / bk.ledger[-1]["value"]
    )
    assert (
        u["pending_sell"]["status"] == "DEFERRED"
    )  # 9 · 10 이연 · 마지막 종가 정산 · 소급 매도 없음
    assert not any(f["ticker"] == "A01" and f["side"] == "SELL" for f in bk.fills)
    assert u["last_value_diagnostic"] == pytest.approx(u["units"] * 120.0)


def test_end_unexecuted_open_sell_and_close_valuation():
    n = 12
    vols = {"A05": [1000.0] * n}
    vols["A05"][9:] = [0.0] * 3
    p = _panel(_flat(CODES, n), vols=vols)
    late = CODES[5:] + CODES[:5]
    plans = {0: _plan(p, 0, CODES), 7: _plan(p, 7, late), 10: _plan(p, 10, late)}
    bk = PO.simulate(p, plans, 0, n - 1, C, "L", [0, 7, 10])
    st = {(it["ticker"], it["signal"]): it["status"] for it in bk.intents}
    assert st[("A05", p.axis[7])] == "OPEN_AT_END"
    assert bk.end["open_sells"] == ["A05"] and "A05" in bk.end["holdings"]
    at10 = [s for (t, d), s in st.items() if d == p.axis[10]]
    assert at10 and all(s == "UNEXECUTED_AFTER_END" for s in at10)
    last = bk.ledger[-1]
    assert last["value"] == pytest.approx(
        last["cash"] + sum(u * c for u, c in last["pos"].values())
    )


def test_k_entry_independent_of_scores_and_delay():
    n = 10
    cl = _flat(["069500", "A01"], n)
    cl["069500"] = [100.0 + k for k in range(n)]
    vols = {"069500": [1000.0] * n}
    vols["069500"][3] = 0.0
    p = _panel(cl, vols=vols)
    k = PO.simulate_bench(p, p.ci["069500"], 3, 1, n - 1, C)
    assert k.fills[0]["date"] == p.axis[4] and k.events[0]["type"] == "K_DELAYED"
    assert k.fills[0]["units"] == pytest.approx(100 / (1 + C) / 104.0)
    assert k.ledger[0]["value"] == 100.0 and k.ledger[-1]["value"] == pytest.approx(
        k.fills[0]["units"] * 109.0
    )


# ── 독립 손검산(verify) — 정책을 바꾼 장부를 항등식만으로 통과시키지 않음(판정 §6) ──────────


def _scenario():
    n = 130
    rng = np.random.default_rng(7)
    cl = {c: list(100 * np.cumprod(1 + rng.normal(0, 0.03, n))) for c in CODES}
    p = _panel(cl)
    reviews = list(range(60, n, 5))
    plans, scores = {}, {}
    for i in reviews:
        order = list(rng.permutation(CODES))
        trend = [c for c in CODES if AU._trend(p, p.ci[c], i)]  # I > SMA60(가격에서)
        plans[i] = _plan(p, i, order, trend=trend)
        scores[p.axis[i]] = {p.codes[j]: s for j, s in plans[i].scores.items()}
    return p, plans, scores, reviews


def _book(p, plans, reviews):
    return PO.to_json(PO.simulate(p, plans, 60, len(p.axis) - 1, C, "L", reviews))


def test_audit_passes_on_policy_book():
    p, plans, scores, reviews = _scenario()
    bk = _book(p, plans, reviews)
    assert len(bk["fills"]) > 10
    assert AU.audit_book(p, bk, scores, reviews, 60, len(p.axis) - 1) == []


@pytest.mark.parametrize(
    "attr,value,needle",
    [
        ("KEEP_RANK", 8, "통상 이탈"),
        ("COOLDOWN_REVIEWS", 1, "편입"),
        ("ENTRY_TOP", 7, "편입"),
        ("PROTECT", -0.05, "조건 없는 보호 이탈"),
        ("PROTECT", -0.30, "보호 이탈 누락"),
        ("BUDGET_SHARE", 0.25, "매수 예산"),
    ],
)
def test_audit_catches_changed_policy(monkeypatch, attr, value, needle):
    p, plans, scores, reviews = _scenario()
    with monkeypatch.context() as m:
        m.setattr(PO, attr, value)
        bk = _book(p, plans, reviews)
    probs = AU.audit_book(p, bk, scores, reviews, 60, len(p.axis) - 1)
    assert any(needle in x for x in probs), probs[:5]


def test_rank_eleven_alone_is_a_normal_exit():
    n = 14
    p = _panel(_flat(CODES, n))
    plans = {0: _plan(p, 0, CODES)}
    order = [c for c in CODES if c not in ("A01", "A02", "A03", "A04", "A05")][:6] + [
        "A02",
        "A03",
        "A04",
        "A05",
    ]
    plans[5] = _plan(p, 5, order + ["A01"])  # A02 ~ A05 = 7 ~ 10위(유지) · A01 = 11위
    bk = PO.simulate(p, plans, 0, n - 1, C, "L", [0, 5])
    assert bk.plans[1]["held_rank"]["A01"] == 11 and bk.plans[1]["exits"] == ["A01"]


def test_segment_change_while_held_is_check_required():
    n = 12
    p = _panel(_flat(CODES, n))
    p.seg[p.ci["A01"], 6:] = 1  # 관계 실패 뒤 새 연결 구간(종가는 있음)
    bk = PO.simulate(p, {0: _plan(p, 0, CODES)}, 0, n - 1, C, "L", [0])
    assert bk.status == "CHECK_REQUIRED"
    assert [x["cause"] for x in bk.unresolved["items"]] == ["SEGMENT_CHANGED"]
    assert (
        bk.unresolved["first_unresolved"] == p.axis[6]
        and bk.ledger[-1]["date"] == p.axis[5]
    )


def test_holiday_week_counts_pending_buys():
    n = 12
    p = _panel(_flat(CODES, n))
    # 신호 0 의 실행(2) 전에 다음 주 신호 1 이 오는 연휴 주 — 실행 전 매수 다섯 개가 자리를 차지
    plans = {0: _plan(p, 0, CODES), 1: _plan(p, 1, CODES[5:] + CODES[:5])}
    bk = PO.simulate(p, plans, 0, n - 1, C, "L", [0, 1])
    assert bk.plans[1]["capacity"] == 0 and bk.plans[1]["limit"] == 0
    assert not [it for it in bk.intents if it["signal"] == p.axis[1]]


def test_all_unresolved_holdings_on_the_day_are_recorded():
    n = 12
    cl = _flat(CODES, n)
    for c in ("A02", "A04"):
        cl[c] = [100.0] * 7 + [math.nan] * (n - 7)
    p = _panel(cl)
    bk = PO.simulate(p, {0: _plan(p, 0, CODES)}, 0, n - 1, C, "L", [0])
    items = bk.unresolved["items"]
    assert [x["ticker"] for x in items] == ["A02", "A04"] and bk.unresolved[
        "first_unresolved"
    ] == p.axis[7]
    assert all(x["cause"] == "NO_ROW" and x["last_valid"] == p.axis[6] for x in items)


def test_k_unresolved_record_has_last_value():
    n = 8
    cl = _flat(["069500", "A01"], n)
    cl["069500"] = [100.0] * 5 + [math.nan] * 3
    p = _panel(cl)
    k = PO.simulate_bench(p, p.ci["069500"], 2, 0, n - 1, C)
    x = k.unresolved["items"][0]
    assert k.status == "CHECK_REQUIRED" and x["last_valid"] == p.axis[4]
    assert x["last_value_diagnostic"] == pytest.approx(x["units"] * 100.0)


# ── 체결 쪽 정책 오류 — 정책 재적용(같은 코드)으로는 못 잡는 경우를 손검산이 잡는지(검토 r1) ──────────


def _scenario2(seed, vol0=0.25, n=160):
    rng = np.random.default_rng(seed)
    cl = {c: list(100 * np.cumprod(1 + rng.normal(0, 0.035, n))) for c in CODES}
    vols = {c: list(np.where(rng.random(n) < vol0, 0.0, 1000.0)) for c in CODES}
    p = _panel(cl, vols=vols)
    reviews, i, k = [], 60, 0
    while i < n - 1:  # 주 간격 1 · 2 거래일이 섞인 연휴 주
        reviews.append(i)
        i += (1, 5, 2, 5, 4)[k % 5]
        k += 1
    plans, scores = {}, {}
    for i in reviews:
        order = list(rng.permutation(CODES))
        trend = [c for c in CODES if AU._trend(p, p.ci[c], i)]
        plans[i] = _plan(p, i, order, trend=trend)
        scores[p.axis[i]] = {p.codes[j]: s for j, s in plans[i].scores.items()}
    return p, plans, scores, reviews


def _no_retry(orig):
    def f(p, s, i, today, cost):
        for it in s.sell_live.values():
            if it["status"] == "DEFERRED":
                it["status"] = "STUCK"
        orig(p, s, i, today, cost)

    return f


def _cancel_at_four(orig):
    def f(p, s, i, today, cost):
        if len(s.hold) >= 4:
            for it in [x for x in today if x["side"] == "BUY"]:
                it["status"] = "CANCELED_SLOT_FULL"
                s.buy_live.pop(it["ticker_idx"], None)
            today = [x for x in today if x["side"] == "SELL"]
        orig(p, s, i, today, cost)

    return f


def _drop_protect(orig):
    def f(p, s, i, today, cost):
        orig(p, s, i, [x for x in today if x["reason"] != "PROTECT"], cost)

    return f


def test_audit_has_no_false_alarm_on_holiday_and_deferred_books():
    for seed in range(12):
        p, plans, scores, reviews = _scenario2(seed)
        bk = PO.to_json(PO.simulate(p, plans, 60, len(p.axis) - 1, C, "L", reviews))
        assert AU.audit_book(p, bk, scores, reviews, 60, len(p.axis) - 1) == [], seed


@pytest.mark.parametrize("wrap", [_no_retry, _cancel_at_four, _drop_protect])
def test_audit_catches_execution_side_errors(monkeypatch, wrap):
    changed = caught = 0
    for seed in range(12):
        p, plans, scores, reviews = _scenario2(seed)
        good = PO.to_json(PO.simulate(p, plans, 60, len(p.axis) - 1, C, "L", reviews))
        with monkeypatch.context() as m:
            m.setattr(PO, "_open", wrap(PO._open))
            bad = PO.to_json(
                PO.simulate(p, plans, 60, len(p.axis) - 1, C, "L", reviews)
            )
        if bad["fills"] != good["fills"] or bad["intents"] != good["intents"]:
            changed += 1
            caught += bool(AU.audit_book(p, bad, scores, reviews, 60, len(p.axis) - 1))
    assert changed > 0 and caught == changed


def test_audit_k_checks_entry_and_valuation():
    n = 10
    cl = _flat(["069500", "A01"], n)
    cl["069500"] = [100.0 + k for k in range(n)]
    vols = {"069500": [1000.0] * n}
    vols["069500"][3] = 0.0
    p = _panel(cl, vols=vols)
    good = PO.to_json(PO.simulate_bench(p, p.ci["069500"], 3, 1, n - 1, C))
    assert AU.audit_k(p, good, 3, 1, n - 1) == []
    early = PO.to_json(
        PO.simulate_bench(p, p.ci["069500"], 2, 1, n - 1, C)
    )  # 하루 이른 진입
    assert AU.audit_k(p, early, 3, 1, n - 1)
    bad = json.loads(json.dumps(good))
    bad["ledger"][-1]["value"] *= 1.001
    assert AU.audit_k(p, bad, 3, 1, n - 1)


def test_audit_first_day_stop_with_empty_ledger():
    n = 70
    cl = {
        c: [100.0 + 0.1 * k for k in range(n)] for c in CODES
    }  # 상승 → I > SMA60(추세 성립)
    a = a = (
        63  # 평가 첫날 = 계획 61 의 실행일 · A01 은 그날 시가 매수 뒤 연결 종가 없음
    )
    cl["A01"] = cl["A01"][:a] + [math.nan] * (n - a)
    p = _panel(cl)
    j = p.ci["A01"]
    p.has_row[j, a] = p.exec_ok[j, a] = True
    p.O[j, a] = p.raw_open[j, a] = 106.3
    plans = {61: _plan(p, 61, CODES)}
    bk = PO.to_json(PO.simulate(p, plans, a, n - 1, C, "L", [61]))
    assert (
        bk["status"] == "CHECK_REQUIRED"
        and bk["ledger"] == []
        and len(bk["fills"]) == 5
    )
    sc = {p.axis[61]: {p.codes[k]: s for k, s in plans[61].scores.items()}}
    assert AU.audit_book(p, bk, sc, [61], a, n - 1) == []
    bk["fills"][0]["price"] *= 1.01
    assert AU.audit_book(p, bk, sc, [61], a, n - 1)
