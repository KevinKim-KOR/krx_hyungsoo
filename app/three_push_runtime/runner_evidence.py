"""evidence·본문 조립 및 발송 성공 기록 (KS-10 분리 · 2026-09-07).

`run_three_push_runtime_oci.py` 가 650줄 임계를 넘어 **기계적으로 분리**한 두
블록이다. 판정 로직 변경 0건 — 실패는 튜플로 돌려주고 러너가 `_finish(*fail)`
한다.

보유 브리핑·보유 위험 알림은 §3-c/§3-d 에서 본문을 이미 만들었으므로 이 경로를
타지 않는다(면책 문구 부착 경로 제외 — 설계자 확정).
"""

from __future__ import annotations

from typing import Any, Optional

SKIP_EVIDENCE_KINDS = (
    "holdings_briefing",
    "holdings_risk_alert",
    # POC3-OPS-02B-2 — 시장 브리핑은 §3-e 전용 helper 가 본문을 만든다.
    "market_briefing",
)


def assemble_legacy_evidence(
    record: dict[str, Any],
    *,
    push_kind: str,
    param: Any,
    runtime_kst: Optional[str],
    market_quotes: Optional[dict[str, Any]],
    reeval_fn: Any,
    logger: Any,
    evidence: Any = None,
    message_text: str = "",
    build_runtime_message: Any = None,
) -> tuple[Optional[tuple[str, str, str]], Any, str]:
    """러너 §4 전체 — **구조만 옮겼다. 판정·입출력·예외 동작 동일**.

    POC3-OPS-02B-2 KS-10 Cleanup (2026-09-12). 러너가 650줄을 넘어 이 블록을
    통째로 가져왔다. `SKIP_EVIDENCE_KINDS` 에 속한 종류는 이미 §3-c/§3-d/§3-e
    에서 본문을 만들었으므로 **그대로 통과**시킨다 — 이전과 같다.

    `spike_or_falling_alert` 는 cron 이 없지만 PARAM·수동 경로가 남아 있다.
    **삭제하거나 동작을 바꾸지 않는다.**

    반환 `(실패|None, evidence, message_text)`.
    """
    if push_kind in SKIP_EVIDENCE_KINDS:
        return None, evidence, message_text

    from app.runtime_evidence_composer import compose_runtime_evidence
    from app.three_push_runtime_message_builder import availability_summary
    from app.three_push_runtime_message_builder import (
        build_runtime_message as _default_builder,
    )

    fail, ev, msg = compose_evidence_and_message(
        record,
        push_kind=push_kind,
        param=param,
        runtime_kst=runtime_kst,
        market_quotes=market_quotes,
        reeval_fn=reeval_fn,
        compose_runtime_evidence=compose_runtime_evidence,
        build_runtime_message=build_runtime_message or _default_builder,
        availability_summary=availability_summary,
        logger=logger,
    )
    if fail is not None:
        return fail, ev, message_text
    return None, ev, msg or ""


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


def _save_intraday_state_after_send(
    record: dict[str, Any],
    *,
    intraday: Any,
    runtime_date_kst: str,
    runtime_kst: Optional[str],
) -> None:
    """장중 사업군 상태 저장. **전송 성공 뒤에만 호출된다.**

    저장 실패가 "발송은 됐다" 는 사실을 뒤집으면 안 되므로 예외를 삼킨다.
    대신 기록을 남겨 다음 회차가 중복 발송을 하더라도 원인을 알 수 있게 한다.
    """
    if intraday is None or not getattr(intraday, "message_text", ""):
        return
    try:
        from app.runtime_evidence.holdings_risk_flow import (
            DEFAULT_SECTOR_STATE_PATH,
            _now_kst,
        )
        from app.runtime_evidence.sector_signal_state import (
            load_sector_state,
            merge_sector_entries,
            save_sector_state,
        )

        now = _now_kst(runtime_kst)
        path = getattr(intraday, "state_path", None) or DEFAULT_SECTOR_STATE_PATH
        previous = load_sector_state(path, today_kst=runtime_date_kst)
        # 사업군 **+ 보유 급등** 을 함께 저장한다. `changes.send` 만 쓰면
        # 급등이 상태에 안 남아 다음 틱에 또 신규가 된다(검증자 실측).
        sent = list(getattr(intraday, "sent_signals", None) or [])
        observed = list(getattr(intraday, "observed", None) or [])
        # 평가 불가 범위를 **여기에도** 넘긴다(검증자 P1). 사업군 장애 중 보유
        # 급등만 나가는 회차에 이걸 빠뜨리면, 이 저장이 먼저 사업군 entry 를
        # `continuous=False` 로 내리고 뒤의 관측 저장은 이미 변질된 값을 보존한다.
        unevaluable = set(getattr(intraday, "unevaluable", None) or set())
        save_sector_state(
            path,
            entries=merge_sector_entries(
                sent=sent,
                previous=previous,
                now_kst=now,
                observed=observed,
                unevaluable=unevaluable,
            ),
            today_kst=runtime_date_kst,
            # **보낸 회차만** 센다. 억제·미발송 회차는 올리지 않는다.
            sent_today=(previous.sent_today if previous.comparable else 0) + 1,
        )
        # 이번 회차 집계를 `알림` 으로 확정한다(설계 §8).
        #
        # 집계 파일을 여기서 고치면 안 된다 — D3 이후 **이번 회차 tick 은 아직
        # 없다**(`_finish()` 가 Gate 통과 뒤에 쓴다). 파일의 "마지막 회차" 를
        # 고치면 **직전 회차**를 발송으로 둔갑시키고, 이번 회차는 잠정값
        # (`신호 없음`) 으로 남는다(검증자 실측 `sent=0 · no_signal=1`).
        # 그래서 아직 쓰이지 않은 **pending 의 잠정값**을 고친다.
        try:
            from app.runtime_evidence.holdings_risk_flow import PENDING_KEY
            from app.runtime_evidence.intraday_checkup_tally import OUTCOME_SENT

            pending = record.get(PENDING_KEY)
            if pending is not None:
                pending["tick_outcome"] = OUTCOME_SENT
        except Exception:  # noqa: BLE001 - 집계 실패가 발송 사실을 뒤집지 않는다
            pass
        record["intraday_state_saved"] = True
        record["intraday_sent_today"] = (
            previous.sent_today if previous.comparable else 0
        ) + 1
    except Exception as e:  # noqa: BLE001
        record["intraday_state_save_error"] = f"{type(e).__name__}: {str(e)[:200]}"


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
        # POC3-02C-OPS-02 (설계 §15-2) — 장중 **발송 진척 상태**(`sent_today`
        # 전진 · `last_sent_at`)는 **여기서만** 전진시킨다. 이 줄에 도달 = Telegram
        # 전송 성공이고 `partial_delivery` 가 아니다. 부분 전송이면 위에서 이미
        # 반환됐다. 관측 상태는 조립 단계가 매 회차 저장한다.
        _save_intraday_state_after_send(
            record,
            intraday=holdings_selection_ctx.get("intraday"),
            runtime_date_kst=runtime_date_kst,
            runtime_kst=runtime_kst,
        )
    else:
        save_state(
            holdings_state_path,
            selected=holdings_selection_ctx["selected"],
            slot_id=holdings_selection_ctx.get("slot_id"),
        )
        record["holdings_selection_state_saved"] = True
