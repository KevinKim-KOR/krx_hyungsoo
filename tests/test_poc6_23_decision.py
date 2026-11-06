"""POC6-23 행동 · 분기 정답 · 표준화 · LP(MAE · SPO+) · P/S 장부 · 독립 감사 · 판정 — 가짜 자료만.

봉인 DB · 라이브 DB · POC6-19 실제 사본은 열지 않는다. HiGHS 기본값 선행 호출 확인은 하위 프로세스에서만 한다
(전체 pytest 의 다른 시험이 쓰는 HiGHS 전역 설정을 바꾸지 않게 · PLAN §6 9).
"""

from __future__ import annotations

import copy
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from app.decision_learning import actions as A
from app.decision_learning import audit as AU
from app.decision_learning import labels as LB
from app.decision_learning import learn as LN
from app.decision_learning import policy as PL
from app.decision_learning import report as RP
from app.trend_switch import policy as TP
from app.weekly_selection import data as D
from app.weekly_selection import policy as PO
from tests.test_poc6_21_policy import flat, panel, plan

REPO = Path(__file__).resolve().parents[1]
CODES = [f"{k:06d}" for k in range(12)]
C = 0.002


def _sn(held, cash, sell_live=None, buy_live=()):
    nav = cash + sum(held.values())
    return A.Snapshot(nav, cash, dict(held), dict(sell_live or {}), set(buy_live))


def _names(acts):
    return [A.name(a, CODES) for a in acts]


# ── 행동 ────────────────────────────────────────────────────────────────────────


def test_actions_order_counts_and_bound():
    sn = _sn({0: 10.0, 1: 10.0, 2: 10.0, 3: 10.0}, 60.0)
    acts, why = A.allowed(sn, [4, 5, 6, 7, 8], set(range(12)), C, CODES)
    n = _names(acts)
    assert why is None and len(acts) == 1 + 4 + 5 + 20
    assert n[0] == "KEEP"
    assert n[1:5] == [f"SELL:{CODES[j]}" for j in range(4)]
    assert n[5:10] == [f"BUY:{CODES[j]}" for j in range(4, 9)]
    assert n[10:] == [
        f"SWITCH:{CODES[i]}>{CODES[j]}" for i in range(4) for j in range(4, 9)
    ]
    full = _sn({j: 10.0 for j in range(5)}, 50.0)
    acts, _ = A.allowed(full, [5, 6, 7, 8, 9], set(range(12)), C, CODES)
    assert len(acts) == 1 + 5 + 25 and not any(a.kind == "BUY" for a in acts)
    rng = np.random.default_rng(23)
    for _ in range(300):
        held = {
            int(j): float(rng.uniform(1, 30))
            for j in rng.choice(12, rng.integers(0, 6), replace=False)
        }
        live = {j: "PROTECT" for j in held if rng.random() < 0.2}
        cands = [int(j) for j in rng.choice(12, 5, replace=False)]
        acts, _ = A.allowed(
            _sn(held, float(rng.uniform(0, 50)), live), cands, set(range(12)), C, CODES
        )
        n = _names(acts)
        assert len(acts) <= 36 and len(set(n)) == len(n) and n[0] == "KEEP"
        assert all(a.sell is None or a.sell != a.buy for a in acts)
        assert acts == sorted(acts, key=lambda a: A.order_key(a, CODES))
        assert all(
            A.parse(x, {c: k for k, c in enumerate(CODES)}) == a
            for x, a in zip(n, acts)
        )


def test_pending_normal_intent_allows_keep_only_but_protect_does_not():
    held = {0: 10.0, 1: 10.0}
    assert A.allowed(
        _sn(held, 80.0, buy_live=[5]), [5, 6], set(range(12)), C, CODES
    ) == ([A.KEEP], "NORMAL_PENDING")
    assert A.allowed(
        _sn(held, 80.0, {0: "EXIT"}), [5, 6], set(range(12)), C, CODES
    ) == ([A.KEEP], "NORMAL_PENDING")
    acts, why = A.allowed(
        _sn(held, 80.0, {0: "PROTECT"}), [5, 6], set(range(12)), C, CODES
    )
    n = _names(acts)
    assert why is None and "SELL:000000" not in n and "SELL:000001" in n
    # Q4: 자격 밖 보유는 매도 대상 아님
    acts, _ = A.allowed(_sn(held, 80.0), [5], {1, 5}, C, CODES)
    assert "SELL:000000" not in _names(acts) and "SELL:000001" in _names(acts)
    acts, why = A.allowed(_sn({}, 100.0), [], set(), C, CODES)
    assert (acts, why) == ([A.KEEP], "NO_ACTION")


def test_slot_and_budget_boundaries_q2():
    elig = set(range(12))
    held = {j: 19.0 for j in range(5)}
    nav = 95.0
    # 보호 예정 1종 = 예정 빈자리 · 예산 h 가 1e-9 위면 BUY 포함 · 아래면 빠짐(SWITCH 는 매도 대금으로 남음)
    for h, buy in ((2e-9, True), (0.5e-9, False)):
        cash = h * nav / (1 - h)
        acts, _ = A.allowed(_sn(held, cash, {0: "PROTECT"}), [6, 7], elig, C, CODES)
        assert any(a.kind == "BUY" for a in acts) is buy
        assert any(a.kind == "SWITCH" for a in acts)
    # 보호 예정 없음 · 5종 보유 = 빈자리 0 → BUY 없음(현금이 있어도)
    acts, _ = A.allowed(_sn(held, 50.0), [6], elig, C, CODES)
    assert not any(a.kind == "BUY" for a in acts) and any(
        a.kind == "SWITCH" for a in acts
    )
    # 보호 예정 대금은 예산에 넣지 않는다: 현금 0 → 빈자리가 있어도 BUY 없음
    acts, _ = A.allowed(_sn(held, 0.0, {0: "PROTECT"}), [6], elig, C, CODES)
    assert not any(a.kind == "BUY" for a in acts)
    # 매수 대기 1 = 빈자리 −1(미결이라 KEEP 만이지만 식은 같다) · 4종 보유 = 빈자리 1
    acts, _ = A.allowed(_sn({j: 19.0 for j in range(4)}, 1e-6), [6], elig, C, CODES)
    assert any(a.kind == "BUY" for a in acts)


@pytest.mark.parametrize("cost", [0.002, 0.004])
def test_amounts_and_z_use_book_cost_q3(cost):
    sn = _sn({0: 30.0}, 10.0)
    a = A.Action("SWITCH", sell=0, buy=5)
    b, s, k = A.amounts(sn, a, cost)
    assert s == pytest.approx(0.75) and b == pytest.approx(0.2 / (1 + cost))
    assert k == pytest.approx(cost * (0.2 / (1 + cost) + 0.75))
    u = {0: np.arange(34.0), 5: -np.arange(34.0)}
    z = A.z_vector(a, b, s, u)
    assert (
        z[0] == b
        and np.allclose(z[1:35], b * u[5])
        and z[35] == s
        and np.allclose(z[36:], s * u[0])
    )
    small = _sn({0: 1.0}, 0.05)
    b2, s2, _ = A.amounts(small, A.Action("SWITCH", sell=0, buy=5), cost)
    assert b2 == pytest.approx(min(0.2, 0.05 / 1.05 + (1 - cost) / 1.05) / (1 + cost))
    assert A.amounts(sn, A.KEEP, cost) == (0.0, 0.0, 0.0)


# ── 참조 경로 · 분기 정답 ────────────────────────────────────────────────────────


def _rows(p, val=1.0):
    return {j: [val] * 34 for j in range(len(p.codes))}


def _dplans(p, specs):
    return {
        i: PL.DPlan(
            signal=i,
            r0=plan(p, i, sc, cands=cands, excluded=ex),
            rows=rows or _rows(p),
            quarter=q,
        )
        for i, sc, cands, ex, rows, q in specs
    }


def _ref(p, plans, end=None):
    end = end if end is not None else len(p.axis) - 1
    return LB.reference(p, plans, min(plans), end, C)


def test_reference_loop_equals_poc6_21_simulate_and_snapshot_before_weekly():
    rng = np.random.default_rng(5)
    closes = {
        c: list(100 * np.exp(np.cumsum(rng.normal(0, 0.03, 120)))) for c in "ABCDEFGH"
    }
    p = panel(closes)
    specs = []
    for i in range(0, 95, 5):
        sc = {c: float(rng.normal(0, 0.01)) for c in "ABCDEFGH"}
        specs.append((i, sc, list("ABCDE") if i % 2 else list("DEFGH"), None, None, ""))
    plans = _dplans(p, specs)
    bk, states = _ref(p, plans, 110)
    assert LB.reference_same(p, plans, 0, 110, C, bk)
    assert bk.status == "OK" and set(states) == set(plans)
    sn0, _pl = states[0]
    assert sn0.nav == 100.0 and not sn0.held  # 첫 판단 = 편입 전


def _scene(no_trade=(), no_row=()):
    p = flat("ABCDEFG", n=40, no_trade=no_trade, no_row=no_row)
    plans = _dplans(
        p,
        [
            (
                0,
                {"A": 1.0, "B": 1.0, "C": -1, "D": -1, "E": -1},
                list("ABCDE"),
                None,
                None,
                "",
            ),
            (5, dict.fromkeys("ABCDEFG", 0.0), list("CDEFG"), None, None, ""),
        ],
    )
    bk, states = _ref(p, plans)
    snap, payload = states[5]
    return p, plans, snap, payload


def test_branch_labels_match_hand_calculation_on_flat_prices():
    p, plans, snap, payload = _scene()
    rec = LB.label(p, plans[5], snap, payload, 5, C)
    ci = p.ci
    units = 20.0 / (1 + C) / 100.0
    va = units * 100.0
    nav_d = 60.0 + 2 * va
    assert snap.nav == pytest.approx(nav_d) and rec["excluded"] is None
    g = dict(zip(rec["actions"], rec["g"]))
    assert g["KEEP"] == 0.0
    eq = 60.0 + 2 * va
    buy = min(0.2 * eq, 60.0)
    assert g["BUY:C"] == pytest.approx(-buy * C / (1 + C) / nav_d, rel=1e-12)
    assert g["SELL:A"] == pytest.approx(-va * C / nav_d, rel=1e-12)
    cash2 = 60.0 + va * (1 - C)
    buy2 = min(0.2 * (cash2 + va), cash2)
    assert g["SWITCH:A>C"] == pytest.approx(
        (-va * C - buy2 * C / (1 + C)) / nav_d, rel=1e-12
    )
    assert len(rec["actions"]) == 1 + 2 + 5 + 10 and ci["C"] in plans[5].rows


def test_branch_cancel_defer_and_unresolved_exclusion():
    # E = 7 에 C 거래 불가 → 매수 취소 · 비용 0 → g = 0(KEEP 과 같은 값)
    p, plans, snap, payload = _scene(no_trade=(("C", 7),))
    g = dict(
        zip(*[LB.label(p, plans[5], snap, payload, 5, C)[k] for k in ("actions", "g")])
    )
    assert g["BUY:C"] == 0.0
    # E = 7 에 A 거래 불가 → 매도 이연(8 일 체결) · 같은 평탄 가격이라 g 는 체결 비용만
    p, plans, snap, payload = _scene(no_trade=(("A", 7),))
    g = dict(
        zip(*[LB.label(p, plans[5], snap, payload, 5, C)[k] for k in ("actions", "g")])
    )
    va = 20.0 / (1 + C)
    assert g["SELL:A"] == pytest.approx(-va * C / snap.nav, rel=1e-12)
    # 분기 안(≤ T = 26)에 보유 A 의 행이 없음 → 한 행동이라도 미확정 → D 전체 제외(행동 삭제 없음)
    p, plans, snap, payload = _scene(no_row=(("A", 20),))
    rec = LB.label(p, plans[5], snap, payload, 5, C)
    assert rec["excluded"] == "BRANCH_UNRESOLVED" and rec["g"] is None
    assert "SELL:A" not in rec["unresolved"] and "KEEP" in rec["unresolved"]


def test_branch_protect_inside_horizon_and_pending_keep_only():
    closes = {c: [100.0] * 40 for c in "ABCDEFG"}
    closes["A"] = [100.0] * 12 + [80.0] * 28
    p = panel(closes)
    plans = _dplans(
        p,
        [
            (
                0,
                {"A": 1.0, "B": 1.0, "C": -1, "D": -1, "E": -1},
                list("ABCDE"),
                None,
                None,
                "",
            ),
            (5, dict.fromkeys("ABCDEFG", 0.0), list("CDEFG"), None, None, ""),
            (6, dict.fromkeys("ABCDEFG", 0.0), list("CDEFG"), None, None, ""),
        ],
    )
    plans[5].r0.scores[p.ci["C"]] = 1.0  # R0 가 5 일에 C 를 사서 6 일엔 매수 대기
    _bk, states = _ref(p, plans)
    rec5 = LB.label(p, plans[5], *states[5], 5, C)
    g = dict(zip(rec5["actions"], rec5["g"]))
    units = 20.0 / (1 + C) / 100.0
    # KEEP 분기: 12 일 −20% → 보호 매도 14 일(80) · SELL:A 분기: 7 일 100 에 매도 → 차이 = units × 20 − 비용 차
    assert g["SELL:A"] == pytest.approx(
        (units * 100 * (1 - C) - units * 80 * (1 - C)) / states[5][0].nav, rel=1e-12
    )
    rec6 = LB.label(p, plans[6], *states[6], 6, C)
    assert rec6["excluded"] == "NORMAL_PENDING" and rec6["actions"] == ["KEEP"]
    assert rec6["g"] is None and "nav_t" not in rec6  # 제외된 D 는 정답을 만들지 않는다


# ── 표준화 · 결측 대치 ───────────────────────────────────────────────────────────


def test_column_stats_date_balanced_population_variance_missing_and_constant():
    names = ["c0", "c1", "c2", "c3"]
    dates = [
        [
            [1.0, None, 5.0, None],
            [3.0, None, 5.0, None],
        ],  # c1 은 이 날 전체 결측 → 그 열에서만 빠짐
        [[10.0, 2.0, 5.0, None], [None, 4.0, 5.0, None], [None, 6.0, 5.0, 7.0]],
    ]
    mu, sd, const, info = LN.column_stats(dates, names)
    assert mu[0] == pytest.approx((2.0 + 10.0) / 2)
    assert sd[0] == pytest.approx(math.sqrt(((25 + 9) / 2 + 16) / 2))
    assert mu[1] == pytest.approx(4.0) and sd[1] == pytest.approx(math.sqrt(8 / 3))
    assert const[2] and sd[2] == 0.0 and const[3]  # c3 관측 1개 = 상수
    assert info[1] == {
        "column": "c1",
        "observed": 3,
        "missing": 2,
        "dates": 1,
        "constant": False,
    }
    u, imp = LN.transform([None, 4.0, 5.0, 7.0], mu, sd, const)
    assert imp == 1 and u[0] == 0.0 and u[1] == 0.0 and u[2] == 0.0 and u[3] == 0.0
    u, imp = LN.transform([10.0, 6.0, 5.0, None], mu, sd, const)
    assert (
        imp == 1
        and u[0] == pytest.approx(4.0 / sd[0])
        and u[1] == pytest.approx(2.0 / sd[1])
    )
    with pytest.raises(D.CheckRequired, match="유효 관측 0"):
        LN.column_stats([[[None]], [[None]]], ["x"])
    with pytest.raises(D.CheckRequired, match="비유한"):
        LN.transform([math.inf], [0.0], [1.0], [False])


def test_scale_rms_date_balanced_with_floor():
    assert LN.scale([[0.1, -0.1], [0.2]]) == pytest.approx(math.sqrt((0.01 + 0.04) / 2))
    assert LN.scale([[0.0], [0.0, 0.0]]) == LN.SG_MIN


# ── LP · SPO+ ───────────────────────────────────────────────────────────────────


def _problem(rng, nd=12, kappa=True, dim=None):
    dates = []
    for _ in range(nd):
        n = int(rng.integers(1, 6))
        z = np.zeros((n, LN.NB))
        if dim is None:
            z[:, :8] = rng.normal(0, 1, (n, 8))
        else:
            z[:, dim] = rng.normal(0, 1, n)
        y = rng.normal(0, 1, n)
        kap = np.abs(rng.normal(0, 0.2, n)) if kappa else np.zeros(n)
        star = int(np.argmax(np.concatenate([[0.0], y])))
        dates.append({"z": z, "kappa": kap, "y": y, "star": star})
    return LN.Problem(dates)


def _grid(pb, kind):
    best = math.inf
    for b in np.linspace(-1, 1, 4001):
        beta = np.zeros(LN.NB)
        beta[0] = b
        v = LN.direct_mae(pb, beta) if kind == "P" else LN.direct_spo(pb, beta)[0]
        best = min(best, v)
    return best


@pytest.mark.parametrize("kind", ["P", "S"])
def test_lp_matches_one_dimensional_search_and_numeric_conditions(kind):
    pb = _problem(np.random.default_rng(7), dim=0)
    rec = LN.fit(pb, kind)
    assert rec["status"] == 0 and LN.check(rec) == []
    assert rec["abs_diff"] <= LN.TOL and rec["l1"] <= 1 + LN.TOL
    g = _grid(pb, kind)
    assert rec["lp_full"] <= g + 1e-9 and abs(rec["lp_full"] - g) < 5e-3
    assert rec["notices"] == 1 and rec["options"] == {"threads": 1}
    if kind == "S":
        assert rec["c_fixed"] != 0.0 and rec["upper_margin"] >= -LN.UPPER_TOL


@pytest.mark.parametrize("kind", ["P", "S"])
@pytest.mark.parametrize("shift", [1e-5, -1e-5])
def test_absolute_difference_catches_both_directions(kind, shift):
    pb = _problem(np.random.default_rng(11))
    rec = LN.fit(pb, kind)
    bad = {**rec, **LN.measure(pb, kind, rec["x"], rec["fun_raw"] + shift)}
    assert any("abs_diff" in x for x in LN.check(bad))


def test_spo_raw_objective_negative_but_full_loss_nonnegative():
    rng = np.random.default_rng(3)
    dates = []
    for _ in range(8):
        z = np.zeros((3, LN.NB))
        z[:, 0] = rng.normal(0, 1, 3)
        y = np.array([5.0, -1.0, -2.0])
        dates.append({"z": z, "kappa": np.full(3, 0.3), "y": y, "star": 1})
    rec = LN.fit(LN.Problem(dates), "S")
    assert (
        rec["fun_raw"] < 0 < rec["c_fixed"]
        and rec["direct"] >= 0
        and LN.check(rec) == []
    )


def test_spo_properties_on_random_finite_sets():
    rng = np.random.default_rng(29)
    for _ in range(40):
        pb = _problem(rng, nd=6)
        beta = rng.normal(0, 0.3, LN.NB)
        loss, margin = LN.direct_spo(pb, beta)
        assert loss >= 0 and margin >= -1e-12
    beta = np.zeros(LN.NB)
    beta[:4] = [0.2, -0.3, 0.1, 0.25]
    dates = []
    for _ in range(5):
        z = np.zeros((4, LN.NB))
        z[:, :4] = rng.normal(0, 1, (4, 4))
        kap = np.abs(rng.normal(0, 0.1, 4))
        y = z @ beta - kap  # 예측 = 정답
        dates.append(
            {
                "z": z,
                "kappa": kap,
                "y": y,
                "star": int(np.argmax(np.concatenate([[0.0], y]))),
            }
        )
    assert LN.direct_spo(LN.Problem(dates), beta)[0] == pytest.approx(0.0, abs=1e-12)


_SUB = """
import sys, warnings
sys.path.insert(0, {repo!r})
import numpy as np
from scipy.optimize import linprog
from app.decision_learning import learn as LN
if {default_first}:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        linprog([1.0], A_ub=[[-1.0]], b_ub=[0.0], bounds=(0, None), method="highs-ds")
z = np.zeros((2, LN.NB)); z[:, 0] = [1.0, -1.0]
pb = LN.Problem([{{"z": z, "kappa": np.zeros(2), "y": np.array([0.5, -0.5]), "star": 1}}])
rec = LN.fit(pb, "S")
print(rec["status"], len(LN.check(rec)))
"""


@pytest.mark.parametrize("default_first,expect", [(False, "0 0"), (True, "4 1")])
def test_highs_threads_one_from_first_call_no_default_fallback(default_first, expect):
    code = _SUB.format(repo=str(REPO), default_first=default_first)
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=120
    )
    assert out.returncode == 0, out.stderr[-500:]
    assert out.stdout.strip().splitlines()[-1] == expect


def test_only_one_linprog_call_site_in_package():
    src = [f for f in (REPO / "app/decision_learning").glob("*.py")]
    hits = [
        (f.name, line)
        for f in src
        for line in f.read_text().splitlines()
        if "linprog(" in line
    ]
    assert [h[0] for h in hits] == ["learn.py"] and len(hits) == 1


# ── P/S 장부 · 독립 감사 ─────────────────────────────────────────────────────────


def _model(beta0=1.0, sg=1.0):
    beta = [0.0] * LN.NB
    beta[0] = beta0
    return {
        "Q": {
            "mu": [0.0] * 34,
            "sigma": [1.0] * 34,
            "constant": [False] * 34,
            "s_g": sg,
            "P": {"beta": beta},
            "S": {"beta": [-x for x in beta]},
        }
    }


def _book_scene(cost=C, excluded=None):
    rng = np.random.default_rng(9)
    closes = {
        c: list(100 * np.exp(np.cumsum(rng.normal(0.001, 0.02, 90))))
        for c in "ABCDEFGHIJ"
    }
    p = panel(closes)
    specs = []
    for i in range(0, 80, 5):
        sc = {c: float(rng.normal(0, 0.01)) for c in "ABCDEFGHIJ"}
        sc["A"] = sc["B"] = 0.05
        cands = (
            list("ABCDE")
            if i == 0
            else sorted("ABCDEFGHIJ", key=lambda c: (-closes[c][i], c))[:5]
        )
        specs.append((i, sc, cands, None, None, "Q"))
    plans = _dplans(p, specs)
    if excluded:
        i, t, why = excluded
        del plans[i].rows[p.ci[t]]
        del plans[i].r0.scores[p.ci[t]]
        plans[i].r0.excluded[p.ci[t]] = why
    return p, plans


def _ctx(p, plans):
    sigs = sorted(plans)
    return {
        "cands": {p.axis[i]: [p.codes[j] for j in plans[i].r0.cands] for i in sigs},
        "outs": {
            p.axis[i]: {p.codes[j]: w for j, w in plans[i].r0.excluded.items()}
            for i in sigs
        },
        "members": {p.axis[i]: {p.codes[j] for j in plans[i].rows} for i in sigs},
        "rows": {
            p.axis[i]: {p.codes[j]: v for j, v in plans[i].rows.items()} for i in sigs
        },
        "assign": {p.axis[i]: "Q" for i in sigs},
        "scores_r": {
            p.axis[i]: {p.codes[j]: s for j, s in plans[i].r0.scores.items()}
            for i in sigs
        },
    }


@pytest.mark.parametrize("kind", ["P", "S"])
def test_ps_book_chooses_argmax_and_audit_passes(kind):
    p, plans = _book_scene()
    models = _model()
    bk = PO.to_json(PL.simulate(p, plans, models, kind, 0, 89, C, f"{kind}_20"))
    assert bk["status"] == "OK" and bk["plans"][0]["first"] is True
    for pl in bk["plans"][1:]:
        qs = [v for _n, v in pl["actions"]]
        assert pl["chosen"] == pl["actions"][int(np.argmax(qs))][0]
    kinds = {pl["chosen"].split(":")[0] for pl in bk["plans"][1:]}
    assert (
        ("BUY" in kinds or "SWITCH" in kinds)
        if kind == "P"
        else kinds <= {"KEEP", "SELL"}
    )
    ctx = _ctx(p, plans)
    assert AU.audit_book(p, bk, ctx, models, kind, ctx["scores_r"], 0, 89) == []


def _mut_chosen(bk):
    pl = next(pl for pl in bk["plans"][1:] if pl["chosen"] != "KEEP")
    pl["chosen"] = "KEEP"


def _mut_q(bk):
    pl = next(pl for pl in bk["plans"][1:] if len(pl["actions"]) > 1)
    pl["actions"][1][1] += 1e-3


def _mut_order(bk):
    pl = next(pl for pl in bk["plans"][1:] if len(pl["actions"]) > 2)
    pl["actions"][1], pl["actions"][2] = pl["actions"][2], pl["actions"][1]


def _mut_intent(bk):
    it = next(it for it in bk["intents"] if it.get("action") and it["side"] == "BUY")
    it["gap"] = 999


def _mut_model(bk):
    bk["plans"][1]["model"] = "Z_P"


def _mut_heldout(bk):
    bk["plans"][2]["held_not_eligible"] = [["000000", "liquidity"]]


@pytest.mark.parametrize(
    "mut", [_mut_chosen, _mut_q, _mut_order, _mut_intent, _mut_model, _mut_heldout]
)
def test_independent_audit_catches_decision_record_changes(mut):
    p, plans = _book_scene()
    models = _model()
    bk = PO.to_json(PL.simulate(p, plans, models, "P", 0, 89, C, "P_20"))
    bad = copy.deepcopy(bk)
    mut(bad)
    ctx = _ctx(p, plans)
    assert AU.audit_book(p, bad, ctx, models, "P", ctx["scores_r"], 0, 89)


def test_audit_catches_slot_rule_variant(monkeypatch):
    """빈자리를 하나 덜 센 변이(4종 보유를 5종처럼 · 판정 Q2 와 다른 식)를 정책에 넣으면 독립 감사가 잡는다."""
    p, plans = _book_scene()
    models = _model()
    real = A.allowed

    def variant(sn, cands, eligible, cost, codes):
        acts, why = real(sn, cands, eligible, cost, codes)
        if len(sn.held) == 4:
            acts = [a for a in acts if a.kind != "BUY"]
        return acts, why

    monkeypatch.setattr(A, "allowed", variant)
    bk = PO.to_json(PL.simulate(p, plans, models, "P", 0, 89, C, "P_20"))
    monkeypatch.undo()
    led = {r["date"]: r for r in bk["ledger"]}
    hit = [
        pl
        for pl in bk["plans"][1:]
        if len(led[pl["signal"]]["pos"]) == 4 and not pl["keep_only"]
    ]
    assert hit, "4종 보유 · 미결 없는 판단일이 장면에 없음"
    ctx = _ctx(p, plans)
    probs = AU.audit_book(p, bk, ctx, models, "P", ctx["scores_r"], 0, 89)
    assert any("행동 집합" in x for x in probs)


def test_q4_held_out_and_missing_reason():
    p, plans = _book_scene(excluded=(20, "A", "liquidity"))
    bk = PO.to_json(PL.simulate(p, plans, _model(), "S", 0, 89, C, "S_20"))
    led = {r["date"]: r for r in bk["ledger"]}
    assert (
        "A" in led[p.axis[20]]["pos"]
    )  # S(β0 < 0) 는 KEEP 만 → 첫 계획에서 산 A 를 계속 보유
    pl = next(pl for pl in bk["plans"] if pl["signal"] == p.axis[20])
    assert pl["held_not_eligible"] == [["A", "liquidity"]]
    assert not any(n.startswith(("SELL:A", "SWITCH:A")) for n, _q in pl["actions"])
    ctx = _ctx(p, plans)
    assert AU.audit_book(p, bk, ctx, _model(), "S", ctx["scores_r"], 0, 89) == []
    p, plans = _book_scene(excluded=(20, "A", "liquidity"))
    del plans[20].r0.excluded[p.ci["A"]]
    with pytest.raises(D.CheckRequired, match="자격 · 제외 사유 없음"):
        PL.simulate(p, plans, _model(), "S", 0, 89, C, "S_20")


def test_40bp_book_uses_same_beta_and_book_cost():
    p, plans = _book_scene()
    models = _model()
    bk = PO.to_json(PL.simulate(p, plans, models, "P", 0, 89, 0.004, "P_40"))
    pl = next(
        pl
        for pl in bk["plans"][1:]
        if any(n.startswith("BUY:") for n, _ in pl["actions"])
    )
    h = pl["cash"] / pl["nav"]
    b = min(0.2, h) / 1.004
    q = dict(pl["actions"])[next(n for n, _ in pl["actions"] if n.startswith("BUY:"))]
    assert q == pytest.approx(b - 0.004 * b, rel=1e-12)


def test_check_bounds_rejects_more_than_five_or_negative_cash():
    p = flat("ABCDEFG", n=5)
    st = PO._State(p, PO.Book(curve="X", cost=C), 4)
    st.hold = {j: {"units": 1.0} for j in range(6)}
    with pytest.raises(D.CheckRequired, match="슬롯"):
        PL.check_bounds(p, st, 0)
    st.hold, st.cash = {}, -1e-6
    with pytest.raises(D.CheckRequired, match="현금"):
        PL.check_bounds(p, st, 0)


# ── 판정 ────────────────────────────────────────────────────────────────────────


def _curve(cagr, mdd=-0.2, subs=(0.1, 0.1, 0.1), to=2.0):
    return {
        "total": {"cagr": cagr, "mdd": mdd},
        "subperiods": [{"return": x} for x in subs],
        "turnover": {"annual": to},
    }


def _base_case():
    test = {}
    for c in ("20", "40"):
        test[f"P_{c}"] = _curve(0.05)
        test[f"S_{c}"] = _curve(0.07, subs=(0.2, 0.2, 0.0))
        test[f"R_{c}"] = _curve(0.05)
        test[f"K_{c}"] = _curve(0.05)
    ex = {
        f"{k}_{c}": {"underwater": {"longest_days": 100}}
        for k in "PSRK"
        for c in ("20", "40")
    }
    return test, ex, {"ci95": [0.0001, 0.002]}


def _set(test, ex, boot, case):
    if case == "gap":
        test["S_20"]["total"]["cagr"] = 0.0599
    elif case == "subs":
        test["S_20"]["subperiods"] = [{"return": x} for x in (0.2, 0.0, 0.0)]
    elif case == "purpose":
        test["R_20"]["total"]["cagr"] = 0.065
    elif case == "mdd":
        test["S_40"]["total"]["mdd"] = -0.2501
    elif case == "uw":
        ex["S_20"]["underwater"]["longest_days"] = 227
    elif case == "turnover":
        test["S_40"]["turnover"]["annual"] = 6.01
    elif case == "cost":
        test["K_40"]["total"]["cagr"] = 0.07
    elif case == "boot0":
        boot["ci95"] = [0.0, 0.002]
    elif case == "bootneg":
        boot["ci95"] = [-0.003, -0.0001]


@pytest.mark.parametrize(
    "case,field,value",
    [
        (None, "candidate", "FURTHER_REVIEW_CANDIDATE"),
        ("gap", "decision_gain", "NOT_SHOWN"),
        ("subs", "decision_gain", "NOT_SHOWN"),
        ("purpose", "purpose", "PURPOSE_NOT_MET"),
        ("mdd", "risk_burden", "RISK_BURDEN_NOT_MET"),
        ("uw", "risk_burden", "RISK_BURDEN_NOT_MET"),
        ("turnover", "risk_burden", "RISK_BURDEN_NOT_MET"),
        ("cost", "cost_stress", "COST_STRESS_NOT_MET"),
        ("boot0", "uncertainty", "UNCERTAIN"),
        ("bootneg", "uncertainty", "NEGATIVE_IN_STUDY"),
    ],
)
def test_judge_combination_table(case, field, value):
    test, ex, boot = _base_case()
    _set(test, ex, boot, case)
    j = RP.judge("OK", test, ex, boot)
    assert j[field] == value
    assert (j["candidate"] == "FURTHER_REVIEW_CANDIDATE") is (case is None)
    assert j["OPERATION_ADOPTION"] == "NO" and j["TOTAL_RETURN_VALIDATED"] == "NO"
    if case is None:
        assert (
            j["uncertainty"] == "POSITIVE_IN_STUDY"
            and j["decision_gain"] == "DECISION_GAIN_OBSERVED"
        )


def test_judge_boundaries_are_inclusive_where_designed():
    test, ex, boot = _base_case()
    test["P_20"]["total"]["cagr"] = 0.0
    test["S_20"]["total"]["cagr"] = 0.01  # 정확히 1%p(부동소수 그대로) = 충족
    assert RP.judge("OK", test, ex, boot)["decision_gain"] == "DECISION_GAIN_OBSERVED"
    test, ex, boot = _base_case()
    test["P_40"]["total"]["mdd"] = test["K_40"]["total"]["mdd"] = 0.0
    test["S_40"]["total"]["mdd"] = -0.05  # 정확히 5%p 더 큰 낙폭 = 허용
    ex["S_20"]["underwater"]["longest_days"] = 226  # K + 126 = 허용
    test["S_20"]["turnover"]["annual"] = 6.0
    assert RP.judge("OK", test, ex, boot)["risk_burden"] == "RISK_BURDEN_MET"


@pytest.mark.parametrize(
    "validity", ["CHECK_REQUIRED", "DATA_SHORT", "INSUFFICIENT_DATA", "BUDGET_STOP"]
)
def test_judge_not_judged_when_not_ok(validity):
    j = RP.judge(validity, None, None, None)
    assert j["candidate"] == "NOT_JUDGED" and j["decision_gain"] == "NOT_JUDGED"


# ── 변이 대비 보강(경계 · 정의) ──────────────────────────────────────────────────


def test_label_end_is_close_of_twentieth_trading_day_from_e():
    """T = E 를 1일로 센 20번째 = D + 21 종가 — 그 날 가격 변화가 정답에 들어가고 다음 날은 안 들어간다."""
    for jump, inside in ((26, True), (27, False)):
        closes = {c: [100.0] * 40 for c in "ABCDEFG"}
        closes["A"] = [100.0] * jump + [110.0] * (40 - jump)
        p = panel(closes)
        plans = _dplans(
            p,
            [
                (
                    0,
                    {"A": 1.0, "B": 1.0, "C": -1, "D": -1, "E": -1},
                    list("ABCDE"),
                    None,
                    None,
                    "",
                ),
                (5, dict.fromkeys("ABCDEFG", 0.0), list("CDEFG"), None, None, ""),
            ],
        )
        _bk, states = _ref(p, plans)
        snap, payload = states[5]
        rec = LB.label(p, plans[5], snap, payload, 5, C)
        g = dict(zip(rec["actions"], rec["g"]))
        units = 20.0 / (1 + C) / 100.0
        end_px = 110.0 if inside else 100.0
        assert g["SELL:A"] == pytest.approx(
            (units * 100 * (1 - C) - units * end_px) / snap.nav, rel=1e-12
        )


def test_problem_star_kappa_and_y_from_labels():
    from app.decision_learning import flow as FW

    closes = {c: [100.0] * 40 for c in "ABCDEFG"}
    closes["A"] = [100.0] * 12 + [80.0] * 28
    p = panel(closes)
    rows = {
        j: [float(j + 1)] * 33 + [None if j % 2 == 0 else float(j)]
        for j in range(len(p.codes))
    }
    plans = _dplans(
        p,
        [
            (
                0,
                {"A": 1.0, "B": 1.0, "C": -1, "D": -1, "E": -1},
                list("ABCDE"),
                None,
                rows,
                "Q",
            ),
            (5, dict.fromkeys("ABCDEFG", 0.0), list("CDEFG"), None, rows, "Q"),
        ],
    )
    _bk, states = _ref(p, plans)
    rec = LB.label(p, plans[5], *states[5], 5, C)
    pb, meta = FW.problem(p, plans, {p.axis[5]: rec}, [5])
    g = rec["g"]
    sg = LN.scale([g[1:]])
    d = pb.dates[0]
    assert meta["s_g"] == sg and d["star"] == int(np.argmax(g)) == rec["actions"].index(
        "SELL:A"
    )
    assert np.allclose(d["y"], np.asarray(g[1:]) / sg, rtol=0, atol=0)
    sn = states[5][0]
    for k, n in enumerate(rec["actions"][1:]):
        b, s, kk = A.amounts(sn, A.parse(n, p.ci), C)
        assert d["kappa"][k] == kk / sg
    need = A.needed([A.parse(n, p.ci) for n in rec["actions"]])
    assert meta["imputed_cells"] == sum(1 for j in need if j % 2 == 0) > 0
    assert meta["columns"][33]["missing"] == meta["imputed_cells"]
    assert meta["columns"][33]["observed"] == len(need) - meta["imputed_cells"]


def test_problem_star_is_keep_when_every_action_loses():
    from app.decision_learning import flow as FW

    p, plans, snap, payload = _scene()
    rec = LB.label(p, plans[5], snap, payload, 5, C)
    assert max(rec["g"][1:]) < 0
    pb, _meta = FW.problem(p, plans, {p.axis[5]: rec}, [5])
    assert pb.dates[0]["star"] == 0


def test_ties_choose_first_in_fixed_order():
    p, plans = _book_scene()
    zero = _model(beta0=0.0)
    bk = PO.to_json(PL.simulate(p, plans, zero, "P", 0, 89, 0.0, "P_0"))
    assert {pl["chosen"] for pl in bk["plans"][1:]} == {"KEEP"}
    assert all(all(q == 0.0 for _n, q in pl["actions"]) for pl in bk["plans"][1:])


def test_reference_same_detects_a_different_book():
    p, plans, _snap, _payload = _scene()
    bk, _states = _ref(p, plans, 30)
    assert LB.reference_same(p, plans, 0, 30, C, bk)
    bk.ledger[-1]["value"] += 1e-9
    assert not LB.reference_same(p, plans, 0, 30, C, bk)


def test_losses_are_date_balanced_by_hand():
    z1 = np.zeros((1, LN.NB))
    z3 = np.zeros((3, LN.NB))
    z1[0, 0], z3[:, 0] = 1.0, [1.0, 2.0, -1.0]
    d1 = {"z": z1, "kappa": np.array([0.1]), "y": np.array([0.5]), "star": 1}
    d2 = {
        "z": z3,
        "kappa": np.array([0.0, 0.2, 0.1]),
        "y": np.array([-0.3, 0.4, 0.0]),
        "star": 2,
    }
    pb = LN.Problem([d1, d2])
    beta = np.zeros(LN.NB)
    beta[0] = 0.5
    q1 = [0.5 - 0.1]
    q2 = [0.5 - 0.0, 1.0 - 0.2, -0.5 - 0.1]
    mae = (
        abs(q1[0] - 0.5) + (abs(q2[0] + 0.3) + abs(q2[1] - 0.4) + abs(q2[2] - 0.0)) / 3
    ) / 2
    assert LN.direct_mae(pb, beta) == pytest.approx(mae, rel=1e-12)
    v1 = [0.0, 2 * q1[0] - 0.5]
    v2 = [0.0] + [2 * a - b for a, b in zip(q2, [-0.3, 0.4, 0.0])]
    spo = ((max(v1) - v1[1]) + (max(v2) - v2[2])) / 2
    assert LN.direct_spo(pb, beta)[0] == pytest.approx(spo, rel=1e-12)


# ── 실행 전 독립 검토 지적 보강 ──────────────────────────────────────────────────


@pytest.mark.parametrize("which", ["l1", "violation", "bound", "objective"])
def test_numeric_check_branches_each_caught(which):
    pb = _problem(np.random.default_rng(13))
    rec = LN.fit(pb, "P")
    x = np.asarray(rec["x"], dtype=float)
    fun = rec["fun_raw"]
    if which == "l1":
        x[: LN.NB] *= 3.0
        x[LN.NB : 2 * LN.NB] *= 3.0  # noqa: E203
        # 행 제약은 만족하게 t 를 키움
        x[2 * LN.NB :] += 50.0  # noqa: E203
        fun = float(LN.mae_lp(pb)[0] @ x)
    elif which == "violation":
        x[2 * LN.NB] = 0.0
        x[: 2 * LN.NB] = 0.0
        x[0] = 0.5
        fun = float(LN.mae_lp(pb)[0] @ x)
    elif which == "bound":
        x[-1] = -0.5
        fun = float(LN.mae_lp(pb)[0] @ x)
    else:
        fun += 1e-3
    bad = {**rec, **LN.measure(pb, "P", x, fun)}
    key = {"l1": "l1_excess", "violation": "max_violation", "bound": "bound_violation"}
    probs = LN.check(bad)
    if which == "objective":
        bad2 = {**bad, "fun_recomputed": rec["fun_raw"] + 1.0}
        assert any("목적값 재계산" in x for x in LN.check(bad2))
    else:
        assert any(key[which] in x for x in probs), probs


def test_solve_reemits_other_warnings_and_counts_threads_notice(monkeypatch):
    real = LN.linprog

    def noisy(*a, **k):
        import warnings

        warnings.warn("다른 경고", LN.OptimizeWarning)
        warnings.warn(
            "Unrecognized options detected: {'threads': 1, 'foo': 2}",
            LN.OptimizeWarning,
        )
        return real(*a, **k)

    monkeypatch.setattr(LN, "linprog", noisy)
    pb = _problem(np.random.default_rng(17), nd=3)
    with pytest.warns(LN.OptimizeWarning) as got:
        rec = LN.fit(pb, "S")
    msgs = [str(w.message) for w in got]
    assert "다른 경고" in msgs and any("'foo': 2" in m for m in msgs)
    assert rec["notices"] == 1


def test_problem_star_tie_with_keep_goes_to_keep():
    from app.decision_learning import flow as FW

    p, plans, snap, payload = _scene(no_trade=(("C", 7),))
    rec = LB.label(p, plans[5], snap, payload, 5, C)
    g = dict(zip(rec["actions"], rec["g"]))
    assert g["BUY:C"] == 0.0 == max(rec["g"])  # 매수 취소 = KEEP 과 같은 값(동점)
    pb, _meta = FW.problem(p, plans, {p.axis[5]: rec}, [5])
    assert pb.dates[0]["star"] == 0


def _protect_scene():
    closes = {c: [100.0] * 40 for c in "ABCDEFG"}
    closes["A"] = [100.0] * 5 + [80.0] * 4 + [60.0] * 31
    p = panel(closes, no_trade=(("A", 7),))
    plans = _dplans(
        p,
        [
            (
                0,
                {"A": 1.0, "B": 1.0, "C": -1, "D": -1, "E": -1},
                list("ABCDE"),
                None,
                None,
                "",
            ),
            (5, dict.fromkeys("ABCDEFG", 0.0), list("CDEFG"), None, None, ""),
        ],
    )
    _bk, states = _ref(p, plans)
    return p, plans, states[5]


def test_restored_state_keeps_shared_intents_and_deferred_protect_resolves():
    p, _plans, (snap, payload) = _protect_scene()
    assert snap.sell_live == {
        p.ci["A"]: "PROTECT"
    }  # D 종가 보호 · 실행일 E 는 거래 불가
    st = LB._restore(p, payload, 30, C)
    for it in st.sell_live.values():
        assert any(it is x for x in st.due.get(it["exec_idx"], []))
    units = 20.0 / (1 + C) / 100.0
    want = 60.0 + units * 80.0 * (1 - C) + units * 100.0  # 8일 이연 체결(80) · B 평탄
    assert LB.branch(p, payload, 5, A.KEEP, C) == pytest.approx(want, rel=1e-12)


def test_check_bounds_is_called_inside_walk_and_branch(monkeypatch):
    real = PO._open

    def sixth(p, st, i, today, cost):
        real(p, st, i, today, cost)
        if len(st.hold) == 2 and 6 not in st.hold:
            st.hold.update({k: dict(st.hold[next(iter(st.hold))]) for k in range(2, 6)})
            st.hold[6] = dict(st.hold[2])

    p, plans, (snap, payload) = _protect_scene()
    monkeypatch.setattr(PO, "_open", sixth)
    with pytest.raises(D.CheckRequired, match="슬롯"):
        PL.walk(
            p,
            plans,
            0,
            30,
            C,
            "X",
            lambda i, st, ls: TP._weekly(p, st, plans[i].r0, i, False, ls),
        )
    with pytest.raises(D.CheckRequired, match="슬롯"):
        LB.branch(p, payload, 5, A.KEEP, C)


def _full_scene():
    closes = {c: [100.0] * 60 for c in "ABCDEFG"}
    closes["A"] = [100.0] * 10 + [80.0] * 50
    p = panel(closes, no_trade=(("A", 12),))
    specs = [
        (
            0,
            {"A": 1.0, "B": 1.0, "C": 1.0, "D": 1.0, "E": -1.0},
            list("ABCDE"),
            None,
            None,
            "Q",
        ),
        (
            5,
            {**dict.fromkeys("ABCD", 0.0), "E": 1.0, "F": 0.0, "G": 0.0},
            list("EFGAB"),
            None,
            None,
            "Q",
        ),
        (10, dict.fromkeys("ABCDEFG", 0.0), list("FGABC"), None, None, "Q"),
        (15, dict.fromkeys("ABCDEFG", 0.0), list("FGABC"), None, None, "Q"),
    ]
    return p, _dplans(p, specs)


def test_slot_actually_full_at_buy_cancels_buy_only():
    """보호 매도 예정 = 예정 빈자리(BUY 포함) · E 에 그 매도가 이연되면 실제 빈자리 없음 → 매수만 취소(g = 0)."""
    p, plans = _full_scene()
    _bk, states = _ref(p, plans)
    snap, payload = states[10]
    assert (
        len(snap.held) == 5
        and snap.sell_live == {p.ci["A"]: "PROTECT"}
        and snap.cash > 0
    )
    rec = LB.label(p, plans[10], snap, payload, 10, C)
    g = dict(zip(rec["actions"], rec["g"]))
    assert "BUY:F" in g and g["BUY:F"] == 0.0
    beta = [0.0] * LN.NB
    beta[0], beta[35] = 1.0, -1.0  # BUY 만 양수 · 매도 블록 음수 → 10일에 BUY 를 고름
    models = {"Q": {**_model()["Q"], "P": {"beta": beta}}}
    bk = PO.to_json(PL.simulate(p, plans, models, "P", 0, 40, C, "P_20"))
    pl10 = next(pl for pl in bk["plans"] if pl["signal"] == p.axis[10])
    assert pl10["chosen"].startswith("BUY:")
    assert any(it["status"] == "CANCELED_SLOT_FULL" for it in bk["intents"])
    assert max(len(r["pos"]) for r in bk["ledger"]) <= 5
    assert any(f["ticker"] == "A" and f["reason"] == "PROTECT" for f in bk["fills"])
    ctx = _ctx(p, plans)
    assert AU.audit_book(p, bk, ctx, models, "P", ctx["scores_r"], 0, 40) == []


@pytest.mark.parametrize("drop_day,pending", [(9, False), (11, True)])
def test_exit_relabelled_to_protect_before_or_after_decision(drop_day, pending):
    """통상 이탈(EXIT)이 이연 중 보호로 바뀐 시점이 D 이전이면 보호 매도(정상 행동) · D 뒤면 D 에는 미결(KEEP 만)."""
    closes = {c: [100.0] * 60 for c in "ABCDEFG"}
    closes["A"] = [100.0] * drop_day + [80.0] * (60 - drop_day)
    p = panel(closes, no_trade=tuple(("A", k) for k in range(7, 13)))
    specs = [
        (
            0,
            {"A": 1.0, "B": 1.0, "C": -1, "D": -1, "E": -1},
            list("ABCDE"),
            None,
            None,
            "Q",
        ),
        (5, dict.fromkeys("ABCDEFG", 0.0), list("CDEFG"), None, None, "Q"),
        (10, dict.fromkeys("ABCDEFG", 0.0), list("CDEFG"), None, None, "Q"),
        (15, dict.fromkeys("ABCDEFG", 0.0), list("CDEFG"), None, None, "Q"),
    ]
    plans = _dplans(p, specs)
    beta = [0.0] * LN.NB
    beta[0], beta[35] = -1.0, 1.0  # SELL 이 가장 큼 → 5일에 SELL:A
    models = {"Q": {**_model()["Q"], "P": {"beta": beta}}}
    bk = PO.to_json(PL.simulate(p, plans, models, "P", 0, 40, C, "P_20"))
    pl5 = next(pl for pl in bk["plans"] if pl["signal"] == p.axis[5])
    assert pl5["chosen"] == "SELL:A"
    it = next(it for it in bk["intents"] if it.get("planned_reason") == "EXIT")
    assert it["reason"] == "PROTECT" and it["protect_at"] == p.axis[drop_day]
    pl10 = next(pl for pl in bk["plans"] if pl["signal"] == p.axis[10])
    assert (pl10["keep_only"] == "NORMAL_PENDING") is pending
    if not pending:
        assert ["A", "PROTECT"] in pl10["held_exiting"]
        assert not any(n.endswith(":A") or ":A>" in n for n, _q in pl10["actions"])
    ctx = _ctx(p, plans)
    assert AU.audit_book(p, bk, ctx, models, "P", ctx["scores_r"], 0, 40) == []


def test_window_boundaries_exact_by_hand():
    """경계일에 신호를 놓고 손 숫자로 확인 — 위치(D)+21 ≤ 위치(C)−20 포함 · 하루 뒤 제외 · 5년 하한 포함 · 하루 앞 제외."""
    import datetime as dt

    from app.decision_learning import protocol as P23

    d, axis = dt.date(2012, 1, 2), []
    while d <= dt.date(2026, 12, 31):
        if d.weekday() < 5:
            axis.append(d.isoformat())
        d += dt.timedelta(days=1)
    cut = max(k for k, x in enumerate(axis) if x < "2018-01-01")
    lo_i = next(k for k, x in enumerate(axis) if x >= "2013-01-01")
    q = P23.windows(axis, [lo_i - 1, lo_i, cut - 41, cut - 40])[0]
    assert (q["id"], q["lo"], q["cutoff"]) == ("2018Q1", "2013-01-01", axis[cut])
    assert q["upper"] == 2 and (q["first"], q["last"]) == (axis[lo_i], axis[cut - 41])
