"""Runtime Evidence Composer (Runtime Evidence DB Connection v1) 전용 테스트.

지시문 §15 최소 검증 커버:
1. market_discovery_snapshot available
2. 실제 수치와 as-of 가 extra_notes 포함
3. table 만 있고 실데이터가 없으면 unavailable
4. daily data 가 realtime source 로 승격되지 않음
5. Holdings 파일 존재 + evidence 존재 시 contentful
6. Holdings 파일 부재 시 정확한 unavailable reason
7. NAV row 존재 / 부재 분기
8. US / ML / news / universe source unavailable 유지
9. Runtime 과 diagnosis 가 동일 Composer 사용
10. diagnosis 가 temp runtime DB active PARAM 사용
11. pure Composer test 의 실제 state 무변경 (기존 isolation fixture 로 검증)
12~15. runtime dry-run · privacy · package fallback 은 기존 test 로 커버.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from app.holdings import Holding
from app.runtime_evidence_composer import (
    REASON_EXTERNAL_FETCH_REQUIRED,
    REASON_NOT_IMPLEMENTED,
    REASON_SOURCE_MISSING_HOLDINGS,
    SRC_HOLDINGS,
    SRC_KR_REALTIME,
    SRC_MARKET_DISCOVERY,
    SRC_ML_BASELINE,
    SRC_NAV_DISCOUNT,
    SRC_NEWS,
    SRC_OVERNIGHT_US,
    SRC_UNIVERSE_MOMENTUM,
    compose_runtime_evidence,
)

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


# ── §15.1~15.4 market_discovery ──────────────────────────────────────────────


def test_market_briefing_available_with_contentful_notes(tmp_path: Path) -> None:
    result = compose_runtime_evidence(
        "market_briefing",
        market_db_path=tmp_path / "market_data.sqlite",
        holdings_file=tmp_path / "holdings.json",
        topn_fn=lambda **_: _ok_topn_payload(asof="2026-07-11"),
    )
    assert result.available_sources[SRC_MARKET_DISCOVERY] == "available"
    # us / ml / news / kr_realtime 은 unavailable 유지 (지시문 §5.4 · §5.5 · §5.6 · §5.7).
    assert result.available_sources[SRC_KR_REALTIME] == REASON_EXTERNAL_FETCH_REQUIRED
    assert result.available_sources[SRC_OVERNIGHT_US] == REASON_EXTERNAL_FETCH_REQUIRED
    assert result.available_sources[SRC_ML_BASELINE] == REASON_NOT_IMPLEMENTED
    assert result.available_sources[SRC_NEWS] == REASON_NOT_IMPLEMENTED
    # 실제 수치 · as-of 포함.
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
    """지시문 §5.4 · §15.4: daily close 가 realtime source 로 승격되지 않음."""
    result = compose_runtime_evidence(
        "market_briefing",
        market_db_path=tmp_path / "market_data.sqlite",
        holdings_file=tmp_path / "holdings.json",
        topn_fn=lambda **_: _ok_topn_payload(),
    )
    assert result.available_sources[SRC_KR_REALTIME] == REASON_EXTERNAL_FETCH_REQUIRED


# ── §15.5~15.6 holdings ─────────────────────────────────────────────────────


def _fake_holdings_ok() -> list[Holding]:
    return [Holding(ticker="069500", quantity=10, avg_buy_price=35000.0)]


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


def test_holdings_briefing_available_when_file_present(tmp_path: Path) -> None:
    hfile = tmp_path / "holdings.json"
    hfile.write_text("{}", encoding="utf-8")

    def _fake_nav_fn(*, etf_ticker: str, db_path: Path):
        return None  # NAV 는 부재 케이스.

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
        holdings_file=tmp_path / "no_holdings.json",  # 부재.
        topn_fn=lambda **_: _ok_topn_payload(),
    )
    assert result.available_sources[SRC_HOLDINGS] == REASON_SOURCE_MISSING_HOLDINGS
    assert result.available_sources[SRC_NAV_DISCOUNT] == REASON_SOURCE_MISSING_HOLDINGS
    assert result.diagnostics["holdings_source_present"] is False


# ── §15.7 NAV ──────────────────────────────────────────────────────────────


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


# ── §15.8 spike source ─────────────────────────────────────────────────────


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
    # A-1 정정: spike 는 market_discovery / holdings 미사용 → contentful 은 0.
    assert result.diagnostics["contentful_fact_count"] == 0
    assert result.diagnostics["selection_result_count"] == 0
    # B-6 정정: spike 는 topn_fn 을 호출하지 않아야 함 (불필요 계산 제거).
    assert calls == []
    # source_statuses 는 unavailable 라벨 (not_applicable 아님).
    assert all(
        v == "unavailable" for v in result.diagnostics["source_statuses"].values()
    )


def test_market_briefing_contentful_only_counts_own_sources(tmp_path: Path) -> None:
    """A-1: market_briefing contentful 은 market_discovery 만 집계 (Holdings/NAV 미가산)."""
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
    # market_discovery 는 available.
    assert ss[SRC_MARKET_DISCOVERY] == "available"
    # 나머지 4 는 모두 unavailable.
    for src in (SRC_KR_REALTIME, SRC_OVERNIGHT_US, SRC_ML_BASELINE, SRC_NEWS):
        assert ss[src] == "unavailable", f"{src}: {ss[src]}"


def test_holdings_broad_exception_propagates(tmp_path: Path) -> None:
    """B-1: 프로그래머 오류 (TypeError 등) 는 unavailable 로 위장하지 않고 propagate."""
    import pytest as _pytest

    hfile = tmp_path / "holdings.json"
    hfile.write_text("{}", encoding="utf-8")

    def _boom() -> list[Holding]:
        raise TypeError("programmer_error_intentional")

    with _pytest.raises(TypeError, match="programmer_error_intentional"):
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
    """B-1 정정 r2: ValueError 도 프로그래머 오류로 propagate (JSONDecodeError 만 제외)."""
    import pytest as _pytest

    hfile = tmp_path / "holdings.json"
    hfile.write_text("{}", encoding="utf-8")

    def _boom() -> list[Holding]:
        raise ValueError("programmer_value_error")

    with _pytest.raises(ValueError, match="programmer_value_error"):
        compose_runtime_evidence(
            "holdings_briefing",
            market_db_path=tmp_path / "market_data.sqlite",
            holdings_file=hfile,
            holdings_loader=_boom,
            topn_fn=lambda **_: _ok_topn_payload(),
            evidence_fn=_ok_evidence_fn,
            nav_fn=lambda **_: None,
        )


def test_holdings_unavailable_when_market_asof_missing(tmp_path: Path) -> None:
    """A-1 정정 r3: Holdings 시장 evidence 는 market_asof 부재 시 unavailable.
    NAV 는 자체 조건 (row.asof + 값) 만으로 판정되어 available 유지 (독립).
    """
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
    # Holdings 시장 evidence 는 unavailable.
    assert result.available_sources[SRC_HOLDINGS] == "holdings_market_asof_missing"
    # NAV 는 독립적으로 available (row.asof + 값 존재).
    assert result.available_sources[SRC_NAV_DISCOUNT] == "available"
    # extra_notes 는 NAV 만 포함.
    assert any("NAV" in n and "2026-07-11 기준" in n for n in result.extra_notes)
    # contentful_fact_count 는 NAV 만 계산 (holdings=0 + nav=1).
    assert result.diagnostics["contentful_fact_count"] >= 1


def test_nav_unavailable_when_row_asof_missing(tmp_path: Path) -> None:
    """A-1 정정 r4: NAV row 자체의 as-of 부재 시 available 처리하지 않음 (지시문 §5.3)."""
    hfile = tmp_path / "holdings.json"
    hfile.write_text("{}", encoding="utf-8")
    result = compose_runtime_evidence(
        "holdings_briefing",
        market_db_path=tmp_path / "market_data.sqlite",
        holdings_file=hfile,
        holdings_loader=_fake_holdings_ok,
        topn_fn=lambda **_: _ok_topn_payload(),
        evidence_fn=_ok_evidence_fn,
        # row 반환 but asof=None → NAV 는 unavailable.
        nav_fn=lambda **_: _fake_nav_row(asof=None),
    )
    assert result.available_sources[SRC_NAV_DISCOUNT] != "available"
    # extra_notes 에 "None 기준" 이 절대 나오지 않아야 함.
    assert not any("None 기준" in n for n in result.extra_notes)
    assert not any("NAV" in n for n in result.extra_notes)


def test_nav_independent_from_holdings_market_asof(tmp_path: Path) -> None:
    """A-1 정정 r3 (재확인): NAV 는 Holdings 시장 asof 종속 없음."""
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
    # source_asof 에 NAV asof 는 반영, Holdings asof 는 None (반영 안 됨).
    source_asof = result.diagnostics["source_asof"]
    assert source_asof.get(SRC_NAV_DISCOUNT) == "2026-07-11"
    # Holdings 시장 evidence 는 unavailable 이므로 source_asof 에 없어야 함
    # (asof=None 이므로 조립 시 필터됨).
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
    # Holdings source 의 asof 가 source_asof 에 포함.
    assert source_asof.get(SRC_HOLDINGS) == "2026-07-11"
    # 문장에도 기준일 명시.
    assert any("2026-07-11 기준" in n for n in result.extra_notes)


# ── §15.11 실제 state 무변경 (Composer pure test 확인) ─────────────────────


def test_composer_does_not_touch_real_market_db(tmp_path: Path) -> None:
    """지시문 §15.11: pure Composer test 는 실제 state 를 변경하지 않는다.

    이번 test 는 tmp market_db_path 를 명시적으로 전달하므로 실제 DB 는
    open 조차 되지 않는다.
    """
    before = _snapshot(_REAL_MARKET_DB)
    compose_runtime_evidence(
        "market_briefing",
        market_db_path=tmp_path / "market_data.sqlite",
        holdings_file=tmp_path / "holdings.json",
        topn_fn=lambda **_: _ok_topn_payload(),
    )
    after = _snapshot(_REAL_MARKET_DB)
    assert before == after


# ── §15.9~15.10 diagnosis 정합화 ──────────────────────────────────────────


def test_diagnosis_reproducer_uses_runtime_state_db(
    tmp_path: Path, monkeypatch
) -> None:
    """지시문 §11: diagnosis reproducer 가 runtime_state.sqlite 의 active PARAM 을 사용.

    conftest 가 이미 runtime_state_db.DEFAULT_DB_PATH 를 tmp 로 격리했으므로
    이 test 는 그 격리 위에서 seed 후 reproducer 호출 시 정상 동작하는지 확인.
    """
    from app.push_content_gap_diagnosis_reproducers import reproduce_param_runtime
    from app.runtime_param_store import activate_param_version, create_param_version
    from app.three_push_runtime_param import build_manual_seed_param

    # tmp DB seed.
    param = build_manual_seed_param()
    version_id, _, _ = create_param_version(param.to_dict())
    activate_param_version(version_id, activated_by="test")

    # reproduce_param_runtime 호출 시 legacy JSON 을 사용하지 않고 runtime_state DB 를 읽음.
    result = reproduce_param_runtime("market_briefing")
    assert result["param_available"] is True
    assert result["param_id"] == param.param_id
    assert result["push_kind_enabled_in_param"] is True
