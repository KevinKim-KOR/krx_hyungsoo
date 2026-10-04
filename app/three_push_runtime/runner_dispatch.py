"""push kind 별 조립 · flag 뒤 판정 (POC5-01A 러너 기계 분리 · 2026-10-03).

`run_three_push_runtime_oci.py` §3-c · §3-d · §3-e(조립)와 §6-c(판정)를 **문장 순서 그대로**
옮겼다. 판정 · 본문 · record 기록 · 상태 저장 순서 변경 0건. 판정은 실패 튜플로 돌려주고
러너가 `_finish(*fail)` 한다(튜플 모양도 원래 인자 그대로).

조립과 판정 사이에 러너의 §4 · §5 · §6(enable flag guard)이 그대로 남는다 — 판정을 flag
guard 앞으로 당기면 `no_selection`·`non_trading_day` 가 `push_kind_disabled` 를 가로챈다.

테스트가 러너 모듈에서 바꿔 끼우는 `kst_today`(함수) · 상태 경로 2개는 러너가 **호출 때**
인자로 넘긴다(PLAN 1-8). `_hrf` · `_mb` 는 모듈 속성으로 호출 때 조회한다(테스트가
`runner_market_briefing.assemble` 을 바꿔 끼운다). logger 는 러너 것을 받는다.

POC5-01B 는 kind 별 조립 결과를 `KindAssembly` 에 additive 필드로 실어 나를 수 있다
(PLAN 1-12 · 이번 단계에서는 붙이지 않는다).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

from app.runtime_evidence import holdings_risk_flow as _hrf
from app.runtime_evidence.holdings_selection_flow import assemble_holdings_push
from app.three_push_runtime import runner_market_briefing as _mb


@dataclass
class KindAssembly:
    """§3-c · §3-d · §3-e 결과. 판정은 flag guard 뒤 `decide_after_flag_guard`."""

    holdings_outcome: Any = None
    risk_outcome: Any = None
    # 장중 조립 결과 그대로 — `.intraday` 는 원래처럼 §6-c 에서 읽는다.
    risk_assembly: Any = None
    market_outcome: Any = None
    fail: Optional[tuple[str, str, str]] = None
    skip_non_trading_day: bool = False
    message_text: str = ""


def assemble_push_kind(
    record: dict[str, Any],
    *,
    push_kind: str,
    market_quotes: Optional[dict[str, Any]],
    price_refresh_diag: dict[str, Any],
    slot_id: Optional[str],
    runtime_kst: str,
    runtime_date_kst: str,
    kst_today: Callable[[], str],
    holdings_state_path: Path,
    risk_state_path: Path,
    logger: Any,
) -> KindAssembly:
    """러너 §3-c · §3-d · §3-e. **판정하지 않는다** — 결과만 담아 돌려준다."""
    asm = KindAssembly()
    # ── 3-c. 보유 브리핑 선정 · 본문 조립 (POC3-OPS-01A) ────────────────────
    # 조립만 한다. **모든 skip·fail 결정은 enable flag guard(§6) 뒤(§6-c)** 다 —
    # 여기서 return 하면 push_kind 가 비활성인데도 `no_selection`·데이터 실패가
    # 기존 계약인 `push_kind_disabled` 를 가로챈다(실제로 겪은 결함).
    # 순서 계약은 `assemble_holdings_push` 안에 있다: 비거래일 판정 → 완전성
    # 가드 → 선정(휴장일엔 선정·이력조회를 아예 돌리지 않는다).
    if push_kind == "holdings_briefing":
        from app.holdings import load as _load_holdings_for_selection
        from app.market_data_store import fetch_price_history as _fetch_history

        _asm = assemble_holdings_push(
            market_quotes=market_quotes or {},
            price_refresh_diag=price_refresh_diag,
            today_kst=kst_today(),
            state_path=holdings_state_path,
            slot_id=slot_id,
            runtime_kst=runtime_kst,
            holdings_loader=_load_holdings_for_selection,
            fetch_history=_fetch_history,
            logger=logger,
        )
        record.update(_asm.diagnostics)
        asm.fail = _asm.fail  # 판정은 §6-c (위 주석 참조)
        asm.skip_non_trading_day = _asm.skip_non_trading_day
        asm.holdings_outcome = _asm.outcome
        asm.message_text = _asm.message_text

    # ── 3-d. 보유 위험 즉시 알림 조립 (POC3-OPS-02A) ─────────────────────────
    # 기존 spike 신호·본문을 재사용하지 않는다 (OPS-01C `REJECT`). 조립만 하고
    # **모든 skip·fail 결정은 §6-c** — flag guard 뒤다.
    if push_kind == "holdings_risk_alert":
        from app.holdings import load as _load_holdings_for_risk
        from app.market_data_store import fetch_price_history as _fetch_history_risk

        _rasm = _hrf.assemble_holdings_risk_push(
            market_quotes=market_quotes or {},
            price_refresh_diag=price_refresh_diag,
            today_kst=kst_today(),
            state_path=risk_state_path,
            runtime_kst=runtime_kst,
            holdings_loader=_load_holdings_for_risk,
            fetch_history=_fetch_history_risk,
            logger=logger,
        )
        record.update(_rasm.diagnostics)
        asm.fail = _rasm.fail  # 판정은 §6-c
        asm.skip_non_trading_day = _rasm.skip_non_trading_day
        asm.risk_outcome = _rasm.outcome
        asm.risk_assembly = _rasm
        asm.message_text = _rasm.message_text
        record[_hrf.PENDING_KEY] = _rasm.intraday_records

    # ── 3-e. 시장 흐름 브리핑 조립 (POC3-OPS-02B-2) ──────────────────────────
    asm.market_outcome = _mb.assemble(
        record, push_kind=push_kind, today_kst=runtime_date_kst, runtime_kst=runtime_kst
    )
    if asm.market_outcome is not None:
        asm.message_text = asm.market_outcome.message_text
    return asm


def decide_after_flag_guard(
    asm: KindAssembly,
    *,
    message_text: str,
    slot_id: Optional[str],
    save_state: Callable[..., Any],
    holdings_state_path: Path,
    logger: Any,
) -> tuple[Optional[tuple], dict[str, Any]]:
    """러너 §6-c. 반환 `(실패 튜플 | None, holdings_selection_ctx)`.

    조립은 §3-c · §3-d · §3-e 에서 끝났다. 여기서는 발송 여부만 정한다. 조립 단계에서
    잡힌 실패를 **flag guard 뒤**에서 확정한다.
    """
    holdings_selection_ctx: dict[str, Any] = {}
    if asm.fail is not None:
        return asm.fail, holdings_selection_ctx

    if asm.skip_non_trading_day:
        # 판정·evidence 기록은 §3-c 에서 끝났다. 여기서는 발송 여부만 정한다.
        return ("skipped", "non_trading_day"), holdings_selection_ctx

    mb_fail = _mb.decide(asm.market_outcome, logger=logger)
    if mb_fail is not None:
        return mb_fail, holdings_selection_ctx

    risk_outcome = asm.risk_outcome
    if risk_outcome is not None and risk_outcome.skip_reason and not message_text:
        # 신규·악화 없음. 단 장중 본문이 있으면 보낸다(OPS-02 사업군 단독 신호).
        logger.info(
            "위험 알림 skip: %s (선정 %d건 · 억제 %d건)",
            risk_outcome.skip_reason,
            len(risk_outcome.selected),
            len(risk_outcome.changes.suppressed) if risk_outcome.changes else 0,
        )
        return ("skipped", risk_outcome.skip_reason), holdings_selection_ctx

    if risk_outcome is not None:
        holdings_selection_ctx = {
            "risk": risk_outcome,
            "intraday": asm.risk_assembly.intraday,
        }

    holdings_outcome = asm.holdings_outcome
    if holdings_outcome is not None:
        if holdings_outcome.skip_reason:
            if holdings_outcome.save_empty_state:
                save_state(holdings_state_path, selected=[], slot_id=slot_id)
            logger.info(
                "보유 브리핑 skip: %s (선정 %d건)",
                holdings_outcome.skip_reason,
                len(holdings_outcome.selected),
            )
            return ("skipped", holdings_outcome.skip_reason), holdings_selection_ctx
        holdings_selection_ctx = {
            "selected": holdings_outcome.selected,
            "slot_id": slot_id,
        }
    return None, holdings_selection_ctx
