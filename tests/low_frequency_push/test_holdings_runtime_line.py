"""Holdings overlay / runtime line / selection_count.

`tests/test_low_frequency_push_operation.py` (1548줄) 가 KS-10 테스트 임계를
넘어 책임별로 분해한 것이다. **test 본문·docstring·assertion 을 고치지 않았다.**
helper 는 `tests/low_frequency_push/_fixtures.py` 에 있다.
"""

from __future__ import annotations

import pytest

from app.holdings_market_evidence import build_holdings_market_evidence

from app.runtime_evidence.holdings_evidence import build_holdings_facts

from tests.low_frequency_push._fixtures import (
    _holdings,
    _quote,
    _topn_ok,
)

# ── Holdings overlay / runtime line / selection_count ─────────────────────


def test_holdings_market_quotes_overlay_does_not_modify_file():
    hs = _holdings(2)
    quotes = {"000000": _quote("000000", 1500.0, "2026-07-24T15:30:00+09:00")}
    payload = build_holdings_market_evidence(
        holdings=hs, topn_payload=_topn_ok(), market_quotes=quotes
    )
    assert payload["status"] == "ok"
    h0 = payload["holdings"][0]
    assert h0["holding"]["current_price"] == 1500.0
    assert h0["holding"]["pnl_rate_pct"] == pytest.approx(50.0)
    h1 = payload["holdings"][1]
    assert h1["holding"]["current_price"] is None
    assert hs[0].quantity == 10


def test_holdings_runtime_line_shows_price_pnl_asof():
    payload = {
        "market_asof": "2026-07-24",
        "holdings": [
            {
                "name": "종목A",
                "ticker": "000000",
                "holding": {
                    "quantity": 10,
                    "avg_buy_price": 1000,
                    "evaluation_amount": 15000,
                    "pnl_rate_pct": 50.0,
                    "current_price": 1500.0,
                    "price_asof": "2026-07-24T15:30:00+09:00",
                },
                "topn_match": {"status": "not_in_current_topn"},
                "returns": {"status": "unavailable"},
                "excess_return": {"status": "unavailable"},
                "short_term_momentum": {"status": "unavailable"},
                "constituents_overlap": {"status": "unavailable"},
                "nav_discount": {"status": "unavailable"},
                "evidence_notes": [],
            }
        ],
    }
    notes, _ = build_holdings_facts(payload, "2026-07-24")
    rt = [n for n in notes if "runtime" in n]
    assert len(rt) == 1
    assert "현재가 1,500" in rt[0]
    assert "평가수익률 +50.00%" in rt[0]
    assert "2026-07-24T15:30:00+09:00" in rt[0]


def test_holdings_runtime_line_absent_when_current_price_missing():
    payload = {
        "market_asof": "2026-07-24",
        "holdings": [
            {
                "name": "종목B",
                "ticker": "000001",
                "holding": {
                    "quantity": 10,
                    "avg_buy_price": 1000,
                    "evaluation_amount": None,
                    "pnl_rate_pct": None,
                    "current_price": None,
                    "price_asof": None,
                },
                "topn_match": {"status": "not_in_current_topn"},
                "returns": {"status": "unavailable"},
                "excess_return": {"status": "unavailable"},
                "short_term_momentum": {"status": "unavailable"},
                "constituents_overlap": {"status": "unavailable"},
                "nav_discount": {"status": "unavailable"},
                "evidence_notes": [],
            }
        ],
    }
    notes, _ = build_holdings_facts(payload, "2026-07-24")
    assert not any("runtime" in n for n in notes)


def test_holdings_selection_count_single_per_ticker():
    payload = {
        "market_asof": "2026-07-24",
        "holdings": [
            {
                "name": "종목C",
                "ticker": "000002",
                "holding": {
                    "quantity": 10,
                    "avg_buy_price": 1000,
                    "evaluation_amount": 15000,
                    "pnl_rate_pct": 50.0,
                    "current_price": 1500.0,
                    "price_asof": "2026-07-24T15:30:00+09:00",
                },
                "topn_match": {"status": "not_in_current_topn"},
                "returns": {
                    "status": "ok",
                    "one_month_pct": 5.0,
                    "excess_return_pct": 1.0,
                },
                "excess_return": {"status": "ok", "excess_return_pct": 1.0},
                "short_term_momentum": {"status": "unavailable"},
                "constituents_overlap": {"status": "unavailable"},
                "nav_discount": {"status": "unavailable"},
                "evidence_notes": [],
            }
        ],
    }
    _, counters = build_holdings_facts(payload, "2026-07-24")
    assert counters["holdings_selection_result_count"] == 1
    assert counters["holdings_contentful_fact_count"] == 2


def test_holdings_runtime_line_absent_when_price_asof_missing():
    """A+ 재정정: current_price 있어도 price_asof 없으면 runtime line 생성 안함."""
    payload = {
        "market_asof": "2026-07-24",
        "holdings": [
            {
                "name": "종목D",
                "ticker": "000003",
                "holding": {
                    "quantity": 10,
                    "avg_buy_price": 1000,
                    "evaluation_amount": 15000,
                    "pnl_rate_pct": 50.0,
                    "current_price": 1500.0,
                    "price_asof": None,
                },
                "topn_match": {"status": "not_in_current_topn"},
                "returns": {"status": "unavailable"},
                "excess_return": {"status": "unavailable"},
                "short_term_momentum": {"status": "unavailable"},
                "constituents_overlap": {"status": "unavailable"},
                "nav_discount": {"status": "unavailable"},
                "evidence_notes": [],
            }
        ],
    }
    notes, _ = build_holdings_facts(payload, "2026-07-24")
    assert not any("runtime" in n for n in notes)
