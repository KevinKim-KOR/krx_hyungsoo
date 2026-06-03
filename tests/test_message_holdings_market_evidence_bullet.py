"""POC2 — Holdings × Market Discovery Evidence judgment bullet helper 테스트 (2026-06-03).

지시문 §5.10 — [판단 사유] 섹션 1줄 bullet. 매수/매도 표현 금지.
"""

from __future__ import annotations

from app.message_holdings_market_evidence_bullet import (
    build_holdings_market_evidence_bullet,
    build_holdings_market_evidence_factor_signal,
    render_holdings_market_evidence_bullet,
)


def _snapshot(*, holdings: list[dict], summary: dict | None = None) -> dict:
    return {
        "status": "ok",
        "asof": "2026-06-03",
        "market_asof": "2026-06-03",
        "summary": summary
        or {
            "total_holdings_count": len(holdings),
            "matched_topn_count": 0,
            "not_in_current_topn_count": 0,
            "evidence_unavailable_count": 0,
            "constituents_available_count": 0,
            "constituents_unavailable_count": 0,
            "nav_discount_unavailable_count": 0,
        },
        "holdings": holdings,
        "warnings": [],
    }


def _holding_dict(
    *, ticker: str, name: str, topn_status: str, stm_status: str = "unavailable"
) -> dict:
    return {
        "ticker": ticker,
        "name": name,
        "topn_match": {
            "status": topn_status,
            "rank": 1 if topn_status == "matched_topn_candidate" else None,
        },
        "returns": {"status": "unavailable", "one_month_return_pct": None},
        "excess_return": {"status": "unavailable"},
        "short_term_momentum": {
            "status": stm_status,
            "return_5d_pct": None,
            "excess_vs_kodex200_20d_pctp": 1.5 if stm_status == "ok" else None,
        },
        "constituents_overlap": {
            "status": "constituents_unavailable",
            "overlap_with_market_core": [],
        },
        "nav_discount": {"status": "unavailable"},
        "evidence_notes": [],
    }


# ─── build_holdings_market_evidence_bullet ──────────────────────────


def test_bullet_returns_none_for_non_dict() -> None:
    assert build_holdings_market_evidence_bullet(None) is None
    assert build_holdings_market_evidence_bullet("not a dict") is None


def test_bullet_returns_none_for_empty_holdings() -> None:
    snapshot = _snapshot(holdings=[])
    assert build_holdings_market_evidence_bullet(snapshot) is None


def test_bullet_includes_match_count_label() -> None:
    snapshot = _snapshot(
        holdings=[
            _holding_dict(
                ticker="100100", name="A", topn_status="matched_topn_candidate"
            ),
            _holding_dict(ticker="100200", name="B", topn_status="not_in_current_topn"),
        ],
        summary={
            "total_holdings_count": 2,
            "matched_topn_count": 1,
            "not_in_current_topn_count": 1,
            "evidence_unavailable_count": 0,
            "constituents_available_count": 0,
            "constituents_unavailable_count": 2,
            "nav_discount_unavailable_count": 2,
        },
    )
    bullet = build_holdings_market_evidence_bullet(snapshot)
    assert bullet is not None
    assert "보유 vs 시장" in bullet
    assert "일치 1건" in bullet
    assert "TOP N 외 1건" in bullet


def test_bullet_appends_short_term_excerpt_for_matched() -> None:
    snapshot = _snapshot(
        holdings=[
            _holding_dict(
                ticker="100100",
                name="A",
                topn_status="matched_topn_candidate",
                stm_status="ok",
            )
        ],
        summary={
            "total_holdings_count": 1,
            "matched_topn_count": 1,
            "not_in_current_topn_count": 0,
            "evidence_unavailable_count": 0,
            "constituents_available_count": 0,
            "constituents_unavailable_count": 1,
            "nav_discount_unavailable_count": 1,
        },
    )
    bullet = build_holdings_market_evidence_bullet(snapshot)
    assert bullet is not None
    assert "A 20거래일 KODEX200 대비" in bullet
    assert "+1.50%p" in bullet


def test_bullet_no_buy_sell_language() -> None:
    snapshot = _snapshot(
        holdings=[
            _holding_dict(
                ticker="100100", name="A", topn_status="matched_topn_candidate"
            )
        ],
        summary={
            "total_holdings_count": 1,
            "matched_topn_count": 1,
            "not_in_current_topn_count": 0,
            "evidence_unavailable_count": 0,
            "constituents_available_count": 0,
            "constituents_unavailable_count": 1,
            "nav_discount_unavailable_count": 1,
        },
    )
    bullet = build_holdings_market_evidence_bullet(snapshot)
    assert bullet is not None
    for word in ["매수", "매도", "교체", "진입", "탈락", "비중 확대", "비중 축소"]:
        assert word not in bullet


# ─── build_holdings_market_evidence_factor_signal ───────────────────


def test_factor_signal_none_for_empty_snapshot() -> None:
    sig = build_holdings_market_evidence_factor_signal(
        {}, asof_iso="2026-06-03T00:00:00Z"
    )
    assert sig is None


def test_factor_signal_shape_when_available() -> None:
    snapshot = _snapshot(
        holdings=[
            _holding_dict(
                ticker="100100", name="A", topn_status="matched_topn_candidate"
            )
        ],
        summary={
            "total_holdings_count": 1,
            "matched_topn_count": 1,
            "not_in_current_topn_count": 0,
            "evidence_unavailable_count": 0,
            "constituents_available_count": 0,
            "constituents_unavailable_count": 1,
            "nav_discount_unavailable_count": 1,
        },
    )
    sig = build_holdings_market_evidence_factor_signal(
        snapshot, asof_iso="2026-06-03T00:00:00Z"
    )
    assert sig is not None
    assert sig["scope"] == "holdings_market_evidence"
    assert sig["factor_id"] == "holdings_market_evidence"
    assert sig["is_available"] is True
    assert isinstance(sig["reason_text"], str) and sig["reason_text"]
    assert sig["input_basis"]["total_holdings"] == 1
    assert sig["input_basis"]["matched_topn"] == 1


# ─── render_holdings_market_evidence_bullet (draft_message picker) ──


def test_render_returns_none_when_no_signal() -> None:
    payload = {"factor_signals": [{"scope": "universe", "reason_text": "test"}]}
    assert render_holdings_market_evidence_bullet(payload) is None


def test_render_returns_bullet_when_signal_present() -> None:
    payload = {
        "factor_signals": [
            {
                "scope": "holdings_market_evidence",
                "is_available": True,
                "factor_name": "보유 vs 시장",
                "reason_text": "보유 1건 중 일치 1건; A 20거래일 KODEX200 대비 +1.50%p",
            }
        ]
    }
    bullet = render_holdings_market_evidence_bullet(payload)
    assert bullet is not None
    assert bullet.startswith("- 보유 vs 시장:")
    assert "일치 1건" in bullet


def test_render_returns_none_for_non_dict_payload() -> None:
    assert render_holdings_market_evidence_bullet(None) is None
    assert render_holdings_market_evidence_bullet("oops") is None
