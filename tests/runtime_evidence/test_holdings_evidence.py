"""Holdings evidence 판정 계약 (FIX r3 Q3/Q6/Q7 · 지시문 §15.5).

Cleanup / FIX r7 Round 3B 에서 `tests/test_runtime_evidence_composer.py` 로부터 분리.
"""

from __future__ import annotations

from pathlib import Path

from app.runtime_evidence_composer import (
    REASON_SOURCE_MISSING_HOLDINGS,
    SRC_HOLDINGS,
    SRC_NAV_DISCOUNT,
    compose_runtime_evidence,
)

from tests.runtime_evidence._fixtures import (
    _evidence_matched,
    _evidence_not_in_topn,
    _evidence_topn_failed,
    _evidence_topn_failed_but_asof_preserved,
    _evidence_two_holdings_one_matched,
    _fake_holdings_ok,
    _fake_holdings_two,
    _make_result_for_holdings_briefing,
    _nav_ok,
    _ok_evidence_fn,
    _ok_topn_payload,
)


def test_holdings_briefing_available_when_file_present(tmp_path: Path) -> None:
    hfile = tmp_path / "holdings.json"
    hfile.write_text("{}", encoding="utf-8")

    def _fake_nav_fn(*, etf_ticker: str, db_path: Path):
        return None  # NAV 부재.

    result = compose_runtime_evidence(
        "holdings_briefing",
        market_db_path=tmp_path / "market_data.sqlite",
        holdings_file=hfile,
        holdings_loader=_fake_holdings_ok,
        topn_fn=lambda **_: _ok_topn_payload(),
        evidence_fn=_ok_evidence_fn,
        nav_fn=_fake_nav_fn,
    )
    assert result.available_sources[SRC_HOLDINGS] == "available"
    assert any("KODEX 200" in n for n in result.extra_notes)
    assert result.diagnostics["holdings_source_present"] is True
    assert result.diagnostics["selection_result_count"] >= 1


def test_holdings_briefing_unavailable_when_file_missing(tmp_path: Path) -> None:
    result = compose_runtime_evidence(
        "holdings_briefing",
        market_db_path=tmp_path / "market_data.sqlite",
        holdings_file=tmp_path / "no_holdings.json",
        topn_fn=lambda **_: _ok_topn_payload(),
    )
    assert result.available_sources[SRC_HOLDINGS] == REASON_SOURCE_MISSING_HOLDINGS
    assert result.available_sources[SRC_NAV_DISCOUNT] == REASON_SOURCE_MISSING_HOLDINGS
    assert result.diagnostics["holdings_source_present"] is False


def test_holdings_matched_topn_available_r3(tmp_path: Path) -> None:
    """FIX r3 Q6-1: Holdings 1건 + TOP-N 직접 match → available, selection=1."""
    r = _make_result_for_holdings_briefing(tmp_path, _evidence_matched)
    d = r.diagnostics
    assert r.available_sources[SRC_HOLDINGS] == "available"
    assert d["holdings_snapshot_status"] == "available"
    assert d["holdings_selection_result_count"] == 1
    assert d["holdings_contentful_fact_count"] == 1
    assert d["rendered_holdings_fact_count"] == 1
    assert any("TOP3" in n for n in r.extra_notes)


def test_holdings_not_in_topn_still_available_r3(tmp_path: Path) -> None:
    """FIX r3 Q3/Q6-2: not_in_current_topn 도 정상 비교 evidence → available."""
    r = _make_result_for_holdings_briefing(tmp_path, _evidence_not_in_topn)
    d = r.diagnostics
    assert r.available_sources[SRC_HOLDINGS] == "available"
    assert d["holdings_snapshot_status"] == "available"
    assert d["holdings_selection_result_count"] == 1
    assert any("TOP-N 미포함" in n and "2026-07-11" in n for n in r.extra_notes)


def test_holdings_two_holdings_one_evidence_r3(tmp_path: Path) -> None:
    """FIX r3 Q6-3: Holdings 2건 중 1건만 유효 evidence → selection=1."""
    r = _make_result_for_holdings_briefing(
        tmp_path,
        _evidence_two_holdings_one_matched,
        holdings=_fake_holdings_two,
    )
    d = r.diagnostics
    assert d["holdings_loaded_count"] == 2
    assert d["holdings_evidence_item_count"] == 1
    assert d["holdings_selection_result_count"] == 1
    assert d["holdings_contentful_fact_count"] == 1


def test_holdings_topn_query_failed_unavailable_r3(tmp_path: Path) -> None:
    """FIX r3 Q3/Q6-4: TOP-N 조회 실패 (market_asof 부재) → unavailable."""
    r = _make_result_for_holdings_briefing(tmp_path, _evidence_topn_failed)
    d = r.diagnostics
    assert r.available_sources[SRC_HOLDINGS] != "available"
    assert d["holdings_snapshot_status"] == "unavailable"
    assert d["holdings_snapshot_reason"] in (
        "holdings_market_asof_missing",
        "topn_query_failed",
    )
    assert d["holdings_selection_result_count"] == 0


def test_holdings_fact_attribution_separated_r3(tmp_path: Path) -> None:
    """FIX r3 Q2/Q7: Holdings fact 와 NAV fact 가 명확히 분리 집계."""
    r = _make_result_for_holdings_briefing(tmp_path, _evidence_matched, nav_fn=_nav_ok)
    d = r.diagnostics
    assert d["holdings_contentful_fact_count"] == 1
    assert d["nav_contentful_fact_count"] == 1
    assert d["contentful_fact_count"] == 2


def test_holdings_only_nav_available_holdings_unavailable_r3(tmp_path: Path) -> None:
    """FIX r3 Q6-5: NAV fact 만 있고 Holdings evidence 0건 → holdings=unavailable, nav=available."""

    def _empty_holdings_evidence(**_):
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
                    "topn_match": {"status": "unavailable"},
                    "short_term_momentum": {"status": "unavailable"},
                    "constituents_overlap": {"status": "unavailable"},
                    "nav_discount": {"status": "unavailable"},
                    "evidence_notes": [],
                }
            ],
            "warnings": [],
        }

    r = _make_result_for_holdings_briefing(
        tmp_path, _empty_holdings_evidence, nav_fn=_nav_ok
    )
    assert r.available_sources[SRC_HOLDINGS] != "available"
    assert r.available_sources[SRC_NAV_DISCOUNT] == "available"
    d = r.diagnostics
    assert d["holdings_snapshot_status"] == "unavailable"
    assert d["holdings_contentful_fact_count"] == 0
    assert d["nav_contentful_fact_count"] == 1


def test_holdings_unavailable_note_not_counted_r3(tmp_path: Path) -> None:
    """FIX r3 Q6-7: unavailable 상태 → rendered/contentful/selection 모두 0."""
    r = _make_result_for_holdings_briefing(tmp_path, _evidence_topn_failed)
    d = r.diagnostics
    assert d["holdings_snapshot_status"] == "unavailable"
    assert d["holdings_contentful_fact_count"] == 0
    assert d["rendered_holdings_fact_count"] == 0
    assert d["holdings_selection_result_count"] == 0


def test_holdings_topn_failed_with_preserved_asof_unavailable_r5(
    tmp_path: Path,
) -> None:
    """FIX r5 A-1: TOP-N 실패 + asof 보존 → unavailable (fail-closed)."""
    r = _make_result_for_holdings_briefing(
        tmp_path, _evidence_topn_failed_but_asof_preserved
    )
    d = r.diagnostics
    assert r.available_sources[SRC_HOLDINGS] != "available"
    assert d["holdings_snapshot_status"] == "unavailable"
    assert d["holdings_snapshot_reason"] == "topn_query_failed"
    assert d["holdings_selection_result_count"] == 0
    assert d["holdings_contentful_fact_count"] == 0
