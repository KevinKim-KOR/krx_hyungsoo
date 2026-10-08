"""POC5-05 개정 2 — 입력 정정 모드 저장(PUT /holdings 전체 목록) · 현재 보유 조회.

설계 §6 · §11-1 Q-E · PLAN §2-4:
- 줄 ID 로 맞춰 수량 · 평단 변경 → ADJUSTMENT(그 시점 값 확정 · 매매 아님) · 종목명만 → 표시값
  정정 · 빠진 줄 → 수량 0 정정('입력 정정으로 종료' · 매도 아님) · ID 없는 새 줄 → 잔고 등록.
- 변화가 없으면 기록 0 · 쓰기 0. 이력 문서(V2)에 revision 없는 요청은 409. V1 의 ID 없는
  구형 요청만 (종목, 계좌)로 맞추고, 모호하면 409(새로고침).
- 같은 request_id 재시도는 revision 확인보다 먼저 확인한다.
"""

from __future__ import annotations

import copy
import uuid
from decimal import localcontext
from typing import Any, Optional

from app import holdings as holdings_module
from app import holdings_book as book
from app import holdings_store as store
from app.holdings_history import (
    HistoryConflict,
    HistoryInputError,
    blank_record,
    compute_doc,
    content_hash,
    as_text,
    valid_record_id,
)


def save_full_list(
    rows: list[dict[str, Any]], *, revision: Optional[int], request_id: Optional[str]
) -> dict[str, Any]:
    """전체 목록 저장 → {holdings, revision, status}. 422 · 409 는 위와 같다."""
    if request_id is not None and not valid_record_id(request_id):
        raise HistoryInputError("request_id 는 UUID 여야 합니다.")
    any_ids = any(r.get("position_id") for r in rows)
    try:
        validated = holdings_module.validate_holdings(
            rows, strict_ticker=True, allow_empty=True, unique_triple=not any_ids
        )
    except holdings_module.HoldingsValidationError as e:
        raise HistoryInputError(str(e)) from e
    items = [(r.get("position_id") or None, h) for r, h in zip(rows, validated)]
    fingerprint = content_hash(
        [
            [pid, h.ticker, h.account_group, h.name, as_text(h.quantity)]
            + [as_text(h.avg_buy_price)]
            for pid, h in items
        ]
    )

    def change(state: dict[str, Any]):
        status, doc = state["status"], copy.deepcopy(state["doc"])
        records = doc["personal_trade_history"]["records"]
        if request_id is not None:
            done = [r for r in records if r.get("request_id") == request_id]
            if done:
                if any(r.get("request_hash") != fingerprint for r in done):
                    raise HistoryConflict(
                        "같은 저장 ID 에 다른 내용이 있습니다 — 새로고침하세요."
                    )
                return _list_reply(status, doc), None
        if status == "V2" and revision != doc["revision"]:
            raise HistoryConflict(
                "매매 이력이 있는 보유는 최신 화면에서만 저장할 수 있습니다 — 새로고침하세요."
            )
        if status == "V1" and revision not in (None, 0):
            raise HistoryConflict("다른 화면에서 보유가 바뀌었습니다 — 새로고침하세요.")
        if status == "NO_FILE" and not items:
            raise HistoryInputError("등록할 보유가 없습니다.")
        cur = compute_doc(doc)
        resolved = _match_rows(status, cur, items)
        new = _diff(doc, cur, resolved, store.today_kst())
        if not new:
            return _list_reply(status, doc), None
        at = store.now_kst()
        store.materialize(doc, at)
        for r in new:
            r.update(recorded_at=at, request_id=request_id, request_hash=fingerprint)
            records.append(r)
        result = compute_doc(doc)
        doc["holdings"] = result["holdings"]
        doc["revision"] += 1
        return _list_reply("V2", doc), doc

    return store.commit(change)


def _match_rows(status: str, cur: dict[str, Any], items: list) -> list:
    """(position_id | None, Holding). V1 의 ID 없는 구형 요청만 (종목, 계좌)로 맞춘다."""
    if status == "V1" and items and not any(pid for pid, _ in items):
        by_key: dict[tuple, list] = {}
        for h in cur["holdings"]:
            key = (_ticker_key(h["ticker"]), h["account_group"])
            by_key.setdefault(key, []).append(h["position_id"])
        out = []
        for _, h in items:
            ids = by_key.get((_ticker_key(h.ticker), h.account_group), [])
            if len(ids) > 1:
                raise HistoryConflict(
                    "같은 종목 · 계좌 줄이 여럿이라 맞출 수 없습니다 — 새로고침하세요."
                )
            out.append((ids[0] if ids else None, h))
        matched = [pid for pid, _ in out if pid]
        if len(set(matched)) != len(matched):  # 한 줄에 두 입력이 맞춰지면 줄을 잃는다
            raise HistoryConflict(
                "같은 종목 · 계좌 입력이 여럿이라 맞출 수 없습니다 — 새로고침하세요."
            )
        return out
    open_ids = {h["position_id"] for h in cur["holdings"]}
    given = [pid for pid, _ in items if pid]
    if any(pid not in open_ids for pid in given):
        raise HistoryConflict("없는 보유 줄입니다 — 새로고침하세요.")
    if len(set(given)) != len(given):
        raise HistoryInputError("같은 보유 줄이 두 번 들어 있습니다.")
    return items


def _ticker_key(ticker: str) -> str:
    """종목코드 비교 키 — 입력 경로와 같은 정규화(앞뒤 공백 · 대문자). 화면은 대문자로 보내므로
    기존 파일의 소문자 · 공백 종목코드 줄도 바꾸지 않은 저장이 '종목코드 변경' 이 되지 않는다."""
    return ticker.strip().upper()


def _exact_open(cur: dict[str, Any]) -> dict[str, tuple[str, str]]:
    """줄별 열린 기간의 정확한 (수량, 평단) — History 와 같은 계산(book.PREC). 보유 행의 숫자는
    float 호환 표현이라 float 로 나타낼 수 없는 정확한 잔량 · 평단은 여기서만 얻는다."""
    out: dict[str, tuple[str, str]] = {}
    for pos in cur["positions"]:
        for cy in pos["cycles"]:
            if cy["status"] == "OPEN":
                with localcontext() as ctx:
                    ctx.prec = book.PREC
                    avg = cy["c"] / cy["q"]
                out[pos["position_id"]] = (book.fmt(cy["q"]), book.fmt(avg))
    return out


def _register_position(
    doc: dict[str, Any], open_by_id: dict[str, Any], h: Any, fresh: set[str]
) -> str:
    """잔고 등록 줄의 position_id. Step 2C(같은 종목 · 계좌의 평단별 여러 줄)를 유지한다:
    같은 (종목, 계좌)의 과거 보유가 딱 하나이고 보유 중인 같은 줄이 없을 때만 그 줄의
    새 기간으로 잇고, 그 밖에는 새 줄을 만든다(임의 병합 없음)."""
    positions = doc["personal_trade_history"]["positions"]
    same = [
        p
        for p in positions
        if (p["ticker"], p["account_group"]) == (h.ticker, h.account_group)
    ]
    if len(same) == 1:
        pid = same[0]["position_id"]
        if pid not in open_by_id and pid not in fresh:
            fresh.add(pid)
            return pid
    pid = str(uuid.uuid4())
    positions.append(
        {
            "position_id": pid,
            "ticker": h.ticker,
            "account_group": h.account_group,
            "name": h.name,
        }
    )
    fresh.add(pid)
    return pid


def _diff(doc: dict[str, Any], cur: dict[str, Any], items: list, today: str) -> list:
    """입력 목록과 현재 보유의 차이 → 잔고 등록 · 입력 정정 기록(매매 기록은 만들지 않음)."""
    records = doc["personal_trade_history"]["records"]
    by_id = {h["position_id"]: h for h in cur["holdings"]}
    out: list[dict[str, Any]] = []

    def adjustment(old: dict[str, Any], payload: dict[str, Any]) -> None:
        cid = old["cycle_id"]
        seq = book.next_seq(records + out, cid, today, before=False)
        body = {"effective_date": today, "seq": seq, **payload}
        out.append(blank_record("ADJUSTMENT", old["position_id"], cid, body))

    exact = _exact_open(cur)
    seen: set[str] = set()
    fresh: set[str] = set()
    for pid, h in items:
        if pid is None:
            body = {
                "quantity": as_text(h.quantity),
                "avg_buy_price": as_text(h.avg_buy_price),
            }
            new_pid = _register_position(doc, by_id, h, fresh)
            out.append(blank_record("REGISTER", new_pid, str(uuid.uuid4()), body))
            continue
        seen.add(pid)
        old = by_id[pid]
        same_ticker = _ticker_key(h.ticker) == _ticker_key(old["ticker"])
        if not same_ticker or h.account_group != old["account_group"]:
            raise HistoryInputError(
                "종목코드 · 계좌는 바꿀 수 없습니다 — 그 줄을 지우고(정정 종료) 새로 등록하세요."
            )
        new_qa = (as_text(h.quantity), as_text(h.avg_buy_price))
        old_qa = (as_text(old["quantity"]), as_text(old["avg_buy_price"]))
        payload: dict[str, Any] = {}
        before: dict[str, Any] = {}
        if new_qa != old_qa:
            # 화면은 float 호환값을 보낸다 — 바꾸지 않은 칸은 이력의 정확한 값을 그대로 쓴다
            # (평단만 고쳐도 float 로 나타낼 수 없는 정확한 잔량이 깎이지 않게).
            q0, a0 = exact[pid]
            payload.update(
                quantity=q0 if new_qa[0] == old_qa[0] else new_qa[0],
                avg_buy_price=a0 if new_qa[1] == old_qa[1] else new_qa[1],
            )
            before.update(quantity=q0, avg_buy_price=a0)
        if h.name != old["name"]:
            payload["name"] = h.name
            before["name"] = old["name"]
        if payload:
            adjustment(old, {**payload, "before": before})
    for pid, old in by_id.items():
        if pid not in seen:  # 빠진 줄 = 입력 정정으로 종료(매도 아님)
            q0, a0 = exact[pid]
            payload = {"quantity": "0", "avg_buy_price": a0}
            adjustment(
                old, {**payload, "before": {"quantity": q0, "avg_buy_price": a0}}
            )
    return out


def holding_status(status: str, holdings: list) -> str:
    if status == "NO_FILE":
        return "NO_FILE"
    return "OK" if holdings else "EMPTY"


def _list_reply(status: str, doc: dict[str, Any]) -> dict[str, Any]:
    holdings = doc["holdings"] if status == "V2" else compute_doc(doc)["holdings"]
    return {
        "holdings": holdings,
        "revision": doc["revision"],
        "status": holding_status(status, holdings),
    }


def current_holdings() -> dict[str, Any]:
    """GET /holdings — {holdings(줄 ID 포함), revision, status}. 쓰기 0 · 손상은 예외."""
    state = store.read_document()
    return _list_reply(state["status"], state["doc"])
