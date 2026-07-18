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
    """§15.8 · B-6: Spike 는 universe artifact 부재 + kr_realtime 외부 필요.

    Universe Publication v1 (FIX): universe 는 실제 artifact 상태를 반영하므로
    부재 시 사유는 `artifact_missing_or_invalid_json`. kr_realtime 은 여전히
    `unavailable_external_fetch_required` (§35 - 이 STEP 에서 unavailable 유지).
    """
    calls: list[str] = []

    def _tracking_topn(**_kwargs):
        calls.append("topn_called")
        return _ok_topn_payload()

    # universe artifact 부재를 explicit 하게 시뮬레이션 (loader None 반환).
    result = compose_runtime_evidence(
        "spike_or_falling_alert",
        market_db_path=tmp_path / "market_data.sqlite",
        holdings_file=tmp_path / "holdings.json",
        topn_fn=_tracking_topn,
        universe_artifact_loader=lambda: None,
    )
    # universe 는 실제 artifact 상태 반영 → unavailable + 실제 사유.
    assert result.available_sources[SRC_UNIVERSE_MOMENTUM] != "available"
    assert (
        result.available_sources[SRC_UNIVERSE_MOMENTUM]
        == "artifact_missing_or_invalid_json"
    )
    # kr_realtime 은 여전히 외부 fetch 필요.
    assert result.available_sources[SRC_KR_REALTIME] == REASON_EXTERNAL_FETCH_REQUIRED
    assert result.extra_notes == []
    assert result.diagnostics["contentful_fact_count"] == 0
    assert result.diagnostics["selection_result_count"] == 0
    # topn 은 여전히 spike 에서 호출되지 않아야 함 (universe 만 참조).
    assert calls == []
    # source_statuses: universe=unavailable, kr_realtime=unavailable.
    assert all(
        v == "unavailable" for v in result.diagnostics["source_statuses"].values()
    )
