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


# ── FIX r3 (설계자 확정본 Q3/Q6/Q7): Holdings evidence fact attribution 재검증 ──


def _evidence_matched(**_kwargs: Any) -> dict[str, Any]:
    """matched_topn_candidate 시나리오."""
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
                "topn_match": {"status": "unavailable"},  # 조회 불가.
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


def _make_result_for_holdings_briefing(
    tmp_path: Path, evidence_fn, nav_fn=lambda **_: None, holdings=None
) -> Any:
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
    # note 에 not_in_topn 문장 + market_asof 포함.
    assert any("TOP-N 미포함" in n and "2026-07-11" in n for n in r.extra_notes)


def _fake_holdings_two() -> list[Holding]:
    """Q6-3 전용: 2건 loader."""
    return [
        Holding(ticker="069500", quantity=10, avg_buy_price=35000.0),
        Holding(ticker="222222", quantity=5, avg_buy_price=12000.0),
    ]


def test_holdings_two_holdings_one_evidence_r3(tmp_path: Path) -> None:
    """FIX r3 Q6-3: Holdings 2건 중 1건만 유효 evidence → selection=1."""
    r = _make_result_for_holdings_briefing(
        tmp_path,
        _evidence_two_holdings_one_matched,
        holdings=_fake_holdings_two,
    )
    d = r.diagnostics
    assert d["holdings_loaded_count"] == 2  # 2건 loader.
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

    def _nav_ok(**_):
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

    r = _make_result_for_holdings_briefing(tmp_path, _evidence_matched, nav_fn=_nav_ok)
    d = r.diagnostics
    # Holdings fact 는 topn_match 로 1건.
    assert d["holdings_contentful_fact_count"] == 1
    # NAV fact 는 별도 카운터.
    assert d["nav_contentful_fact_count"] == 1
    # 전체 total = holdings + nav.
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
                    "topn_match": {"status": "unavailable"},  # 조회 불가 상태.
                    "short_term_momentum": {"status": "unavailable"},
                    "constituents_overlap": {"status": "unavailable"},
                    "nav_discount": {"status": "unavailable"},
                    "evidence_notes": [],
                }
            ],
            "warnings": [],
        }

    def _nav_ok(**_):
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

    r = _make_result_for_holdings_briefing(
        tmp_path, _empty_holdings_evidence, nav_fn=_nav_ok
    )
    assert r.available_sources[SRC_HOLDINGS] != "available"
    assert r.available_sources[SRC_NAV_DISCOUNT] == "available"
    d = r.diagnostics
    assert d["holdings_snapshot_status"] == "unavailable"
    assert d["holdings_contentful_fact_count"] == 0
    assert d["nav_contentful_fact_count"] == 1


def test_holdings_briefing_message_privacy_and_content_r3(tmp_path: Path) -> None:
    """FIX r3 Q4 (c): Composer 결과 extra_notes 에 개인정보/금지 문구 미노출 + 필수 요소 포함."""

    def _nav_ok(**_):
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

    r = _make_result_for_holdings_briefing(tmp_path, _evidence_matched, nav_fn=_nav_ok)
    text = "\n".join(r.extra_notes)
    # 필수 포함.
    assert "KODEX 200" in text  # 실제 보유 종목명.
    assert "2026-07-11" in text  # 실제 market_asof.
    # 금지 개인정보 미노출: key 이름 뿐 아니라 실제 값 (35000=avg_buy_price,
    # 350000=invested_amount=35000*10, 10=quantity) 도 검사.
    for kw in (
        "avg_buy_price",
        "account_group",
        "quantity",
        "invested_amount",
        "35000",  # avg_buy_price 실제 값.
        "350000",  # invested_amount = avg * qty.
    ):
        assert kw not in text, f"forbidden {kw!r} leaked in extra_notes"
    # 내부 reason code 미노출.
    for kw in (
        "unavailable_external_fetch_required",
        "unavailable_not_implemented",
        "holdings_source_missing",
    ):
        assert kw not in text
    # FIX r4: Q4 privacy 진단 필드 실측 = 0.
    assert r.diagnostics.get("private_fields_exposed") is False
    assert r.diagnostics.get("raw_identifier_exposed") is False


def test_holdings_unavailable_note_not_counted_r3(tmp_path: Path) -> None:
    """FIX r3 Q6-7: unavailable 상태 (holdings evidence 0건) 는 contentful fact 로 미계산.

    안내 문장 (예: 'Holdings 파일 부재') 만 있을 경우 rendered_holdings_fact_count = 0,
    holdings_contentful_fact_count = 0 유지.
    """
    r = _make_result_for_holdings_briefing(tmp_path, _evidence_topn_failed)
    d = r.diagnostics
    assert d["holdings_snapshot_status"] == "unavailable"
    assert d["holdings_contentful_fact_count"] == 0
    assert d["rendered_holdings_fact_count"] == 0
    assert d["holdings_selection_result_count"] == 0
    # extra_notes 안에 안내 문장이 있더라도 contentful 카운터에 반영되지 않음.


def test_holdings_message_body_no_privacy_leakage_via_build_runtime_message_r3(
    tmp_path: Path,
) -> None:
    """FIX r4 Q4 (b·c): 실제 build_runtime_message() 결과 본문에 개인정보 미노출."""
    from app.three_push_runtime_message_builder import build_runtime_message
    from app.three_push_runtime_param import RuntimeParam

    def _nav_ok(**_):
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

    ev = _make_result_for_holdings_briefing(tmp_path, _evidence_matched, nav_fn=_nav_ok)
    param = RuntimeParam(
        param_id="test",
        created_at="2026-07-11T00:00:00+00:00",
        approved_at="2026-07-11T00:00:00+00:00",
        approved_by="test",
        param_source="manual",
        enabled_push_kinds=["holdings_briefing"],
        runtime_policy={},
        evidence_policy={},
        safety_policy={},
    )
    body = build_runtime_message(
        push_kind="holdings_briefing",
        param=param,
        runtime_kst_iso="2026-07-11T09:00:00+09:00",
        available_sources=ev.available_sources,
        extra_notes=ev.extra_notes,
    )
    # 실제 보유 종목명 · market_asof 는 포함.
    assert "KODEX 200" in body
    assert "2026-07-11" in body
    # 금지 개인정보 미노출 (Q4 확정본): key 이름 + 실제 값 (invested_amount 포함).
    for kw in (
        "avg_buy_price",
        "account_group",
        "quantity",
        "invested_amount",
        "35000",
        "350000",  # invested_amount = avg * qty.
    ):
        assert kw not in body, f"forbidden {kw!r} leaked in message body"
    # FIX r5: FORBIDDEN_PHRASES 전체 검사 (실 runner 가 사용하는 목록).
    from app.three_push_runner_common import (
        FORBIDDEN_PHRASES,
        check_forbidden_wording,
    )

    assert check_forbidden_wording(body) is None
    for phrase in FORBIDDEN_PHRASES:
        assert phrase not in body, f"FORBIDDEN_PHRASE {phrase!r} leaked in message body"
    # 내부 reason code · raw 식별자 미노출.
    for kw in (
        "unavailable_external_fetch_required",
        "unavailable_not_implemented",
        "holdings_source_missing",
    ):
        assert kw not in body


# ── FIX r5 (검증자 REJECTED r5 대응): fail-closed + privacy boolean + runner forward 회귀 ──


def _evidence_topn_failed_but_asof_preserved(**_kwargs: Any) -> dict[str, Any]:
    """FIX r5 (검증자 REJECTED r5 A-1 재현): builder 실패 시에도 입력 asof 를 보존.

    실제 builder 는 topn_status != "ok" 여도 topn_payload.asof 를 반환한 dict 의
    market_asof 로 보존할 수 있다 (holdings_market_evidence.build_holdings_market_evidence
    참고). 따라서 Composer 는 market_asof 존재만으로 성공 판정하면 안 되고,
    per-holding topn_match.status ∈ {matched, not_in_current_topn} 로만 판정해야 한다.
    """
    return {
        "status": "ok",
        "asof": "2026-07-11",
        "market_asof": "2026-07-11",  # ← builder 실패 상태에서도 보존.
        "market_context": {},
        "summary": {},
        "holdings": [
            {
                "ticker": "069500",
                "name": "KODEX 200",
                "returns": {"status": "unavailable"},
                "excess_return": {"status": "unavailable"},
                "topn_match": {"status": "unavailable"},  # TOP-N reader 실패 신호.
                "short_term_momentum": {"status": "unavailable"},
                "constituents_overlap": {"status": "unavailable"},
                "nav_discount": {"status": "unavailable"},
                "evidence_notes": [],
            }
        ],
        "warnings": [],
    }


def test_holdings_topn_failed_with_preserved_asof_unavailable_r5(
    tmp_path: Path,
) -> None:
    """FIX r5 A-1 (검증자 REJECTED r5 재현): TOP-N 실패 + asof 보존 → unavailable.

    이전 FIX r4 구현은 market_asof 존재만으로 available 로 잘못 통과.
    """
    r = _make_result_for_holdings_briefing(
        tmp_path, _evidence_topn_failed_but_asof_preserved
    )
    d = r.diagnostics
    assert r.available_sources[SRC_HOLDINGS] != "available"
    assert d["holdings_snapshot_status"] == "unavailable"
    assert d["holdings_snapshot_reason"] == "topn_query_failed"
    assert d["holdings_selection_result_count"] == 0
    assert d["holdings_contentful_fact_count"] == 0


def test_holdings_privacy_fields_are_boolean_r5(tmp_path: Path) -> None:
    """FIX r5 A-1: private_fields_exposed / raw_identifier_exposed 는 boolean."""
    r = _make_result_for_holdings_briefing(tmp_path, _evidence_matched)
    d = r.diagnostics
    assert isinstance(d.get("private_fields_exposed"), bool)
    assert isinstance(d.get("raw_identifier_exposed"), bool)
    assert d["private_fields_exposed"] is False
    assert d["raw_identifier_exposed"] is False


def test_holdings_privacy_detects_actual_value_leak_r5(tmp_path: Path) -> None:
    """FIX r5 A-1: 실제 개인정보 값 (quantity/avg_buy_price/invested_amount) 이
    notes 에 나타나면 private_fields_exposed=True 로 감지."""

    def _leaky_evidence(**_kwargs: Any) -> dict[str, Any]:
        return {
            "status": "ok",
            "market_asof": "2026-07-11",
            "market_context": {},
            "summary": {},
            "holdings": [
                {
                    "ticker": "069500",
                    "name": "KODEX 200 수량 10 평단 35000",  # ← 개인정보 값 포함.
                    "returns": {"status": "unavailable"},
                    "excess_return": {"status": "unavailable"},
                    "topn_match": {
                        "status": "matched_topn_candidate",
                        "rank": 1,
                    },
                    "short_term_momentum": {"status": "unavailable"},
                    "constituents_overlap": {"status": "unavailable"},
                    "nav_discount": {"status": "unavailable"},
                    "evidence_notes": [],
                }
            ],
            "warnings": [],
        }

    r = _make_result_for_holdings_briefing(tmp_path, _leaky_evidence)
    d = r.diagnostics
    assert d["private_fields_exposed"] is True


def test_holdings_briefing_runner_record_forwards_all_diagnostics_r6(
    tmp_path: Path, monkeypatch
) -> None:
    """FIX r6 (검증자 REJECTED r6 대응): runner 실행 후 record 에 진단 10 필드 실제 전달.

    monkeypatch 로 compose_runtime_evidence + 부수효과 (DB write / Telegram) 를
    차단하고 실제 run() 을 호출해 반환된 record 를 검사.
    """
    from app.runtime_evidence_composer import (
        RuntimeEvidenceResult,
        SRC_MARKET_DISCOVERY,
    )
    from app.three_push_runtime_param import RuntimeParam
    import scripts.run_three_push_runtime_oci as runner_mod

    fake_evidence = RuntimeEvidenceResult(
        available_sources={
            SRC_HOLDINGS: "available",
            SRC_NAV_DISCOUNT: "available",
            SRC_MARKET_DISCOVERY: "available",
        },
        extra_notes=["KODEX 200 (2026-07-11 기준): Market Discovery TOP1."],
        diagnostics={
            "contentful_fact_count": 1,
            "selection_result_count": 1,
            "unavailable_reasons": {},
            "holdings_snapshot_status": "available",
            "holdings_snapshot_reason": "",
            "holdings_loaded_count": 35,
            "holdings_evidence_item_count": 35,
            "holdings_contentful_fact_count": 35,
            "nav_contentful_fact_count": 32,
            "holdings_selection_result_count": 35,
            "rendered_holdings_fact_count": 35,
            "private_fields_exposed": False,
            "raw_identifier_exposed": False,
        },
    )
    fake_param = RuntimeParam(
        param_id="test-p",
        created_at="2026-07-11T00:00:00+00:00",
        approved_at="2026-07-11T00:00:00+00:00",
        approved_by="test",
        param_source="manual",
        enabled_push_kinds=["holdings_briefing"],
        runtime_policy={},
        evidence_policy={},
        safety_policy={},
    )
    monkeypatch.setattr(
        runner_mod, "compose_runtime_evidence", lambda pk: fake_evidence
    )
    monkeypatch.setattr(
        runner_mod, "read_active_param_dict", lambda: fake_param.to_dict()
    )
    monkeypatch.setattr(runner_mod, "param_from_dict", lambda d: fake_param)
    monkeypatch.setattr(runner_mod, "insert_status_from_record", lambda r: None)
    monkeypatch.setattr(runner_mod, "_HISTORY_PATH", tmp_path / "history.jsonl")
    monkeypatch.setattr(
        runner_mod, "telegram_send", lambda *a, **kw: (False, "blocked_by_test")
    )
    monkeypatch.setattr(
        runner_mod, "build_runtime_message", lambda **kw: "test body 2026-07-11"
    )

    record = runner_mod.run("holdings_briefing", "dry-run")

    # 필수 10 필드가 record 에 실제로 전달됐는지 검사.
    assert record["holdings_snapshot_status"] == "available"
    assert record["holdings_snapshot_reason"] == ""
    assert record["holdings_loaded_count"] == 35
    assert record["holdings_evidence_item_count"] == 35
    assert record["holdings_contentful_fact_count"] == 35
    assert record["nav_contentful_fact_count"] == 32
    assert record["holdings_selection_result_count"] == 35
    assert record["rendered_holdings_fact_count"] == 35
    # boolean 계약.
    assert record["private_fields_exposed"] is False
    assert record["raw_identifier_exposed"] is False
    # Telegram 미발송.
    assert record["telegram_attempted"] is False
    assert record["telegram_sent"] is False


def test_holdings_privacy_boolean_on_source_missing_r6(tmp_path: Path) -> None:
    """FIX r6 (검증자 REJECTED r6): Holdings 파일 부재 조기 반환 경로에서도
    진단 필드가 boolean False (정수 0 아님)."""
    result = compose_runtime_evidence(
        "holdings_briefing",
        market_db_path=tmp_path / "market_data.sqlite",
        holdings_file=tmp_path / "missing_holdings.json",  # 부재.
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
    """FIX r6: Holdings 빈 리스트 조기 반환에서도 boolean."""
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
    """FIX r6: Holdings loader 예외 (validation 실패) 경로에서도 boolean."""
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


def test_holdings_privacy_detects_short_two_char_value_r6(tmp_path: Path) -> None:
    """FIX r6 A-1 (검증자 REJECTED r6): quantity=10 (2자) 노출도 감지."""

    def _leaky_qty10_evidence(**_kwargs: Any) -> dict[str, Any]:
        return {
            "status": "ok",
            "market_asof": "2026-07-11",
            "market_context": {},
            "summary": {},
            "holdings": [
                {
                    "ticker": "069500",
                    # 종목명에 실제 quantity 값 "10" 이 노출된 상황 시뮬레이션.
                    "name": "KODEX 200 보유수량 10주",
                    "returns": {"status": "unavailable"},
                    "excess_return": {"status": "unavailable"},
                    "topn_match": {"status": "matched_topn_candidate", "rank": 1},
                    "short_term_momentum": {"status": "unavailable"},
                    "constituents_overlap": {"status": "unavailable"},
                    "nav_discount": {"status": "unavailable"},
                    "evidence_notes": [],
                }
            ],
            "warnings": [],
        }

    r = _make_result_for_holdings_briefing(tmp_path, _leaky_qty10_evidence)
    assert r.diagnostics["private_fields_exposed"] is True
