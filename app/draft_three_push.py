"""POC2 3-PUSH Message Contract — PUSH-1 / PUSH-3 draft entry 분리 모듈.

지시문 §4.2 / §4.4 / §10. 본 모듈은 draft.py 의 KS-10 책임 집중을 분리하기 위해
PUSH-1 / PUSH-3 전용 draft entry 와 evidence loader 를 모았다 (FIX r3 — 검증자
B-2 / B-3 수용).

본 모듈이 담당하는 책임:
- generate_market_briefing_draft (PUSH-1 builder 호출 + Run 생성).
- generate_spike_alert_draft (PUSH-3 builder 호출 + Run 생성).
- generate_market_briefing_via_generic / generate_spike_alert_via_generic —
  POST /runs/generate 의 input_data.push_kind 분기로 들어왔을 때 read-only
  evidence 를 로드해 위 함수로 위임 (별도 PUSH endpoint 신설 금지 §3 / §11
  준수).
- _load_universe_artifact_for_spike — universe_momentum_latest.json 의 부재
  (정상) 와 손상 (이상) 을 logger 로 구분 (검증자 B-1 의심 해소).

본 모듈은 절대 하지 않는 것:
- 외부 source 호출 / Telegram 직접 호출 / 신규 PUSH endpoint 신설.
- ML 산식 변경 / baseline scoring 변경 / 매수·매도 / 현금비중 / 위험 threshold.

draft.py 의 generate_draft 는 본 모듈의 generate_*_via_generic 함수를 동적 import
로 호출 (circular import 회피).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from app import store
from app.models import Run
from app.momentum import LATEST_ARTIFACT_FILE as UNIVERSE_LATEST_FILE
from app.push_context import build_push_context
from app.runtime_package import build_runtime_package
from app.runtime_probe_cache import get_runtime_probe_snapshot

logger = logging.getLogger(__name__)

# PUSH-1/3 PC test probe 대상 ticker (Q2 — holdings/benchmark/spike 후보).
# 기본 benchmark ETF: KODEX 200 (069500), KODEX 코스닥150 (229200).
# holdings 종목은 PUSH-2 흐름에서 별도 주입되며, PUSH-1/3 은 benchmark 만 시도.
PUSH13_DEFAULT_KR_TICKERS: tuple[str, ...] = ("069500", "229200")


def _new_run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"run_{stamp}_{uuid4().hex[:8]}"


def _build_market_briefing_evidence(
    *,
    ml_baseline_snapshot: Optional[dict[str, Any]],
    topn_payload: Optional[dict[str, Any]],
) -> dict[str, Any]:
    """PUSH-1 evidence dict — market_discovery + ml_baseline + data_quality 채움."""
    return {
        "holdings_snapshot": {},
        "market_discovery_snapshot": topn_payload or {},
        "ml_baseline_snapshot": ml_baseline_snapshot or {},
        "universe_momentum_snapshot": {},
        "nav_discount_snapshot": {},
        "data_quality_snapshot": {
            "asof_date": (topn_payload or {}).get("asof") or "",
            "warnings": [],
            "errors": [],
            "stale_sources": [],
            "unavailable_sources": [],
        },
    }


def _build_spike_alert_evidence(
    *,
    topn_payload: Optional[dict[str, Any]],
    universe_artifact: Optional[dict[str, Any]],
) -> dict[str, Any]:
    """PUSH-3 evidence dict — universe_momentum + market_discovery 채움."""
    return {
        "holdings_snapshot": {},
        "market_discovery_snapshot": topn_payload or {},
        "ml_baseline_snapshot": {},
        "universe_momentum_snapshot": universe_artifact or {},
        "nav_discount_snapshot": {},
        "data_quality_snapshot": {
            "asof_date": (topn_payload or {}).get("asof") or "",
            "warnings": [],
            "errors": [],
            "stale_sources": [],
            "unavailable_sources": [],
        },
    }


def _runtime_snapshot_with_cache(kr_tickers: list[str]) -> dict[str, Any]:
    """cache-aware runtime probe — 호출자가 ticker 주입. 외부 호출 timeout 격리.

    cache 손상 / 네트워크 timeout 만 흡수 (원인 보존: logger.warning 에 예외 타입
    명시). 그 외 예외 (코드 결함 등) 는 호출자에게 전파.
    """
    try:
        return get_runtime_probe_snapshot(kr_tickers=kr_tickers)
    except (OSError, TimeoutError) as e:
        logger.warning(
            "runtime probe I/O 실패 (%s): %s — unavailable snapshot 대체",
            type(e).__name__,
            e,
        )
        from app.runtime_kr_quote_probe import (
            empty_unavailable_snapshot as _kr_empty,
        )
        from app.runtime_us_indices_probe import (
            empty_unavailable_snapshot as _us_empty,
        )

        return {
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "kr_realtime_price_snapshot": _kr_empty(f"{type(e).__name__}: {e}"),
            "overnight_us_market_snapshot": _us_empty(f"{type(e).__name__}: {e}"),
            "cache_status": "miss",
        }


def generate_market_briefing_draft(
    *,
    ml_baseline_snapshot: Optional[dict[str, Any]] = None,
    topn_payload: Optional[dict[str, Any]] = None,
) -> Run:
    """PUSH-1 시장 흐름 브리핑 Run 생성 (지시문 §4.2).

    외부 fetch 0건 — 호출자가 read-only artifact / 정규화 evidence 를 주입.
    push_kind="market_briefing" 명시. delivery / OCI consumer 는 push_kind 를
    읽지 않으며 message_text 만 그대로 발송한다 (단일 소스 유지).
    """
    from app.message_market_briefing import (
        PUSH_KIND as MARKET_BRIEFING_KIND,
    )
    from app.message_market_briefing import (
        build_market_briefing_message,
    )

    run_id = _new_run_id()
    asof = datetime.now(timezone.utc).isoformat()

    # 3-PUSH Runtime Package PC 검증 (2026-06-13) — 입력 흐름 정렬:
    #   evidence + runtime → push_context → message_text → runtime_package.
    runtime_snapshot = _runtime_snapshot_with_cache(list(PUSH13_DEFAULT_KR_TICKERS))
    pc_evidence = _build_market_briefing_evidence(
        ml_baseline_snapshot=ml_baseline_snapshot, topn_payload=topn_payload
    )
    push_context = build_push_context(
        push_kind=MARKET_BRIEFING_KIND,
        pc_evidence=pc_evidence,
        runtime_snapshot=runtime_snapshot,
    )
    from app.push_user_copy import collect_unavailable_source_keys

    unavail_keys = collect_unavailable_source_keys(
        push_kind=MARKET_BRIEFING_KIND,
        pc_evidence=pc_evidence,
        runtime_snapshot=runtime_snapshot,
    )
    message_text = build_market_briefing_message(
        asof_iso=asof,
        ml_baseline_snapshot=ml_baseline_snapshot,
        topn_payload=topn_payload,
        push_context=push_context,
        unavailable_source_keys=unavail_keys,
    )
    runtime_package = build_runtime_package(
        push_kind=MARKET_BRIEFING_KIND,
        message_text=message_text,
        pc_evidence_snapshot=pc_evidence,
        runtime_snapshot=runtime_snapshot,
        push_context=push_context,
    )

    # FIX r5 (검증자 4차 NOTES A-1 / B-1 / B-6): runtime_package 가 failed 면
    # Run.message_text 도 None 으로 비운다 — 승인/preview 단일 소스에서도 정상
    # 본문이 보이지 않게 (계약 §12).
    is_failed_package = (runtime_package.get("generation_status") or {}).get(
        "status"
    ) == "failed"

    payload: dict[str, Any] = {
        "title": "시장 흐름 브리핑",
        "asof": asof,
        "push_kind": MARKET_BRIEFING_KIND,
        "note": "PUSH-1: 시장 내부 신호 + 위험 패턴 참고 + 외부 변수 체크리스트.",
        "recommendations": [],
        "runtime_package": runtime_package,
    }
    run = Run(
        run_id=run_id,
        asof=asof,
        status="PENDING_APPROVAL",
        draft_payload=payload,
        message_text=None if is_failed_package else message_text,
        push_kind=MARKET_BRIEFING_KIND,
    )
    store.save(run)
    return run


def generate_spike_alert_draft(
    *,
    topn_payload: Optional[dict[str, Any]] = None,
    universe_artifact: Optional[dict[str, Any]] = None,
) -> Run:
    """PUSH-3 급등락 관찰 신호 Run 생성 (지시문 §4.4).

    외부 fetch 0건 — 호출자가 compute_topn() 결과 + universe_momentum_latest.json
    artifact 를 read 해 주입. 본 함수는 신규 source 를 호출하지 않는다
    (개별 주식 전체 source 도입 금지 — §4.4).
    """
    from app.message_spike_alert import (
        PUSH_KIND as SPIKE_ALERT_KIND,
    )
    from app.message_spike_alert import (
        build_spike_alert_message,
    )

    run_id = _new_run_id()
    asof = datetime.now(timezone.utc).isoformat()

    # 3-PUSH Runtime Package PC 검증 (2026-06-13) — 입력 흐름 정렬:
    #   evidence + runtime → push_context → message_text → runtime_package.
    runtime_snapshot = _runtime_snapshot_with_cache(list(PUSH13_DEFAULT_KR_TICKERS))
    pc_evidence = _build_spike_alert_evidence(
        topn_payload=topn_payload, universe_artifact=universe_artifact
    )
    push_context = build_push_context(
        push_kind=SPIKE_ALERT_KIND,
        pc_evidence=pc_evidence,
        runtime_snapshot=runtime_snapshot,
    )
    from app.push_user_copy import collect_unavailable_source_keys

    unavail_keys = collect_unavailable_source_keys(
        push_kind=SPIKE_ALERT_KIND,
        pc_evidence=pc_evidence,
        runtime_snapshot=runtime_snapshot,
    )
    message_text = build_spike_alert_message(
        asof_iso=asof,
        topn_payload=topn_payload,
        universe_artifact=universe_artifact,
        push_context=push_context,
        unavailable_source_keys=unavail_keys,
    )
    runtime_package = build_runtime_package(
        push_kind=SPIKE_ALERT_KIND,
        message_text=message_text,
        pc_evidence_snapshot=pc_evidence,
        runtime_snapshot=runtime_snapshot,
        push_context=push_context,
    )

    # FIX r5 (검증자 4차 NOTES A-1 / B-1 / B-6) — PUSH-1 과 동일 정책.
    is_failed_package = (runtime_package.get("generation_status") or {}).get(
        "status"
    ) == "failed"

    payload: dict[str, Any] = {
        "title": "급등락 관찰 신호",
        "asof": asof,
        "push_kind": SPIKE_ALERT_KIND,
        "note": "PUSH-3: ETF universe 변동성 확대 + 기존 급락 ETF 신호 재사용.",
        "recommendations": [],
        "runtime_package": runtime_package,
    }
    run = Run(
        run_id=run_id,
        asof=asof,
        status="PENDING_APPROVAL",
        draft_payload=payload,
        message_text=None if is_failed_package else message_text,
        push_kind=SPIKE_ALERT_KIND,
    )
    store.save(run)
    return run


def generate_market_briefing_via_generic(input_data: dict[str, Any]) -> Run:
    """POST /runs/generate (push_kind="market_briefing") → PUSH-1 흐름.

    내부에서 read-only evidence loader 를 호출 후 generate_market_briefing_draft
    로 위임. 외부 source 호출 0건 — 저장된 evidence / SQLite read-only.
    """
    from app.market_data_store import DEFAULT_DB_PATH as _MARKET_DB
    from app.market_topn import (
        DEFAULT_BASIS,
        DEFAULT_N,
        DEFAULT_ORDER,
        compute_topn,
    )
    from app.ml_baseline_evidence import build_ml_baseline_evidence_snapshot

    ml_snapshot = build_ml_baseline_evidence_snapshot()
    topn_payload = compute_topn(
        n=DEFAULT_N,
        db_path=_MARKET_DB,
        basis=DEFAULT_BASIS,
        order=DEFAULT_ORDER,
    )
    return generate_market_briefing_draft(
        ml_baseline_snapshot=ml_snapshot,
        topn_payload=topn_payload,
    )


def generate_spike_alert_via_generic(input_data: dict[str, Any]) -> Run:
    """POST /runs/generate (push_kind="spike_or_falling_alert") → PUSH-3 흐름.

    universe_momentum_latest.json read-only 로딩. 손상 / 부재는 logger 로 구분
    (B-1 의심 해소: 손상은 명시 WARNING, 부재는 DEBUG — 정상 흐름).
    """
    from app.market_data_store import DEFAULT_DB_PATH as _MARKET_DB
    from app.market_topn import (
        DEFAULT_BASIS,
        DEFAULT_N,
        DEFAULT_ORDER,
        compute_topn,
    )

    topn_payload = compute_topn(
        n=DEFAULT_N,
        db_path=_MARKET_DB,
        basis=DEFAULT_BASIS,
        order=DEFAULT_ORDER,
    )
    universe_artifact = _load_universe_artifact_for_spike()
    return generate_spike_alert_draft(
        topn_payload=topn_payload,
        universe_artifact=universe_artifact,
    )


def _load_universe_artifact_for_spike() -> Optional[dict[str, Any]]:
    """universe_momentum_latest.json read-only 로드.

    부재 (정상 미실행 상태) → None 반환, 로깅 DEBUG.
    JSON 손상 → None 반환 + 명시 WARNING (검증자 B-1 의심 해소).
    """
    if not UNIVERSE_LATEST_FILE.exists():
        logger.debug("universe artifact 부재 — PUSH-3 spike 섹션 생략")
        return None
    try:
        text = UNIVERSE_LATEST_FILE.read_text(encoding="utf-8")
        data = json.loads(text)
    except (OSError, json.JSONDecodeError) as e:
        logger.warning(
            "universe artifact 손상 — PUSH-3 본문은 ETF universe 섹션만 사용. "
            "원인: %s",
            e,
        )
        return None
    return data if isinstance(data, dict) else None
