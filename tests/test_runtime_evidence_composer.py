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
    result = compose_runtime_evidence(
        "spike_or_falling_alert",
        market_db_path=tmp_path / "market_data.sqlite",
        holdings_file=tmp_path / "holdings.json",
        topn_fn=lambda **_: _ok_topn_payload(),
    )
    assert result.available_sources[SRC_UNIVERSE_MOMENTUM] == REASON_NOT_IMPLEMENTED
    assert result.available_sources[SRC_KR_REALTIME] == REASON_EXTERNAL_FETCH_REQUIRED
    assert result.extra_notes == []
    assert result.diagnostics["selection_result_count"] == 0


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
