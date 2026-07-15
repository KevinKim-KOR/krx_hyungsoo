"""Diagnostics 필드 · source_status labels · contentful count 분리 (지시문 §9).

Cleanup / FIX r7 Round 3B 에서 `tests/test_runtime_evidence_composer.py` 로부터 분리.
"""

from __future__ import annotations

from pathlib import Path

from app.runtime_evidence_composer import (
    SRC_KR_REALTIME,
    SRC_MARKET_DISCOVERY,
    SRC_ML_BASELINE,
    SRC_NEWS,
    SRC_OVERNIGHT_US,
    compose_runtime_evidence,
)

from tests.runtime_evidence._fixtures import _ok_topn_payload


def test_market_briefing_contentful_only_counts_own_sources(tmp_path: Path) -> None:
    """A-1: market_briefing contentful 은 market_discovery 만 집계."""
    result = compose_runtime_evidence(
        "market_briefing",
        market_db_path=tmp_path / "market_data.sqlite",
        holdings_file=tmp_path / "holdings.json",
        topn_fn=lambda **_: _ok_topn_payload(asof="2026-07-11"),
    )
    # fixture: kodex + kospi + preview = 3 fact.
    assert result.diagnostics["contentful_fact_count"] == 3


def test_market_briefing_source_status_labels_are_unavailable(tmp_path: Path) -> None:
    """A-1: 고정 unavailable source 는 status='unavailable' (not_applicable X)."""
    result = compose_runtime_evidence(
        "market_briefing",
        market_db_path=tmp_path / "market_data.sqlite",
        holdings_file=tmp_path / "holdings.json",
        topn_fn=lambda **_: _ok_topn_payload(),
    )
    ss = result.diagnostics["source_statuses"]
    assert ss[SRC_MARKET_DISCOVERY] == "available"
    for src in (SRC_KR_REALTIME, SRC_OVERNIGHT_US, SRC_ML_BASELINE, SRC_NEWS):
        assert ss[src] == "unavailable", f"{src}: {ss[src]}"
