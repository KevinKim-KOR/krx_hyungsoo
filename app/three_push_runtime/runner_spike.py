"""Spike 재평가 진단 전달 (KS-10 분리 · 2026-09-04).

`run_three_push_runtime_oci.py` 가 650줄 임계를 넘어 **기계적으로 분리**한 블록이다.
`return _finish(...)` 은 러너 closure 라 실패 사유를 튜플로 돌려주고 러너가 그대로
`_finish` 에 넘긴다. 판정 로직 변경 0건.

**logger 는 러너 것을 그대로 받는다.** `setup_logging(name)` 은 그 이름의 logger
에만 파일·콘솔 handler 를 붙이므로, 모듈 자체 `getLogger(__name__)` 을 쓰면 분리
전에는 운영 로그 파일에 남던 줄이 사라진다 (검증자 r3 지적). 기계적 분리라면
로그 경로도 같아야 한다.
"""

from __future__ import annotations

from typing import Any, Optional


def apply_spike_reevaluation(
    record: dict[str, Any], evidence: Any, *, logger: Any
) -> Optional[tuple[str, str, Optional[str]]]:
    """Spike 재평가 결과를 record 에 싣는다.

    반환: 실패면 `(status, reason, detail)`, 정상이면 None.
    """
    fps = getattr(evidence, "spike_signal_fingerprints", []) or []
    record["spike_signal_fingerprints"] = fps
    reeval_status = evidence.diagnostics.get("reevaluate_status")
    record["reevaluate_status"] = reeval_status
    record["reevaluate_missing_fields"] = evidence.diagnostics.get(
        "reevaluate_missing_fields", []
    )
    record["reevaluate_quote_missing_tickers"] = evidence.diagnostics.get(
        "reevaluate_quote_missing_tickers", []
    )
    record["reevaluate_candidate_missing_fields"] = evidence.diagnostics.get(
        "reevaluate_candidate_missing_fields", {}
    )
    if reeval_status == "failed":
        return (
            "failed",
            "reevaluate_missing_published_evidence",
            f"missing_fields={record['reevaluate_missing_fields']}",
        )
    if reeval_status == "partial":
        return (
            "failed",
            "reevaluate_partial",
            (
                "quote_missing="
                f"{record['reevaluate_quote_missing_tickers']}"
                " candidate_missing="
                f"{list(record['reevaluate_candidate_missing_fields'].keys())}"
            ),
        )
    return None


def resolve_spike_duplicates(
    record: dict[str, Any],
    evidence: Any,
    *,
    push_kind: str,
    param: Any,
    runtime_date_kst: str,
    runtime_kst: str,
    build_runtime_message: Any,
    resolve_registry_date_field: Any,
    registry_key: Any,
    is_already_sent: Any,
    logger: Any,
) -> tuple[Optional[tuple[str, str, Optional[str]]], Optional[str]]:
    """Spike fingerprint 별 중복 판정 + 신규분만으로 body 재조립.

    반환: `(실패튜플|None, 재조립된 message_text|None)`.

    실패튜플 3번째 원소는 `_finish(status, reason, error)` 의 `error` 로 그대로
    들어간다. **중복 skip 은 분리 전과 같이 `error=None`** 이어야 한다 — 빈
    문자열을 넣으면 record 계약이 달라진다(검증자 A-3 지적).
    러너의 `_finish` closure 대신 실패 사유를 튜플로 돌려준다. 판정 로직 변경 0건.
    """
    _resolve_registry_date_field = resolve_registry_date_field
    _registry_key = registry_key
    fps_all = record.get("spike_signal_fingerprints") or []
    new_fps: list[str] = []
    already_fps: list[str] = []
    for fp in fps_all:
        date_field = _resolve_registry_date_field(
            runtime_date_kst, signal_fingerprint=fp
        )
        try:
            if is_already_sent(push_kind, param.param_id, date_field):
                already_fps.append(fp)
            else:
                new_fps.append(fp)
        except Exception as e:
            logger.error("registry DB 접근 실패 (fp=%s): %s", fp, e)
            return ("failed", "registry_corrupted", str(e)[:400]), None
    record["spike_new_fingerprints"] = new_fps
    record["spike_already_sent_fingerprints"] = already_fps
    record["duplicate_key"] = (
        _registry_key(
            push_kind,
            param.param_id,
            runtime_date_kst,
            signal_fingerprint=new_fps[0],
        )
        if new_fps
        else ""
    )
    if not new_fps:
        logger.info(
            "중복 발송 차단: 신규 fingerprint 없음 (already_fps=%d)",
            len(already_fps),
        )
        return ("skipped", "duplicate_runtime", None), None
    # A+ 재정정 (B): 혼합 신호 시 body 를 신규 fp 만으로 재조립. 기발송 신호가
    # 본문에 포함되어 재발송되는 문제 해소. length mismatch 는 composer 계약
    # 위반이므로 즉시 failed.
    from app.three_push_runtime.spike_body import (
        filter_extra_notes_to_new_signals,
    )

    try:
        filtered_notes = filter_extra_notes_to_new_signals(
            evidence.extra_notes, fps_all, new_fps
        )
    except ValueError as e:
        logger.error("spike body 재조립 계약 위반: %s", e)
        return ("failed", "spike_body_contract_error", str(e)[:400]), None
    try:
        message_text = build_runtime_message(
            push_kind=push_kind,
            param=param,
            runtime_kst_iso=runtime_kst,
            available_sources=evidence.available_sources,
            extra_notes=filtered_notes,
        )
    except Exception as e:  # format_spike_signal_note 등의 재-빌드 예외
        logger.error("runtime message 재조립 실패: %s", e)
        return ("failed", "runtime_message_build_error", str(e)[:400]), None
    record["message_text_length"] = len(message_text)
    return None, message_text
