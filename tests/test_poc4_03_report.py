"""POC4-03 — 부분 가중 바스켓 · 전략 성과 · 10,000회 CI · paired · 강건성 · 판정 순서 (PLAN §2-4~§2-7).

순수 함수만 — DB·파일을 열지 않는다.
"""

from __future__ import annotations

import random

import pytest

from app import ml_rf_gate_report as rep
from app import ml_rf_gate_verdict as vd
from app.ml_pit_bias_report import basket_series
from app.ml_score_validity_metrics import replaced_fraction, top_fraction
from app.ml_strategy_performance import build_strategy_performance


def _rows(n, seed=1, ties=False):
    rng = random.Random(seed)
    out = []
    for i in range(n):
        score = float(i // 3) if ties else float(i) + rng.random() / 10
        out.append((f"C{i:03d}", score, rng.gauss(0, 0.05)))
    rng.shuffle(out)
    return out


# --- 부분 가중 바스켓 --------------------------------------------------------------------


@pytest.mark.parametrize("n", [1, 7, 40, 91])
def test_partial_top_without_ties_equals_02a_top_fraction(n):
    rows = _rows(n)
    got = rep.partial_top(rows, 0.1)
    top = top_fraction(rows, 0.1)
    assert got["weights"] == {r[0]: 1.0 for r in top}
    assert got["mean"] == sum(r[2] for r in top) / len(top)
    assert got["boundary_tie"] is False and got["k"] == len(top)


def test_partial_top_splits_the_boundary_tie_group_evenly():
    # 점수 내림차순: 9(1) · 8(3) · 7(3) · … — k = round(30×0.1) = 3 → 경계 점수 8 묶음 3개 중 2개분
    rows = [(f"A{i}", 9.0, 0.1) for i in range(1)]
    rows += [(f"B{i}", 8.0, float(i)) for i in range(3)]
    rows += [(f"C{i}", 7.0, 0.0) for i in range(26)]
    got = rep.partial_top(rows, 0.1)
    assert got["k"] == 3 and got["above"] == 1 and got["tie_group"] == 3
    assert got["boundary_tie"] is True
    assert got["weights"] == {"A0": 1.0, "B0": 2 / 3, "B1": 2 / 3, "B2": 2 / 3}
    assert got["mean"] == pytest.approx((0.1 + (2 / 3) * (0 + 1 + 2)) / 3)


def test_partial_top_weights_do_not_depend_on_labels():
    rows = _rows(60, ties=True)
    shuffled = [(c, s, random.Random(9).random()) for c, s, _ in rows]
    assert (
        rep.partial_top(rows, 0.1)["weights"]
        == rep.partial_top(shuffled, 0.1)["weights"]
    )


def test_partial_top_empty():
    got = rep.partial_top([], 0.1)
    assert got["mean"] is None and got["weights"] == {} and got["k"] == 0


def test_weighted_replaced_reduces_to_replaced_fraction_and_handles_fractions():
    prev, cur = ["A", "B", "C"], ["B", "C", "D", "E"]
    as_w = lambda xs: {x: 1.0 for x in xs}  # noqa: E731
    assert rep.weighted_replaced(as_w(prev), as_w(cur), 4) == replaced_fraction(
        prev, cur
    )
    assert rep.weighted_replaced(None, as_w(cur), 4) is None
    assert rep.weighted_replaced({}, as_w(cur), 4) == 1.0
    frac = rep.weighted_replaced({"A": 0.5, "B": 1.0}, {"A": 1.0, "C": 0.5}, 1)
    assert frac == pytest.approx(0.5 + 0.5)


def _tie_free_records(n_dates=14, n=40):
    recs, items = [], []
    days = [f"2020-{m:02d}-28" for m in range(1, 13)] + ["2021-01-28", "2021-02-26"]
    for k in range(n_dates):
        rows = _rows(n, seed=k)
        top = rep.partial_top(rows, 0.1)
        tickers = [c for c in top["weights"]]
        entry, exit_ = days[k], days[k + 1] if k + 1 < len(days) else "2021-03-30"
        mean = top["mean"] if k != 5 else None  # 상위 10% 없는 날 흉내
        weights = top["weights"] if k != 5 else {}
        recs.append(
            {
                "signal_date": entry,
                "entry_date": entry,
                "exit_date": exit_,
                "top_decile_mean": mean,
                "top_decile_tickers": tickers if k != 5 else [],
            }
        )
        items.append(
            {
                "signal_date": entry,
                "entry_date": entry,
                "exit_date": exit_,
                "mean": mean,
                "weights": weights,
                "k": top["k"],
            }
        )
    return recs, items


def test_weighted_basket_series_equals_02a_basket_series_without_ties():
    recs, items = _tie_free_records()
    got = rep.weighted_basket_series(
        [(i["signal_date"], i["mean"], i["weights"], i["k"]) for i in items]
    )
    ref = basket_series(
        [
            (r["signal_date"], r["top_decile_mean"], r["top_decile_tickers"])
            for r in recs
        ]
    )
    for key in ("gross", "turnover", "net", "net_by_date"):
        assert got[key] == ref[key], key


def test_weighted_strategy_equals_build_strategy_performance_without_ties():
    recs, items = _tie_free_records()
    closes = {}
    for k, r in enumerate(recs):
        closes[r["entry_date"]] = 100.0 + k
        closes[r["exit_date"]] = 100.5 + k
    ref = build_strategy_performance(recs, closes)
    got = rep.weighted_strategy(items, closes)
    assert (
        got["periods"] == ref["periods"]
        and got["calendar_days"] == ref["calendar_days"]
    )
    for name, sc in ref["scenarios"].items():
        assert got["scenarios"][name]["absolute"] == sc["absolute"], name
        assert got["scenarios"][name]["relative"] == sc["relative"], name


# --- CI · paired · 강건성 ------------------------------------------------------------------


def test_summary_uses_10000_iterations_seed_42_block_6(monkeypatch):
    seen = {}

    def fake(series, **kw):
        seen.update(kw)
        return (0.0, 1.0)

    monkeypatch.setattr(rep, "circular_block_bootstrap_ci", fake)
    out = rep.summary([0.1, 0.2, 0.3])
    assert seen == {"block_len": 6, "iterations": 10000, "seed": 42}
    assert out["bootstrap_ci_95"] == {"low": 0.0, "high": 1.0}


def test_paired_is_mean_of_daily_differences_and_lists_missing():
    a = {"d1": 0.3, "d2": 0.1, "d3": None, "d4": 0.2}
    b = {"d1": 0.1, "d2": 0.2, "d3": 0.5}
    got = rep.paired(a, b)
    assert got["n_paired"] == 2
    assert got["mean_diff"] == pytest.approx(((0.3 - 0.1) + (0.1 - 0.2)) / 2)
    assert [m["date"] for m in got["missing_dates"]] == ["d3", "d4"]


def test_period_bounds_146_is_49_49_48():
    dates = [f"d{i:03d}" for i in range(146)]
    sizes = [len(b) for b in rep.period_bounds(dates)]
    assert sizes == [49, 49, 48]
    assert rep.period_bounds(dates)[1][0] == "d049"


def _series(ic, net):
    return {"ic": ic, "net25": net}


def test_robustness_leave_one_year_out_and_2026():
    dates = ["2024-01-31", "2024-02-29", "2025-01-31", "2025-02-28", "2026-01-30"]
    a = _series(dict(zip(dates, [0.5, 0.5, 0.1, 0.1, 0.9])), dict.fromkeys(dates, 0.01))
    b = _series(dict.fromkeys(dates, 0.2), dict.fromkeys(dates, 0.0))
    got = rep.robustness(a, b, dates)
    loyo = got["leave_one_year_out"]["ic"]
    # 2024 를 빼면 (−0.1 −0.1 +0.7)/3 · 2026 을 빼면 (0.3 0.3 −0.1 −0.1)/4
    assert loyo["by_excluded_year"]["2026"] == pytest.approx(0.1)
    assert loyo["min"] == pytest.approx(0.1) and loyo["worst_excluded_year"] == "2026"
    assert got["excluding_2026"]["dates"] == 4
    assert [p["dates"] for p in got["periods"]] == [2, 2, 1]


# --- 판정 순서 ----------------------------------------------------------------------------


def _cmp(ic, net, ic_low=0.01, net_low=0.01):
    band = lambda low: {"low": low, "high": 1.0}  # noqa: E731
    return {
        "ic": {"mean_diff": ic, "bootstrap_ci_95": band(ic_low)},
        "net25": {"mean_diff": net, "bootstrap_ci_95": band(net_low)},
    }


def _robust(ic_min=0.1, net_min=0.1, periods=3, complete=True):
    return {
        "leave_one_year_out": {
            "ic": {"min": ic_min, "complete": complete},
            "net25": {"min": net_min, "complete": complete},
        },
        "periods": [{"both_positive": i < periods} for i in range(3)],
    }


def _decide(primary=(0.1, 0.1), configs=((0.1, 0.1),) * 3, robust=None, invalid=()):
    comps = {"RF_PRIMARY_vs_MOM": _cmp(*primary)}
    for name, (i, n) in zip(("RF_A", "RF_B", "RF_C"), configs):
        comps[f"{name}_vs_MOM"] = _cmp(i, n)
    return vd.decide(vd.conditions(comps, robust or _robust()), list(invalid))


def test_decide_pass_when_all_hold():
    assert _decide()["verdict"] == vd.PASS


def test_decide_invalid_first():
    assert (
        _decide(invalid=["PREFLIGHT_RF_A:BLOCKED_LEAKAGE"])["verdict"]
        == vd.INVALID_STOP
    )


def test_decide_reject_when_both_points_not_better():
    got = _decide(primary=(0.0, -0.01))
    assert got["verdict"] == vd.REJECT_CLOSED and got["failed"] == ["C1", "C3"]


@pytest.mark.parametrize(
    "primary,failed", [((0.1, -0.01), ["C3"]), ((None, 0.1), ["C1"])]
)
def test_decide_inconclusive_when_one_metric_worse(primary, failed):
    got = _decide(primary=primary)
    assert got["verdict"] == vd.INCONCLUSIVE_CLOSED and got["failed"] == failed


@pytest.mark.parametrize(
    "kw,failed",
    [
        ({"configs": ((0.1, 0.1), (0.1, -0.1), (-0.1, 0.1))}, ["C5"]),
        ({"robust": _robust(net_min=-0.01)}, ["C6"]),
        ({"robust": _robust(complete=False)}, ["C6"]),
        ({"robust": _robust(periods=1)}, ["C7"]),
    ],
)
def test_decide_reject_on_period_or_config_dependence(kw, failed):
    got = _decide(**kw)
    assert got["verdict"] == vd.REJECT_CLOSED and got["failed"] == failed


def test_decide_reject_before_ci_inconclusive():
    comps = {"RF_PRIMARY_vs_MOM": _cmp(0.1, 0.1, ic_low=-0.01)}
    for name in ("RF_A", "RF_B", "RF_C"):
        comps[f"{name}_vs_MOM"] = _cmp(0.1, 0.1)
    got = vd.decide(vd.conditions(comps, _robust(periods=1)), [])
    assert got["verdict"] == vd.REJECT_CLOSED


def test_decide_inconclusive_when_ci_includes_zero():
    comps = {"RF_PRIMARY_vs_MOM": _cmp(0.1, 0.1, net_low=None)}
    for name in ("RF_A", "RF_B", "RF_C"):
        comps[f"{name}_vs_MOM"] = _cmp(0.1, 0.1)
    got = vd.decide(vd.conditions(comps, _robust()), [])
    assert got["verdict"] == vd.INCONCLUSIVE_CLOSED and got["failed"] == ["C4"]


def test_final_verdict_requires_determinism_and_candidate():
    cand = _decide()
    assert vd.final_verdict(cand, True) == cand
    assert vd.final_verdict(cand, False)["failed"] == ["C9"]
    assert vd.final_verdict(None, False)["failed"] == ["C9"]  # 결정성 실패를 먼저 본다
    assert vd.final_verdict(None, True)["failed"] == ["NO_CANDIDATE"]


def test_recipe_is_frozen_and_names_the_conditions():
    vd.assert_frozen_recipe()
    r = vd.recipe()
    assert set(r["conditions"]) >= {"C1", "C5", "C6", "C7", "none_rule"}
    assert "49·49·48" in r["conditions"]["C7"]
    assert vd.KILL_GATE[vd.REJECT_CLOSED].startswith("POC4-04·05 미개방")


def test_tied_baskets_across_days_turnover_net_and_strategy():
    """A 1 · B·C·D 1/3 (k=2) → B 1 · C·D·E·F 1/4 (k=2): 교체비율 = (1 + 1/4 − 1/3 … ) / 2 = 7/12."""
    day1 = (
        [("A", 9.0, 0.02)]
        + [(c, 5.0, 0.01) for c in "BCD"]
        + [(f"Z{i}", 1.0, 0.0) for i in range(16)]
    )
    day2 = (
        [("B", 9.0, 0.03)]
        + [(c, 5.0, -0.01) for c in "CDEF"]
        + [(f"Y{i}", 1.0, 0.0) for i in range(15)]
    )
    b1, b2 = rep.partial_top(day1, 0.1), rep.partial_top(day2, 0.1)
    assert b1["k"] == b2["k"] == 2 and b1["boundary_tie"] and b2["boundary_tie"]
    turnover = rep.weighted_replaced(b1["weights"], b2["weights"], b2["k"])
    assert turnover == pytest.approx(7 / 12)
    series = rep.weighted_basket_series(
        [("d1", b1["mean"], b1["weights"], 2), ("d2", b2["mean"], b2["weights"], 2)]
    )
    assert series["turnover"] == [pytest.approx(7 / 12)]
    assert series["net"]["25"][1] == pytest.approx(b2["mean"] - 7 / 12 * 0.0025 * 2)
    items = [
        {
            "signal_date": "d1",
            "entry_date": "2020-01-02",
            "exit_date": "2020-02-03",
            "mean": b1["mean"],
            "weights": b1["weights"],
            "k": 2,
        },
        {
            "signal_date": "d2",
            "entry_date": "2020-02-03",
            "exit_date": "2020-03-02",
            "mean": b2["mean"],
            "weights": b2["weights"],
            "k": 2,
        },
    ]
    closes = {"2020-01-02": 100.0, "2020-02-03": 101.0, "2020-03-02": 99.0}
    got = rep.weighted_strategy(items, closes)
    sc = got["scenarios"][rep.STRATEGY_REFERENCE_SCENARIO]
    net1 = b1["mean"] + 0.01
    net2 = b2["mean"] + (99.0 / 101.0 - 1) - 7 / 12 * (11.5 / 10000) * 2
    assert sc["absolute"]["end_equity"] == pytest.approx((1 + net1) * (1 + net2))
    assert sc["role"] == "STRATEGY_REFERENCE" and sc["role_02a"] == "PRIMARY"
    assert got["strategy_reference_curves"]["exit_dates"] == [
        "2020-02-03",
        "2020-03-02",
    ]
    assert got["first_entry_date"] == "2020-01-02" and got["price_basis"]


def test_model_series_uses_weighted_net_not_code_order():
    rows = [("A", 9.0, 0.02)] + [(c, 5.0, v) for c, v in zip("BCD", (0.3, 0.0, 0.0))]
    rows += [(f"Z{i}", 1.0, 0.0) for i in range(16)]
    basket = rep.partial_top(rows, 0.1)
    code_order_top = [r for r in sorted(rows, key=lambda x: x[1], reverse=True)][:2]
    code_order_mean = sum(r[2] for r in code_order_top) / 2
    assert basket["mean"] != pytest.approx(code_order_mean)
    entry = {
        "record": {
            "signal_date": "d1",
            "ic_filter": 0.1,
            "n_filter": 20,
            "split": {"status": "OK"},
        },
        "basket": basket,
    }
    got = rep.model_series([entry])
    assert got["net25"]["d1"] == basket["mean"]  # 첫 날 비용 0 · 부분 가중 평균


def test_paired_records_missing_reasons_and_yearly_table():
    rec = lambda day, n, status="OK": {  # noqa: E731
        "signal_date": day,
        "ic_filter": None,
        "n_filter": n,
        "split": {"status": status},
    }
    empty = rep.partial_top([], 0.1)
    entries = [
        {"record": rec("2020-01-31", 1), "basket": empty},
        {"record": rec("2020-02-28", 0, "NO_MODEL"), "basket": empty},
    ]
    series = rep.model_series(entries)
    assert series["ic_why"] == {
        "2020-01-31": "평가 단면 2개 미만",
        "2020-02-28": "NO_MODEL 날",
    }
    got = rep.paired(series["ic"], {"2020-01-31": 0.1}, series["ic_why"], {})
    assert got["missing_dates"][0]["a_reason"] == "평가 단면 2개 미만"
    table = rep.yearly_table(
        {"ic": {"2020-01-31": 0.2, "2021-01-29": None}, "net25": {"2020-01-31": 0.01}},
        ["2020-01-31", "2021-01-29"],
    )
    assert table["2020"] == {"dates": 1, "ic_mean": 0.2, "net25_mean": 0.01}
    assert table["2021"]["ic_mean"] is None
