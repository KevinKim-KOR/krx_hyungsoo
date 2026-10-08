"""POC5-05 개정 2 — 보유 · 매매 이력 저장 경계 · 매매 명령 · 입력 정정 · History(API · tmp 파일).

설계 §5 · §6 · §9 수용 기준 1 · 3 ~ 7 · §11 · PLAN §3. 보유 파일은 conftest 가 tmp 로 바꿔 끼운
holdings.HOLDINGS_FILE 만 쓴다(라이브 파일 0).
"""

from __future__ import annotations

import ast
import hashlib
import json
import threading
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import api as api_module
from app import holdings as holdings_module
from app import holdings_store as store

TODAY = "2026-10-08"
TH = "/holdings/trade-history"
V1_ROWS = [
    {
        "ticker": "069500",
        "quantity": 10,
        "avg_buy_price": 10000,
        "name": "KODEX 200",
        "account_group": "ISA",
    },
    {
        "ticker": "005930",
        "quantity": 3,
        "avg_buy_price": 71200.5,
        "name": "삼성전자",
        "account_group": "연금",
    },
    {
        "ticker": "069500",
        "quantity": 0.1234567,
        "avg_buy_price": 35000.123,
        "name": "KODEX 200",
        "account_group": "일반",
    },
]


@pytest.fixture(autouse=True)
def _today(monkeypatch):
    monkeypatch.setattr(store, "today_kst", lambda: TODAY)


@pytest.fixture
def client():
    return TestClient(api_module.app)


def _file() -> Path:
    return holdings_module.HOLDINGS_FILE


def _write_v1(rows=V1_ROWS):
    _file().parent.mkdir(parents=True, exist_ok=True)
    _file().write_text(
        json.dumps({"holdings": rows}, ensure_ascii=False), encoding="utf-8"
    )


def _sha() -> str:
    return hashlib.sha256(_file().read_bytes()).hexdigest()


def _doc() -> dict:
    return json.loads(_file().read_text(encoding="utf-8"))


def _cmd(client, **body):
    body.setdefault("record_id", str(uuid.uuid4()))
    return client.put(TH, json=body)


def _trade(day=TODAY, price="12000", qty="5", **kw):
    return {"trade_date": day, "price": price, "quantity": qty, **kw}


def _ids(client):
    g = client.get("/holdings").json()
    return g, [h["position_id"] for h in g["holdings"]]


# ── 3 · 기존 보유(V1) → 기준잔고 · 조회는 쓰지 않음 ─────────────────────────


def test_reads_do_not_write_and_v1_ids_are_stable(client):
    assert client.get("/holdings").json() == {
        "holdings": [],
        "revision": 0,
        "status": "NO_FILE",
    }
    assert client.get(TH).json()["status"] == "NO_FILE"
    assert not _file().exists()  # 조회가 파일을 만들지 않는다
    _write_v1()
    before = _sha()
    g1, ids1 = _ids(client)
    client.get(TH)
    g2, ids2 = _ids(client)
    assert (
        _sha() == before
        and ids1 == ids2
        and g1["revision"] == 0
        and g1["status"] == "OK"
    )
    hist = client.get(TH).json()
    assert all(
        c["opened_by"] == "BASELINE" for p in hist["positions"] for c in p["cycles"]
    )
    assert all(
        e["recorded_at"] is None
        for p in hist["positions"]
        for c in p["cycles"]
        for e in c["events"]
    )


def test_first_change_materializes_baseline_for_every_row(client):
    _write_v1()
    _, ids = _ids(client)
    r = _cmd(client, base_revision=0, action="buy", position_id=ids[0], trade=_trade())
    assert r.status_code == 200 and r.json()["revision"] == 1
    doc = _doc()
    recs = doc["personal_trade_history"]["records"]
    bases = [x for x in recs if x["kind"] == "BASELINE"]
    assert (
        len(bases) == 3
        and all(x["recorded_at"] for x in bases)
        and not any("virtual" in x for x in recs)
    )
    assert [x["payload"] for x in bases] == [
        {"quantity": "10", "avg_buy_price": "10000"},
        {"quantity": "3", "avg_buy_price": "71200.5"},
        {
            "quantity": "0.1234567",
            "avg_buy_price": "35000.123",
        },  # 기준잔고는 자릿수 한도 소급 없음
    ]
    rows = {h["position_id"]: h for h in doc["holdings"]}
    assert (
        rows[ids[1]]["quantity"] == 3.0 and rows[ids[1]]["avg_buy_price"] == 71200.5
    )  # 다른 줄 불변
    assert (
        rows[ids[2]]["quantity"] == 0.1234567
        and rows[ids[2]]["avg_buy_price"] == 35000.123
    )
    assert rows[ids[0]]["quantity"] == 15.0  # 다른 계좌의 같은 종목과 섞이지 않음
    hist = client.get(TH).json()
    base_cycle = next(p for p in hist["positions"] if p["position_id"] == ids[1])[
        "cycles"
    ][0]
    assert (
        base_cycle["opened_by"] == "BASELINE" and base_cycle["start_date"] is None
    )  # 매수일 미상


# ── 1 · 2 · 매매 한 번 = 보유와 이력이 같이 바뀜 ─────────────────────────────


def test_each_trade_is_one_file_replace_and_section3_example(client, monkeypatch):
    _write_v1(V1_ROWS[:1])
    _, (pid,) = _ids(client)
    writes = []
    real = store._atomic_write
    monkeypatch.setattr(store, "_atomic_write", lambda d: (writes.append(1), real(d)))
    steps = [
        ("buy", _trade("2026-10-06", "12000", "5"), 15.0),
        ("sell", _trade("2026-10-07", "13000", "6"), 9.0),
        ("sell_all", _trade("2026-10-08", "10000", "9"), None),
    ]
    for rev, (action, trade, qty) in enumerate(steps):
        r = _cmd(client, base_revision=rev, action=action, position_id=pid, trade=trade)
        assert r.status_code == 200, r.text
        body = r.json()
        assert len(writes) == rev + 1
        cur = [h for h in body["holdings"] if h["position_id"] == pid]
        assert (cur[0]["quantity"] if cur else None) == qty
        assert client.get("/holdings").json()["holdings"] == body["holdings"]
    cy = client.get(TH).json()["positions"][0]["cycles"][0]
    sells = [e for e in cy["events"] if e["kind"] == "SELL"]
    assert [
        (e["cost_of_sold"], e["realized_pnl"], e["realized_rate"]) for e in sells
    ] == [
        ("64000", "14000", "21.875"),
        ("96000", "-6000", "-6.25"),
    ]
    assert (cy["status"], cy["realized_pnl"], cy["realized_rate"]) == (
        "CLOSED",
        "8000",
        "5",
    )
    buy_ev = next(e for e in cy["events"] if e["kind"] == "BUY")
    assert buy_ev["payload"]["amount"] == "60000"


def test_new_position_register_and_rebuy_link(client):
    r = _cmd(
        client,
        base_revision=0,
        action="new_position",
        ticker="305540",
        account_group="일반",
        name="TIGER 2차전지테마",
        trade=_trade("2026-09-01", "10000", "100"),
    )
    assert r.status_code == 200
    pid = r.json()["record"]["position_id"]
    assert (
        _cmd(
            client,
            base_revision=1,
            action="new_position",
            ticker="305540",
            account_group="일반",
            trade=_trade(),
        ).status_code
        == 409
    )  # 보유 중 → 추가매수로
    assert (
        _cmd(
            client,
            base_revision=1,
            action="sell_all",
            position_id=pid,
            trade=_trade("2026-09-22", "9425", "100"),
        ).status_code
        == 200
    )
    r = _cmd(
        client,
        base_revision=2,
        action="new_position",
        position_id=pid,
        ticker="305540",
        account_group="일반",
        trade=_trade("2026-10-02", "9850", "20"),
    )
    assert r.status_code == 200
    pos = client.get(TH, params={"position_id": pid}).json()["positions"][0]
    assert [c["status"] for c in pos["cycles"]] == ["CLOSED", "OPEN"]
    assert pos["cycles"][1]["avg_buy_price"] == "9850"  # 이전 기간 원가를 넘기지 않음
    r = _cmd(
        client,
        base_revision=3,
        action="register",
        ticker="069500",
        account_group="ISA",
        holding={"quantity": "3", "avg_buy_price": "35000"},
    )
    assert r.status_code == 200 and r.json()["record"]["kind"] == "REGISTER"
    early = _cmd(
        client,
        base_revision=4,
        action="buy",
        position_id=pid,
        trade=_trade("2026-09-10", "1", "1"),
    )
    assert early.status_code == 409  # 이전 기간 종료일보다 앞 날짜


def test_ambiguous_closed_positions_require_explicit_rebuy(client):
    for acct_rev in (0, 2):
        r = (
            _cmd(
                client,
                base_revision=acct_rev,
                action="register",
                ticker="000660",
                account_group="연금",
                holding={"quantity": "1", "avg_buy_price": "100"},
            )
            if acct_rev == 0
            else None
        )
    # 같은 (종목, 계좌) 과거 줄 2개 만들기: 등록 → 정정 종료 → 입력 정정 모드로 새 줄 등록 → 정정 종료
    g, ids = _ids(client)
    assert (
        client.put(
            "/holdings", json={"holdings": [], "revision": g["revision"]}
        ).status_code
        == 200
    )
    g = client.get("/holdings").json()
    row = {
        "ticker": "000660",
        "quantity": 2,
        "avg_buy_price": 200,
        "account_group": "연금",
    }
    assert (
        client.put(
            "/holdings", json={"holdings": [row], "revision": g["revision"]}
        ).status_code
        == 200
    )
    hist = client.get(TH).json()
    assert len(hist["positions"]) == 1  # 과거 줄이 하나면 그 줄의 새 기간으로 잇는다
    g = client.get("/holdings").json()
    second = {**row, "avg_buy_price": 300}
    rows = [{**row, "position_id": g["holdings"][0]["position_id"]}, second]
    assert (
        client.put(
            "/holdings", json={"holdings": rows, "revision": g["revision"]}
        ).status_code
        == 200
    )
    assert len(client.get(TH).json()["positions"]) == 2  # Step 2C: 평단별 여러 줄 유지
    g = client.get("/holdings").json()
    assert (
        client.put(
            "/holdings", json={"holdings": [], "revision": g["revision"]}
        ).status_code
        == 200
    )
    r = _cmd(
        client,
        base_revision=client.get("/holdings").json()["revision"],
        action="new_position",
        ticker="000660",
        account_group="연금",
        trade=_trade(),
    )
    assert r.status_code == 409 and "고르세요" in r.json()["detail"]


# ── 4 · 실패 · 재시도 · 오래된 화면 · 동시 요청 ──────────────────────────────


def test_failure_before_replace_keeps_file(client, monkeypatch):
    _write_v1()
    before = _sha()
    _, ids = _ids(client)

    def boom(*a, **k):
        raise OSError("주입")

    monkeypatch.setattr(store.os, "replace", boom)
    with pytest.raises(OSError):
        _cmd(client, base_revision=0, action="buy", position_id=ids[0], trade=_trade())
    assert _sha() == before
    assert not [
        p for p in _file().parent.iterdir() if p.name.startswith(".holdings-")
    ]  # 임시 파일 정리


def test_same_id_retry_and_conflicts_and_retry_before_revision(client):
    _write_v1()
    _, ids = _ids(client)
    rid = str(uuid.uuid4())
    body = {
        "record_id": rid,
        "base_revision": 0,
        "action": "buy",
        "position_id": ids[0],
        "trade": _trade(),
    }
    first = client.put(TH, json=body).json()
    again = client.put(
        TH, json=body
    )  # 응답 유실 뒤 같은 요청 — base_revision 은 이제 낡았다
    assert again.status_code == 200 and again.json() == first
    assert (
        _doc()["revision"] == 1 and _doc()["holdings"][0]["quantity"] == 15.0
    )  # 한 번만 반영
    same_value = {**body, "trade": _trade(price="12000.00", qty="5.000")}
    assert (
        client.put(TH, json=same_value).status_code == 200
    )  # 정규화가 같으면 같은 내용
    assert client.put(TH, json={**body, "trade": _trade(qty="6")}).status_code == 409
    stale = _cmd(
        client, base_revision=0, action="buy", position_id=ids[0], trade=_trade()
    )
    assert stale.status_code == 409 and "새로고침" in stale.json()["detail"]


def test_concurrent_saves_are_serialized(client):
    _write_v1()
    _, ids = _ids(client)
    results = []

    def go():
        results.append(
            _cmd(
                client,
                base_revision=0,
                action="buy",
                position_id=ids[0],
                trade=_trade(),
            ).status_code
        )

    ts = [threading.Thread(target=go) for _ in range(2)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert sorted(results) == [200, 409]
    assert _doc()["holdings"][0]["quantity"] == 15.0


def test_correct_and_void_recompute_and_keep_trail(client):
    _write_v1(V1_ROWS[:1])
    _, (pid,) = _ids(client)
    b = _cmd(
        client, base_revision=0, action="buy", position_id=pid, trade=_trade(qty="5")
    ).json()
    rid = b["record"]["record_id"]
    c = _cmd(
        client,
        base_revision=1,
        action="correct",
        supersedes_id=rid,
        trade=_trade(qty="2"),
    )
    assert c.status_code == 200 and c.json()["holdings"][0]["quantity"] == 12.0
    assert (
        _cmd(
            client, base_revision=2, action="correct", supersedes_id=rid, trade=_trade()
        ).status_code
        == 409
    )
    new_id = c.json()["record"]["record_id"]
    v = _cmd(client, base_revision=2, action="void", supersedes_id=new_id)
    assert v.status_code == 200 and v.json()["holdings"][0]["quantity"] == 10.0
    assert (
        _cmd(
            client,
            base_revision=3,
            action="void",
            supersedes_id=v.json()["record"]["record_id"],
        ).status_code
        == 409
    )
    cy = client.get(TH).json()["positions"][0]["cycles"][0]
    assert [e["kind"] for e in cy["events"]] == ["BASELINE"]
    assert [x["record_id"] for x in cy["voided"]] == [new_id]
    oversell = _cmd(
        client, base_revision=3, action="sell", position_id=pid, trade=_trade(qty="11")
    )
    assert oversell.status_code == 409 and "잔량" in oversell.json()["detail"]
    assert (
        _cmd(
            client,
            base_revision=3,
            action="sell_all",
            position_id=pid,
            trade=_trade(qty="9"),
        ).status_code
        == 409
    )


def test_voiding_only_buy_keeps_trail_at_position_level(client):
    r = _cmd(
        client,
        base_revision=0,
        action="new_position",
        ticker="305540",
        account_group="일반",
        trade=_trade("2026-10-01", "10000", "1"),
    )
    rid = r.json()["record"]["record_id"]
    assert (
        _cmd(client, base_revision=1, action="void", supersedes_id=rid).status_code
        == 200
    )
    assert client.get("/holdings").json()["status"] == "EMPTY"
    pos = client.get(TH).json()["positions"][0]
    assert pos["cycles"] == [] and [v["record_id"] for v in pos["voided"]] == [
        rid
    ]  # 기록은 남는다


def test_name_only_correction_does_not_block_earlier_full_sell(client):
    _write_v1([{**V1_ROWS[0], "name": None}])
    g, (pid,) = _ids(client)
    rows = [{**g["holdings"][0], "name": "KODEX 200"}]
    assert (
        client.put("/holdings", json={"holdings": rows, "revision": 0}).status_code
        == 200
    )
    r = _cmd(
        client,
        base_revision=1,
        action="sell_all",
        position_id=pid,
        trade=_trade("2026-10-05", "11000", "10"),
    )
    assert r.status_code == 200, r.text  # 종목명 정정은 계산 경로에 없다(설계 §11-1)
    cy = client.get(TH).json()["positions"][0]["cycles"][0]
    assert (cy["status"], cy["closed_by"], cy["end_date"]) == (
        "CLOSED",
        "SELL",
        "2026-10-05",
    )
    assert cy["realized_pnl"] == "10000"


def test_conflict_detail_lists_related_records(client):
    _write_v1(V1_ROWS[:1])  # 기준잔고 10주
    _, (pid,) = _ids(client)
    ok = _cmd(
        client,
        base_revision=0,
        action="sell",
        position_id=pid,
        trade=_trade("2026-10-08", "11000", "6"),
    )
    assert ok.status_code == 200
    # 앞 날짜로 5주 매도를 끼워 넣으면 10-08 매도 6주가 잔량(5)을 넘는다.
    r = _cmd(
        client,
        base_revision=1,
        action="sell",
        position_id=pid,
        trade=_trade("2026-10-07", "11000", "5"),
    )
    assert r.status_code == 409
    assert "관련 기록: 2026-10-08 매도 6주" in r.json()["detail"]


def test_full_sell_of_legacy_fractional_balance(client):
    _write_v1([{**V1_ROWS[0], "quantity": 0.1234567}])
    _, (pid,) = _ids(client)
    r = _cmd(
        client,
        base_revision=0,
        action="sell_all",
        position_id=pid,
        trade=_trade(price="11000", qty="0.1234567"),
    )
    assert (
        r.status_code == 200
    ), r.text  # 기준잔고 정밀도에 새 입력 자릿수 한도를 소급하지 않는다
    assert r.json()["holdings"] == []
    bad = _cmd(
        client,
        base_revision=1,
        action="buy",
        position_id=pid,
        trade=_trade(qty="0.1234567"),
    )
    assert bad.status_code == 422  # 새 매매 입력은 소수 6자리 한도 그대로


def test_legacy_put_matching_two_inputs_to_one_row_is_409(client):
    _write_v1(V1_ROWS[:1])
    before = _sha()
    rows = [{**V1_ROWS[0]}, {**V1_ROWS[0], "quantity": 5, "avg_buy_price": 35000}]
    r = client.put("/holdings", json={"holdings": rows})  # 구형 화면 · ID 없음
    assert r.status_code == 409 and _sha() == before  # 줄을 조용히 잃지 않는다


def test_legacy_save_refuses_corrupt_file(client):
    _file().parent.mkdir(parents=True, exist_ok=True)
    _file().write_bytes(b"{broken")
    with pytest.raises(holdings_module.HoldingsValidationError):
        holdings_module.save([holdings_module.Holding("069500", 1.0, 1.0)])
    assert _file().read_bytes() == b"{broken"


# ── 5 · 전량매도 · 정상 빈 보유 · 손상 ──────────────────────────────────────


def test_all_sold_is_normal_empty_and_corrupt_is_not(client):
    _write_v1(V1_ROWS[:1])
    _, (pid,) = _ids(client)
    assert (
        _cmd(
            client,
            base_revision=0,
            action="sell_all",
            position_id=pid,
            trade=_trade(qty="10", price="11000"),
        ).status_code
        == 200
    )
    g = client.get("/holdings").json()
    assert (g["holdings"], g["status"]) == ([], "EMPTY")
    assert holdings_module.load() == []  # 공용 로더 = 정상 빈 보유
    assert (
        holdings_module.serialize_payload([])
        == json.dumps({"holdings": []}, indent=2).encode()
    )
    hist = client.get(TH).json()["positions"][0]
    assert hist["is_open"] is False and hist["cycles"][0]["realized_pnl"] == "10000"
    _file().write_bytes(b"{not json")
    before = _sha()
    assert client.get("/holdings").status_code == 500
    assert client.get(TH).status_code == 500
    assert (
        _cmd(
            client, base_revision=1, action="buy", position_id=pid, trade=_trade()
        ).status_code
        == 500
    )
    assert client.put("/holdings", json={"holdings": V1_ROWS[:1]}).status_code == 500
    assert _sha() == before  # 손상 파일 위에 쓰지 않는다


# ── 6 · 입력 정정 모드(PUT /holdings) ───────────────────────────────────────


def test_edit_mode_records_adjustments_not_trades(client):
    _write_v1(V1_ROWS[:2])
    g, ids = _ids(client)
    rows = [dict(h) for h in g["holdings"]]
    rows[0]["quantity"] = 12
    rows[0]["avg_buy_price"] = 9500
    rows[1]["name"] = "삼성전자우"
    r = client.put(
        "/holdings",
        json={"holdings": rows, "revision": 0, "request_id": str(uuid.uuid4())},
    )
    assert r.status_code == 200 and r.json()["revision"] == 1
    recs = _doc()["personal_trade_history"]["records"]
    adjs = [x for x in recs if x["kind"] == "ADJUSTMENT"]
    assert len(adjs) == 2 and not [x for x in recs if x["kind"] in ("BUY", "SELL")]
    qa = next(a for a in adjs if a["position_id"] == ids[0])["payload"]
    assert (qa["quantity"], qa["avg_buy_price"], qa["before"]) == (
        "12",
        "9500",
        {"quantity": "10", "avg_buy_price": "10000"},
    )
    name_only = next(a for a in adjs if a["position_id"] == ids[1])["payload"]
    assert "quantity" not in name_only and name_only["name"] == "삼성전자우"
    hist = {p["position_id"]: p for p in client.get(TH).json()["positions"]}
    assert hist[ids[0]]["cycles"][0]["has_adjustment"] is True
    assert (
        hist[ids[1]]["cycles"][0]["has_adjustment"] is False
    )  # 종목명 정정은 원가 기준 변경 아님
    assert hist[ids[1]]["cycles"][0]["cost"] == "213601.5"


def test_edit_mode_revision_rules_noop_and_removal(client):
    _write_v1(V1_ROWS[:2])
    g, ids = _ids(client)
    rows = g["holdings"]
    same = client.put("/holdings", json={"holdings": rows, "revision": 0})
    assert same.status_code == 200 and same.json()["revision"] == 0
    assert (
        holdings_module.is_history_document(_doc()) is False
    )  # 변화 없음 = 쓰기 0(변환도 없음)
    rid = str(uuid.uuid4())
    r = client.put(
        "/holdings", json={"holdings": rows[:1], "revision": 0, "request_id": rid}
    )
    assert r.status_code == 200 and [
        h["position_id"] for h in r.json()["holdings"]
    ] == [ids[0]]
    again = client.put(
        "/holdings", json={"holdings": rows[:1], "revision": 0, "request_id": rid}
    )
    assert (
        again.status_code == 200 and again.json()["revision"] == 1
    )  # 재시도 = 기록 추가 0
    assert (
        client.put("/holdings", json={"holdings": rows[:1]}).status_code == 409
    )  # 이력 문서 · revision 없음
    assert (
        client.put("/holdings", json={"holdings": rows[:1], "revision": 0}).status_code
        == 409
    )
    closed = next(
        p for p in client.get(TH).json()["positions"] if p["position_id"] == ids[1]
    )
    cy = closed["cycles"][0]
    assert (cy["status"], cy["closed_by"], cy["realized_pnl"]) == (
        "CLOSED",
        "ADJUSTMENT",
        "0",
    )
    assert cy["events"][-1]["realized_pnl"] is None  # 정정 종료는 손익 대상 아님
    moved = [{**rows[0], "ticker": "069501"}]
    assert (
        client.put("/holdings", json={"holdings": moved, "revision": 1}).status_code
        == 422
    )


def test_legacy_idless_put_on_v1_matches_by_ticker_account(client):
    _write_v1(V1_ROWS[:2])
    _, ids = _ids(client)
    rows = [dict(r) for r in V1_ROWS[:2]]
    rows[1]["quantity"] = 4
    r = client.put(
        "/holdings", json={"holdings": rows}
    )  # 구형 화면 · ID · revision 없음
    assert r.status_code == 200
    assert [h["position_id"] for h in r.json()["holdings"]] == ids
    assert r.json()["holdings"][1]["quantity"] == 4.0


# ── 입력 검증 422 ───────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "over",
    [
        {"trade_date": "2026-10-09"},
        {"trade_date": "2026-10-8"},
        {"trade_time": "24:00"},
        {"price": "1.234"},
        {"price": "0"},
        {"price": "NaN"},
        {"quantity": "1.1234567"},
        {"quantity": "Infinity"},
        {"quantity": True},
        {"quantity": "1e20"},
        {"memo": "가" * 201},
    ],
)
def test_invalid_trade_input_is_422_and_writes_nothing(client, over):
    _write_v1()
    before = _sha()
    _, ids = _ids(client)
    r = _cmd(
        client,
        base_revision=0,
        action="buy",
        position_id=ids[0],
        trade={**_trade(), **over},
    )
    assert r.status_code == 422, over
    assert _sha() == before


@pytest.mark.parametrize(
    "body",
    [
        {"record_id": "x", "base_revision": 0, "action": "buy"},
        {"record_id": str(uuid.uuid4()), "base_revision": 0, "action": "upsert"},
        {
            "record_id": str(uuid.uuid4()),
            "base_revision": -1,
            "action": "void",
            "supersedes_id": "a",
        },
        {"record_id": str(uuid.uuid4()), "base_revision": 0, "action": "void"},
        {
            "record_id": str(uuid.uuid4()),
            "base_revision": 0,
            "action": "register",
            "ticker": "111",
        },
    ],
)
def test_bad_command_shapes_are_422(client, body):
    assert client.put(TH, json=body).status_code == 422


def test_same_day_before_inserts_ahead_of_existing_record(client):
    _write_v1(V1_ROWS[:1])
    _, (pid,) = _ids(client)
    s = _cmd(
        client,
        base_revision=0,
        action="sell",
        position_id=pid,
        trade=_trade(qty="12", price="11000"),
    )
    assert s.status_code == 409  # 기준잔고 10 주 → 12 주 매도 불가
    b = _cmd(
        client, base_revision=0, action="buy", position_id=pid, trade=_trade(qty="5")
    )
    assert b.status_code == 200
    late = _cmd(
        client,
        base_revision=1,
        action="sell",
        position_id=pid,
        trade=_trade(qty="12", price="11000"),
    )
    assert late.status_code == 200
    ahead = _cmd(
        client,
        base_revision=2,
        action="buy",
        position_id=pid,
        same_day="before",
        trade=_trade(qty="1", price="1000"),
    )
    assert ahead.status_code == 200
    kinds = [
        e["kind"] for e in client.get(TH).json()["positions"][0]["cycles"][0]["events"]
    ]
    assert kinds == [
        "BASELINE",
        "BUY",
        "BUY",
        "SELL",
    ]  # '앞' 으로 넣은 매수가 같은 날 맨 앞
    seqs = [
        e["payload"].get("seq")
        for e in client.get(TH).json()["positions"][0]["cycles"][0]["events"][1:]
    ]
    assert seqs == [-1, 0, 1]


def test_holiday_and_timeless_trade_dates_are_kept(client):
    _write_v1(V1_ROWS[:1])
    _, (pid,) = _ids(client)
    r = _cmd(
        client,
        base_revision=0,
        action="buy",
        position_id=pid,
        trade=_trade("2026-10-05", "1,000.5", "1"),
    )
    p = r.json()["record"]["payload"]
    assert (p["trade_date"], p["trade_time"], p["price"], p["amount"]) == (
        "2026-10-05",
        None,
        "1000.5",
        "1000.5",
    )


# ── 7 · OCI payload 경계 · 다른 자료 · 모듈 경계 ────────────────────────────


def test_history_document_payload_has_only_allowed_fields(client):
    _write_v1(V1_ROWS[:1])
    _, (pid,) = _ids(client)
    _cmd(
        client,
        base_revision=0,
        action="buy",
        position_id=pid,
        trade=_trade(memo="메모"),
    )
    payload = holdings_module.serialize_payload(holdings_module.load())
    text = payload.decode()
    assert json.loads(text) == {
        "holdings": [
            {
                "ticker": "069500",
                "quantity": 15.0,
                "avg_buy_price": 10666.666666666666,
                "name": "KODEX 200",
                "account_group": "ISA",
            }
        ]
    }
    for word in (
        "personal_trade_history",
        "position_id",
        "cycle_id",
        "메모",
        "revision",
    ):
        assert word not in text
    with pytest.raises(holdings_module.HoldingsValidationError):
        holdings_module.save(
            holdings_module.load()
        )  # 구판 writer 는 이력 문서를 덮어쓰지 않는다


def test_market_flow_route_reads_only_404_and_read_failure(
    client, tmp_path, monkeypatch
):
    from app import market_data_store
    from app.market_briefing import calendar as cal

    db = tmp_path / "market" / "market_data.sqlite"
    monkeypatch.setattr(market_data_store, "DEFAULT_DB_PATH", db)
    monkeypatch.setattr(cal, "CALENDAR_DIR", tmp_path / "market_meta")
    _write_v1(V1_ROWS[:1])
    _, (pid,) = _ids(client)
    r = _cmd(
        client,
        base_revision=0,
        action="buy",
        position_id=pid,
        trade=_trade("2026-10-06"),
    )
    cid = r.json()["record"]["cycle_id"]
    before = _sha()
    url = f"{TH}/market-flow"
    assert (
        client.get(url, params={"position_id": pid, "cycle_id": "x"}).status_code == 404
    )
    ok = client.get(url, params={"position_id": pid, "cycle_id": cid})
    assert ok.status_code == 200
    body = ok.json()
    assert (
        body["read_only"] is True
        and body["db_present"] is False
        and body["purchase_date_unknown"] is True
    )
    assert [e["ticker"]["reason_code"] for e in body["events"]] == ["NO_DB"]
    assert (
        not db.exists() and _sha() == before
    )  # 시세 DB 를 만들지 않고 보유 파일도 그대로
    db.parent.mkdir(parents=True)
    db.write_bytes(b"not a sqlite file" * 64)
    bad = client.get(url, params={"position_id": pid, "cycle_id": cid})
    assert bad.status_code == 500 and "시세 DB 조회 실패" in bad.json()["detail"]
    assert (
        client.get(TH).status_code == 200
    )  # 시장 흐름 실패와 무관하게 History 는 조회된다


def test_new_modules_have_no_network_or_oci_imports():
    root = Path(__file__).resolve().parents[1] / "app"
    banned = (
        "subprocess",
        "requests",
        "httpx",
        "telegram",
        "ledger_store",
        "holdings_oci_apply",
        "paramiko",
    )
    for name in (
        "holdings_store",
        "holdings_book",
        "holdings_history",
        "holdings_edit",
        "holdings_history_view",
        "api_holdings",
        "api_holdings_history",
    ):
        tree = ast.parse((root / f"{name}.py").read_text(encoding="utf-8"))
        mods = [
            a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names
        ]
        mods += [
            n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)
        ]
        assert not [m for m in mods if any(b in m for b in banned)], name
