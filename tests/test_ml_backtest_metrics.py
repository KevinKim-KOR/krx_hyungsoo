"""POC4-01 작업 6 — 성과지표 · 거래비용 분해 계약 (설계자 판정 2026-09-24 §3-2 · §3-3)."""

from __future__ import annotations

import copy
import math
from datetime import date

import pytest

from app import ml_strategy_performance as perf


def test_cost_scenarios_follow_designer_decision():
    sc = {s["name"]: s for s in perf.cost_scenarios()}
    assert sc["legacy_all_in_25bp"]["one_way_bp"] == 25.0
    assert sc["legacy_all_in_25bp"]["role"] == "LEGACY_COMPARISON"
    one_way = {
        int(s["slippage_bp"]): s["one_way_bp"] for s in sc.values() if s["slippage_bp"]
    }
    assert one_way == {5: 6.5, 10: 11.5, 25: 26.5, 50: 51.5}
    primary = [s for s in sc.values() if s["role"] == "PRIMARY"]
    assert len(primary) == 1 and primary[0]["one_way_bp"] == 11.5
    assert sc["decomposed_slippage_50bp"]["role"] == "STRESS"
    for s in sc.values():
        if s["role"] != "LEGACY_COMPARISON":
            assert s["transaction_tax_bp"] == 0.0 and s["commission_bp"] == 1.5
    assert "ASSUMPTION" in perf.COST_NOTES["commission_bp"]
    assert "배당소득세" in perf.COST_NOTES["excluded"]


def test_equity_curve_and_max_drawdown_by_hand():
    eq = perf.equity_curve([0.1, -0.2, 0.05])
    assert eq == pytest.approx([1.1, 0.88, 0.924])
    assert perf.max_drawdown(eq) == pytest.approx(0.88 / 1.1 - 1.0)
    # 첫 기간부터 손실이면 시작값 1.0 이 고점이다
    assert perf.max_drawdown(perf.equity_curve([-0.1, 0.05])) == pytest.approx(-0.1)
    assert perf.max_drawdown(perf.equity_curve([0.01, 0.02])) == 0.0


def test_cagr_and_annualized_ratio_by_hand():
    assert perf.cagr(1.21, 730) == pytest.approx(1.21 ** (365.25 / 730) - 1.0)
    rets = [0.02, -0.01, 0.03, 0.0]
    mean = sum(rets) / 4
    sd = math.sqrt(sum((r - mean) ** 2 for r in rets) / 3)
    assert perf.annualized_ratio(rets, 12) == pytest.approx(mean / sd * math.sqrt(12))
    assert perf.annualized_volatility(rets, 12) == pytest.approx(sd * math.sqrt(12))
    assert perf.annualized_ratio([0.01], 12) is None
    assert perf.annualized_ratio([0.01, 0.01], 12) is None  # 표준편차 0


def _records():
    return [
        {
            "signal_date": "2020-01-31",
            "entry_date": "2020-02-03",
            "exit_date": "2020-03-02",
            "top_decile_mean": 0.02,
            "top_decile_tickers": ["A", "B"],
        },
        {
            "signal_date": "2020-02-28",
            "entry_date": "2020-03-02",
            "exit_date": "2020-04-01",
            "top_decile_mean": -0.01,
            "top_decile_tickers": ["A", "C"],
        },
        {
            "signal_date": "2020-03-31",
            "entry_date": "2020-04-01",
            "exit_date": "2020-05-04",
            "top_decile_mean": None,
            "top_decile_tickers": [],
        },
    ]


CLOSES = {"2020-02-03": 100.0, "2020-03-02": 110.0, "2020-04-01": 99.0}


def test_build_uses_gross_excess_plus_benchmark_and_monthly_turnover():
    records = _records()
    before = copy.deepcopy(records)
    out = perf.build_strategy_performance(records, CLOSES)
    assert records == before, "평가 기록을 바꾸면 안 된다"
    assert out["status"] == "OK" and out["periods"] == 2
    assert [e["reason"] for e in out["excluded_periods"]] == ["상위 10% 없음"]

    b1, b2 = 0.10, 99.0 / 110.0 - 1.0
    g1, g2 = 0.02 + b1, -0.01 + b2
    legacy = out["scenarios"]["legacy_all_in_25bp"]
    net1 = g1  # 첫 달은 직전 바스켓이 없어 비용 0 (A2 규칙)
    net2 = g2 - 0.5 * (25.0 / 10000.0) * 2.0  # 교체비율 1/2
    assert legacy["absolute"]["end_equity"] == pytest.approx((1 + net1) * (1 + net2))
    assert legacy["relative"]["benchmark_end_equity"] == pytest.approx(
        (1 + b1) * (1 + b2)
    )
    primary = out["scenarios"]["decomposed_slippage_10bp"]
    assert primary["one_way_bp"] == 11.5 and primary["role"] == "PRIMARY"
    assert "sharpe_0rf" in primary["absolute"] and "sharpe" not in primary["absolute"]


def test_relative_wealth_is_equity_ratio_not_compounded_difference():
    records = _records()[:2]
    out = perf.build_strategy_performance(records, CLOSES)
    sc = out["scenarios"]["legacy_all_in_25bp"]
    rel = sc["relative"]["relative_wealth_end"]
    assert rel == pytest.approx(
        sc["absolute"]["end_equity"] / sc["relative"]["benchmark_end_equity"]
    )
    net = [
        0.02 + 0.10,
        -0.01 + (99.0 / 110.0 - 1.0) - 0.5 * 0.0025 * 2.0,
    ]
    bench = [0.10, 99.0 / 110.0 - 1.0]
    compounded_diff = (1 + net[0] - bench[0]) * (1 + net[1] - bench[1])
    assert rel != pytest.approx(compounded_diff), "차감 수익률 복리로 만들면 안 된다"
    curves = out["primary_curves"]
    assert curves["exit_dates"] == ["2020-03-02", "2020-04-01"]
    assert len(curves["relative_wealth"]) == 2


def test_missing_benchmark_close_excludes_the_period():
    records = _records()[:2]
    out = perf.build_strategy_performance(records, {"2020-02-03": 100.0})
    assert out["status"] == "NO_PERIODS"
    assert {e["reason"] for e in out["excluded_periods"]} == {"KODEX200 종가 없음"}


def test_tracking_error_information_ratio_and_relative_mdd_by_hand():
    out = perf.build_strategy_performance(_records()[:2], CLOSES)
    sc = out["scenarios"]["legacy_all_in_25bp"]
    b = [0.10, 99.0 / 110.0 - 1.0]
    net = [0.02 + b[0], -0.01 + b[1] - 0.5 * 0.0025 * 2.0]
    active = [n - x for n, x in zip(net, b)]
    ppy = out["periods_per_year"]
    mean = sum(active) / 2
    sd = math.sqrt(sum((a - mean) ** 2 for a in active) / 1)
    assert sc["relative"]["tracking_error"] == pytest.approx(sd * math.sqrt(ppy))
    assert sc["relative"]["information_ratio"] == pytest.approx(
        mean / sd * math.sqrt(ppy)
    )
    rel = [
        (1 + net[0]) / (1 + b[0]),
        (1 + net[0]) * (1 + net[1]) / ((1 + b[0]) * (1 + b[1])),
    ]
    assert sc["relative"]["relative_mdd"] == pytest.approx(
        min(0.0, rel[1] / max(1.0, rel[0]) - 1.0)
    )
    days = (date(2020, 4, 1) - date(2020, 2, 3)).days
    assert out["calendar_days"] == days and ppy == pytest.approx(2 / (days / 365.25))
