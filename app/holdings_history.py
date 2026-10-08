"""POC5-05 개정 2 — 매매 명령(PUT /holdings/trade-history) · 입력 검증 · 공용 도우미(PC).

설계 §2 · §4 · §5 · §6 · §11 · PLAN §2-1 ~ §2-4:
- 매매 명령 한 번 = 기록 1건 추가 → 전체 재계산(holdings_book) → 현재 보유 갱신이 한 문서
  교체로 끝난다(holdings_store.commit).
- 같은 record_id 재시도: 같은 내용(정규화한 명령의 hash) → 저장된 결과 그대로 · 다른 내용 → 409.
  이 확인은 revision 확인보다 먼저다. 그다음 base_revision 이 다르면 409(새로고침).
- 입력 규칙(개정 1 재사용): 거래일 = KST 오늘 이하(휴장일 허용) · 시각 HH:MM 선택 · 수량 소수
  6자리 · 체결단가 소수 2자리 · 자릿수 초과 · NaN · Infinity = 입력 오류(반올림 · 절삭 없음).
  매매대금 = 단가 × 수량 정확값(자르지 않음).
- 입력 정정 모드 저장은 holdings_edit · History 조회는 holdings_history_view.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import re
import uuid
from datetime import date
from decimal import Decimal, DecimalException, InvalidOperation
from typing import Any, Optional

from app import holdings as holdings_module
from app import holdings_book as book
from app import holdings_store as store

QUANTITY_PLACES = 6
PRICE_PLACES = 2
MAX_INTEGER_DIGITS = 15
MEMO_MAX = 200
ACTIONS = ("buy", "sell", "sell_all", "new_position", "register", "correct", "void")
_TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


class HistoryInputError(ValueError):
    """입력 오류(422)."""


class HistoryConflict(Exception):
    """같은 ID 다른 내용 · 오래된 화면 · 대상 없음 · 계산 불가(409)."""


# ── 입력 검증 · 정규화 ──────────────────────────────────────────────────────


def _decimal(
    value: Any, field: str, places: Optional[int], *, limit: bool = True
) -> str:
    """입력 십진수: 유한 · 양수 · (limit) 정수부 15자리 미만 · (places) 소수 자릿수 —
    반올림 · 절삭 없음. places=None · limit=False 는 형식 · 유한 · 양수 · float 범위만(잔고 등록 ·
    매도 · 정정 수량 — 매매 수량 한도는 저장 경계의 _check_new_quantity 가 판정)."""
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise HistoryInputError(f"{field} 는 숫자여야 합니다.")
    text = value.strip().replace(",", "") if isinstance(value, str) else repr(value)
    try:
        d = Decimal(text)
    except InvalidOperation as e:
        raise HistoryInputError(f"{field} 는 숫자여야 합니다.") from e
    if not d.is_finite():
        raise HistoryInputError(f"{field} 는 유한한 값이어야 합니다.")
    if d <= 0:
        raise HistoryInputError(f"{field} 는 0 보다 커야 합니다.")
    if limit and d.adjusted() >= MAX_INTEGER_DIGITS:
        raise HistoryInputError(f"{field} 가 너무 큽니다.")
    # 한도 없는 값도 보유 호환 표현(float)의 범위 안이어야 한다 — 기존 보유 입력 규칙과 같다.
    if not limit:
        as_float = float(d)
        if not math.isfinite(as_float) or as_float <= 0:
            raise HistoryInputError(f"{field} 가 나타낼 수 있는 범위를 벗어났습니다.")
    if places is not None:
        try:
            exact = d == d.quantize(Decimal(1).scaleb(-places))
        except InvalidOperation as e:
            raise HistoryInputError(f"{field} 가 너무 큽니다.") from e
        if not exact:  # 반올림 · 절삭하지 않는다
            raise HistoryInputError(
                f"{field} 는 소수 {places}자리까지만 입력할 수 있습니다."
            )
    return book.fmt(d)


def valid_record_id(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return str(uuid.UUID(value)) == value.lower()
    except ValueError:
        return False


def _trade(raw: Any, *, today: str, exact_quantity: bool = False) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise HistoryInputError("trade 는 객체여야 합니다.")
    day = raw.get("trade_date")
    try:
        parsed = date.fromisoformat(day) if isinstance(day, str) else None
    except ValueError:
        parsed = None
    if parsed is None or parsed.isoformat() != day:
        raise HistoryInputError("거래일 형식은 YYYY-MM-DD 입니다.")
    if day > today:
        raise HistoryInputError("거래일은 오늘(KST) 이전이어야 합니다.")
    time_raw = raw.get("trade_time")
    if time_raw in (None, ""):
        trade_time = None
    elif isinstance(time_raw, str) and _TIME.match(time_raw):
        trade_time = time_raw
    else:
        raise HistoryInputError("거래 시각 형식은 HH:MM 입니다(모르면 비워 두세요).")
    memo = raw.get("memo")
    if memo is not None and not isinstance(memo, str):
        raise HistoryInputError("메모는 문자열이어야 합니다.")
    memo = (memo or "").strip() or None
    if memo is not None and len(memo) > MEMO_MAX:
        raise HistoryInputError(f"메모는 {MEMO_MAX}자 이하여야 합니다.")
    price = _decimal(raw.get("price"), "체결단가", PRICE_PLACES)
    # 전량매도 수량 = 서버 잔량과 정확히 같아야 한다 — 기존 기준잔고 정밀도에 새 입력의
    # 소수 6자리 한도를 소급하지 않는다(설계 §3). 같은지 확인은 _new_record 가 한다.
    places = None if exact_quantity else QUANTITY_PLACES
    quantity = _decimal(raw.get("quantity"), "수량", places, limit=not exact_quantity)
    return {
        "trade_date": day,
        "trade_time": trade_time,
        "price": price,
        "quantity": quantity,
        "amount": _amount(price, quantity),
        "memo": memo,
    }


def _amount(price: str, quantity: str) -> str:
    """매매대금 = 단가 × 수량의 정확한 곱(설계 §3 · 반올림 · 절삭 없음)."""
    try:
        return book.exact_product(price, quantity)
    except DecimalException as e:  # Inexact 등 — 입력 한도 안에서는 일어나지 않는다
        raise HistoryInputError("매매대금을 정확히 계산할 수 없는 값입니다.") from e


def _identity(raw: dict[str, Any]) -> dict[str, Any]:
    ticker = raw.get("ticker")
    ticker = ticker.strip() if isinstance(ticker, str) else ""
    if not holdings_module.TICKER_PATTERN.match(ticker):
        raise HistoryInputError("종목코드는 영숫자 6자리여야 합니다.")
    try:
        account = holdings_module.normalize_account_group(raw.get("account_group"))
    except holdings_module.HoldingsValidationError as e:
        raise HistoryInputError(str(e)) from e
    name = raw.get("name")
    name = (name.strip() or None) if isinstance(name, str) else None
    return {"ticker": ticker, "account_group": account, "name": name}


def normalize_command(req: Any, *, today: str) -> dict[str, Any]:
    """명령 → 정규화한 내용(재시도 비교 · 기록 생성의 근거). 실패면 HistoryInputError."""
    if not isinstance(req, dict):
        raise HistoryInputError("요청은 객체여야 합니다.")
    if not valid_record_id(req.get("record_id")):
        raise HistoryInputError("record_id 는 UUID 여야 합니다.")
    action = req.get("action")
    if action not in ACTIONS:
        raise HistoryInputError(f"action 은 {', '.join(ACTIONS)} 중 하나입니다.")
    base = req.get("base_revision")
    if isinstance(base, bool) or not isinstance(base, int) or base < 0:
        raise HistoryInputError("base_revision 은 0 이상의 정수입니다.")
    same_day = req.get("same_day") or "after"
    if same_day not in ("after", "before"):
        raise HistoryInputError("same_day 는 after 또는 before 입니다.")
    pid = req.get("position_id")
    if pid is not None and not isinstance(pid, str):
        raise HistoryInputError("position_id 는 문자열입니다.")
    cmd: dict[str, Any] = {"action": action}
    if action in ("buy", "sell", "sell_all"):
        if not pid:
            raise HistoryInputError("매매할 보유 줄(position_id)이 필요합니다.")
        # 매도 수량의 입력 한도는 저장 경계 안에서 판정한다(_check_new_quantity) — 잔량을 0 으로
        # 만드는 매도는 기존 잔량 정밀도 · 크기 그대로일 수 있다(설계 §3 · 소급 금지).
        exact = action != "buy"
        trade = _trade(req.get("trade"), today=today, exact_quantity=exact)
        cmd.update(position_id=pid, trade=trade)
    elif action in ("new_position", "register"):
        if pid:
            # 재매수 = 선택한 줄의 새 기간 — 종목 · 계좌는 그 줄의 값(기존 비정형 종목코드 포함)을
            # 쓴다. 보내온 종목코드를 새 입력 형식으로 다시 검사하지 않는다(소급 금지).
            cmd.update(position_id=pid, ticker=None, account_group=None, name=None)
        else:
            cmd.update(position_id=None, **_identity(req))
        if action == "new_position":
            cmd["trade"] = _trade(req.get("trade"), today=today)
        else:
            h = req.get("holding")
            if not isinstance(h, dict):
                raise HistoryInputError("holding(수량 · 평단)이 필요합니다.")
            # 잔고 등록 = 거래를 모르는 기존 잔고(매매 아님) — 입력 정정 모드의 새 줄(REGISTER)과 같은
            # 기존 보유 입력 규칙(형식 · 유한 · 양수 · 새 매매 입력의 자릿수 · 크기 한도 없음 · 설계 §3).
            cmd["holding"] = {
                "quantity": _decimal(h.get("quantity"), "수량", None, limit=False),
                "avg_buy_price": _decimal(
                    h.get("avg_buy_price"), "평단", None, limit=False
                ),
            }
    else:
        target = req.get("supersedes_id")
        if not isinstance(target, str) or not target:
            raise HistoryInputError("정정 · 취소할 기록(supersedes_id)이 필요합니다.")
        cmd["supersedes_id"] = target
        if action == "correct":
            # 수량 한도는 저장 경계 안에서 원래 기록과 비교해 판정한다(_check_new_quantity).
            cmd["trade"] = _trade(req.get("trade"), today=today, exact_quantity=True)
    if "trade" in cmd:
        cmd["same_day"] = same_day
    return cmd


def content_hash(content: Any) -> str:
    body = json.dumps(
        content, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


# ── 매매 명령 ───────────────────────────────────────────────────────────────


_KIND_TEXT = {
    "BASELINE": "기준잔고",
    "REGISTER": "잔고 등록",
    "BUY": "매수",
    "SELL": "매도",
    "ADJUSTMENT": "입력 정정",
}


def _related_text(doc: dict[str, Any], ids: list[str]) -> str:
    """409 문구에 붙일 관련 기록(날짜 · 종류 · 수량) — 어느 기록을 고칠지 알 수 있게."""
    by_id = {r["record_id"]: r for r in doc["personal_trade_history"]["records"]}
    parts = []
    for rid in ids:
        r = by_id.get(rid)
        if r is None:
            continue
        day = book.event_date(r) or "매수일 미상"
        qty = r["payload"].get("quantity")
        unit = f" {qty}주" if qty is not None else ""
        parts.append(f"{day} {_KIND_TEXT.get(r['kind'], r['kind'])}{unit}")
    return f" — 관련 기록: {', '.join(parts)}" if parts else ""


def compute_doc(doc: dict[str, Any]) -> dict[str, Any]:
    try:
        return book.compute(doc)
    except book.BookError as e:
        raise HistoryConflict(f"{e}{_related_text(doc, e.related)}") from e


def _open_cycle(cur: dict[str, Any], pid: str) -> Optional[dict[str, Any]]:
    for pos in cur["positions"]:
        if pos["position_id"] == pid:
            return next((c for c in pos["cycles"] if c["status"] == "OPEN"), None)
    return None


def resolve_position(
    doc: dict[str, Any], cur: dict[str, Any], cmd: dict[str, Any]
) -> str:
    """새 보유(최초 매수 · 잔고 등록)의 position_id — 재매수면 같은 줄 · 새 기간."""
    positions = doc["personal_trade_history"]["positions"]
    if cmd.get("position_id"):
        if not any(p["position_id"] == cmd["position_id"] for p in positions):
            raise HistoryConflict("재매수할 과거 보유 줄이 없습니다 — 새로고침하세요.")
        if _open_cycle(cur, cmd["position_id"]) is not None:
            raise HistoryConflict(
                "이미 보유 중인 줄입니다 — 그 줄의 추가매수로 입력하세요."
            )
        return cmd["position_id"]
    same = [
        p
        for p in positions
        if p["ticker"] == cmd["ticker"] and p["account_group"] == cmd["account_group"]
    ]
    if any(_open_cycle(cur, p["position_id"]) for p in same):
        raise HistoryConflict(
            "같은 종목 · 계좌를 이미 보유 중입니다 — 그 줄의 매매(추가매수)나 입력 정정을 쓰세요."
        )
    if len(same) > 1:
        raise HistoryConflict(
            "같은 종목 · 계좌의 과거 보유가 여러 줄입니다 — 과거 보유에서 재매수할 줄을 고르세요."
        )
    if same:
        return same[0]["position_id"]
    pid = str(uuid.uuid4())
    positions.append(
        {
            "position_id": pid,
            "ticker": cmd["ticker"],
            "account_group": cmd["account_group"],
            "name": cmd["name"],
        }
    )
    return pid


def _target(doc: dict[str, Any], record_id: str) -> dict[str, Any]:
    eff = book.effective_records(doc["personal_trade_history"]["records"])
    for r in eff:
        if r["record_id"] == record_id and r["kind"] in book.TRADES:
            return r
    raise HistoryConflict(
        "정정 · 취소할 수 있는 매매 기록이 아닙니다(이미 정정 · 취소됐거나 매매 기록이 아님)."
    )


def blank_record(
    kind: str, pid: str, cid: str, payload: dict[str, Any]
) -> dict[str, Any]:
    return {
        "record_id": str(uuid.uuid4()),
        "request_id": None,
        "request_hash": None,
        "recorded_at": None,
        "kind": kind,
        "position_id": pid,
        "cycle_id": cid,
        "supersedes_id": None,
        "payload": payload,
    }


def _new_record(
    doc: dict[str, Any], cur: dict[str, Any], cmd: dict[str, Any], record_id: str
) -> dict[str, Any]:
    records = doc["personal_trade_history"]["records"]
    action = cmd["action"]
    target: Optional[dict[str, Any]] = None
    if action in ("buy", "sell", "sell_all"):
        cycle = _open_cycle(cur, cmd["position_id"])
        if cycle is None:
            raise HistoryConflict("보유 중인 줄이 아닙니다 — 새로고침하세요.")
        pid, cid = cmd["position_id"], cycle["cycle_id"]
        kind = "BUY" if action == "buy" else "SELL"
        if action == "sell_all" and Decimal(cmd["trade"]["quantity"]) != cycle["q"]:
            raise HistoryConflict(
                f"전량매도 수량이 현재 잔량({book.fmt(cycle['q'])})과 다릅니다 — 새로고침하세요."
            )
    elif action in ("new_position", "register"):
        pid = resolve_position(doc, cur, cmd)
        cid = str(uuid.uuid4())
        kind = "BUY" if action == "new_position" else "REGISTER"
    else:
        target = _target(doc, cmd["supersedes_id"])
        pid, cid = target["position_id"], target["cycle_id"]
        kind = target["kind"] if action == "correct" else "VOID"
    if kind in book.TRADES:
        t = cmd["trade"]
        if target is not None and t["trade_date"] == target["payload"]["trade_date"]:
            seq = int(target["payload"]["seq"])
        else:
            before = cmd["same_day"] == "before"
            seq = book.next_seq(records, cid, t["trade_date"], before)
        payload: dict[str, Any] = {**t, "seq": seq}
    elif kind == "REGISTER":
        payload = dict(cmd["holding"])
    else:
        payload = {}
    record = blank_record(kind, pid, cid, payload)
    record["record_id"] = record_id
    record["supersedes_id"] = target["record_id"] if target is not None else None
    return record


def _check_new_quantity(
    record: dict[str, Any], result: Optional[dict[str, Any]], doc: dict[str, Any]
) -> None:
    """새로 입력한 매매 수량만 입력 한도(소수 6자리 · 정수부 15자리 미만)를 지킨다.

    한도를 적용하지 않는 경우(설계 §3 '기존 정밀도에 새 입력 한도를 소급하지 않는다'):
    - 정정에서 원래 기록과 같은 수량(이미 받아들인 값 · 단가 · 날짜만 고치는 정정)
    - 그 보유 기간의 잔량을 0 으로 만드는 매도(전량매도 · 잔량과 정확히 같은 값)
    이미 저장된 기록은 나중에 다시 검사하지 않는다. 실패면 HistoryInputError(422 · 쓰기 0).
    매수는 예외가 없어 재계산 전에(result=None) · 매도는 잔량 0 여부를 보려고 재계산 뒤에 부른다.
    """
    if record["kind"] not in book.TRADES:
        return
    qty = Decimal(record["payload"]["quantity"])
    if record["supersedes_id"]:
        by_id = {r["record_id"]: r for r in doc["personal_trade_history"]["records"]}
        original = by_id.get(record["supersedes_id"])
        if original is not None and Decimal(original["payload"]["quantity"]) == qty:
            return
    if record["kind"] == "SELL" and result is not None:
        for pos in result["positions"]:
            for cy in pos["cycles"]:
                for ev in cy["events"]:
                    if ev["record"]["record_id"] == record["record_id"]:
                        if ev["q_after"] == 0:
                            return
    _decimal(record["payload"]["quantity"], "수량", QUANTITY_PLACES)


def _public(record: dict[str, Any]) -> dict[str, Any]:
    keep = ("record_id", "kind", "recorded_at", "position_id", "cycle_id")
    return {
        **{k: record[k] for k in keep},
        "supersedes_id": record["supersedes_id"],
        "payload": record["payload"],
    }


def _reply(doc: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    return {
        "record": _public(record),
        "holdings": doc["holdings"],
        "revision": doc["revision"],
    }


def apply_command(req: Any) -> dict[str, Any]:
    """매매 명령 1건 → {record, holdings, revision}. 422 = 입력 오류 · 409 = 충돌."""
    cmd = normalize_command(req, today=store.today_kst())
    record_id = req["record_id"]
    fingerprint = content_hash(cmd)

    def change(state: dict[str, Any]):
        doc = copy.deepcopy(state["doc"])
        records = doc["personal_trade_history"]["records"]
        same = next(
            (
                r
                for r in records
                if r["record_id"] == record_id and not r.get("virtual")
            ),
            None,
        )
        if same is not None:  # 재시도 확인이 revision 확인보다 먼저다
            if same.get("request_hash") != fingerprint:
                raise HistoryConflict(
                    "같은 저장 ID 에 다른 내용이 있습니다 — 새로고침하세요."
                )
            return _reply(doc, same), None
        if doc["revision"] != req["base_revision"]:
            raise HistoryConflict(
                "다른 화면에서 보유가 바뀌었습니다 — 새로고침한 뒤 다시 입력하세요."
            )
        cur = compute_doc(doc)
        record = _new_record(doc, cur, cmd, record_id)
        at = store.now_kst()
        store.materialize(doc, at)
        record.update(recorded_at=at, request_hash=fingerprint)
        if record["kind"] == "BUY":  # 새 입력 매수 수량 — 재계산 전에 입력 오류(422)로
            _check_new_quantity(record, None, doc)
        records.append(record)
        result = compute_doc(doc)
        if record["kind"] == "SELL":  # 잔량을 0 으로 만드는 매도는 한도 예외
            _check_new_quantity(record, result, doc)
        if cmd["action"] == "sell_all":
            closed = any(
                c["cycle_id"] == record["cycle_id"] and c["status"] == "CLOSED"
                for p in result["positions"]
                for c in p["cycles"]
            )
            if not closed:
                raise HistoryConflict(
                    "전량매도 뒤에도 잔량이 남습니다 — 날짜 · 순서를 확인하세요."
                )
        doc["holdings"] = result["holdings"]
        doc["revision"] += 1
        return _reply(doc, record), doc

    return store.commit(change)


def as_text(value: Any) -> str:
    """기존 float 값을 읽은 그대로의 십진 문자열(정밀도 손실 복원이 아님)."""
    return book.fmt(Decimal(repr(float(value))))
