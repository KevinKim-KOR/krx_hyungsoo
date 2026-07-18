"""Runtime Evidence 오케스트레이터 — compose_runtime_evidence 진입점.

책임 (지시문 §6.1):
- push_kind 에 따른 source composer 선택.
- source 결과 병합 (available_sources · extra_notes).
- diagnostics 조립 위임 (diagnostics 모듈).
- 기존 호출자와의 계약 유지 (facade `app.runtime_evidence_composer` 재-export).

담당하지 않음 (§6.1):
- Holdings JSON validation → holdings_composer.py.
- 개별 Holdings evidence 판정 → holdings_evidence.py.
- NAV row 해석 → nav_evidence.py.
- privacy token 정의 · 탐지 → privacy.py.
- diagnostics 세부 집계 → diagnostics.py.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Optional

from app import holdings as _holdings_mod
from app.holdings import Holding, load as _holdings_load
from app.holdings_market_evidence import (
    build_holdings_market_evidence as _build_holdings_market_evidence,
)
from app.market_data_store import DEFAULT_DB_PATH as _MARKET_DB_DEFAULT
from app.market_topn import compute_topn as _compute_topn
from app.etf_nav_store import fetch_latest_nav as _fetch_latest_nav

from app.runtime_evidence.constants import (
    REASON_EXTERNAL_FETCH_REQUIRED,
    REASON_NOT_IMPLEMENTED,
    RuntimeEvidenceResult,
    SRC_HOLDINGS,
    SRC_KR_REALTIME,
    SRC_MARKET_DISCOVERY,
    SRC_ML_BASELINE,
    SRC_NAV_DISCOUNT,
    SRC_NEWS,
    SRC_OVERNIGHT_US,
    SRC_UNIVERSE_MOMENTUM,
)
from app.runtime_evidence.diagnostics import (
    add_holdings_briefing_diagnostics,
    add_spike_alert_diagnostics,
    build_base_diagnostics,
)
from app.runtime_evidence.holdings_composer import compose_holdings_and_nav
from app.runtime_evidence.market_discovery import compose_market_discovery
from app.runtime_evidence.universe_momentum import compose_universe_momentum

_MD_PUSH_KINDS = {"market_briefing"}
_HOLDINGS_PUSH_KINDS = {"holdings_briefing"}
_SPIKE_PUSH_KINDS = {"spike_or_falling_alert"}


def _resolve_market_briefing_sources(
    md_status: str, md_diag: dict[str, Any]
) -> dict[str, str]:
    return {
        SRC_KR_REALTIME: REASON_EXTERNAL_FETCH_REQUIRED,
        SRC_OVERNIGHT_US: REASON_EXTERNAL_FETCH_REQUIRED,
        SRC_MARKET_DISCOVERY: (
            "available"
            if md_status == "available"
            else md_diag.get("reason", "unavailable")
        ),
        SRC_ML_BASELINE: REASON_NOT_IMPLEMENTED,
        SRC_NEWS: REASON_NOT_IMPLEMENTED,
    }


def _resolve_holdings_briefing_sources(
    h_status: str,
    h_diag: dict[str, Any],
    nav_status: str,
    nav_diag: dict[str, Any],
) -> dict[str, str]:
    return {
        SRC_HOLDINGS: (
            "available"
            if h_status == "available"
            else h_diag.get("reason", "unavailable")
        ),
        SRC_KR_REALTIME: REASON_EXTERNAL_FETCH_REQUIRED,
        SRC_NAV_DISCOUNT: (
            "available"
            if nav_status == "available"
            else nav_diag.get("reason", "unavailable")
        ),
        SRC_ML_BASELINE: REASON_NOT_IMPLEMENTED,
    }


def compose_runtime_evidence(
    push_kind: str,
    *,
    market_db_path: Optional[Path] = None,
    holdings_file: Optional[Path] = None,
    holdings_loader: Optional[Callable[[], list[Holding]]] = None,
    topn_fn: Optional[Callable[..., dict]] = None,
    nav_fn: Optional[Callable[..., Any]] = None,
    evidence_fn: Optional[Callable[..., dict[str, Any]]] = None,
    universe_artifact_loader: Optional[Callable[[], Optional[dict[str, Any]]]] = None,
) -> RuntimeEvidenceResult:
    """OCI Runtime + Diagnosis 공통 evidence 조립.

    DI (지시문 Q10): 모든 reader 를 파라미터로 override 가능. default 는 프로덕션.
    """
    market_db = market_db_path or _MARKET_DB_DEFAULT
    # `app.holdings.HOLDINGS_FILE` 를 call time 에 조회 → test monkeypatch 반영.
    hfile = holdings_file or _holdings_mod.HOLDINGS_FILE
    hload = holdings_loader or _holdings_load
    tfn = topn_fn or _compute_topn
    nfn = nav_fn or _fetch_latest_nav
    efn = evidence_fn or _build_holdings_market_evidence

    result = RuntimeEvidenceResult()
    diag_sources: dict[str, Any] = {}

    md_status = "unavailable"
    md_notes: list[str] = []
    md_diag: dict[str, Any] = {"status": "unavailable"}
    if push_kind in _MD_PUSH_KINDS:
        md_status, md_notes, md_diag = compose_market_discovery(tfn, market_db)
        diag_sources[SRC_MARKET_DISCOVERY] = md_diag

    h_status = "unavailable"
    h_notes: list[str] = []
    h_diag: dict[str, Any] = {}
    nav_status = "unavailable"
    nav_notes: list[str] = []
    nav_diag: dict[str, Any] = {}
    if push_kind in _HOLDINGS_PUSH_KINDS:
        (h_status, h_notes, h_diag), (nav_status, nav_notes, nav_diag) = (
            compose_holdings_and_nav(hload, hfile, tfn, market_db, efn, nfn)
        )
        diag_sources[SRC_HOLDINGS] = h_diag
        diag_sources[SRC_NAV_DISCOUNT] = nav_diag

    u_status = "unavailable"
    u_notes: list[str] = []
    u_diag: dict[str, Any] = {}
    if push_kind in _SPIKE_PUSH_KINDS:
        u_status, u_notes, u_diag = compose_universe_momentum(
            artifact_loader=universe_artifact_loader
        )
        diag_sources[SRC_UNIVERSE_MOMENTUM] = u_diag

    if push_kind == "market_briefing":
        result.available_sources = _resolve_market_briefing_sources(md_status, md_diag)
        if md_status == "available":
            result.extra_notes = md_notes
        contentful_fact_count = (
            (md_diag.get("contentful_fact_count", 0) or 0)
            if md_status == "available"
            else 0
        )
        selection_result_count = (
            md_diag.get("candidates_count", 0) if md_status == "available" else 0
        )
    elif push_kind == "holdings_briefing":
        result.available_sources = _resolve_holdings_briefing_sources(
            h_status, h_diag, nav_status, nav_diag
        )
        combined_notes: list[str] = []
        if h_status == "available":
            combined_notes.extend(h_notes)
        if nav_status == "available":
            combined_notes.extend(nav_notes)
        result.extra_notes = combined_notes
        contentful_fact_count = (
            (h_diag.get("contentful_fact_count", 0) or 0)
            if h_status == "available"
            else 0
        ) + (
            (nav_diag.get("contentful_fact_count", 0) or 0)
            if nav_status == "available"
            else 0
        )
        selection_result_count = (
            h_diag.get("matched_evidence_count", 0) if h_status == "available" else 0
        )
    elif push_kind == "spike_or_falling_alert":
        result.available_sources = {
            SRC_UNIVERSE_MOMENTUM: (
                "available"
                if u_status == "available"
                else (u_diag.get("universe_snapshot_reason") or "unavailable")
            ),
            SRC_KR_REALTIME: REASON_EXTERNAL_FETCH_REQUIRED,
        }
        result.extra_notes = u_notes if u_status == "available" else []
        contentful_fact_count = int(
            u_diag.get("universe_contentful_fact_count", 0) or 0
        )
        selection_result_count = int(u_diag.get("universe_selected_count", 0) or 0)
    else:
        result.available_sources = {}
        result.extra_notes = []
        contentful_fact_count = 0
        selection_result_count = 0

    result.diagnostics = build_base_diagnostics(
        push_kind,
        result.available_sources,
        diag_sources,
        contentful_fact_count,
        selection_result_count,
    )
    if push_kind == "holdings_briefing":
        add_holdings_briefing_diagnostics(result.diagnostics, diag_sources)
    if push_kind == "spike_or_falling_alert":
        add_spike_alert_diagnostics(
            result.diagnostics, diag_sources, result.extra_notes
        )

    return result
