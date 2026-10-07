"""POC5-01B — 원장 item 만들기(보유 · 장중) · disposition · 상태 전이(이미 계산된 값만 읽는다).

PLAN `docs/ai_plan/POC5/POC5-01B_OPERATIONAL_DECISION_EVENT_LEDGER_PLAN_V1.md`
§1-3(disposition 매핑) · §1-4(강도 · 회복) · §6 · §8(설계자 판정 Q-B · Q-C · Q-D · Q-E).
시장 브리핑 item · 태그는 `ledger_market`(Q-H).

```text
입력      KindAssembly(asm) · 실행 record — 조립이 이미 만든 값. 시세 · DB · 외부 조회 0
          (원장 자기 행만 읽는다 — 직전 평가 · 같은 날 PRIMARY · 직전 미국 세션 · Q-C 승인)
sent      '조립된 발송 본문에 실림'. 실제 전달 여부는 같은 event_id 의 delivery 로 본다(Q-E)
전이      event_type = 직전 평가 대비 실제 전이 · exposure = 같은 날 같은 subject · state 첫 노출만
          PRIMARY(Q29 · Q-D). 같은 계열 약화 = repeat_exposure · 비교 불가 변경 = new_entry
```

개인값(수량 · 매입가 · 금액 · 계좌)은 담지 않는다.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from app.three_push_runtime import ledger_store as store

SENT = "sent"
SUPPRESSED = "suppressed"
CUT_SECTION = "cut_by_section_cap"
CUT_DAILY = "cut_by_daily_cap"
NOT_SELECTED = "not_selected"
DATA_UNAVAILABLE = "data_unavailable"

NEW_ENTRY = "new_entry"
REPEAT = "repeat_exposure"
WORSENED = "worsened"
REENTRY = "reentry_after_recovery"
PRIMARY = "PRIMARY"
SECONDARY = "SECONDARY"

# 강도 — 코드에 있는 순서만(PLAN §1-4). 같은 계열 안에서만 비교한다.
#   보유 브리핑 20거래일 하락: holdings_selection.GROUP_ORDER(강한 것부터) 의 역순.
#   장중 급락 · 급등: holdings_risk.severity · surge_severity.
#   사업군 3 state: 순서 없음(각자 한 계열 · 다른 state 로 바뀌면 비교 불가).
_BRIEFING_FAMILY = "briefing_decline"
_DROP_FAMILY = "risk_drop"
_SURGE_FAMILY = "risk_surge"
AXIS_BRIEFING, AXIS_RISK, AXIS_SECTOR = "briefing", "risk", "sector"
HELD_SECTOR_KEY = "보유"  # intraday_alert_flow.HELD_SECTOR_KEY(급등 관측의 sector_key)

SECTOR_BLOCK_SUBJECT = "sectors"

# 사업군 제외 사유 중 '자료 없음' 으로 보는 것(PLAN §1-3 · held 는 not_selected).
_SECTOR_DATA_REASONS = frozenset(
    {
        "no_quote",
        "no_day_return",
        "short_history",
        "trend_not_t1",
        "ticker_not_t1",
        "representative_missing",
        "intraday_config_unavailable",
    }
)


def attr_of(obj: Any, name: str, default: Any = None) -> Any:
    return getattr(obj, name, default) if obj is not None else default


def make_item(
    subject_kind: str,
    subject_id: str,
    *,
    state: Optional[str],
    disposition: str,
    values: dict[str, Any],
    held: Optional[int] = None,
    axis: Optional[str] = None,
    t0: Any = None,
    evaluable: bool = True,
) -> dict[str, Any]:
    """item 1행. `evaluable=False` = 평가 불가(직전 평가로 쓰지 않는다 · 코드 UNEVALUABLE).
    `t0` 는 판정에 **실제로 쓴** 시세만 넘긴다(버린 시세는 None)."""
    return {
        "subject_kind": subject_kind,
        "subject_id": subject_id,
        "held": held,
        "state": state,
        "disposition": disposition,
        "values": values,
        "axis": axis,
        "evaluable": evaluable,
        "t0_price": attr_of(t0, "current_price"),
        "t0_price_asof": attr_of(t0, "price_asof"),
    }


# ── 보유 브리핑 ──────────────────────────────────────────────────────────────


def _briefing_level(state: Optional[str]) -> Optional[tuple[str, int]]:
    from app.runtime_evidence.holdings_selection import (
        GROUP_ORDER,
        REASON_RECENT_DECLINE,
    )

    bands = [s for r, s in GROUP_ORDER if r == REASON_RECENT_DECLINE]
    if state not in bands:
        return None
    return _BRIEFING_FAMILY, len(bands) - bands.index(state)


def holdings_briefing_items(outcome: Any) -> list[dict[str, Any]]:
    observations = list(attr_of(outcome, "observations", None) or [])
    if not observations:
        return []
    selected = {s.ticker: s for s in (attr_of(outcome, "selected", None) or [])}
    changes = attr_of(outcome, "changes")
    send_full = (
        changes is None
        or bool(attr_of(changes, "full_send"))
        or not attr_of(changes, "has_change", False)
    )
    if send_full:
        in_body = set(selected)
    else:
        in_body = {s.ticker for s in attr_of(changes, "new", [])} | {
            s.ticker for s, _ in attr_of(changes, "moved", [])
        }
    has_body = bool(attr_of(outcome, "message_text", ""))
    items = []
    for ob in observations:
        ticker = ob["ticker"]
        sel = selected.get(ticker)
        values = {
            "return_20d_pct": ob.get("return_pct"),
            "profit_loss_pct": ob.get("profit_loss_pct"),
            "base_day": ob.get("base_day"),
            "base_close": ob.get("base_close"),
            "drawdown_20d_pct": attr_of(sel, "drawdown_20d_pct"),
            "unavailable_cause": ob.get("cause"),
        }
        state = ob.get("state")
        cause = ob.get("cause")
        if cause:
            disposition, state = DATA_UNAVAILABLE, "DATA_UNAVAILABLE_OR_STALE"
        elif state is None:
            disposition = NOT_SELECTED
        elif has_body and ticker in in_body:
            disposition = SENT
        else:
            disposition = SUPPRESSED
        items.append(
            make_item(
                "ticker",
                ticker,
                state=state,
                disposition=disposition,
                values=values,
                held=1,
                axis=AXIS_BRIEFING,
                # 현재가를 버린 종목(원인 current_price)은 t0 를 남기지 않는다.
                t0=(
                    None
                    if cause == "current_price"
                    else _Quote(ob.get("current"), ob.get("quote_asof"))
                ),
                evaluable=not cause,
            )
        )
    return items


class _Quote:
    def __init__(self, current: Any, asof: Any) -> None:
        self.current_price, self.price_asof = current, asof


# ── 장중 보유 위험 · 사업군 ───────────────────────────────────────────────────


def _risk_level(state: Optional[str]) -> Optional[tuple[str, int]]:
    from app.runtime_evidence import holdings_risk as hr

    if state in (hr.STATE_D5_7, hr.STATE_D7_10, hr.STATE_D10_PLUS):
        return _DROP_FAMILY, hr.severity(state)
    if state in (hr.STATE_U5_7, hr.STATE_U7_10, hr.STATE_U10_PLUS):
        return _SURGE_FAMILY, hr.surge_severity(state)
    return None


def risk_items(risk_assembly: Any, *, intraday_isolated: bool) -> list[dict[str, Any]]:
    outcome = attr_of(risk_assembly, "outcome")
    evaluated = list(attr_of(outcome, "evaluated", None) or [])
    intraday = None if intraday_isolated else attr_of(risk_assembly, "intraday_eval")
    # 급등은 정책이 켜지고 급등 선정이 예외 없이 끝난 회차에서만 평가된다. 아니면
    # 급락 구간 밖 종목의 급등은 '모름' — 그 '상태 없음' 행은 비활성 관측이 아니라
    # 평가 불가다(PLAN §1-4 · 직전 상태와 상관없이 회복으로 세지 않는다).
    surge_evaluated = bool(
        (attr_of(intraday, "diagnostics", {}) or {}).get("intraday_policy_enabled")
    ) and not attr_of(intraday, "surge_error")
    held_set = {
        r.get("ticker")
        for r in (attr_of(outcome, "holding_rows", None) or [])
        if r.get("ticker")
    }
    changes = attr_of(outcome, "changes")
    selected = {s.ticker: s for s in (attr_of(outcome, "selected", None) or [])}
    drop_send = {i.ticker for i in attr_of(changes, "new", []) or []} | {
        i.ticker for i, _ in (attr_of(changes, "worsened", []) or [])
    }
    drop_suppressed = set(attr_of(changes, "suppressed", []) or [])
    plan = attr_of(intraday, "plan")
    daily_cap = bool(attr_of(intraday, "daily_cap_reached"))
    surge_changes = attr_of(intraday, "surge_changes")
    surge_send = {s.ticker for s in (attr_of(surge_changes, "send", []) or [])}
    surge_suppressed = {t for t, _ in (attr_of(surge_changes, "suppressed", []) or [])}
    surge_state = {
        s.ticker: s.state
        for s in (attr_of(intraday, "observed", []) or [])
        if getattr(s, "sector_key", None) == HELD_SECTOR_KEY
    }
    dropped = {
        (d.get("ticker"), d.get("state")) for d in (attr_of(plan, "dropped", []) or [])
    }
    if plan is not None and attr_of(intraday, "message_text"):
        body_drop = {attr_of(i, "ticker") for i in plan.held_drop}
        body_surge = {attr_of(i, "ticker") for i in plan.held_surge}
    else:
        # 정책 비활성 · 격리 회차 = 구 본문(신규 + 악화 전부 · holdings_risk_render).
        has_old_body = bool(attr_of(outcome, "message_text", "")) and not daily_cap
        body_drop = drop_send if has_old_body else set()
        body_surge = set()

    items = []
    for ev in evaluated:
        ticker = ev["ticker"]
        state = ev.get("state") or surge_state.get(ticker)
        sel = selected.get(ticker)
        values = {
            "day_return_pct": ev.get("day_return"),
            "drawdown_pct": attr_of(sel, "drawdown_pct"),
            "profit_loss_pct": attr_of(sel, "profit_loss_pct"),
        }
        lvl = _risk_level(state)
        surge = lvl is not None and lvl[0] == _SURGE_FAMILY
        unavailable = bool(ev.get("unavailable"))
        if unavailable:
            disposition = DATA_UNAVAILABLE
        elif state is None:
            disposition = NOT_SELECTED
        elif daily_cap and (ticker in drop_send or ticker in surge_send):
            disposition = CUT_DAILY
        elif (ticker, state) in dropped:
            disposition = CUT_SECTION
        elif ticker in (body_surge if surge else body_drop):
            disposition = SENT
        elif ticker in (surge_suppressed if surge else drop_suppressed):
            disposition = SUPPRESSED
        else:
            disposition = NOT_SELECTED
        items.append(
            make_item(
                "ticker",
                ticker,
                state=state,
                disposition=disposition,
                values=values,
                held=1,
                axis=AXIS_RISK,
                t0=(
                    None
                    if unavailable
                    else _Quote(ev.get("current"), ev.get("price_asof"))
                ),
                evaluable=not unavailable and (surge_evaluated or state is not None),
            )
        )
    if intraday is not None:
        items.extend(
            _sector_items(
                intraday, daily_cap=daily_cap, dropped=dropped, held_set=held_set
            )
        )
    return items


def _sector_items(
    intraday: Any,
    *,
    daily_cap: bool,
    dropped: set[tuple[Any, Any]],
    held_set: set[Any],
) -> list[dict[str, Any]]:
    sector = attr_of(intraday, "sector")
    plan = attr_of(intraday, "plan")
    changes = attr_of(intraday, "changes")
    send = {(s.ticker, s.state) for s in (attr_of(changes, "send", []) or [])}
    suppressed = set(attr_of(changes, "suppressed", []) or [])
    in_body: set[tuple[Any, Any]] = set()
    if plan is not None and attr_of(intraday, "message_text"):
        for s in plan.avoid_drop + plan.avoid_chase + plan.entry:
            in_body.add((s.ticker, s.state))
    excluded = list(attr_of(sector, "excluded", []) or [])
    block = [e for e in excluded if not e.get("sector_key")]
    err = attr_of(intraday, "sector_error")
    evaluated = list(attr_of(sector, "evaluated", []) or [])
    omitted = attr_of(sector, "entry_omitted_reason")
    items = []
    if err or block or (omitted and not evaluated and not excluded):
        # 구역 전체 장애(조회 예외 · provider 장애 · 커버리지 미달 · 설정 못 읽음) 1행.
        reason = (
            "sector_error" if err else (block[0].get("reason") if block else omitted)
        )
        items.append(
            make_item(
                "sector_block",
                SECTOR_BLOCK_SUBJECT,
                state=reason,
                disposition=DATA_UNAVAILABLE,
                values={
                    "excluded": block,
                    "error_type": (err or "").split(":")[0] or None,
                },
                evaluable=False,  # 구역 장애 = 평가 불가
            )
        )
    reasons = {
        e["sector_key"]: e.get("reason") for e in excluded if e.get("sector_key")
    }
    seen = set()
    for row in evaluated:
        key, ticker, used_alt, ret, r5, r20, rank, state = row
        quote = (attr_of(sector, "quotes", None) or {}).get(ticker)
        seen.add(key)
        reason = reasons.get(key)
        values = {
            "ticker": ticker,
            "used_alternate": used_alt,
            "day_return_pct": ret,
            "return_5d_pct": r5,
            "return_20d_pct": r20,
            "rank": rank,
            "evaluated_count": attr_of(sector, "evaluated_count"),
            "excluded_reason": reason,
        }
        if reason == "held":
            disposition = NOT_SELECTED
        elif reason in _SECTOR_DATA_REASONS:
            disposition = DATA_UNAVAILABLE
        elif state is None:
            disposition = NOT_SELECTED
        elif daily_cap and (ticker, state) in send:
            disposition = CUT_DAILY
        elif (ticker, state) in dropped:
            disposition = CUT_SECTION
        elif (ticker, state) in in_body:
            disposition = SENT
        elif (ticker, state) in suppressed:
            disposition = SUPPRESSED
        else:
            disposition = NOT_SELECTED
        items.append(
            make_item(
                "sector",
                key,
                state=state,
                disposition=disposition,
                values=values,
                held=1 if ticker in held_set else 0,
                axis=AXIS_SECTOR,
                t0=quote,
                # 보유로 제외된 사업군 · 자료없음 = 평가 불가(코드 UNEVALUABLE · 직전 관측 유지).
                evaluable=reason != "held" and disposition != DATA_UNAVAILABLE,
            )
        )
    for e in excluded:  # 당일 등락률이 없어 평가에 못 들어간 사업군
        key = e.get("sector_key")
        if key and key not in seen:
            items.append(
                make_item(
                    "sector",
                    key,
                    state=None,
                    disposition=DATA_UNAVAILABLE,
                    values={
                        "ticker": e.get("ticker"),
                        "excluded_reason": e.get("reason"),
                    },
                    held=1 if e.get("ticker") in held_set else 0,
                    axis=AXIS_SECTOR,
                    evaluable=False,
                )
            )
    return items


# ── 전이 · 노출 (원장 자기 행 · 같은 트랜잭션) ─────────────────────────────────


def _level(axis: Optional[str], state: Optional[str]) -> Optional[tuple[str, int]]:
    """`(계열, 강도)` — 활성 state 가 아니면 None. 계열은 state 에서 정한다."""
    if state is None:
        return None
    if axis == AXIS_BRIEFING:
        return _briefing_level(state)
    if axis == AXIS_RISK:
        return _risk_level(state)
    if axis == AXIS_SECTOR:
        return f"sector:{state}", 1  # 사업군 — state 마다 한 계열(순서 없음)
    return None


# 전이를 매기는 disposition(설계서 §6 — 비선정 · 자료없음 · 시장 관찰은 비워 둔다).
_TRANSITION_DISPOSITIONS = frozenset({SENT, SUPPRESSED, CUT_SECTION, CUT_DAILY})


def apply_transitions(
    con: Any, items: list[dict[str, Any]], *, push_kind: str, runtime_date_kst: str
) -> list[dict[str, Any]]:
    """event_type · exposure · prev_state 를 채우고 저장 행 모양으로 돌려준다.

    직전 평가 = 같은 kind · subject 의 가장 최근 확정 · 예정 회차 · 평가된 item.
    """
    rows = []
    for it in items:
        event_type = exposure = prev_state = None
        evaluable = bool(it.get("evaluable", True))
        if it.get("axis") is not None and evaluable:
            prev = store.previous_item(
                con,
                push_kind=push_kind,
                subject_kind=it["subject_kind"],
                subject_id=it["subject_id"],
            )
            prev_state = prev[0] if prev else None
            cur = _level(it["axis"], it.get("state"))
            if cur is not None and it["disposition"] in _TRANSITION_DISPOSITIONS:
                event_type = _event_type(con, push_kind, it, prev, cur)
                exposure = SECONDARY if event_type == REPEAT else PRIMARY
                if exposure == PRIMARY and store.primary_today(
                    con,
                    push_kind=push_kind,
                    subject_kind=it["subject_kind"],
                    subject_id=it["subject_id"],
                    state=it["state"],
                    runtime_date_kst=runtime_date_kst,
                ):
                    exposure = SECONDARY  # 같은 날 같은 state 는 첫 노출만(Q29 · Q-D)
        rows.append(
            {
                "subject_kind": it["subject_kind"],
                "subject_id": it["subject_id"],
                "held": it.get("held"),
                "state": it.get("state"),
                "prev_state": prev_state,
                "disposition": it["disposition"],
                "event_type": event_type,
                "exposure": exposure,
                "values_json": json.dumps(
                    it["values"], ensure_ascii=False, default=str
                ),
                "t0_price": it.get("t0_price"),
                "t0_price_asof": it.get("t0_price_asof"),
                "evaluable": int(evaluable),
            }
        )
    return rows


def _event_type(
    con: Any,
    push_kind: str,
    it: dict[str, Any],
    prev: Optional[tuple[Optional[str], str]],
    cur: tuple[str, int],
) -> str:
    if prev is None:
        return NEW_ENTRY  # 첫 활성(첫 활성일 포함 · Q-C 승인)
    prev_state = prev[0]
    if prev_state is None:
        was = store.ever_active(
            con,
            push_kind=push_kind,
            subject_kind=it["subject_kind"],
            subject_id=it["subject_id"],
        )
        return REENTRY if was else NEW_ENTRY
    if prev_state == it["state"]:
        return REPEAT
    before = _level(it["axis"], prev_state)
    if before is None or before[0] != cur[0]:
        return NEW_ENTRY  # 비교 불가능한 상태 변경(설계서 §6)
    return WORSENED if cur[1] > before[1] else REPEAT  # 같은 계열 약화 = 반복(Q-D)


__all__ = [
    "CUT_DAILY",
    "CUT_SECTION",
    "DATA_UNAVAILABLE",
    "NEW_ENTRY",
    "NOT_SELECTED",
    "PRIMARY",
    "REENTRY",
    "REPEAT",
    "SECONDARY",
    "SENT",
    "SUPPRESSED",
    "WORSENED",
    "apply_transitions",
    "attr_of",
    "make_item",
    "holdings_briefing_items",
    "risk_items",
]
