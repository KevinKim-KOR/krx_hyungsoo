"""evidence·본문 조립 및 발송 성공 기록 (KS-10 분리 · 2026-09-07).

`run_three_push_runtime_oci.py` 가 650줄 임계를 넘어 **기계적으로 분리**한 두
블록이다. 판정 로직 변경 0건 — 실패는 튜플로 돌려주고 러너가 `_finish(*fail)`
한다.

보유 브리핑·보유 위험 알림은 §3-c/§3-d 에서 본문을 이미 만들었으므로 이 경로를
타지 않는다(면책 문구 부착 경로 제외 — 설계자 확정).
"""

from __future__ import annotations

from typing import Any, Optional

SKIP_EVIDENCE_KINDS = ("holdings_briefing", "holdings_risk_alert")


def compose_evidence_and_message(
    record: dict[str, Any],
    *,
    push_kind: str,
    param: Any,
    runtime_kst: Optional[str],
    market_quotes: Optional[dict[str, Any]],
    reeval_fn: Any,
    compose_runtime_evidence: Any,
    build_runtime_message: Any,
    availability_summary: Any,
    logger: Any,
) -> tuple[Optional[tuple[str, str, str]], Any, Optional[str]]:
    """러너 §4 / §4-b. 반환 `(실패|None, evidence, message_text|None)`.

    `message_text` 가 None 이면 러너가 기존 본문을 유지한다.
    """
    try:
        evidence = compose_runtime_evidence(
            push_kind,
            market_quotes=(market_quotes or None),
            universe_reevaluate_fn=reeval_fn,
        )
    except Exception as e:  # noqa: BLE001
        logger.error("runtime evidence 조립 실패: %s", e)
        return ("failed", "runtime_evidence_error", str(e)[:400]), None, None

    try:
        message_text = build_runtime_message(
            push_kind=push_kind,
            param=param,
            runtime_kst_iso=runtime_kst,
            available_sources=evidence.available_sources,
            extra_notes=evidence.extra_notes,
        )
    except Exception as e:  # noqa: BLE001
        logger.error("runtime message 생성 실패: %s", e)
        return ("failed", "runtime_message_build_error", str(e)[:400]), evidence, None

    record["message_text_length"] = len(message_text)
    record["availability"] = availability_summary(evidence.available_sources)
    # 지시문 §9: record 에 diagnostics summary 추가.
    record["contentful_fact_count"] = evidence.diagnostics.get(
        "contentful_fact_count", 0
    )
    record["selection_result_count"] = evidence.diagnostics.get(
        "selection_result_count", 0
    )
    record["unavailable_reasons"] = evidence.diagnostics.get("unavailable_reasons", {})
    return None, evidence, message_text


def record_send_success(
    record: dict[str, Any],
    *,
    push_kind: str,
    param: Any,
    runtime_date_kst: str,
    runtime_kst: Optional[str],
    registry_date_field: Optional[str],
    partial_delivery: bool,
    holdings_selection_ctx: Optional[dict[str, Any]],
    sent_at: str,
    resolve_registry_date_field: Any,
    mark_sent: Any,
    save_state: Any,
    save_risk_state: Any,
    holdings_state_path: Any,
    risk_state_path: Any,
) -> None:
    """러너 §8 발송 성공 이후 기록. **여기 도달 = Telegram 발송 성공**이다."""
    if push_kind == "spike_or_falling_alert":
        # 발송 성공 시 신규 fingerprint 각각 registry entry 기록.
        for fp in record.get("spike_new_fingerprints", []):
            mark_sent(
                push_kind=push_kind,
                param_id=param.param_id,
                runtime_date_kst=resolve_registry_date_field(
                    runtime_date_kst, signal_fingerprint=fp
                ),
                sent_at_utc=sent_at,
            )
    else:
        mark_sent(
            push_kind=push_kind,
            param_id=param.param_id,
            runtime_date_kst=registry_date_field,
            sent_at_utc=sent_at,
        )

    # POC3-OPS-01A · PLAN §4.6 — **전체 발송 성공 이후에만** 선정 상태 확정.
    # 부분·전체 실패면 이 줄에 도달하지 않아 이전 상태가 유지되고, 다음 슬롯에서
    # 같은 변화를 다시 시도한다. 미발송 신호가 발송 완료로 기록되면 안 된다.
    if not holdings_selection_ctx or partial_delivery:
        return
    risk = holdings_selection_ctx.get("risk")
    if risk is not None:
        # OPS-02A — 그날 도달한 최악 구간. **전체 발송 성공 뒤에만** 저장.
        save_risk_state(
            risk_state_path,
            entries=risk.save_entries or {},
            today_kst=risk.today_kst or runtime_date_kst,
            runtime_kst=runtime_kst,
        )
        record["holdings_risk_state_saved"] = True
    else:
        save_state(
            holdings_state_path,
            selected=holdings_selection_ctx["selected"],
            slot_id=holdings_selection_ctx.get("slot_id"),
        )
        record["holdings_selection_state_saved"] = True
