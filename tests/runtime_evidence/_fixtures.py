"""Runtime Evidence 테스트 공통 fixture · helper.

Cleanup / FIX r7 Round 3 에서 `tests/test_runtime_evidence_composer.py` 로부터
분리. 각 책임별 test file 이 이 모듈에서 fake payload / holdings loader /
NAV row / result builder 등을 import.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from app.holdings import Holding
from app.runtime_evidence_composer import compose_runtime_evidence

_REAL_MARKET_DB = Path("state/market/market_data.sqlite")


def _snapshot(p: Path) -> dict[str, Any]:
    if not p.exists():
        return {"exists": False}
    b = p.read_bytes()
    return {
        "exists": True,
        "size": len(b),
        "sha256": hashlib.sha256(b).hexdigest(),
    }


# ── fake topn payload builders ────────────────────────────────────────────────


def _ok_topn_payload(asof: str = "2026-07-11") -> dict[str, Any]:
    return {
        "status": "ok",
        "asof": asof,
        "candidates": [
            {
                "rank": 1,
                "ticker": "069500",
                "name": "KODEX 200",
                "selected_return_pct": 3.21,
                "tags": [],
                "returns": {},
            },
            {
                "rank": 2,
                "ticker": "252670",
                "name": "KODEX 코스닥150",
                "selected_return_pct": 2.44,
                "tags": [],
                "returns": {},
            },
        ],
        "market_context": {
            "kodex200": {
                "status": "ok",
                "return_1m_pct": 3.21,
                "return_3m_pct": 5.45,
            },
            "kospi": {
                "status": "ok",
                "return_1m_pct": 2.88,
                "return_3m_pct": 4.90,
            },
        },
    }


def _empty_topn_payload() -> dict[str, Any]:
    return {"status": "empty", "asof": None, "candidates": []}


def _missing_topn_payload() -> dict[str, Any]:
    return {"status": "missing", "asof": None, "candidates": []}


# ── fake holdings loaders ─────────────────────────────────────────────────────


def _fake_holdings_ok() -> list[Holding]:
    return [Holding(ticker="069500", quantity=10, avg_buy_price=35000.0)]


def _fake_holdings_two() -> list[Holding]:
    """Q6-3: 2건 loader."""
    return [
        Holding(ticker="069500", quantity=10, avg_buy_price=35000.0),
        Holding(ticker="222222", quantity=5, avg_buy_price=12000.0),
    ]


# ── evidence_fn payloads ─────────────────────────────────────────────────────


def _ok_evidence_fn(**_kwargs: Any) -> dict[str, Any]:
    return {
        "status": "ok",
        "asof": "2026-07-11",
        "holdings_asof": "2026-07-11T00:00:00+00:00",
        "market_asof": "2026-07-11",
        "market_context": {},
        "summary": {},
        "holdings": [
            {
                "ticker": "069500",
                "name": "KODEX 200",
                "returns": {
                    "status": "ok",
                    "one_month_return_pct": 3.21,
                    "three_month_return_pct": 5.45,
                },
                "excess_return": {
                    "status": "ok",
                    "vs_kodex200_1m_pctp": 1.10,
                },
                "topn_match": {"status": "matched_topn_candidate", "rank": 1},
                "short_term_momentum": {"status": "unavailable"},
                "constituents_overlap": {"status": "unavailable"},
                "nav_discount": {"status": "unavailable"},
                "evidence_notes": [],
            }
        ],
        "warnings": [],
    }


def _evidence_matched(**_kwargs: Any) -> dict[str, Any]:
    """matched_topn_candidate 시나리오 (rank=3)."""
    return {
        "status": "ok",
        "asof": "2026-07-11",
        "holdings_asof": "2026-07-11T00:00:00+00:00",
        "market_asof": "2026-07-11",
        "market_context": {},
        "summary": {"market_topn_status": "ok"},
        "holdings": [
            {
                "ticker": "069500",
                "name": "KODEX 200",
                "returns": {"status": "unavailable"},
                "excess_return": {"status": "unavailable"},
                "topn_match": {"status": "matched_topn_candidate", "rank": 3},
                "short_term_momentum": {"status": "unavailable"},
                "constituents_overlap": {"status": "unavailable"},
                "nav_discount": {"status": "unavailable"},
                "evidence_notes": [],
            }
        ],
        "warnings": [],
    }


def _evidence_not_in_topn(**_kwargs: Any) -> dict[str, Any]:
    """FIX r3 Q3: not_in_current_topn 도 Holdings evidence."""
    return {
        "status": "ok",
        "asof": "2026-07-11",
        "market_asof": "2026-07-11",
        "market_context": {},
        "summary": {"market_topn_status": "ok"},
        "holdings": [
            {
                "ticker": "069500",
                "name": "KODEX 200",
                "returns": {"status": "unavailable"},
                "excess_return": {"status": "unavailable"},
                "topn_match": {"status": "not_in_current_topn"},
                "short_term_momentum": {"status": "unavailable"},
                "constituents_overlap": {"status": "unavailable"},
                "nav_discount": {"status": "unavailable"},
                "evidence_notes": [],
            }
        ],
        "warnings": [],
    }


def _evidence_two_holdings_one_matched(**_kwargs: Any) -> dict[str, Any]:
    """Holdings 2건 중 1건만 유효 evidence."""
    return {
        "status": "ok",
        "market_asof": "2026-07-11",
        "market_context": {},
        "summary": {"market_topn_status": "ok"},
        "holdings": [
            {
                "ticker": "069500",
                "name": "KODEX 200",
                "returns": {"status": "unavailable"},
                "excess_return": {"status": "unavailable"},
                "topn_match": {"status": "matched_topn_candidate", "rank": 1},
                "short_term_momentum": {"status": "unavailable"},
                "constituents_overlap": {"status": "unavailable"},
                "nav_discount": {"status": "unavailable"},
                "evidence_notes": [],
            },
            {
                "ticker": "222222",
                "name": "SomeETF",
                "returns": {"status": "unavailable"},
                "excess_return": {"status": "unavailable"},
                "topn_match": {"status": "unavailable"},
                "short_term_momentum": {"status": "unavailable"},
                "constituents_overlap": {"status": "unavailable"},
                "nav_discount": {"status": "unavailable"},
                "evidence_notes": [],
            },
        ],
        "warnings": [],
    }


def _evidence_topn_failed(**_kwargs: Any) -> dict[str, Any]:
    """FIX r3 Q3: TOP-N 조회 실패 → holdings_snapshot=unavailable."""
    return {
        "status": "ok",
        "market_asof": None,
        "market_context": {},
        "summary": {},
        "holdings": [
            {
                "ticker": "069500",
                "name": "KODEX 200",
                "returns": {"status": "unavailable"},
                "excess_return": {"status": "unavailable"},
                "topn_match": {"status": "unavailable"},
                "short_term_momentum": {"status": "unavailable"},
                "constituents_overlap": {"status": "unavailable"},
                "nav_discount": {"status": "unavailable"},
                "evidence_notes": [],
            }
        ],
        "warnings": ["market_topn status=empty"],
    }


def _evidence_topn_failed_but_asof_preserved(**_kwargs: Any) -> dict[str, Any]:
    """FIX r5 A-1 재현: builder 실패 시에도 입력 asof 를 보존."""
    return {
        "status": "ok",
        "asof": "2026-07-11",
        "market_asof": "2026-07-11",
        "market_context": {},
        "summary": {},
        "holdings": [
            {
                "ticker": "069500",
                "name": "KODEX 200",
                "returns": {"status": "unavailable"},
                "excess_return": {"status": "unavailable"},
                "topn_match": {"status": "unavailable"},
                "short_term_momentum": {"status": "unavailable"},
                "constituents_overlap": {"status": "unavailable"},
                "nav_discount": {"status": "unavailable"},
                "evidence_notes": [],
            }
        ],
        "warnings": [],
    }


# ── nav row ──────────────────────────────────────────────────────────────────


def _fake_nav_row(asof: str = "2026-07-11", discount: float = -1.5):
    class _Row:
        pass

    r = _Row()
    r.etf_ticker = "069500"
    r.asof = asof
    r.nav = 40000.0
    r.market_price = 39400.0
    r.discount_rate_pct = discount
    r.source = "seibro"
    r.status = "ok"
    r.message = None
    return r


def _nav_ok(**_):
    """NAV row (fact_attribution / privacy body test 공용)."""

    class R:
        pass

    r = R()
    r.etf_ticker = "069500"
    r.asof = "2026-07-11"
    r.nav = 40000.0
    r.market_price = 39500.0
    r.discount_rate_pct = -1.2
    r.source = "seibro"
    r.status = "ok"
    r.message = None
    return r


# ── result builders ──────────────────────────────────────────────────────────


def _make_result_for_holdings_briefing(
    tmp_path: Path, evidence_fn, nav_fn=lambda **_: None, holdings=None
):
    hfile = tmp_path / "holdings.json"
    hfile.write_text("{}", encoding="utf-8")
    return compose_runtime_evidence(
        "holdings_briefing",
        market_db_path=tmp_path / "market_data.sqlite",
        holdings_file=hfile,
        holdings_loader=(holdings if holdings else _fake_holdings_ok),
        topn_fn=lambda **_: _ok_topn_payload(),
        evidence_fn=evidence_fn,
        nav_fn=nav_fn,
    )
