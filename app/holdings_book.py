"""POC5-05 개정 2 — 보유 · 매매 이력 계산(이동평균 · 보유 기간). 파일 · 네트워크 0.

설계 §3 · §4 · §6 · §11-1 Q-E · §11-2:
- 정본은 records 다. 현재 보유 · 원가 · 실현손익은 여기서 매번 다시 계산하고 저장하지 않는다.
- 기간(cycle)별 상태 = 수량 Q · 남은 원가 C. 추가매수 C += b×p · 매도분 원가 = C×s/Q ·
  실현손익 = s×p − 매도분 원가 · 남은 평단 유지 · 전량매도는 남은 C 전부 배분.
- 계산 순서: BASELINE · REGISTER(매수일 미상)로 시작한 기간은 그 기준잔고를 먼저 적용하고,
  실제 최초 매수로 시작한 기간은 Q = C = 0 에서 모든 유효 BUY · SELL 을 (날짜, seq) 순으로.
- 입력 정정(ADJUSTMENT)은 매매가 아니다. 수량 · 평단 정정 = 자기 위치(저장한 KST 날짜 맨 뒤)
  에서 Q 와 C = Q × 입력 평단을 확정 · 수량 0 = '입력 정정으로 종료'(SELL · 손익 0원 거래가
  아님) · 종목명만 정정 = 표시값만 바꿈(Q · C 불변).
- 거래 오기 정정 = 같은 kind 새 기록 + supersedes_id · 취소 = VOID. 대체 · 취소된 기록은
  계산에 남지 않는다.
- 거절(BookError): 매도 > 잔량 · 기간 중간 잔량 0 뒤 기록 · 열린 기간 둘 이상 · 닫힌 기간이
  다시 열리는데 뒤 기간이 있음 · 기간 경계 밖 거래일.
- 문서 무결성(check_document · compute 가 먼저 부른다): 허용 키 · ID 유일 · 모든 기록이 있는
  줄을 가리킴 · 기간은 한 줄에만 · 기록 없는 줄 없음 · 종류별 내용(날짜 · 양수 십진수 ·
  매매대금 = 정확한 곱 · 정수 seq) · 정정 · 취소 연결(앞선 매매 기록 · 같은 줄 · 기간 · 한 번만 ·
  정정은 같은 종류). 하나라도 어기면 손상 — 연결이 끊긴 기록을 조용히 빼고 계산하지 않는다.
"""

from __future__ import annotations

import re
from datetime import date
import math
from decimal import Decimal, Inexact, InvalidOperation, localcontext
from typing import Any, Optional

PREC = 40
ANCHORS = ("BASELINE", "REGISTER")
TRADES = ("BUY", "SELL")


class BookError(Exception):
    """records 를 계산할 수 없음(409) — 관련 기록 ID 와 함께."""

    def __init__(self, message: str, related: Optional[list[str]] = None):
        super().__init__(message)
        self.related = related or []


def dec(text: Any) -> Decimal:
    return Decimal(str(text))


def fmt(d: Optional[Decimal]) -> Optional[str]:
    """십진 문자열(지수 표기 없이 · 반올림 없이) — 화면 반올림은 UI 몫.

    normalize() 는 현재 문맥 정밀도로 반올림하므로, 값의 자릿수 이상 정밀도에서 부른다
    (기본 28자리 문맥이 매매대금 · 원가를 깎지 않게).
    """
    if d is None:
        return None
    if d == 0:
        return "0"
    with localcontext() as ctx:
        ctx.prec = max(PREC, len(d.as_tuple().digits))
        return format(d.normalize(), "f")


def exact_product(a: str, b: str) -> str:
    """두 십진 문자열의 정확한 곱(매매대금 · 자르지 않음).

    정밀도 = 두 값의 유효 자릿수 합 이상이라 어떤 크기에서도 정확하다(전량매도는 기존
    기준잔고 정밀도 그대로일 수 있음). Inexact 는 조용한 반올림을 막는 안전장치다.
    """
    da, db = dec(a), dec(b)
    with localcontext() as ctx:
        ctx.prec = max(PREC, len(da.as_tuple().digits) + len(db.as_tuple().digits) + 1)
        ctx.traps[Inexact] = True
        product = da * db
    return fmt(product)


def effective_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """대체 · 취소되지 않은 기록(VOID 자체 제외)."""
    replaced = {r["supersedes_id"] for r in records if r.get("supersedes_id")}
    return [
        r for r in records if r["record_id"] not in replaced and r["kind"] != "VOID"
    ]


def event_date(r: dict[str, Any]) -> Optional[str]:
    p = r["payload"]
    if r["kind"] in TRADES:
        return p["trade_date"]
    if r["kind"] == "ADJUSTMENT":
        return p["effective_date"]
    return None


def _order_key(r: dict[str, Any]) -> tuple:
    if r["kind"] in ANCHORS:
        return (0, "", 0)
    return (1, event_date(r), int(r["payload"]["seq"]))


def name_only(r: dict[str, Any]) -> bool:
    """종목명만 고친 입력 정정 — 표시값만 바꾸고 계산 경로(Q · C · 종료 판정)에는 없다."""
    return r["kind"] == "ADJUSTMENT" and "quantity" not in r["payload"]


# ── 문서 무결성 ─────────────────────────────────────────────────────────────

KINDS = ANCHORS + TRADES + ("ADJUSTMENT", "VOID")
DOC_KEYS = {"schema_version", "revision", "holdings", "personal_trade_history"}
HIST_KEYS = {"positions", "records"}
POSITION_KEYS = {"position_id", "ticker", "account_group", "name"}
RECORD_KEYS = {
    "record_id",
    "request_id",
    "request_hash",
    "recorded_at",
    "kind",
    "position_id",
    "cycle_id",
    "supersedes_id",
    "payload",
    "virtual",  # 저장하지 않은 V1 기준잔고(메모리 안에서만)
}
RECORD_REQUIRED = RECORD_KEYS - {"request_id", "request_hash", "virtual"}
PAYLOAD_KEYS = {
    "BASELINE": {"quantity", "avg_buy_price"},
    "REGISTER": {"quantity", "avg_buy_price"},
    "BUY": {"trade_date", "trade_time", "price", "quantity", "amount", "memo", "seq"},
    "SELL": {"trade_date", "trade_time", "price", "quantity", "amount", "memo", "seq"},
    "ADJUSTMENT": {
        "effective_date",
        "seq",
        "quantity",
        "avg_buy_price",
        "name",
        "before",
    },
    "VOID": set(),
}
_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
_DECIMAL_RE = re.compile(
    r"^\d+(\.\d+)?$"
)  # 저장 형식(fmt 결과) — 지수 · 공백 · 부호 없음
_MAX_VALUE = (
    Decimal(10) ** 15
)  # 새 매매 입력 한도(정수부 15자리 미만) — 기존 값에는 소급 안 함
MEMO_MAX = 200
ACCOUNT_MAX = 30


def _corrupt(msg: str, rid: Optional[str] = None) -> None:
    raise BookError(f"이력 문서 손상: {msg}", [rid] if rid else [])


def _text(v: Any) -> bool:
    return isinstance(v, str) and v != ""


def _number(
    p: dict,
    key: str,
    rid: str,
    *,
    zero_ok: bool = False,
    places: Optional[int] = None,
    capped: bool = False,
) -> None:
    """저장된 십진 문자열: 형식(지수 · 공백 없음) · 유한 · 양수(정정 수량만 0).

    상한(capped) · 소수 자릿수(places)는 새 매매 입력 한도라 매수 수량 · 매매 단가에만 둔다.
    기준잔고 · 잔고 등록 · 입력 정정은 기존 보유 입력 규칙(자릿수 · 크기 한도 없음 · PLAN
    §2-1 '읽은 값 그대로')이고, 전량매도 수량은 서버 잔량과 정확히 같아야 해 한도가 없다.
    """
    v = p.get(key)
    try:
        d = Decimal(v) if isinstance(v, str) and _DECIMAL_RE.match(v) else None
    except InvalidOperation:
        d = None
    if (
        d is None
        or not d.is_finite()
        or (capped and d >= _MAX_VALUE)
        or (d == 0 and not zero_ok)
        or (places is not None and d != d.quantize(Decimal(1).scaleb(-places)))
    ):
        _corrupt(f"{key} 값이 올바르지 않습니다.", rid)


def _day(v: Any) -> bool:
    try:
        return isinstance(v, str) and date.fromisoformat(v).isoformat() == v
    except ValueError:
        return False


def _check_payload(r: dict[str, Any]) -> None:
    kind, p, rid = r["kind"], r["payload"], r["record_id"]
    if not isinstance(p, dict) or set(p) - PAYLOAD_KEYS[kind]:
        _corrupt("기록 내용 형식이 올바르지 않습니다.", rid)
    recorded_day = r["recorded_at"][:10] if isinstance(r["recorded_at"], str) else None
    if kind in ANCHORS:
        _number(p, "quantity", rid)
        _number(p, "avg_buy_price", rid)
    elif kind in TRADES:
        if not _day(p.get("trade_date")) or (
            recorded_day is not None and p["trade_date"] > recorded_day
        ):
            _corrupt("거래일이 올바르지 않습니다(형식 · 저장일 이후).", rid)
        if p.get("trade_time") is not None and not (
            isinstance(p["trade_time"], str) and _TIME_RE.match(p["trade_time"])
        ):
            _corrupt("거래 시각이 올바르지 않습니다.", rid)
        _number(p, "price", rid, places=2, capped=True)
        if kind == "BUY":
            _number(p, "quantity", rid, places=6, capped=True)
        else:  # 매도 수량: 전량매도는 기존 기준잔고 정밀도 · 크기 그대로일 수 있다
            _number(p, "quantity", rid)
        try:
            exact = exact_product(p["price"], p["quantity"])
        except (ArithmeticError, KeyError):
            exact = None
        if exact is None or p.get("amount") != exact:
            _corrupt("매매대금이 단가 × 수량과 다릅니다.", rid)
        memo = p.get("memo")
        if memo is not None and not (
            isinstance(memo, str) and memo.strip() == memo and 0 < len(memo) <= MEMO_MAX
        ):
            _corrupt("메모 형식이 올바르지 않습니다.", rid)
    elif kind == "ADJUSTMENT":
        if not _day(p.get("effective_date")) or (
            recorded_day is not None and p["effective_date"] > recorded_day
        ):
            _corrupt("입력 정정 날짜가 올바르지 않습니다.", rid)
        if "quantity" in p or "avg_buy_price" in p:
            _number(p, "quantity", rid, zero_ok=True)
            _number(p, "avg_buy_price", rid)
        elif "name" not in p:
            _corrupt("입력 정정 내용이 없습니다.", rid)
        if "name" in p and p["name"] is not None and not isinstance(p["name"], str):
            _corrupt("종목명 형식이 올바르지 않습니다.", rid)
    if kind in TRADES or kind == "ADJUSTMENT":
        seq = p.get("seq")
        if isinstance(seq, bool) or not isinstance(seq, int):
            _corrupt("같은 날 순번이 올바르지 않습니다.", rid)


def check_document(doc: dict[str, Any]) -> None:
    """이력 문서 전체 무결성. 어기면 BookError(손상) — 조용히 빼고 계산하지 않는다."""
    if not isinstance(doc, dict) or set(doc) - DOC_KEYS:
        _corrupt("문서 최상위 형식이 올바르지 않습니다.")
    version, revision = doc.get("schema_version"), doc.get("revision")
    if type(version) is not int or version != 2:  # noqa: E721 — bool · float 거절
        _corrupt("문서 형식 번호가 올바르지 않습니다.")
    if type(revision) is not int or revision < 0:  # noqa: E721
        _corrupt("문서 revision 이 올바르지 않습니다.")
    hist = doc.get("personal_trade_history")
    if not isinstance(hist, dict) or set(hist) != HIST_KEYS:
        _corrupt("이력 형식이 올바르지 않습니다.")
    positions, records = hist["positions"], hist["records"]
    if not isinstance(positions, list) or not isinstance(records, list):
        _corrupt("이력 형식이 올바르지 않습니다.")
    pos_ids: set[str] = set()
    for pos in positions:
        if not isinstance(pos, dict) or set(pos) != POSITION_KEYS:
            _corrupt("보유 줄 형식이 올바르지 않습니다.")
        pid = pos["position_id"]
        if not _text(pid) or pid in pos_ids:
            _corrupt("보유 줄 ID 가 없거나 겹칩니다.")
        acct = pos["account_group"]
        if not (
            _text(pos["ticker"])
            and pos["ticker"].strip()
            and isinstance(acct, str)
            and acct == acct.strip()
            and 0 < len(acct) <= ACCOUNT_MAX
        ):
            _corrupt("보유 줄의 종목 · 계좌가 올바르지 않습니다.")
        if pos["name"] is not None and not isinstance(pos["name"], str):
            _corrupt("보유 줄의 종목명 형식이 올바르지 않습니다.")
        pos_ids.add(pid)
    by_id: dict[str, dict[str, Any]] = {}
    cycle_owner: dict[str, str] = {}
    superseded: set[str] = set()
    used_positions: set[str] = set()
    for r in records:
        if not isinstance(r, dict) or set(r) - RECORD_KEYS or RECORD_REQUIRED - set(r):
            _corrupt("기록 형식이 올바르지 않습니다.")
        rid = r["record_id"]
        if not _text(rid) or rid in by_id:
            _corrupt("기록 ID 가 없거나 겹칩니다.")
        if r["kind"] not in KINDS:
            _corrupt("알 수 없는 기록 종류입니다.", rid)
        if r["position_id"] not in pos_ids:
            _corrupt("기록이 없는 보유 줄을 가리킵니다(연결 끊김).", rid)
        if not _text(r["cycle_id"]):
            _corrupt("보유 기간 ID 가 없습니다.", rid)
        if cycle_owner.setdefault(r["cycle_id"], r["position_id"]) != r["position_id"]:
            _corrupt("한 보유 기간이 여러 줄에 걸쳐 있습니다.", rid)
        virtual = r.get("virtual")
        if virtual not in (None, True) or (
            not _text(r["recorded_at"]) and not (virtual and r["recorded_at"] is None)
        ):
            _corrupt("기록 시각이 올바르지 않습니다.", rid)
        _check_payload(r)
        sid = r["supersedes_id"]
        if r["kind"] == "VOID" and sid is None:
            _corrupt("취소 기록에 대상이 없습니다.", rid)
        if sid is not None:
            target = by_id.get(sid)  # 앞선 기록만 — 순환 연결 불가
            if (
                target is None
                or target["kind"] not in TRADES
                or r["kind"] not in (target["kind"], "VOID")
                or (target["position_id"], target["cycle_id"])
                != (r["position_id"], r["cycle_id"])
                or sid in superseded
            ):
                _corrupt("정정 · 취소 연결이 올바르지 않습니다.", rid)
            superseded.add(sid)
        by_id[rid] = r
        used_positions.add(r["position_id"])
    if pos_ids - used_positions:
        _corrupt("기록이 없는 보유 줄이 있습니다.")
    # 계산 순서 = (날짜, seq) — 같은 기간 · 같은 날 유효 기록의 seq 가 겹치면 순서가 저장
    # 순서에 기대게 되므로 손상이다.
    slots: set[tuple] = set()
    for r in effective_records(records):
        day = event_date(r)
        if day is None:
            continue
        slot = (r["cycle_id"], day, r["payload"]["seq"])
        if slot in slots:
            _corrupt("같은 날 순번이 겹칩니다.", r["record_id"])
        slots.add(slot)


def replay_cycle(records: list[dict[str, Any]]) -> dict[str, Any]:
    """한 기간의 유효 기록을 계산 순서로 적용한다. 실패면 BookError."""
    anchors = [r for r in records if r["kind"] in ANCHORS]
    if len(anchors) > 1:
        raise BookError(
            "한 보유 기간에 기준잔고 · 잔고 등록이 둘 이상입니다.",
            [r["record_id"] for r in anchors],
        )
    ordered = sorted(records, key=_order_key)
    events: list[dict[str, Any]] = []
    q = c = Decimal(0)
    realized = sold_cost = Decimal(0)
    adjusted = False
    closed_by: Optional[str] = None
    closing: Optional[dict[str, Any]] = None
    with localcontext() as ctx:
        ctx.prec = PREC
        for r in ordered:
            if closing is not None and not name_only(r):
                raise BookError(
                    "보유가 0 이 된 뒤에 같은 기간의 기록이 있습니다 — 날짜 · 순서를 확인하세요.",
                    [closing["record_id"], r["record_id"]],
                )
            p = r["payload"]
            ev: dict[str, Any] = {"record": r}
            kind = r["kind"]
            if kind in ANCHORS:
                q = dec(p["quantity"])
                c = q * dec(p["avg_buy_price"])
            elif kind == "BUY":
                b, price = dec(p["quantity"]), dec(p["price"])
                q, c = q + b, c + b * price
            elif kind == "SELL":
                s, price = dec(p["quantity"]), dec(p["price"])
                if s > q:
                    raise BookError(
                        f"{p['trade_date']} 매도 수량이 그 시점 잔량({fmt(q)})보다 많습니다.",
                        [r["record_id"]],
                    )
                cost = c if s == q else c * s / q
                pnl = s * price - cost
                ev.update(
                    cost_of_sold=cost, realized_pnl=pnl, realized_rate=pnl / cost * 100
                )
                realized, sold_cost = realized + pnl, sold_cost + cost
                q, c = q - s, c - cost
                if q == 0:
                    c = Decimal(0)
                    closed_by, closing = "SELL", r
            elif kind == "ADJUSTMENT" and "quantity" in p:
                adjusted = True
                q = dec(p["quantity"])
                c = q * dec(p["avg_buy_price"]) if q > 0 else Decimal(0)
                if q == 0:
                    closed_by, closing = "ADJUSTMENT", r
            ev.update(q_after=q, c_after=c, avg_after=(c / q) if q > 0 else None)
            events.append(ev)
    opened_by = anchors[0]["kind"] if anchors else "BUY"
    buys = [r for r in ordered if r["kind"] == "BUY"]
    return {
        "events": events,
        "q": q,
        "c": c,
        "status": "OPEN" if q > 0 else "CLOSED",
        "closed_by": closed_by,
        "opened_by": opened_by,
        "start_date": (
            buys[0]["payload"]["trade_date"] if opened_by == "BUY" and buys else None
        ),
        "end_date": event_date(closing) if closing is not None else None,
        "first_date": next(
            (event_date(r) for r in ordered if event_date(r) and not name_only(r)),
            None,
        ),
        "realized": realized,
        "sold_cost": sold_cost,
        "has_adjustment": adjusted,
    }


def current_name(
    position: dict[str, Any], records: list[dict[str, Any]]
) -> Optional[str]:
    """종목명 = 등록 값 → 유효한 입력 정정의 name 이 저장 순서대로 덮는다(표시값)."""
    name = position.get("name")
    for r in records:
        if r["kind"] == "ADJUSTMENT" and "name" in r["payload"]:
            name = r["payload"]["name"]
    return name


def compute(doc: dict[str, Any]) -> dict[str, Any]:
    """문서 전체 계산 → {positions: [...], holdings: [...]}. 손상 · 계산 불가면 BookError."""
    check_document(doc)
    hist = doc["personal_trade_history"]
    records = hist["records"]
    eff = effective_records(records)
    out_positions = []
    holdings = []
    for pos in hist["positions"]:
        pid = pos["position_id"]
        mine = [r for r in eff if r["position_id"] == pid]
        cycle_ids: list[str] = []
        for r in records:  # 기간 순서 = 그 기간 첫 기록의 저장 순서
            if r["position_id"] == pid and r["cycle_id"] not in cycle_ids:
                cycle_ids.append(r["cycle_id"])
        cycles = []
        for cid in cycle_ids:
            rs = [r for r in mine if r["cycle_id"] == cid]
            kinds = {r["kind"] for r in rs}
            if not kinds & {"BASELINE", "REGISTER", "BUY"}:
                # 시작 기록(기준잔고 · 잔고 등록 · 유효 매수)이 없는 기간 = 없는 기간(설계 §11-2:
                # 최초 BUY 취소 뒤 다른 유효 매수가 없으면 현재 보유에서 빠진다). 매도가 남았으면
                # 계산할 수 없는 손상이다. 입력 정정만 남은 기간도 경계 계산에 넣지 않는다.
                if "SELL" in kinds:
                    raise BookError(
                        "매수 없이 매도만 남은 보유 기간입니다 — 관련 기록을 정정하세요.",
                        [r["record_id"] for r in rs if r["kind"] == "SELL"],
                    )
                continue
            cycles.append({"cycle_id": cid, **replay_cycle(rs)})
        _check_cycles(cycles)
        name = current_name(pos, mine)
        out_positions.append({**pos, "name": name, "cycles": cycles})
        open_cycle = next((cy for cy in cycles if cy["status"] == "OPEN"), None)
        if open_cycle is not None:
            with localcontext() as ctx:
                ctx.prec = PREC
                avg = open_cycle["c"] / open_cycle["q"]
            qf, af = float(open_cycle["q"]), float(avg)
            if not (math.isfinite(qf) and math.isfinite(af) and qf > 0 and af > 0):
                raise BookError("보유 수량 · 평단을 숫자로 나타낼 수 없습니다(손상).")
            holdings.append(
                {
                    "ticker": pos["ticker"],
                    "quantity": qf,
                    "avg_buy_price": af,
                    "name": name,
                    "account_group": pos["account_group"],
                    "position_id": pid,
                    "cycle_id": open_cycle["cycle_id"],
                }
            )
    return {"positions": out_positions, "holdings": holdings}


def _check_cycles(cycles: list[dict[str, Any]]) -> None:
    """열린 기간은 마지막 하나뿐 · 뒤 기간의 날짜는 **앞선 모든 기간**의 가장 늦은 종료일 이후
    (같은 날 허용) — 인접한 기간만 보면 종료일 없는 기간 하나로 경계를 건너뛸 수 있다."""
    latest_end: Optional[str] = None
    for i, cy in enumerate(cycles):
        if i < len(cycles) - 1 and cy["status"] == "OPEN":
            ids = [e["record"]["record_id"] for e in cy["events"][-1:]]
            raise BookError(
                "끝난 보유 기간이 다시 열려 그 뒤의 보유 기간과 겹칩니다 — 관련 기록을 정정하세요.",
                ids,
            )
        if latest_end and cy["first_date"] and cy["first_date"] < latest_end:
            raise BookError(
                f"이전 보유 기간 종료일({latest_end})보다 앞선 날짜의 기록입니다 — "
                "그 기간의 기록으로 입력하세요.",
                [cy["events"][0]["record"]["record_id"]],
            )
        if cy["end_date"] and (latest_end is None or cy["end_date"] > latest_end):
            latest_end = cy["end_date"]


def next_seq(
    records: list[dict[str, Any]], cycle_id: str, day: str, before: bool
) -> int:
    """같은 기간 · 같은 날 기존 기록의 맨 뒤(기본) 또는 맨 앞."""
    same = [
        int(r["payload"]["seq"])
        for r in effective_records(records)
        if r["cycle_id"] == cycle_id and event_date(r) == day
    ]
    if not same:
        return 0
    return min(same) - 1 if before else max(same) + 1
