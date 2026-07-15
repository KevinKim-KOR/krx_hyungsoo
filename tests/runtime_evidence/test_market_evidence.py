"""market_discovery + spike + kr_realtime unavailable (지시문 §15.1~15.4 · §15.8).

Cleanup / FIX r7 Round 3B 에서 `tests/test_runtime_evidence_composer.py` 로부터 분리.
"""

from __future__ import annotations

from pathlib import Path

from app.runtime_evidence_composer import (
    REASON_EXTERNAL_FETCH_REQUIRED,
    REASON_NOT_IMPLEMENTED,
    SRC_KR_REALTIME,
    SRC_MARKET_DISCOVERY,
    SRC_ML_BASELINE,
    SRC_NEWS,
    SRC_OVERNIGHT_US,
    SRC_UNIVERSE_MOMENTUM,
    compose_runtime_evidence,
)

from tests.runtime_evidence._fixtures import (
    _empty_topn_payload,
    _missing_topn_payload,
    _ok_topn_payload,
)


def test_market_briefing_available_with_contentful_notes(tmp_path: Path) -> None:
    result = compose_runtime_evidence(
        "market_briefing",
        market_db_path=tmp_path / "market_data.sqlite",
        holdings_file=tmp_path / "holdings.json",
        topn_fn=lambda **_: _ok_topn_payload(asof="2026-07-11"),
    )
    assert result.available_sources[SRC_MARKET_DISCOVERY] == "available"
    assert result.available_sources[SRC_KR_REALTIME] == REASON_EXTERNAL_FETCH_REQUIRED
    assert result.available_sources[SRC_OVERNIGHT_US] == REASON_EXTERNAL_FETCH_REQUIRED
    assert result.available_sources[SRC_ML_BASELINE] == REASON_NOT_IMPLEMENTED
    assert result.available_sources[SRC_NEWS] == REASON_NOT_IMPLEMENTED
    assert any("2026-07-11" in n for n in result.extra_notes)
    assert any("KODEX200" in n or "KOSPI" in n for n in result.extra_notes)
    assert result.diagnostics["contentful_fact_count"] >= 1
    assert result.diagnostics["selection_result_count"] == 2


def test_market_briefing_unavailable_when_empty(tmp_path: Path) -> None:
    result = compose_runtime_evidence(
        "market_briefing",
        market_db_path=tmp_path / "market_data.sqlite",
        holdings_file=tmp_path / "holdings.json",
        topn_fn=lambda **_: _empty_topn_payload(),
    )
    assert result.available_sources[SRC_MARKET_DISCOVERY] != "available"
    assert result.extra_notes == []
    assert result.diagnostics["contentful_fact_count"] == 0


def test_market_briefing_unavailable_when_missing_db(tmp_path: Path) -> None:
    result = compose_runtime_evidence(
        "market_briefing",
        market_db_path=tmp_path / "market_data.sqlite",
        holdings_file=tmp_path / "holdings.json",
        topn_fn=lambda **_: _missing_topn_payload(),
    )
    assert result.available_sources[SRC_MARKET_DISCOVERY] != "available"
    assert result.diagnostics["contentful_fact_count"] == 0


def test_kr_realtime_not_promoted_from_daily_data(tmp_path: Path) -> None:
    """§15.4: daily close 가 realtime source 로 승격되지 않음."""
    result = compose_runtime_evidence(
        "market_briefing",
        market_db_path=tmp_path / "market_data.sqlite",
        holdings_file=tmp_path / "holdings.json",
        topn_fn=lambda **_: _ok_topn_payload(),
    )
    assert result.available_sources[SRC_KR_REALTIME] == REASON_EXTERNAL_FETCH_REQUIRED


def test_spike_or_falling_alert_all_unavailable(tmp_path: Path) -> None:
    """§15.8 · B-6: Spike source 는 모두 unavailable, contentful/selection 은 0."""
    calls: list[str] = []

    def _tracking_topn(**_kwargs):
        calls.append("topn_called")
        return _ok_topn_payload()

    result = compose_runtime_evidence(
        "spike_or_falling_alert",
        market_db_path=tmp_path / "market_data.sqlite",
        holdings_file=tmp_path / "holdings.json",
        topn_fn=_tracking_topn,
    )
    assert result.available_sources[SRC_UNIVERSE_MOMENTUM] == REASON_NOT_IMPLEMENTED
    assert result.available_sources[SRC_KR_REALTIME] == REASON_EXTERNAL_FETCH_REQUIRED
    assert result.extra_notes == []
    assert result.diagnostics["contentful_fact_count"] == 0
    assert result.diagnostics["selection_result_count"] == 0
    assert calls == []
    assert all(
        v == "unavailable" for v in result.diagnostics["source_statuses"].values()
    )
