"""POC2 3-PUSH Runtime Package PC 검증 — runtime_package 빌더 (2026-06-13).

지시문 §4 / §6 / §9 — three_push_runtime_package.v1 구조 빌더. PC 단계에서
pc_evidence_snapshot + runtime_snapshot + push_context + message_contract +
safety_guards + generation_status 를 결합한 dict 를 반환한다.

본 모듈 정책:
- 외부 source 호출 0건 — 호출자가 evidence / runtime 결과를 주입.
- 산식 변경 0건 — 기존 builder 결과를 dict 형태로 그대로 포함.
- push_kind 별로 필수 evidence / runtime 항목 차이를 generation_status 에 반영.
- fake 값 0건 — 사용 불가 항목은 비어있는 dict / status="unavailable" 명시.

본 모듈은 message_text 를 직접 생성하지 않는다 — 기존
`message_market_briefing` / `message_spike_alert` / `draft_message`
빌더가 별도로 message_text 를 만든다. 본 모듈은 그 결과를
message_contract.message_text 에 채워주는 역할만 한다.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "three_push_runtime_package.v1"
SOURCE_MODE_PC_TEST = "pc_test"
TIMEZONE_KST = "Asia/Seoul"
ALLOWED_PUSH_KINDS = ("market_briefing", "holdings_briefing", "spike_or_falling_alert")

# push_kind 별 필수 evidence / runtime 항목.
REQUIRED_EVIDENCE_BY_KIND: dict[str, tuple[str, ...]] = {
    "market_briefing": ("market_discovery_snapshot", "data_quality_snapshot"),
    "holdings_briefing": ("holdings_snapshot",),
    "spike_or_falling_alert": (),  # universe_momentum 또는 kr_realtime 중 하나면 충족.
}


def _new_package_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"three-push-{stamp}-{uuid4().hex[:6]}"


def _empty_evidence_snapshot() -> dict[str, Any]:
    return {
        "holdings_snapshot": {},
        "market_discovery_snapshot": {},
        "ml_baseline_snapshot": {},
        "universe_momentum_snapshot": {},
        "nav_discount_snapshot": {},
        "data_quality_snapshot": {},
    }


def _empty_runtime_snapshot() -> dict[str, Any]:
    return {
        "captured_at": None,
        "kr_realtime_price_snapshot": {},
        "overnight_us_market_snapshot": {},
        "news_snapshot": {"status": "unavailable", "items": []},
    }


def _has_data(snapshot: Any) -> bool:
    """evidence/runtime snapshot dict 가 의미 있는 데이터를 갖고 있는지."""
    if not isinstance(snapshot, dict) or not snapshot:
        return False
    # status="unavailable" 또는 "failed" 만 있으면 빈 것으로 간주 (단 필수 확인 시).
    status = snapshot.get("status")
    if status in ("unavailable", "failed", None):
        # 비어있는 dict 와 status=ok 가 없는 경우 fallback —  key 가 1개라도 있으면 truthy.
        if status in ("unavailable", "failed"):
            return False
    return True


def _check_market_briefing_requirements(
    evidence: dict[str, Any],
) -> tuple[bool, list[str]]:
    missing = []
    md = evidence.get("market_discovery_snapshot")
    if not _has_data(md):
        missing.append("market_discovery_snapshot")
    dq = evidence.get("data_quality_snapshot")
    if not isinstance(dq, dict) or not dq:
        # data_quality 는 비어있어도 dict 형태가 있으면 OK (warnings/errors 빈 배열).
        missing.append("data_quality_snapshot")
    return len(missing) == 0, missing


def _check_holdings_briefing_requirements(
    evidence: dict[str, Any], push_context: dict[str, Any]
) -> tuple[bool, list[str]]:
    """지시문 §7.2 — holdings_snapshot + (market_view 또는 market_discovery_snapshot)."""
    missing: list[str] = []
    if not _has_data(evidence.get("holdings_snapshot")):
        missing.append("holdings_snapshot")
    has_market_view = isinstance(push_context.get("market_view"), dict) and bool(
        push_context.get("market_view")
    )
    has_market_discovery = _has_data(evidence.get("market_discovery_snapshot"))
    if not (has_market_view or has_market_discovery):
        missing.append("market_view or market_discovery_snapshot")
    return len(missing) == 0, missing


def _check_spike_alert_requirements(
    evidence: dict[str, Any], runtime: dict[str, Any]
) -> tuple[bool, list[str]]:
    """universe_momentum 또는 kr_realtime 중 하나면 충족."""
    um = evidence.get("universe_momentum_snapshot")
    kr = runtime.get("kr_realtime_price_snapshot")
    if _has_data(um):
        return True, []
    if isinstance(kr, dict) and kr.get("status") in ("ok", "partial"):
        return True, []
    return False, ["universe_momentum_snapshot or kr_realtime_price_snapshot"]


def _evaluate_generation_status(
    *,
    push_kind: str,
    pc_evidence: dict[str, Any],
    runtime_snapshot: dict[str, Any],
    push_context: dict[str, Any],
) -> dict[str, Any]:
    """push_kind 별 필수 evidence / runtime / push_context 확인 후 generation_status 산정."""
    warnings: list[str] = []
    missing_sections: list[str] = []

    if push_kind == "market_briefing":
        ok, missing = _check_market_briefing_requirements(pc_evidence)
        missing_sections.extend(missing)
    elif push_kind == "holdings_briefing":
        ok, missing = _check_holdings_briefing_requirements(pc_evidence, push_context)
        missing_sections.extend(missing)
    elif push_kind == "spike_or_falling_alert":
        ok, missing = _check_spike_alert_requirements(pc_evidence, runtime_snapshot)
        missing_sections.extend(missing)
    else:
        return {
            "status": "failed",
            "missing_sections": [f"unsupported push_kind: {push_kind}"],
            "warnings": [],
            "errors": [f"unsupported push_kind: {push_kind}"],
        }

    # runtime snapshot 부분 실패 / 미수행은 warning (FIX r3 — unavailable 도 정상
    # 으로 통과시키지 않는다, 검증자 2차 NOTES A-1).
    us = runtime_snapshot.get("overnight_us_market_snapshot")
    if isinstance(us, dict):
        us_status = us.get("status")
        if us_status in ("failed", "partial", "unavailable"):
            warnings.append(f"overnight_us_market_snapshot={us_status}")
    kr = runtime_snapshot.get("kr_realtime_price_snapshot")
    if isinstance(kr, dict):
        kr_status = kr.get("status")
        if kr_status in ("failed", "partial", "unavailable"):
            warnings.append(f"kr_realtime_price_snapshot={kr_status}")

    if not ok:
        return {
            "status": "failed",
            "missing_sections": missing_sections,
            "warnings": warnings,
            "errors": [],
        }
    if warnings:
        return {
            "status": "partial",
            "missing_sections": missing_sections,
            "warnings": warnings,
            "errors": [],
        }
    return {
        "status": "ok",
        "missing_sections": [],
        "warnings": [],
        "errors": [],
    }


def _safety_guards() -> dict[str, bool]:
    """계약 §11 안전 가드 — PC 테스트 모드 고정 값."""
    return {
        "requires_pc_approval_for_test_send": True,
        "allow_unapproved_delivery": False,
        "frontend_may_build_message_text": False,
        "telegram_direct_call_from_pc": False,
        "oci_consumer_contract_required": True,
        "actual_send_allowed_in_tests": False,
    }


def _message_contract(message_text: str) -> dict[str, Any]:
    return {
        "max_length": 3500,
        "language": "ko",
        "sections": [
            "title",
            "summary",
            "key_observations",
            "review_points",
            "limitations",
        ],
        "forbidden_content": [
            "raw_json",
            "token",
            "chat_id",
            "buy_order",
            "sell_order",
            "cash_allocation_instruction",
            "regime_confirmation",
            "risk_threshold_confirmation",
        ],
        "message_text": message_text or "",
    }


def build_runtime_package(
    *,
    push_kind: str,
    message_text: str,
    pc_evidence_snapshot: Optional[dict[str, Any]] = None,
    runtime_snapshot: Optional[dict[str, Any]] = None,
    push_context: Optional[dict[str, Any]] = None,
    data_cutoff: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """three_push_runtime_package.v1 구조 dict 빌더.

    호출자 책임:
    - pc_evidence_snapshot: 기존 evidence builder 결과 dict (없으면 빈 dict).
    - runtime_snapshot: probe 결과 (없으면 빈 dict).
    - push_context: push_kind 별 중간 관찰 구조 (없으면 빈 dict — message_text
      는 기존 빌더가 만든 것을 그대로 message_contract.message_text 로 둔다).
    - message_text: 기존 message_text 빌더 결과. 본 모듈은 만들지 않는다.

    반환 dict 는 draft_payload.runtime_package 에 그대로 저장된다.
    """
    if push_kind not in ALLOWED_PUSH_KINDS:
        # 알 수 없는 push_kind 도 거부하지 않고 generation_status=failed 로 노출.
        logger.warning("build_runtime_package: 알 수 없는 push_kind=%s", push_kind)

    evidence = pc_evidence_snapshot or _empty_evidence_snapshot()
    # 빠진 key 는 빈 dict 로 채움 (계약 §7 형식 유지).
    for k in _empty_evidence_snapshot().keys():
        evidence.setdefault(k, {})

    runtime = runtime_snapshot or _empty_runtime_snapshot()
    for k, v in _empty_runtime_snapshot().items():
        runtime.setdefault(k, v)

    generation_status = _evaluate_generation_status(
        push_kind=push_kind,
        pc_evidence=evidence,
        runtime_snapshot=runtime,
        push_context=push_context or {},
    )

    # FIX r3 — 검증자 2차 NOTES A-1 (3): generation_status=failed 인 package 의
    # message_contract.message_text 는 빈 문자열로 강제. "failed 인데 정상 발송
    # 본문이 들어있다" 는 계약 문서 §12 위반 상태를 차단. Run.message_text 는
    # 별도 — preview UI 가 generation_status 와 함께 보고 판단한다.
    effective_message_text = (
        "" if generation_status["status"] == "failed" else message_text
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "package_id": _new_package_id(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "asof_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "timezone": TIMEZONE_KST,
        "source_mode": SOURCE_MODE_PC_TEST,
        "push_kind": push_kind,
        "data_cutoff": data_cutoff
        or {
            "kr_market_asof": None,
            "ml_feature_asof": None,
            "market_discovery_asof": None,
            "holdings_asof": None,
            "runtime_snapshot_at": runtime.get("captured_at"),
        },
        "pc_evidence_snapshot": evidence,
        "runtime_snapshot": runtime,
        "push_context": push_context or {},
        "message_contract": _message_contract(effective_message_text),
        "safety_guards": _safety_guards(),
        "generation_status": generation_status,
    }
