"""POC5-05 개정 2 — History 조회 · 시장 흐름 입력(읽기 전용 · 쓰기 0).

설계 §2 · §8 · PLAN §2-4 · §2-8: position 별 보유 기간(현재 · 지난) · 기록 · 매도별 실현손익 ·
기간 누적 · 정정 전 입력 · 취소 기록. 계산은 매번 records 로 다시 한다(저장하지 않음).
"""

from __future__ import annotations

from decimal import localcontext
from typing import Any, Optional

from app import holdings_book as book
from app import holdings_store as store
from app.holdings_history import compute_doc


def _record_view(r: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_id": r["record_id"],
        "kind": r["kind"],
        "recorded_at": r["recorded_at"],
        "supersedes_id": r["supersedes_id"],
        "payload": r["payload"],
    }


def _event_view(ev: dict[str, Any], by_id: dict[str, Any]) -> dict[str, Any]:
    r = ev["record"]
    out = _record_view(r)
    out["date"] = book.event_date(r)
    for k in ("cost_of_sold", "realized_pnl", "realized_rate"):
        out[k] = book.fmt(ev.get(k))
    for k in ("q_after", "c_after", "avg_after"):
        out[k] = book.fmt(ev.get(k))
    previous, sid = [], r["supersedes_id"]
    while sid and sid in by_id:
        previous.append(_record_view(by_id[sid]))
        sid = by_id[sid]["supersedes_id"]
    out["previous"] = previous
    return out


def _cycle_view(cy: dict[str, Any], by_id: dict, voids: dict) -> dict[str, Any]:
    voided = [
        {**_record_view(by_id[t]), "voided_at": v["recorded_at"]}
        for t, v in voids.items()
        if t in by_id and by_id[t]["cycle_id"] == cy["cycle_id"]
    ]
    q, c = cy["q"], cy["c"]
    with localcontext() as ctx:  # 계산과 같은 정밀도(book.PREC)
        ctx.prec = book.PREC
        rate = cy["realized"] / cy["sold_cost"] * 100 if cy["sold_cost"] > 0 else None
        avg = c / q if q > 0 else None
    return {
        "cycle_id": cy["cycle_id"],
        "status": cy["status"],
        "opened_by": cy["opened_by"],
        "closed_by": cy["closed_by"],
        "start_date": cy["start_date"],
        "end_date": cy["end_date"],
        "has_adjustment": cy["has_adjustment"],
        "quantity": book.fmt(q),
        "cost": book.fmt(c),
        "avg_buy_price": book.fmt(avg),
        "realized_pnl": book.fmt(cy["realized"]),
        "sold_cost": book.fmt(cy["sold_cost"]),
        "realized_rate": book.fmt(rate),
        "events": [_event_view(ev, by_id) for ev in cy["events"]],
        "voided": voided,
    }


def history(position_id: Optional[str] = None) -> dict[str, Any]:
    """position 별 보유 기간 · 기록 · 계산값. 쓰기 0 · 손상은 예외."""
    state = store.read_document()
    doc = state["doc"]
    cur = compute_doc(doc)
    records = doc["personal_trade_history"]["records"]
    by_id = {r["record_id"]: r for r in records}
    voids = {r["supersedes_id"]: r for r in records if r["kind"] == "VOID"}
    open_order = {h["position_id"]: i for i, h in enumerate(cur["holdings"])}
    opened, closed = [], []
    for pos in cur["positions"]:
        if position_id and pos["position_id"] != position_id:
            continue
        cycles = [_cycle_view(cy, by_id, voids) for cy in pos["cycles"]]
        # 줄 단위 취소 기록 — 기간의 매매가 모두 취소돼 기간이 계산에서 빠져도 보인다.
        voided = [
            {**_record_view(by_id[t]), "voided_at": v["recorded_at"]}
            for t, v in voids.items()
            if t in by_id and by_id[t]["position_id"] == pos["position_id"]
        ]
        view = {
            "position_id": pos["position_id"],
            "ticker": pos["ticker"],
            "name": pos["name"],
            "account_group": pos["account_group"],
            "is_open": pos["position_id"] in open_order,
            "cycles": cycles,
            "voided": voided,
        }
        (opened if view["is_open"] else closed).append(view)
    opened.sort(key=lambda p: open_order[p["position_id"]])
    closed.sort(
        key=lambda p: max((c["end_date"] or "" for c in p["cycles"]), default=""),
        reverse=True,
    )
    return {
        "status": state["status"],
        "revision": doc["revision"],
        "positions": opened + closed,
    }


def market_flow_input(position_id: str, cycle_id: str) -> tuple[str, dict[str, Any]]:
    """시장 흐름 계산 입력(종목코드 · 기간). 없으면 LookupError. 쓰기 0."""
    doc = store.read_document()["doc"]
    cur = compute_doc(doc)
    for pos in cur["positions"]:
        if pos["position_id"] != position_id:
            continue
        for cy in pos["cycles"]:
            if cy["cycle_id"] != cycle_id:
                continue
            events = [
                {
                    "record_id": ev["record"]["record_id"],
                    "kind": ev["record"]["kind"],
                    "trade_date": ev["record"]["payload"]["trade_date"],
                }
                for ev in cy["events"]
                if ev["record"]["kind"] in book.TRADES
            ]
            cycle = {
                "cycle_id": cycle_id,
                "opened_by": cy["opened_by"],
                "status": cy["status"],
                "events": events,
            }
            return pos["ticker"], cycle
    raise LookupError("보유 기간을 찾을 수 없습니다.")
