"""POC5-01B — 시장 브리핑 원장 item · 태그(이미 계산된 값 · 원장 직전 시장 run · 로컬 캘린더).

PLAN `docs/ai_plan/POC5/POC5-01B_OPERATIONAL_DECISION_EVENT_LEDGER_PLAN_V1.md` §1-3 · §8(Q-H).

```text
item      S&P500 방향 1행 · 기초지수 후보 그룹(본문 최대 2) 또는 구역 상태 1행 — 전이 없음(시장 관찰)
태그      outlook_state · flat_or_none · input_delay(미국 입력 · session_check.reason ≠ ok) ·
          same_us_session(원장 직전 예정 시장 run 의 sp500_asof 와 같음) ·
          after_kr_market_closure(기대 T-1 과 오늘 사이 한국 평일 휴장 · 로컬 캘린더)
```
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Optional

from app.three_push_runtime import ledger_store as store
from app.three_push_runtime.ledger_items import (
    DATA_UNAVAILABLE,
    NOT_SELECTED,
    SENT,
    attr_of,
    make_item,
)

SP500_SUBJECT = "SP500"
INDEX_BLOCK_SUBJECT = "KR_INDEX"
_INDEX_NORMAL_EMPTY = "no_candidate_normal"


def market_items(outcome: Any, record: dict[str, Any]) -> list[dict[str, Any]]:
    outlook = attr_of(outcome, "outlook")
    index = attr_of(outcome, "index")
    if outlook is None and index is None:
        return []  # 비거래일 — 평가 전에 끝났다
    notice = (attr_of(outcome, "diagnostics", {}) or {}).get(
        "batch_failure_notice"
    ) or {}
    in_body = bool(attr_of(outcome, "message_text", "")) and not notice.get(
        "notice_only"
    )
    session = record.get("sp500_session_check") or {}
    items = []
    if outlook is not None:
        items.append(
            make_item(
                "market",
                SP500_SUBJECT,
                state=outlook.state,
                disposition=(
                    DATA_UNAVAILABLE
                    if not outlook.usable
                    else (SENT if in_body else NOT_SELECTED)
                ),
                values={
                    "sp500_return_pct": outlook.sp500_return_pct,
                    "sp500_asof": record.get("sp500_asof"),
                    "reason": outlook.reason,
                    "session_check_reason": session.get("reason"),
                    "expected_session": session.get("expected_session"),
                },
                evaluable=bool(outlook.usable),  # 미국 입력 없음(NONE) = 평가 불가
            )
        )
    if index is None:
        return items
    if index.status == "ok" and index.candidates:
        for rank, c in enumerate(index.candidates, start=1):
            items.append(
                make_item(
                    "index_group",
                    c.identifier,
                    state=None,
                    disposition=SENT if in_body else NOT_SELECTED,
                    values={
                        "rank": rank,
                        "ret_5d_pct": c.ret_5d_pct,
                        "ret_20d_pct": c.ret_20d_pct,
                        "ticker_count": c.ticker_count,
                        "tickers": list(getattr(c, "tickers", ()) or ()),
                        "products": list(c.products),
                        "price_asof": index.price_asof,
                        "lookback_dates": (index.diagnostics or {}).get(
                            "lookback_dates"
                        ),
                    },
                )
            )
    else:
        status = index.status if index.status != "ok" else _INDEX_NORMAL_EMPTY
        items.append(
            make_item(
                "index_block",
                INDEX_BLOCK_SUBJECT,
                state=status,
                disposition=(
                    NOT_SELECTED if status == _INDEX_NORMAL_EMPTY else DATA_UNAVAILABLE
                ),
                values={
                    "price_asof": index.price_asof,
                    "diagnostics": index.diagnostics,
                },
                evaluable=status == _INDEX_NORMAL_EMPTY,  # 구역 장애 = 평가 불가
            )
        )
    return items


def market_tags(
    con: Any,
    record: dict[str, Any],
    items: list[dict[str, Any]],
    *,
    runtime_date_kst: str,
    calendar_dir: Optional[Path],
) -> dict[str, Any]:
    """Q14 · Q-H — 이미 있는 값과 원장 직전 시장 run 만으로 만든다."""
    sp = next((i for i in items if i["subject_kind"] == "market"), None)
    state = sp["state"] if sp else None
    session = record.get("sp500_session_check") or {}
    tags: dict[str, Any] = {
        "outlook_state": state,
        "flat_or_none": state in ("FLAT", "NONE") if state else None,
        # 미국 입력 점검 결과가 있을 때만 판정한다(없으면 모름).
        "input_delay": (session.get("reason") != "ok") if session else None,
        "index_status": record.get("index_status"),
        "batch_failure_reasons": list(
            ((record.get("batch_failure_notice") or {}).get("reasons")) or []
        ),
        "same_us_session": None,
        "after_kr_market_closure": None,
    }
    asof = record.get("sp500_asof")
    prev_raw = store.previous_run_value(
        con,
        push_kind="market_briefing",
        subject_kind="market",
        subject_id=SP500_SUBJECT,
    )
    if prev_raw and asof:
        try:
            prev_asof = json.loads(prev_raw).get("sp500_asof")
        except ValueError:
            prev_asof = None
        # 직전 미국 기준일을 모르면 판정하지 않는다(모름 = None).
        tags["same_us_session"] = (prev_asof == asof) if prev_asof else None
    tags["after_kr_market_closure"] = _after_kr_closure(runtime_date_kst, calendar_dir)
    return tags


def _after_kr_closure(today: str, calendar_dir: Optional[Path]) -> Optional[bool]:
    """기대 T-1 과 오늘 사이에 한국 평일 휴장이 있었는가(로컬 캘린더 · 외부 조회 0)."""
    from app import trading_day_lag

    try:
        t1 = trading_day_lag.expected_previous_trading_day(
            today, calendar_dir=calendar_dir
        )
        if not t1:
            return None
        d, end = date.fromisoformat(t1) + timedelta(days=1), date.fromisoformat(today)
        while d < end:
            if d.weekday() < 5 and not trading_day_lag.is_trading_day(
                d.isoformat(), calendar_dir=calendar_dir
            ):
                return True
            d += timedelta(days=1)
        return False
    except (ValueError, OSError):
        return None


__all__ = ["INDEX_BLOCK_SUBJECT", "SP500_SUBJECT", "market_items", "market_tags"]
