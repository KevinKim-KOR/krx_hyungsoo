"""NAV row 해석 · market_asof 독립성 (지시문 §15.7).

Cleanup / FIX r7 Round 3B 에서 `tests/test_runtime_evidence_composer.py` 로부터 분리.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.runtime_evidence_composer import (
    SRC_HOLDINGS,
    SRC_NAV_DISCOUNT,
    compose_runtime_evidence,
)

from tests.runtime_evidence._fixtures import (
    _fake_holdings_ok,
    _fake_nav_row,
    _ok_evidence_fn,
    _ok_topn_payload,
)


def test_nav_available_when_row_present(tmp_path: Path) -> None:
    hfile = tmp_path / "holdings.json"
    hfile.write_text("{}", encoding="utf-8")
    result = compose_runtime_evidence(
        "holdings_briefing",
        market_db_path=tmp_path / "market_data.sqlite",
        holdings_file=hfile,
        holdings_loader=_fake_holdings_ok,
        topn_fn=lambda **_: _ok_topn_payload(),
        evidence_fn=_ok_evidence_fn,
        nav_fn=lambda **_: _fake_nav_row(),
    )
    assert result.available_sources[SRC_NAV_DISCOUNT] == "available"
    assert any("NAV" in n and "2026-07-11" in n for n in result.extra_notes)


def test_nav_unavailable_when_row_missing(tmp_path: Path) -> None:
    hfile = tmp_path / "holdings.json"
    hfile.write_text("{}", encoding="utf-8")
    result = compose_runtime_evidence(
        "holdings_briefing",
        market_db_path=tmp_path / "market_data.sqlite",
        holdings_file=hfile,
        holdings_loader=_fake_holdings_ok,
        topn_fn=lambda **_: _ok_topn_payload(),
        evidence_fn=_ok_evidence_fn,
        nav_fn=lambda **_: None,
    )
    assert result.available_sources[SRC_NAV_DISCOUNT] != "available"


def test_nav_unavailable_when_row_asof_missing(tmp_path: Path) -> None:
    """A-1 정정 r4: NAV row 자체의 as-of 부재 시 available 처리하지 않음 (§5.3)."""
    hfile = tmp_path / "holdings.json"
    hfile.write_text("{}", encoding="utf-8")
    result = compose_runtime_evidence(
        "holdings_briefing",
        market_db_path=tmp_path / "market_data.sqlite",
        holdings_file=hfile,
        holdings_loader=_fake_holdings_ok,
        topn_fn=lambda **_: _ok_topn_payload(),
        evidence_fn=_ok_evidence_fn,
        nav_fn=lambda **_: _fake_nav_row(asof=None),
    )
    assert result.available_sources[SRC_NAV_DISCOUNT] != "available"
    assert not any("None 기준" in n for n in result.extra_notes)
    assert not any("NAV" in n for n in result.extra_notes)


def test_holdings_unavailable_when_market_asof_missing(tmp_path: Path) -> None:
    """A-1 정정 r3: Holdings 시장 evidence 는 market_asof 부재 시 unavailable.
    NAV 는 자체 조건 (row.asof + 값) 만으로 판정되어 available 유지 (독립)."""
    hfile = tmp_path / "holdings.json"
    hfile.write_text("{}", encoding="utf-8")

    def _evidence_without_asof(**_kwargs: Any) -> dict[str, Any]:
        payload = _ok_evidence_fn(**_kwargs)
        payload["market_asof"] = None
        return payload

    result = compose_runtime_evidence(
        "holdings_briefing",
        market_db_path=tmp_path / "market_data.sqlite",
        holdings_file=hfile,
        holdings_loader=_fake_holdings_ok,
        topn_fn=lambda **_: _ok_topn_payload(),
        evidence_fn=_evidence_without_asof,
        nav_fn=lambda **_: _fake_nav_row(asof="2026-07-11"),
    )
    assert result.available_sources[SRC_HOLDINGS] == "holdings_market_asof_missing"
    assert result.available_sources[SRC_NAV_DISCOUNT] == "available"
    assert any("NAV" in n and "2026-07-11 기준" in n for n in result.extra_notes)
    assert result.diagnostics["contentful_fact_count"] >= 1


def test_nav_independent_from_holdings_market_asof(tmp_path: Path) -> None:
    """A-1 정정 r3: NAV 는 Holdings 시장 asof 종속 없음."""
    hfile = tmp_path / "holdings.json"
    hfile.write_text("{}", encoding="utf-8")

    def _evidence_missing_asof(**_kwargs: Any) -> dict[str, Any]:
        payload = _ok_evidence_fn(**_kwargs)
        payload["market_asof"] = None
        return payload

    result = compose_runtime_evidence(
        "holdings_briefing",
        market_db_path=tmp_path / "market_data.sqlite",
        holdings_file=hfile,
        holdings_loader=_fake_holdings_ok,
        topn_fn=lambda **_: _ok_topn_payload(),
        evidence_fn=_evidence_missing_asof,
        nav_fn=lambda **_: _fake_nav_row(asof="2026-07-11"),
    )
    source_asof = result.diagnostics["source_asof"]
    assert source_asof.get(SRC_NAV_DISCOUNT) == "2026-07-11"
    assert SRC_HOLDINGS not in source_asof


def test_holdings_source_asof_populated_when_available(tmp_path: Path) -> None:
    """A-3 정정 r2: Holdings diag 의 asof 가 source_asof 에 정확히 반영됨."""
    hfile = tmp_path / "holdings.json"
    hfile.write_text("{}", encoding="utf-8")
    result = compose_runtime_evidence(
        "holdings_briefing",
        market_db_path=tmp_path / "market_data.sqlite",
        holdings_file=hfile,
        holdings_loader=_fake_holdings_ok,
        topn_fn=lambda **_: _ok_topn_payload(),
        evidence_fn=_ok_evidence_fn,
        nav_fn=lambda **_: _fake_nav_row(asof="2026-07-11"),
    )
    source_asof = result.diagnostics["source_asof"]
    assert source_asof.get(SRC_HOLDINGS) == "2026-07-11"
    assert any("2026-07-11 기준" in n for n in result.extra_notes)
