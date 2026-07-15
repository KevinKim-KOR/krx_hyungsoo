"""Holdings + NAV source 조립기.

Cleanup / FIX r7 Round 2 정정: orchestrator (composer.py) 는 push_kind 라우팅만
담당하고, 실제 Holdings/NAV 조립은 이 모듈이 담당한다. 지시문 §6.1 준수.

책임:
- Holdings 파일 부재 / load 오류 / 빈 holdings 조기 반환 처리.
- Holdings × Market evidence payload 조회 (build_holdings_market_evidence 사용).
- TOP-N reader 성공 판정 위임 (holdings_evidence.signal_topn_reader_failed).
- Holdings evidence fact 생성 위임 (holdings_evidence.build_holdings_facts).
- NAV row 해석 위임 (nav_evidence.build_nav_facts).
- Privacy 탐지 위임 (privacy.detect_*).
- diagnostics 필드 값을 각 helper 가 반환한 카운터로 채운다 (세부 집계 로직 X).

이 모듈은 다음을 하지 않는다 (§6.1):
- 개별 Holdings evidence 판정 알고리즘 (→ holdings_evidence.py).
- NAV row 해석 세부 (→ nav_evidence.py).
- privacy token 정의 · 탐지 알고리즘 (→ privacy.py).
- diagnostics 최종 조립 (→ diagnostics.py).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from app.holdings import Holding, HoldingsValidationError
from app.holdings_market_evidence import get_holdings_file_mtime_iso

from app.runtime_evidence.constants import (
    REASON_NAV_UNAVAILABLE,
    REASON_NO_CONTENTFUL_FACT,
    REASON_SOURCE_MISSING_HOLDINGS,
)
from app.runtime_evidence.holdings_evidence import (
    build_holdings_facts,
    signal_topn_reader_failed,
)
from app.runtime_evidence.nav_evidence import build_nav_facts
from app.runtime_evidence.privacy_detector import (
    detect_private_values_exposed,
    detect_raw_identifier_exposed,
)


def _set_privacy_defaults(diag: dict[str, Any]) -> None:
    """조기 반환 경로 diagnostics 에 boolean 기본값 세팅."""
    diag["private_fields_exposed"] = False
    diag["raw_identifier_exposed"] = False
    diag.setdefault("holdings_loaded_count", 0)
    diag.setdefault("holdings_evidence_item_count", 0)
    diag.setdefault("holdings_contentful_fact_count", 0)
    diag.setdefault("holdings_selection_result_count", 0)
    diag.setdefault("rendered_holdings_fact_count", 0)


def _early_return_source_missing() -> tuple[
    tuple[str, list[str], dict[str, Any]],
    tuple[str, list[str], dict[str, Any]],
]:
    h = {
        "status": "unavailable",
        "source_present": False,
        "reason": REASON_SOURCE_MISSING_HOLDINGS,
    }
    nav = {
        "status": "unavailable",
        "asof": None,
        "matched_count": 0,
        "reason": REASON_SOURCE_MISSING_HOLDINGS,
    }
    _set_privacy_defaults(h)
    return ("unavailable", [], h), ("unavailable", [], nav)


def _early_return_load_error(exc_name: str) -> tuple[
    tuple[str, list[str], dict[str, Any]],
    tuple[str, list[str], dict[str, Any]],
]:
    h = {
        "status": "unavailable",
        "source_present": True,
        "reason": f"holdings_load_error:{exc_name}",
    }
    nav = {
        "status": "unavailable",
        "asof": None,
        "matched_count": 0,
        "reason": "holdings_load_error",
    }
    _set_privacy_defaults(h)
    return ("unavailable", [], h), ("unavailable", [], nav)


def _early_return_empty_holdings() -> tuple[
    tuple[str, list[str], dict[str, Any]],
    tuple[str, list[str], dict[str, Any]],
]:
    h = {
        "status": "unavailable",
        "source_present": True,
        "reason": "holdings_empty",
        "holdings_count": 0,
    }
    nav = {
        "status": "unavailable",
        "asof": None,
        "matched_count": 0,
        "reason": "holdings_empty",
    }
    _set_privacy_defaults(h)
    return ("unavailable", [], h), ("unavailable", [], nav)


def _build_holdings_status_and_diag(
    holdings: list[Holding],
    evidence_payload: dict[str, Any],
) -> tuple[str, list[str], dict[str, Any]]:
    """Holdings evidence 판정 + diagnostics 채우기 (privacy 검사 포함)."""
    market_asof = evidence_payload.get("market_asof")
    diag: dict[str, Any] = {
        "source_present": True,
        "asof": market_asof,
        "market_asof": market_asof,
        "holdings_count": len(holdings),
    }

    topn_reader_failed = signal_topn_reader_failed(evidence_payload)

    if not market_asof or topn_reader_failed:
        diag["status"] = "unavailable"
        diag["reason"] = (
            "holdings_market_asof_missing" if not market_asof else "topn_query_failed"
        )
        notes: list[str] = []
        counters = {
            "holdings_evidence_item_count": 0,
            "holdings_selection_result_count": 0,
            "holdings_contentful_fact_count": 0,
        }
    else:
        notes, counters = build_holdings_facts(evidence_payload, market_asof)
        if counters["holdings_contentful_fact_count"] == 0:
            diag["status"] = "unavailable"
            diag["reason"] = REASON_NO_CONTENTFUL_FACT
        else:
            diag["status"] = "available"
            diag["contentful_fact_count"] = counters["holdings_contentful_fact_count"]
            diag["matched_evidence_count"] = counters["holdings_selection_result_count"]

    # 진단 카운터 (설계자 확정본 Q7).
    diag["holdings_loaded_count"] = len(holdings)
    diag["holdings_evidence_item_count"] = counters["holdings_evidence_item_count"]
    diag["holdings_contentful_fact_count"] = counters["holdings_contentful_fact_count"]
    diag["holdings_selection_result_count"] = counters[
        "holdings_selection_result_count"
    ]
    diag["rendered_holdings_fact_count"] = counters["holdings_contentful_fact_count"]
    # Privacy 진단 boolean (전용 detector 위임).
    diag["private_fields_exposed"] = detect_private_values_exposed(
        holdings, notes, evidence_payload=evidence_payload
    )
    diag["raw_identifier_exposed"] = detect_raw_identifier_exposed(notes)

    status = (
        "available" if counters["holdings_contentful_fact_count"] > 0 else "unavailable"
    )
    return status, notes, diag


def _build_nav_status_and_diag(
    holdings: list[Holding],
    nav_fn: Callable[..., Any],
    market_db_path: Path,
) -> tuple[str, list[str], dict[str, Any]]:
    """NAV evidence 판정 + diagnostics 채우기."""
    notes, fact_count, asof_latest, matched_count = build_nav_facts(
        holdings, nav_fn, market_db_path
    )
    diag: dict[str, Any] = {
        "matched_count": matched_count,
        "asof": asof_latest,
        "nav_contentful_fact_count": fact_count,
    }
    if fact_count == 0:
        diag["status"] = "unavailable"
        diag["reason"] = REASON_NAV_UNAVAILABLE
        return "unavailable", [], diag
    diag["status"] = "available"
    diag["contentful_fact_count"] = fact_count
    return "available", notes, diag


def compose_holdings_and_nav(
    holdings_loader: Callable[[], list[Holding]],
    holdings_file: Path,
    topn_fn: Callable[..., dict],
    market_db_path: Path,
    evidence_fn: Callable[..., dict[str, Any]],
    nav_fn: Callable[..., Any],
) -> tuple[
    tuple[str, list[str], dict[str, Any]],
    tuple[str, list[str], dict[str, Any]],
]:
    """Holdings + NAV source 조립. orchestrator 로부터 호출된다.

    returns ((holdings_status, holdings_notes, holdings_diag),
             (nav_status, nav_notes, nav_diag)).
    """
    # 조기 반환 3경로 (privacy boolean 기본값 유지).
    if not holdings_file.exists():
        return _early_return_source_missing()
    try:
        holdings = holdings_loader()
    except (HoldingsValidationError, json.JSONDecodeError) as e:
        return _early_return_load_error(type(e).__name__)
    if not holdings:
        return _early_return_empty_holdings()

    # Holdings × Market evidence payload 조회.
    topn_payload = topn_fn(db_path=market_db_path)
    holdings_asof = get_holdings_file_mtime_iso(holdings_file)
    evidence_payload = evidence_fn(
        holdings=holdings,
        topn_payload=topn_payload,
        market_quotes=None,
        db_path=market_db_path,
        holdings_asof=holdings_asof,
    )

    holdings_status, holdings_notes, holdings_diag = _build_holdings_status_and_diag(
        holdings, evidence_payload
    )
    nav_status, nav_notes, nav_diag = _build_nav_status_and_diag(
        holdings, nav_fn, market_db_path
    )
    return (
        (holdings_status, holdings_notes, holdings_diag),
        (nav_status, nav_notes, nav_diag),
    )
