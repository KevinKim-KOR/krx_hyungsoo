"""POC5-07 — 기존 보유의 가격 비교 기준일(REFERENCE_DATE · 설계 §2 ~ §6 · §9 · PLAN §2 · §3 · §7).

보유 파일은 conftest 가 tmp 로 바꿔 끼운 holdings.HOLDINGS_FILE 만 쓴다. 시세 DB · 캘린더 · 연구
산출물도 tmp(라이브 state 0 · 외부 조회 0).
"""

from __future__ import annotations

import copy
import socket
import uuid
from collections import Counter
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import api as api_module
from app import holdings as holdings_module
from app import holdings_book as book
from app import holdings_market_flow as mf
from app import holdings_oci_apply
from app import holdings_reference_date as reference_module
from app import holdings_store as store
from app import market_data_store
from app.market_briefing import calendar as cal
from app.reentry_review import model as reentry_model
from app.reentry_review import review
from tests.test_poc5_05_holdings_history import _doc, _sha, _write_v1
from tests.test_poc5_05_market_flow import ETF, FDR, NAVER, STOCK
from tests.test_poc5_05_market_flow import _calendar, _db, _etf, _kospi
from tests.test_poc5_06_reentry_review import DATES as DATES06
from tests.test_poc5_06_reentry_review import ETF as ETF06
from tests.test_poc5_06_reentry_review import TODAY as TODAY06
from tests.test_poc5_06_reentry_review import _market_db

TODAY = "2026-10-08"
TH = "/holdings/trade-history"
REF = "2026-01-02"


@pytest.fixture(autouse=True)
def _today(monkeypatch):
    monkeypatch.setattr(store, "today_kst", lambda: TODAY)


@pytest.fixture
def client():
    return TestClient(api_module.app)


# ── 도우미 ───────────────────────────────────────────────────────────────────


def _hist(client) -> dict:
    return client.get(TH).json()


def _ref(client, targets, day=REF, *, request_id=None, base=None):
    if base is None:
        base = _hist(client)["revision"]
    return client.put(
        TH,
        json={
            "action": "reference_date",
            "request_id": request_id or str(uuid.uuid4()),
            "base_revision": base,
            "reference_date": day,
            "targets": targets,
        },
    )


def _target(pid: str, cid: str) -> dict:
    return {"position_id": pid, "cycle_id": cid}


def _anchor_targets(client) -> list[dict]:
    return [
        _target(p["position_id"], c["cycle_id"])
        for p in _hist(client)["positions"]
        for c in p["cycles"]
        if c["opened_by"] in book.ANCHORS
    ]


def _cycle(client, cid: str) -> dict:
    return next(
        c
        for p in _hist(client)["positions"]
        for c in p["cycles"]
        if c["cycle_id"] == cid
    )


_CALC = (
    "cycle_id",
    "status",
    "opened_by",
    "closed_by",
    "start_date",
    "end_date",
    "has_adjustment",
    "quantity",
    "cost",
    "avg_buy_price",
    "realized_pnl",
    "sold_cost",
    "realized_rate",
)


def _calc(client) -> dict:
    """기준일을 뺀 계산 결과 전부 — 수량 · 원가 · 손익 · 기간 · 사건 · 보유 · OCI payload."""
    hist = _hist(client)
    cycles = [
        (
            p["position_id"],
            tuple(c[k] for k in _CALC),
            tuple((e["record_id"], e["kind"], e["q_after"]) for e in c["events"]),
            tuple(v["record_id"] for v in c["voided"]),
        )
        for p in hist["positions"]
        for c in p["cycles"]
    ]
    return {
        "cycles": cycles,
        "holdings": client.get("/holdings").json()["holdings"],
        "payload": holdings_oci_apply.current_payload_sha256(),
    }


def _trade(day, price, qty):
    return {"trade_date": day, "price": price, "quantity": qty}


def _cmd(client, **body):
    body.setdefault("record_id", str(uuid.uuid4()))
    body.setdefault("base_revision", _hist(client)["revision"])
    res = client.put(TH, json=body)
    assert res.status_code == 200, res.text
    return res.json()


def _pid(client, ticker: str, account: str) -> str:
    return next(
        p["position_id"]
        for p in _hist(client)["positions"]
        if p["ticker"] == ticker and p["account_group"] == account
    )


# ── §6-1 계산 불변 · V1 첫 전환 ──────────────────────────────────────────────


def test_v1_first_set_keeps_ids_calc_and_oci_payload(client):
    _write_v1()
    before = _calc(client)
    targets = _anchor_targets(client)
    rid = str(uuid.uuid4())
    res = _ref(client, targets, request_id=rid)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "V2" and body["revision"] == 1
    assert sorted(body["changed"]) == sorted(t["cycle_id"] for t in targets)
    assert _calc(client) == before  # 줄 · 기간 ID · 수량 · 평단 · 손익 · payload 그대로
    doc = _doc()
    recs = doc["personal_trade_history"]["records"]
    assert Counter(r["kind"] for r in recs) == {"BASELINE": 3, "REFERENCE_DATE": 3}
    for r in recs:
        assert "virtual" not in r
        if r["kind"] == "REFERENCE_DATE":
            assert r["payload"] == {"reference_date": REF}
            assert r["request_id"] == rid and r["request_hash"]
            assert r["supersedes_id"] is None and r["recorded_at"].endswith("+09:00")
    for c in (c for p in _hist(client)["positions"] for c in p["cycles"]):
        assert c["reference_date"] == REF and c["opened_by"] == "BASELINE"
        assert c["start_date"] is None  # 실제 매수일은 계속 미상
        assert [e["kind"] for e in c["events"]] == ["BASELINE"]  # 기준일은 사건 아님
    rec = {"status": "OCI_APPLIED", "last_applied_sha256": before["payload"]}
    assert holdings_oci_apply.pending_apply(rec) is False  # OCI 미적용 변경 없음


# ── §6-1 계산 불변 · 실제 매매가 있는 V2 · 종료 기간 ─────────────────────────


def test_v2_with_trades_set_change_clear_keep_calc(client):
    _write_v1()
    a = _pid(client, "069500", "ISA")
    _cmd(client, action="buy", position_id=a, trade=_trade("2026-03-02", "11000", "2"))
    _cmd(client, action="sell", position_id=a, trade=_trade("2026-05-04", "12000", "3"))
    b = _pid(client, "069500", "일반")
    _cmd(
        client,
        action="sell_all",
        position_id=b,
        trade=_trade("2026-06-01", "36000", "0.1234567"),
    )
    cid_a = next(p for p in _hist(client)["positions"] if p["position_id"] == a)[
        "cycles"
    ][0]["cycle_id"]
    cid_b = next(p for p in _hist(client)["positions"] if p["position_id"] == b)[
        "cycles"
    ][0]["cycle_id"]
    before = _calc(client)
    for day in (REF, "2026-02-02", None):  # 설정 → 수정 → 해제
        res = _ref(client, [_target(a, cid_a)], day)
        assert res.status_code == 200 and res.json()["changed"] == [cid_a]
        assert _calc(client) == before
        assert _cycle(client, cid_a)["reference_date"] == day
    closed = _ref(client, [_target(b, cid_b)])  # 종료된 기준잔고 기간도 설정 가능
    assert closed.status_code == 200, closed.text
    cy = _cycle(client, cid_b)
    assert cy["status"] == "CLOSED" and cy["closed_by"] == "SELL"
    assert cy["reference_date"] == REF and _calc(client) == before
    kinds = [r["kind"] for r in _doc()["personal_trade_history"]["records"]]
    assert kinds.count("REFERENCE_DATE") == 4


# ── §6-2 일괄 원자성 · 재시도 · 충돌 ─────────────────────────────────────────


def test_bulk_is_one_write_and_retries_conflicts_leave_no_partial(client, monkeypatch):
    _write_v1()
    targets = _anchor_targets(client)
    rid = str(uuid.uuid4())
    first = _ref(client, targets, request_id=rid, base=0)
    assert first.status_code == 200 and first.json()["revision"] == 1
    saved = _sha()
    again = _ref(client, targets, request_id=rid, base=0)  # 응답 유실 뒤 같은 요청
    assert again.status_code == 200 and again.json() == first.json()
    assert _sha() == saved  # 중복 기록 · 쓰기 0
    other = _ref(client, targets, "2026-02-02", request_id=rid, base=0)
    assert other.status_code == 409 and "같은 저장 ID" in other.json()["detail"]
    stale = _ref(client, targets, "2026-02-02", base=0)
    assert stale.status_code == 409 and "새로고침" in stale.json()["detail"]
    missing = _ref(client, [targets[0], _target(targets[0]["position_id"], "nope")])
    assert missing.status_code == 409 and _sha() == saved  # 일부만 저장 없음

    def boom(*_a, **_k):
        raise OSError("replace failed")

    monkeypatch.setattr(store.os, "replace", boom)
    req = {
        "action": "reference_date",
        "request_id": str(uuid.uuid4()),
        "base_revision": 1,
        "reference_date": "2026-02-02",
        "targets": targets,
    }
    with pytest.raises(OSError):
        reference_module.apply_reference_dates(req)
    folder = holdings_module.HOLDINGS_FILE.parent
    assert _sha() == saved and not list(folder.glob(".holdings-*"))  # 교체 전 실패


# ── §6-3 구분 · 재매수 · 변경 없음 ───────────────────────────────────────────


def test_accounts_rebuy_buy_cycles_and_no_change(client):
    _write_v1()
    a, b = _pid(client, "069500", "ISA"), _pid(client, "069500", "일반")
    ta = next(t for t in _anchor_targets(client) if t["position_id"] == a)
    tb = next(t for t in _anchor_targets(client) if t["position_id"] == b)
    assert _ref(client, [ta]).status_code == 200
    assert _cycle(client, tb["cycle_id"])["reference_date"] is None  # 다른 계좌 그대로
    _cmd(
        client,
        action="sell_all",
        position_id=a,
        trade=_trade("2026-06-01", "12000", "10"),
    )
    _cmd(
        client,
        action="new_position",
        position_id=a,
        trade=_trade("2026-07-01", "13000", "4"),
    )
    cycles = next(p for p in _hist(client)["positions"] if p["position_id"] == a)[
        "cycles"
    ]
    old, new = cycles
    assert old["reference_date"] == REF and old["start_date"] is None
    assert new["opened_by"] == "BUY" and new["reference_date"] is None  # 복사 없음
    assert new["start_date"] == "2026-07-01"
    saved, rev = _sha(), _hist(client)["revision"]
    buy = _ref(client, [_target(a, new["cycle_id"])])
    assert buy.status_code == 422 and "기준잔고" in buy.json()["detail"]
    mixed = _ref(client, [tb, _target(a, new["cycle_id"])])  # 일괄 안의 매수 기간 하나
    assert mixed.status_code == 422 and _sha() == saved  # 일부만 저장 없음
    assert _cycle(client, tb["cycle_id"])["reference_date"] is None
    same = _ref(client, [ta])  # 같은 값 재설정
    clear = _ref(client, [tb], None)  # 미설정 해제
    for res, cid in ((same, ta["cycle_id"]), (clear, tb["cycle_id"])):
        assert res.status_code == 200 and res.json()["changed"] == []
        assert res.json()["unchanged"] == [cid] and res.json()["revision"] == rev
    assert _sha() == saved
    all_kinds = {e["kind"] for c in cycles for e in c["events"]}
    assert "REFERENCE_DATE" not in all_kinds and "REFERENCE_DATE" not in {
        v["kind"] for c in cycles for v in c["voided"]
    }


def test_register_period_and_adjustment_closed_period(client):
    _write_v1()
    rev = _hist(client)["revision"]
    _cmd(
        client,
        action="register",
        base_revision=rev,
        ticker="102110",
        account_group="ISA",
        name="TIGER 200",
        holding={"quantity": "7", "avg_buy_price": "30000"},
    )
    p = _pid(client, "102110", "ISA")
    cy = next(x for x in _hist(client)["positions"] if x["position_id"] == p)["cycles"][
        0
    ]
    assert cy["opened_by"] == "REGISTER"
    target = _target(p, cy["cycle_id"])
    assert target in _anchor_targets(client)
    assert _ref(client, [target]).status_code == 200
    rows = [
        h for h in client.get("/holdings").json()["holdings"] if h["ticker"] != "102110"
    ]
    put = client.put(
        "/holdings", json={"holdings": rows, "revision": _hist(client)["revision"]}
    )  # 남은 잔고를 입력 정정으로 종료
    assert put.status_code == 200, put.text
    closed = _cycle(client, cy["cycle_id"])
    assert closed["status"] == "CLOSED" and closed["closed_by"] == "ADJUSTMENT"
    before = _calc(client)
    changed = _ref(client, [target], "2026-02-02")  # 매도 없는 정정 종료 기간도 수정
    assert changed.status_code == 200 and _calc(client) == before
    assert _cycle(client, cy["cycle_id"])["reference_date"] == "2026-02-02"


def test_last_stored_record_wins_not_latest_recorded_at(client):
    """저장 순서 마지막 기록이 유효 — 저장 시각을 정렬해 과거 설정을 되살리지 않는다(§9-1)."""
    doc, ref = _saved_doc_with_reference(client)
    later = {
        **ref,
        "record_id": str(uuid.uuid4()),
        "recorded_at": "2026-01-03T09:00:00+09:00",  # 앞 기록보다 이른 시각 · 저장은 뒤
        "payload": {"reference_date": "2026-01-03"},
    }
    doc["personal_trade_history"]["records"].append(later)
    cycles = {
        c["cycle_id"]: c for p in book.compute(doc)["positions"] for c in p["cycles"]
    }
    assert cycles[ref["cycle_id"]]["reference_date"] == "2026-01-03"


# ── §6-4 입력 규칙 ───────────────────────────────────────────────────────────


def test_input_rules(client):
    _write_v1()
    t = _anchor_targets(client)[0]
    for day in ("2026-10-09", "2026-1-2", "2026-02-30", "20260102", 20260102):
        res = _ref(client, [t], day)
        assert res.status_code == 422, day
    assert "오늘(2026-10-08)" in _ref(client, [t], "2026-10-09").json()["detail"]
    holiday = _ref(client, [t], "2026-01-01")  # 휴장일 · 가격 없는 날도 설정은 된다
    assert holiday.status_code == 200, holiday.text
    base = {
        "action": "reference_date",
        "request_id": str(uuid.uuid4()),
        "base_revision": 1,
        "reference_date": REF,
        "targets": [t],
    }
    for bad in (
        {"request_id": "x"},
        {"targets": []},
        {"targets": [t, t]},
        {"targets": [_target("p", f"c{i}") for i in range(201)]},
        {"targets": [{**t, "extra": 1}]},
        {"targets": [{"position_id": "", "cycle_id": "c"}]},
        {"base_revision": True},
        {"base_revision": -1},
        {"extra": 1},
    ):
        res = client.put(TH, json={**base, **bad})
        assert res.status_code == 422, bad
    no_key = {k: v for k, v in base.items() if k != "reference_date"}
    res = client.put(
        TH, json=no_key
    )  # 칸이 없으면 '해제'로 받지 않는다(해제 = null 명시)
    assert res.status_code == 422 and _cycle(client, t["cycle_id"])[
        "reference_date"
    ] == ("2026-01-01")


# ── 무결성(설계 §3 · 판정 §9-2-1 KST 날짜) ───────────────────────────────────


def _saved_doc_with_reference(client) -> tuple[dict, dict]:
    _write_v1()
    assert _ref(client, _anchor_targets(client)[:1]).status_code == 200
    doc = _doc()
    ref = next(
        r
        for r in doc["personal_trade_history"]["records"]
        if r["kind"] == "REFERENCE_DATE"
    )
    return doc, ref


def _broken(doc: dict, ref_id: str, change) -> dict:
    d = copy.deepcopy(doc)
    r = next(
        x for x in d["personal_trade_history"]["records"] if x["record_id"] == ref_id
    )
    change(d, r)
    return d


def test_integrity_rules_and_kst_midnight(client):
    doc, ref = _saved_doc_with_reference(client)
    rid = ref["record_id"]
    book.compute(doc)  # 정상
    assert holdings_module.holdings_from_document(doc)  # 공용 읽기 경로도 이해한다
    baseline = next(
        r
        for r in doc["personal_trade_history"]["records"]
        if r["kind"] == "BASELINE" and r["cycle_id"] == ref["cycle_id"]
    )
    other = next(
        r
        for r in doc["personal_trade_history"]["records"]
        if r["kind"] == "BASELINE" and r["position_id"] != ref["position_id"]
    )

    def at(recorded: str, day: str):
        def change(_d, r):
            r["recorded_at"], r["payload"] = recorded, {"reference_date": day}

        return change

    ok = [
        at("2026-10-10T15:00:05+00:00", "2026-10-11"),  # UTC 전날 15시대 = KST 10-11
        at("2026-10-11T00:00:05+09:00", "2026-10-11"),
    ]
    for change in ok:
        book.compute(_broken(doc, rid, change))
    bad = [
        lambda _d, r: r.update(payload={}),
        lambda _d, r: r.update(payload={"reference_date": REF, "x": 1}),
        lambda _d, r: r.update(payload={"reference_date": "2026-13-01"}),
        at("2026-10-10T15:00:05+00:00", "2026-10-12"),  # KST 저장일 이후
        at("2026-10-11T00:00:05", "2026-10-11"),  # 시간대 없음
        lambda _d, r: r.update(supersedes_id=baseline["record_id"]),
        lambda _d, r: r.update(cycle_id=other["cycle_id"]),  # 다른 줄의 기간
        lambda _d, r: r.update(kind="REFERENCE_DATEX"),  # 알 수 없는 종류 그대로 손상
        lambda d, r: d["personal_trade_history"]["records"].append(
            {
                **r,
                "record_id": str(uuid.uuid4()),
                "kind": "VOID",
                "supersedes_id": rid,
                "payload": {},
            }
        ),  # 기준일은 취소 대상이 아니다
    ]
    for change in bad:
        broken = _broken(doc, rid, change)
        with pytest.raises(book.BookError):
            book.compute(broken)
        with pytest.raises(holdings_module.HoldingsValidationError):
            holdings_module.holdings_from_document(broken)


def test_reference_on_buy_started_cycle_is_corrupt(client):
    _write_v1()
    a = _pid(client, "069500", "ISA")
    _cmd(
        client,
        action="sell_all",
        position_id=a,
        trade=_trade("2026-06-01", "12000", "10"),
    )
    _cmd(
        client,
        action="new_position",
        position_id=a,
        trade=_trade("2026-07-01", "13000", "4"),
    )
    doc = _doc()
    buy_cycle = next(
        c["cycle_id"]
        for p in _hist(client)["positions"]
        for c in p["cycles"]
        if c["opened_by"] == "BUY"
    )
    book.compute(doc)  # 그 전까지는 정상
    rec = {
        "record_id": str(uuid.uuid4()),
        "request_id": None,
        "request_hash": None,
        "recorded_at": "2026-10-08T10:00:00+09:00",
        "kind": "REFERENCE_DATE",
        "position_id": a,
        "cycle_id": buy_cycle,
        "supersedes_id": None,
        "payload": {"reference_date": REF},
    }
    doc["personal_trade_history"]["records"].append(rec)
    with pytest.raises(book.BookError, match="기준잔고 · 잔고 등록으로 시작한 기간"):
        book.compute(doc)


# ── §4 · §6-4 시장 흐름(tmp 시세 DB · 05 규칙 재사용) ────────────────────────


def _anchor_cycle(status: str, *events, reference=REF, opened_by="BASELINE") -> dict:
    return {
        "cycle_id": "cyc-1",
        "opened_by": opened_by,
        "status": status,
        "events": [{"record_id": r, "kind": k, "trade_date": d} for r, k, d in events],
        "reference_date": reference,
    }


@pytest.fixture
def flow_env(tmp_path):
    db, caldir = _db(tmp_path), _calendar(tmp_path)
    prices = {
        "2026-01-02": (100.0, NAVER),
        "2026-03-02": (110.0, FDR),
        "2026-10-07": (120.0, FDR),
    }
    _etf(db, ETF, prices)
    _kospi(db, {d: (c * 30, NAVER) for d, (c, _) in prices.items()})
    return db, caldir


def _flow(env, cycle, ticker=ETF):
    db, caldir = env
    return mf.build_market_flow(
        ticker=ticker, cycle=cycle, db_path=db, calendar_dir=caldir
    )


def test_market_flow_reference_items(flow_env):
    db, _ = flow_env
    before = Path(db).read_bytes()
    out = _flow(flow_env, _anchor_cycle("OPEN"))
    rf = out["reference_flow"]
    assert rf["name"] == "가격 비교 기준일 이후 종가 변화"
    assert rf["window_label"] == "가격 비교 기준일 → 마지막 저장일"
    assert rf["ticker"]["status"] == mf.STATUS_OK
    assert Decimal(rf["ticker"]["change_pct"]) == Decimal("20")
    assert (
        rf["ticker"]["start_date"] == REF and rf["latest_stored_date"] == "2026-10-07"
    )
    assert rf["market"]["status"] == mf.STATUS_OK  # KOSPI 같은 두 날짜
    assert out["purchase_date_unknown"] is True and out["reference_note"]
    assert (
        out["holding_period"]["reason_code"] == "CYCLE_OPEN"
    )  # 미상이어도 숨기지 않음

    holiday = _flow(flow_env, _anchor_cycle("OPEN", reference="2026-01-01"))
    basis = holiday["reference_flow"]["basis"]
    assert basis["basis_date"] == REF and basis["moved_to_next_trading_day"] is True
    no_row = _flow(flow_env, _anchor_cycle("OPEN", reference="2026-02-02"))
    assert no_row["reference_flow"]["ticker"]["reason_code"] == "BASIS_ROW_MISSING"
    late = _flow(flow_env, _anchor_cycle("OPEN", reference="2026-10-08"))
    assert late["reference_flow"]["ticker"]["reason_code"] == "LATEST_BEFORE_BASIS"

    sold = _flow(flow_env, _anchor_cycle("CLOSED", ("s1", "SELL", "2026-03-02")))
    hp = sold["holding_period"]
    assert hp["computed"] is True and hp["start_record_id"] is None
    assert hp["window_label"] == "가격 비교 기준일 → 마지막 매도 기준일"
    assert hp["end_record_id"] == "s1" and Decimal(hp["ticker"]["change_pct"]) == 10
    assert sold["events"][0]["window_label"] == "매도 기준일 → 마지막 저장일"
    reversed_ = _flow(
        flow_env,
        _anchor_cycle("CLOSED", ("s1", "SELL", "2026-03-02"), reference="2026-05-04"),
    )
    assert reversed_["holding_period"]["ticker"]["reason_code"] == "WINDOW_INVALID"
    topped = _flow(  # 기준잔고 기간의 추가매수 뒤 매도 — 시작은 첫 매수가 아니라 기준일
        flow_env,
        _anchor_cycle(
            "CLOSED", ("b1", "BUY", "2026-03-02"), ("s1", "SELL", "2026-10-07")
        ),
    )
    thp = topped["holding_period"]
    assert thp["start_basis"]["basis_date"] == REF and thp["start_record_id"] is None
    assert Decimal(thp["ticker"]["change_pct"]) == Decimal("20")
    adjusted = _flow(flow_env, _anchor_cycle("CLOSED"))  # 매도 없는 입력 정정 종료
    assert adjusted["holding_period"]["reason_code"] == "NO_SELL"
    assert adjusted["reference_flow"] is not None

    none = _flow(flow_env, _anchor_cycle("OPEN", reference=None))
    assert none["reference_flow"] is None and none["reference_date"] is None
    assert none["holding_period"]["reason_code"] == "PURCHASE_DATE_UNKNOWN"
    stock = _flow(flow_env, _anchor_cycle("OPEN"), ticker=STOCK)
    assert stock["reference_flow"]["ticker"]["reason_code"] == "STOCK_NOT_COLLECTED"
    with pytest.raises(ValueError):
        _flow(flow_env, _anchor_cycle("OPEN", opened_by="BUY"))
    with pytest.raises(ValueError):
        _flow(flow_env, _anchor_cycle("OPEN", reference="2026-1-2"))
    assert Path(db).read_bytes() == before  # 읽기 전용


# ── §5 · §6-5 History · 시장 흐름 조회 쓰기 0 · 06 ML 불변 ───────────────────


@pytest.fixture
def env06(tmp_path, monkeypatch):
    db = tmp_path / "market06.sqlite"
    _market_db(db)
    caldir = tmp_path / "cal06"
    caldir.mkdir()
    monkeypatch.setattr(market_data_store, "DEFAULT_DB_PATH", db)
    monkeypatch.setattr(cal, "CALENDAR_DIR", caldir)
    monkeypatch.setattr(review, "RESEARCH_ROOT", tmp_path / "research" / "poc5_06")
    monkeypatch.setattr(store, "today_kst", lambda: TODAY06)
    _write_v1(
        [
            {
                "ticker": ETF06,
                "quantity": 10,
                "avg_buy_price": 10000,
                "name": "KODEX 200",
                "account_group": "ISA",
            }
        ]
    )
    return db


def test_reads_do_not_write_and_reentry_ml_is_unchanged(client, env06, monkeypatch):
    t = _anchor_targets(client)[0]
    q = {"position_id": t["position_id"], "cycle_id": t["cycle_id"]}
    ml1 = client.post(TH + "/reentry-review/ml", json=q).json()
    assert ml1["status"] == "OK"
    day = DATES06[-100]

    def no_model(*_a, **_k):
        raise AssertionError("기준일 설정 · 조회에서 학습하지 않는다")

    def no_db(*_a, **_k):
        raise AssertionError("기준일 설정은 시세 DB 를 열지 않는다")

    def no_net(*_a, **_k):
        raise AssertionError("기준일 설정 · 조회는 외부 조회를 하지 않는다")

    with monkeypatch.context() as m:  # 이 블록의 막기만 되돌린다(tmp 격리는 유지)
        m.setattr(reentry_model, "fit_predict", no_model)
        m.setattr(mf.lop, "open_ro", no_db)
        m.setattr(socket.socket, "connect", no_net)
        m.setattr(socket, "create_connection", no_net)
        assert _ref(client, [t], day).status_code == 200
        with_hist = client.get(TH).json()  # History 열기도 학습 · 시세 DB 0
        assert with_hist["positions"][0]["cycles"][0]["reference_date"] == day
    saved, db_bytes = _sha(), env06.read_bytes()
    flow = client.get(TH + "/market-flow", params=q).json()
    client.get(TH)
    rv = client.get(TH + "/reentry-review", params=q).json()
    assert _sha() == saved and env06.read_bytes() == db_bytes  # 조회 쓰기 0
    assert flow["reference_date"] == day
    assert flow["reference_flow"]["ticker"]["status"] == mf.STATUS_OK
    assert rv["stored_evidence"]["market_flow"]["reference_flow"] is not None
    ml2 = client.post(TH + "/reentry-review/ml", json=q).json()
    assert ml2["result"] == ml1["result"]  # 표본 · 검증 MAE · 추정값 같음
    assert ml2["canonical_sha256"] == ml1["canonical_sha256"]  # 같은 가격 입력
    assert ml2["read_basis"]["doc_sha256"] != ml1["read_basis"]["doc_sha256"]
    assert ml2["read_basis"]["revision"] == ml1["read_basis"]["revision"] + 1
