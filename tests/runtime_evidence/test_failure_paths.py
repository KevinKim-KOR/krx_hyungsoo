"""실패 경로 (조기 반환 · 예외 propagation · 실제 state 불변 · diagnosis reproducer).

Cleanup / FIX r7 Round 3B 에서 `tests/test_runtime_evidence_composer.py` 로부터 분리.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.holdings import Holding
from app.runtime_evidence_composer import compose_runtime_evidence

from tests.runtime_evidence._fixtures import (
    _REAL_MARKET_DB,
    _fake_holdings_ok,
    _ok_evidence_fn,
    _ok_topn_payload,
    _snapshot,
)


def test_holdings_broad_exception_propagates(tmp_path: Path) -> None:
    """B-1: 프로그래머 오류 (TypeError 등) 는 unavailable 로 위장하지 않고 propagate."""
    hfile = tmp_path / "holdings.json"
    hfile.write_text("{}", encoding="utf-8")

    def _boom() -> list[Holding]:
        raise TypeError("programmer_error_intentional")

    with pytest.raises(TypeError, match="programmer_error_intentional"):
        compose_runtime_evidence(
            "holdings_briefing",
            market_db_path=tmp_path / "market_data.sqlite",
            holdings_file=hfile,
            holdings_loader=_boom,
            topn_fn=lambda **_: _ok_topn_payload(),
            evidence_fn=_ok_evidence_fn,
            nav_fn=lambda **_: None,
        )


def test_holdings_value_error_propagates(tmp_path: Path) -> None:
    """B-1 r2: ValueError 도 프로그래머 오류로 propagate (JSONDecodeError 만 catch)."""
    hfile = tmp_path / "holdings.json"
    hfile.write_text("{}", encoding="utf-8")

    def _boom() -> list[Holding]:
        raise ValueError("programmer_value_error")

    with pytest.raises(ValueError, match="programmer_value_error"):
        compose_runtime_evidence(
            "holdings_briefing",
            market_db_path=tmp_path / "market_data.sqlite",
            holdings_file=hfile,
            holdings_loader=_boom,
            topn_fn=lambda **_: _ok_topn_payload(),
            evidence_fn=_ok_evidence_fn,
            nav_fn=lambda **_: None,
        )


def test_holdings_privacy_boolean_on_source_missing_r6(tmp_path: Path) -> None:
    """FIX r6: Holdings 파일 부재 조기 반환 → boolean False."""
    result = compose_runtime_evidence(
        "holdings_briefing",
        market_db_path=tmp_path / "market_data.sqlite",
        holdings_file=tmp_path / "missing_holdings.json",
        holdings_loader=_fake_holdings_ok,
        topn_fn=lambda **_: _ok_topn_payload(),
        evidence_fn=_ok_evidence_fn,
    )
    d = result.diagnostics
    assert d["holdings_snapshot_status"] == "unavailable"
    assert isinstance(d["private_fields_exposed"], bool)
    assert isinstance(d["raw_identifier_exposed"], bool)
    assert d["private_fields_exposed"] is False
    assert d["raw_identifier_exposed"] is False


def test_holdings_privacy_boolean_on_empty_holdings_r6(tmp_path: Path) -> None:
    """FIX r6: Holdings 빈 리스트 조기 반환 → boolean False."""
    hfile = tmp_path / "h.json"
    hfile.write_text("{}", encoding="utf-8")
    result = compose_runtime_evidence(
        "holdings_briefing",
        market_db_path=tmp_path / "market_data.sqlite",
        holdings_file=hfile,
        holdings_loader=lambda: [],
        topn_fn=lambda **_: _ok_topn_payload(),
        evidence_fn=_ok_evidence_fn,
    )
    d = result.diagnostics
    assert d["holdings_snapshot_status"] == "unavailable"
    assert isinstance(d["private_fields_exposed"], bool)
    assert isinstance(d["raw_identifier_exposed"], bool)
    assert d["private_fields_exposed"] is False
    assert d["raw_identifier_exposed"] is False


def test_holdings_privacy_boolean_on_load_error_r6(tmp_path: Path) -> None:
    """FIX r6: Holdings loader 예외 (validation 실패) 경로 → boolean False."""
    from app.holdings import HoldingsValidationError

    hfile = tmp_path / "h.json"
    hfile.write_text("{}", encoding="utf-8")

    def _bad_loader():
        raise HoldingsValidationError("bad")

    result = compose_runtime_evidence(
        "holdings_briefing",
        market_db_path=tmp_path / "market_data.sqlite",
        holdings_file=hfile,
        holdings_loader=_bad_loader,
        topn_fn=lambda **_: _ok_topn_payload(),
        evidence_fn=_ok_evidence_fn,
    )
    d = result.diagnostics
    assert d["holdings_snapshot_status"] == "unavailable"
    assert isinstance(d["private_fields_exposed"], bool)
    assert isinstance(d["raw_identifier_exposed"], bool)
    assert d["private_fields_exposed"] is False
    assert d["raw_identifier_exposed"] is False


def test_composer_does_not_touch_real_market_db(tmp_path: Path) -> None:
    """§15.11: pure Composer test 는 실제 state 를 변경하지 않는다."""
    before = _snapshot(_REAL_MARKET_DB)
    compose_runtime_evidence(
        "market_briefing",
        market_db_path=tmp_path / "market_data.sqlite",
        holdings_file=tmp_path / "holdings.json",
        topn_fn=lambda **_: _ok_topn_payload(),
    )
    after = _snapshot(_REAL_MARKET_DB)
    assert before == after


def test_diagnosis_reproducer_uses_runtime_state_db(
    tmp_path: Path, monkeypatch
) -> None:
    """§11: diagnosis reproducer 가 runtime_state.sqlite active PARAM 을 사용."""
    from app.push_content_gap_diagnosis_reproducers import reproduce_param_runtime
    from app.runtime_param_store import activate_param_version, create_param_version
    from app.three_push_runtime_param import build_manual_seed_param

    param = build_manual_seed_param()
    version_id, _, _ = create_param_version(param.to_dict())
    activate_param_version(version_id, activated_by="test")

    result = reproduce_param_runtime("market_briefing")
    assert result["param_available"] is True
    assert result["param_id"] == param.param_id
    assert result["push_kind_enabled_in_param"] is True
