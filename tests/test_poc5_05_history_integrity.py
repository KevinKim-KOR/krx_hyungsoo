"""POC5-05 개정 2 — 이력 문서 손상 판정 · 기존 값 소급 금지 · 새 입력 한도(API · tmp 파일).

설계 §3 · §6 · §9 · §11 · PLAN §2-1 · §3. 손상 문서는 모든 층에서 손상으로, 기존 V1 값 · 이미
받아들인 값은 손상이나 새 입력 한도 위반으로 보지 않는다. 보유 파일은 conftest 가 tmp 로 바꿔
끼운 holdings.HOLDINGS_FILE 만 쓴다(라이브 파일 0).
"""

from __future__ import annotations

import json
import uuid

import pytest
from fastapi.testclient import TestClient

from app import api as api_module
from app import holdings as holdings_module
from app import holdings_store as store
from tests.test_poc5_05_holdings_history import (
    TH,
    TODAY,
    V1_ROWS,
    _cmd,
    _doc,
    _file,
    _ids,
    _sha,
    _trade,
    _write_v1,
)


@pytest.fixture(autouse=True)
def _today(monkeypatch):
    monkeypatch.setattr(store, "today_kst", lambda: TODAY)


@pytest.fixture
def client():
    return TestClient(api_module.app)


# ── 손상 판정 · 기존 값 · 새 입력 한도 ─────────────────────────────────────────


def test_holdings_inconsistent_with_history_is_corrupt_everywhere(client):
    # 검증자 r1 [P1]: 이력에 잔량 10주가 남은 v2 문서에서 holdings 만 빈 배열 → 손상(500).
    _write_v1(V1_ROWS[:1])
    _, (pid,) = _ids(client)
    assert (
        _cmd(
            client, base_revision=0, action="buy", position_id=pid, trade=_trade()
        ).status_code
        == 200
    )
    doc = _doc()
    doc["holdings"] = []
    _file().write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    before = _sha()
    assert client.get("/holdings").status_code == 500
    assert client.get(TH).status_code == 500
    assert (
        _cmd(
            client, base_revision=1, action="buy", position_id=pid, trade=_trade()
        ).status_code
        == 500
    )
    assert (
        client.put("/holdings", json={"holdings": [], "revision": 1}).status_code == 500
    )
    with pytest.raises(holdings_module.HoldingsValidationError):
        holdings_module.load()
    assert _sha() == before  # 손상 문서 위에 쓰지 않는다
    broken = _doc_after_buy(client)
    broken["personal_trade_history"]["records"][0].pop("payload")  # 기록 손상
    _file().write_text(json.dumps(broken, ensure_ascii=False), encoding="utf-8")
    assert client.get("/holdings").status_code == 500  # 예외가 새지 않고 손상으로


def _doc_after_buy(client) -> dict:
    _file().unlink()
    _write_v1(V1_ROWS[:1])
    _, (pid,) = _ids(client)
    assert (
        _cmd(
            client, base_revision=0, action="buy", position_id=pid, trade=_trade()
        ).status_code
        == 200
    )
    return _doc()


def test_amount_is_exact_product_at_input_limits(client):
    # 검증자 r1 [P2]: 허용 입력의 곱을 반올림하지 않는다(기본 28자리 문맥 금지).
    _write_v1(V1_ROWS[:1])
    _, (pid,) = _ids(client)
    trade = _trade(price="123456789012345.67", qty="123456789012345.123456")
    r = _cmd(client, base_revision=0, action="buy", position_id=pid, trade=trade)
    assert r.status_code == 200, r.text
    assert (
        r.json()["record"]["payload"]["amount"]
        == "15241578753238767078092381604.29703552"
    )
    stored = _doc()["personal_trade_history"]["records"][-1]["payload"]["amount"]
    assert stored == "15241578753238767078092381604.29703552"
    ev = client.get(TH).json()["positions"][0]["cycles"][0]["events"][-1]
    assert ev["payload"]["amount"] == "15241578753238767078092381604.29703552"
    max_trade = _trade(price="999999999999999.99", qty="999999999999999.999999")
    r = _cmd(client, base_revision=1, action="buy", position_id=pid, trade=max_trade)
    assert (
        r.json()["record"]["payload"]["amount"]
        == "999999999999999989999000000000.00000001"  # 정밀도 60 독립 계산값과 같음
    )


def test_unlinked_records_are_corrupt_not_empty(client):
    # 검증자 r2 [P1]: 전량매도로 끝난 정상 문서에서 positions[0].position_id 만 바꾸면 기록이
    # 남았는데 History 200/cycles [] · 보유 EMPTY · 새 매매 200 이었다 → 이제 손상(500 · 쓰기 0).
    from app import holdings_oci_apply

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
    doc = _doc()
    doc["personal_trade_history"]["positions"][0]["position_id"] = str(uuid.uuid4())
    _file().write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    before = _sha()
    assert client.get(TH).status_code == 500
    assert client.get("/holdings").status_code == 500
    r = _cmd(
        client,
        base_revision=1,
        action="new_position",
        ticker="069500",
        account_group="ISA",
        trade=_trade(),
    )
    assert r.status_code == 500 and _sha() == before
    with pytest.raises(holdings_module.HoldingsValidationError):
        holdings_module.load()
    assert holdings_oci_apply._build_payload(_file().read_bytes())[0] is None
    # 변형: 잔량이 남은 BUY 기록 + 연결 줄 없음 + holdings 빈 배열 → 빈 payload 금지.
    doc2 = _doc()
    doc2["personal_trade_history"]["positions"] = []
    doc2["personal_trade_history"]["records"] = [
        r for r in doc2["personal_trade_history"]["records"] if r["kind"] == "BASELINE"
    ]
    _file().write_text(json.dumps(doc2, ensure_ascii=False), encoding="utf-8")
    assert holdings_oci_apply._build_payload(_file().read_bytes())[0] is None
    assert client.get("/holdings").status_code == 500


def _base_history_doc(client) -> dict:
    """정상 이력 문서: 기준잔고 2줄 · 매수 · 매도 · 매도 정정(대체 연결 포함)."""
    _write_v1(V1_ROWS[:2])
    _, ids = _ids(client)
    b = _cmd(
        client,
        base_revision=0,
        action="buy",
        position_id=ids[0],
        trade=_trade("2026-10-06"),
    )
    s = _cmd(
        client,
        base_revision=1,
        action="sell",
        position_id=ids[0],
        trade=_trade("2026-10-07", qty="3"),
    )
    c = _cmd(
        client,
        base_revision=2,
        action="correct",
        supersedes_id=s.json()["record"]["record_id"],
        trade=_trade("2026-10-07", qty="2"),
    )
    assert b.status_code == s.status_code == c.status_code == 200
    return _doc()


def _recs(d):
    return d["personal_trade_history"]["records"]


def _kind(d, k, n=0):
    return [r for r in _recs(d) if r["kind"] == k][n]


_TAMPER = {
    "줄 ID 변경(연결 끊김)": lambda d: d["personal_trade_history"]["positions"][
        0
    ].update(position_id="x"),
    "대체 대상 없음": lambda d: _kind(d, "SELL", 1).update(supersedes_id="nope"),
    "기록 ID 중복": lambda d: _kind(d, "BUY").update(
        record_id=_kind(d, "SELL")["record_id"]
    ),
    "기간이 두 줄에 걸침": lambda d: _kind(d, "BASELINE", 1).update(
        cycle_id=_kind(d, "BUY")["cycle_id"]
    ),
    "매매대금 변조": lambda d: _kind(d, "BUY")["payload"].update(amount="1"),
    "알 수 없는 종류": lambda d: _kind(d, "BUY").update(kind="GIFT"),
    "최상위 추가 키": lambda d: d.update(extra=1),
    "저장된 임시 표시": lambda d: _kind(d, "BASELINE").update(virtual=True),
    "보유 줄 추가 키": lambda d: d["holdings"][0].update(memo="x"),
    "기준잔고 취소": lambda d: _recs(d).append(
        {
            **_kind(d, "BUY"),
            "record_id": "v1",
            "kind": "VOID",
            "payload": {},
            "supersedes_id": _kind(d, "BASELINE")["record_id"],
        }
    ),
    "같은 기록 두 번 대체": lambda d: _recs(d).append(
        {
            **_kind(d, "SELL", 1),
            "record_id": "v2",
            "supersedes_id": _kind(d, "SELL")["record_id"],
        }
    ),
    "정정 종류 바꿈": lambda d: _kind(d, "SELL", 1).update(kind="BUY"),
    "순번 문자열": lambda d: _kind(d, "BUY")["payload"].update(seq="0"),
    "단가 NaN": lambda d: _kind(d, "BUY")["payload"].update(price="NaN"),
    "기록 없는 줄": lambda d: d["personal_trade_history"]["positions"].append(
        {
            "position_id": "lonely",
            "ticker": "000660",
            "account_group": "일반",
            "name": None,
        }
    ),
    "뒤 기록을 대체": lambda d: _kind(d, "BUY").update(
        supersedes_id=_kind(d, "SELL", 1)["record_id"]
    ),
    "거래일 형식": lambda d: _kind(d, "BUY")["payload"].update(trade_date="2026-13-01"),
    "기록 필수 키 없음": lambda d: _kind(d, "BUY").pop("cycle_id"),
    # 반박 검토(r2 정정 중): 표지 키를 지워 기존 형식으로 통과하던 우회
    "표지 키 두 개 삭제": lambda d: [
        d.pop("schema_version"),
        d.pop("personal_trade_history"),
    ],
    "revision 과 빈 holdings 만": lambda d: [
        d.clear(),
        d.update(revision=1, holdings=[]),
    ],
    "기존 형식에 줄 ID 행": lambda d: [
        d.pop("schema_version"),
        d.pop("personal_trade_history"),
        d.pop("revision"),
    ],
    # 반박 검토(통과하는 손상): 수치 · 형식 · 순번 · 줄 단위 값
    "수량 무한대 표기": lambda d: _kind(d, "BASELINE", 1)["payload"].update(
        quantity="1E+400"
    ),
    "revision 음수": lambda d: d.update(revision=-3),
    "형식 번호 실수": lambda d: d.update(schema_version=2.0),
    "holdings 숫자": lambda d: d.update(holdings=5),
    "같은 날 순번 겹침": lambda d: _kind(d, "SELL", 1)["payload"].update(
        trade_date="2026-10-06", seq=_kind(d, "BUY")["payload"]["seq"]
    ),
    "계좌 31자": lambda d: d["personal_trade_history"]["positions"][1].update(
        account_group="가" * 31
    ),
    "종목코드 공백": lambda d: d["personal_trade_history"]["positions"][1].update(
        ticker="   "
    ),
    "지수 표기 단가": lambda d: _kind(d, "BUY")["payload"].update(
        price="1.2E+4", amount="60000"
    ),
    "단가 소수 3자리": lambda d: _kind(d, "BUY")["payload"].update(price="12000.001"),
    "메모 201자": lambda d: _kind(d, "BUY")["payload"].update(memo="가" * 201),
    "거래일이 저장일 뒤": lambda d: _kind(d, "BUY")["payload"].update(
        trade_date="2026-10-09"
    ),
}


@pytest.mark.parametrize("name", list(_TAMPER))
def test_tampered_history_document_is_corrupt_on_every_layer(client, name):
    from app import holdings_oci_apply

    d = _base_history_doc(client)
    _TAMPER[name](d)
    _file().write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    before = _sha()
    with pytest.raises(store.DocumentCorrupt):
        store.read_document()
    with pytest.raises(holdings_module.HoldingsValidationError):
        holdings_module.load()
    assert holdings_oci_apply._build_payload(_file().read_bytes())[0] is None
    assert client.get("/holdings").status_code == 500
    assert client.get(TH).status_code == 500
    assert _sha() == before


def test_side_readers_skip_tampered_history_document(client, tmp_path, monkeypatch):
    # 반박 검토: 판정 없이 원문을 읽던 보조 경로 — 받은 알림 이름표 · 보유 브리핑 미리보기.
    import importlib

    from app.ledger_copy import views

    d = _base_history_doc(client)
    d["holdings"][0]["name"] = "가짜이름"
    _file().write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(views, "HOLDINGS_FILE", _file())
    monkeypatch.setattr(views, "MARKET_DB", tmp_path / "no_market.sqlite")
    assert "가짜이름" not in views.name_map().values()
    preview = importlib.import_module("scripts.build_holdings_selection_preview")
    with pytest.raises(holdings_module.HoldingsValidationError):
        preview._load_holdings(_file())


def test_period_boundary_cannot_be_bypassed_through_empty_cycle(client):
    # 반박 검토(API 만으로): 이름 정정만 남은(매수가 취소된) 기간이 경계 확인을 끊지 않는다.
    r = _cmd(
        client,
        base_revision=0,
        action="new_position",
        ticker="305540",
        account_group="일반",
        name="TIGER",
        trade=_trade("2026-10-01", "10000", "10"),
    )
    pid = r.json()["record"]["position_id"]
    assert (
        _cmd(
            client,
            base_revision=1,
            action="sell_all",
            position_id=pid,
            trade=_trade("2026-10-05", "11000", "10"),
        ).status_code
        == 200
    )
    b = _cmd(
        client,
        base_revision=2,
        action="new_position",
        position_id=pid,
        ticker="305540",
        account_group="일반",
        trade=_trade("2026-10-06", "10000", "1"),
    )
    g = client.get("/holdings").json()
    rows = [{**g["holdings"][0], "name": "TIGER 2차전지"}]
    assert (
        client.put(
            "/holdings", json={"holdings": rows, "revision": g["revision"]}
        ).status_code
        == 200
    )
    rev = client.get("/holdings").json()["revision"]
    assert (
        _cmd(
            client,
            base_revision=rev,
            action="void",
            supersedes_id=b.json()["record"]["record_id"],
        ).status_code
        == 200
    )
    early = _cmd(
        client,
        base_revision=rev + 1,
        action="new_position",
        position_id=pid,
        ticker="305540",
        account_group="일반",
        trade=_trade("2026-10-02", "10000", "1"),
    )
    assert early.status_code == 409 and "종료일(2026-10-05)" in early.json()["detail"]


def test_voiding_first_buy_leaves_holdings_even_with_adjustment(client):
    # 설계 §11-2: 최초 BUY 취소 뒤 다른 유효 매수가 없으면 현재 보유에서 빠진다(입력 정정이 남아도).
    r = _cmd(
        client,
        base_revision=0,
        action="new_position",
        ticker="305540",
        account_group="일반",
        trade=_trade("2026-10-01", "10000", "10"),
    )
    rid = r.json()["record"]["record_id"]
    g = client.get("/holdings").json()
    rows = [{**g["holdings"][0], "quantity": 8}]
    assert (
        client.put("/holdings", json={"holdings": rows, "revision": 1}).status_code
        == 200
    )
    v = _cmd(client, base_revision=2, action="void", supersedes_id=rid)
    assert v.status_code == 200 and v.json()["holdings"] == []
    pos = client.get(TH).json()["positions"][0]
    assert pos["cycles"] == [] and [x["record_id"] for x in pos["voided"]] == [rid]


def test_non_finite_numbers_are_rejected_on_every_layer(client):
    from app import holdings_oci_apply

    _file().parent.mkdir(parents=True, exist_ok=True)
    for bad in ("NaN", "Infinity"):
        _file().write_text(
            '{"holdings": [{"ticker": "069500", "quantity": %s, '
            '"avg_buy_price": 10000, "account_group": "ISA"}]}' % bad,
            encoding="utf-8",
        )
        with pytest.raises(holdings_module.HoldingsValidationError):
            holdings_module.load()
        assert holdings_oci_apply._build_payload(_file().read_bytes())[0] is None
        assert client.get("/holdings").status_code == 500


_LEGACY_ROWS = {
    # 검증자 r3: 기존 형식이 허용하던 값 — 새 검사가 소급되면 안 된다(PLAN §2-1 '읽은 값 그대로').
    "수량 10^15": {
        "ticker": "069500",
        "quantity": 1000000000000000,
        "avg_buy_price": 100,
    },
    "평단 10^15": {
        "ticker": "069500",
        "quantity": 1,
        "avg_buy_price": 1000000000000000,
    },
    "아주 큰 수": {"ticker": "069500", "quantity": 1e20, "avg_buy_price": 1e300},
    "아주 작은 수": {
        "ticker": "069500",
        "quantity": 1e-9,
        "avg_buy_price": 0.000123456789,
    },
    "긴 소수": {"ticker": "069500", "quantity": 0.1 + 0.2, "avg_buy_price": 1 / 3},
    "수량 0.1234567": {
        "ticker": "069500",
        "quantity": 0.1234567,
        "avg_buy_price": 10000,
    },
    "비정형 종목코드": {"ticker": "abc12", "quantity": 1, "avg_buy_price": 10},
    "계좌 없음 · 이름 빈칸": {
        "ticker": "069500",
        "quantity": 1,
        "avg_buy_price": 10,
        "name": "",
    },
    "사용자 계좌 30자": {
        "ticker": "069500",
        "quantity": 1,
        "avg_buy_price": 10,
        "account_group": "가" * 30,
    },
}


@pytest.mark.parametrize("name", list(_LEGACY_ROWS))
def test_legacy_values_are_not_retroactively_corrupt(
    client, name, tmp_path, monkeypatch
):
    from app import holdings_oci_apply, market_data_store
    from app.market_briefing import calendar as cal

    # 시장 흐름 조회는 tmp 시세 DB(없음 = 자료 없음) · tmp 캘린더로 — 라이브 DB 를 열지 않는다.
    monkeypatch.setattr(
        market_data_store, "DEFAULT_DB_PATH", tmp_path / "no_market.sqlite"
    )
    monkeypatch.setattr(cal, "CALENDAR_DIR", tmp_path / "market_meta")

    row = _LEGACY_ROWS[name]
    _write_v1([row, V1_ROWS[1]])
    for _ in range(2):  # 읽기(V1) → 첫 변경(BASELINE 확정 · V2) → 다시 읽기
        assert client.get("/holdings").status_code == 200, name
        assert client.get(TH).status_code == 200, name
        assert holdings_module.load()[0].quantity == float(row["quantity"])
        assert holdings_oci_apply._build_payload(_file().read_bytes())[0] is not None
        g, ids = _ids(client)
        if g["revision"] == 0:
            r = _cmd(
                client,
                base_revision=0,
                action="buy",
                position_id=ids[1],
                trade=_trade(),
            )
            assert r.status_code == 200, (name, r.text)
    rows = [dict(h) for h in client.get("/holdings").json()["holdings"]]
    before = _sha()  # 입력 정정 모드에서 읽은 값을 그대로 저장 = 기록 0 · 파일 그대로
    same = client.put("/holdings", json={"holdings": rows, "revision": 1})
    if name != "비정형 종목코드":
        assert same.status_code == 200 and same.json()["revision"] == 1, (
            name,
            same.text,
        )
    assert _sha() == before, name
    rows[0]["avg_buy_price"] = (
        float(row["avg_buy_price"]) * 2
    )  # 입력 정정도 기존 규칙(한도 없음)
    r = client.put("/holdings", json={"holdings": rows, "revision": 1})
    if (
        name == "비정형 종목코드"
    ):  # 기존 규칙(POC3-08): PUT /holdings 저장은 종목코드 형식 강제
        assert r.status_code == 422 and "종목코드" in r.json()["detail"]
    else:
        assert r.status_code == 200, (name, r.text)
    assert client.get(TH).status_code == 200
    rev = client.get("/holdings").json()["revision"]
    q = client.get(TH).json()["positions"][0]["cycles"][0]["quantity"]
    sell_all = _cmd(
        client,
        base_revision=rev,
        action="sell_all",
        position_id=rows[0]["position_id"],
        trade=_trade(price="1", qty=q),
    )
    assert sell_all.status_code == 200, (
        name,
        sell_all.text,
    )  # 전량매도 = 정확한 잔량 · 한도 없음
    assert client.get(TH).status_code == 200
    # 검증자 r4: 전량매도 기록의 단가만 정정(수량은 그대로) — 기존 수량 예외가 유지된다.
    sold = sell_all.json()["record"]
    fixed = _cmd(
        client,
        base_revision=rev + 1,
        action="correct",
        supersedes_id=sold["record_id"],
        trade=_trade(price="2", qty=sold["payload"]["quantity"]),
    )
    assert fixed.status_code == 200, (name, fixed.text)
    assert fixed.json()["record"]["payload"]["quantity"] == sold["payload"]["quantity"]
    # 재매수(줄 지정) — 종목 · 계좌는 그 줄의 값(비정형 코드 포함) · 보낸 종목코드를 다시 검사하지 않는다.
    rebuy = _cmd(
        client,
        base_revision=rev + 2,
        action="new_position",
        position_id=rows[0]["position_id"],
        ticker=row["ticker"],
        account_group=row.get("account_group"),
        trade=_trade(price="1", qty="1"),
    )
    assert rebuy.status_code == 200, (name, rebuy.text)
    pos = next(
        p
        for p in client.get(TH).json()["positions"]
        if p["position_id"] == rows[0]["position_id"]
    )
    assert [c["status"] for c in pos["cycles"]] == ["CLOSED", "OPEN"]
    for cy in pos["cycles"]:
        flow = client.get(
            f"{TH}/market-flow",
            params={"position_id": pos["position_id"], "cycle_id": cy["cycle_id"]},
        )
        assert flow.status_code == 200, (name, flow.text)


def test_edit_mode_keeps_exact_values_it_did_not_change(client):
    # 입력 정정 모드 화면은 float 호환값을 보낸다. float 로 나타낼 수 없는 정확한 잔량에서
    # 평단만 고쳐도 수량은 이력의 정확한 값 그대로(정정 전 값도 정확한 값) · 바꾸지 않은 저장 = 기록 0.
    _write_v1(
        [{"ticker": "069500", "quantity": 123456789012345, "avg_buy_price": 10000}]
    )
    _, (pid,) = _ids(client)
    buy = _cmd(
        client,
        base_revision=0,
        action="buy",
        position_id=pid,
        trade=_trade(price="10000", qty="0.123456"),
    )
    assert buy.status_code == 200, buy.text
    exact = "123456789012345.123456"
    assert client.get(TH).json()["positions"][0]["cycles"][0]["quantity"] == exact
    rows = [dict(h) for h in client.get("/holdings").json()["holdings"]]
    assert rows[0]["quantity"] == float(exact)  # 화면이 받는 값(float 호환 표현)
    before = _sha()
    same = client.put("/holdings", json={"holdings": rows, "revision": 1})
    assert same.status_code == 200 and same.json()["revision"] == 1
    assert _sha() == before
    rows[0]["avg_buy_price"] = 12000
    r = client.put("/holdings", json={"holdings": rows, "revision": 1})
    assert r.status_code == 200, r.text
    recs = _doc()["personal_trade_history"]["records"]
    adj = [x for x in recs if x["kind"] == "ADJUSTMENT"][-1]["payload"]
    assert adj["quantity"] == exact and adj["avg_buy_price"] == "12000"
    assert adj["before"] == {"quantity": exact, "avg_buy_price": "10000"}
    assert client.get(TH).json()["positions"][0]["cycles"][0]["quantity"] == exact
    # 줄을 지우면(입력 정정으로 종료) 정정 전 값도 정확한 값으로 남는다.
    r = client.put("/holdings", json={"holdings": [], "revision": 2})
    assert r.status_code == 200, r.text
    end = _doc()["personal_trade_history"]["records"][-1]["payload"]
    assert end["quantity"] == "0" and end["before"]["quantity"] == exact


def test_edit_mode_legacy_lowercase_ticker_is_not_a_ticker_change(client):
    # 기존 형식 파일의 소문자 종목코드 줄 — 화면은 종목코드를 대문자로 보낸다(POC3-08). 같은 줄의
    # 같은 종목코드로 보고(입력 경로와 같은 정규화), 줄의 종목코드는 기존 값 그대로 둔다.
    _write_v1(
        [
            {"ticker": "abc123", "quantity": 10, "avg_buy_price": 100},
            {"ticker": "069500", "quantity": 1, "avg_buy_price": 10000},
        ]
    )
    rows = [dict(h) for h in client.get("/holdings").json()["holdings"]]
    for row in rows:
        row["ticker"] = row["ticker"].upper()
    before = _sha()
    same = client.put("/holdings", json={"holdings": rows, "revision": 0})
    assert same.status_code == 200, same.text
    assert _sha() == before  # 바꾸지 않은 저장 = 쓰기 0
    rows[1]["avg_buy_price"] = 11000
    r = client.put("/holdings", json={"holdings": rows, "revision": 0})
    assert r.status_code == 200, r.text
    tickers = {h["ticker"] for h in client.get("/holdings").json()["holdings"]}
    assert tickers == {"abc123", "069500"}
    rows[0]["ticker"] = "ABC124"  # 다른 종목코드는 여전히 변경으로 거절
    bad = client.put("/holdings", json={"holdings": rows, "revision": 1})
    assert bad.status_code == 422 and "바꿀 수 없습니다" in bad.json()["detail"]


def test_balance_register_follows_existing_holding_input_rule(client):
    # 잔고 등록(매매 아님)은 입력 정정 모드의 새 줄(REGISTER)과 같은 기존 보유 입력 규칙 —
    # 형식 · 유한 · 양수만. 매매 입력 한도(수량 소수 6 · 단가 소수 2 · 15자리 미만)는 없다(설계 §3).
    values = [("0.1234567", "35000.123"), ("1000000000000000", "1000000000000000")]
    for i, (qty, avg) in enumerate(values):
        r = _cmd(
            client,
            base_revision=i,
            action="register",
            ticker=f"06950{i}",
            account_group="일반",
            holding={"quantity": qty, "avg_buy_price": avg},
        )
        assert r.status_code == 200, (qty, avg, r.text)
        assert r.json()["record"]["payload"] == {"quantity": qty, "avg_buy_price": avg}
    # 입력 정정 모드의 새 줄도 같은 값을 받는다(두 경로의 REGISTER 규칙이 같다).
    rows = [dict(h) for h in client.get("/holdings").json()["holdings"]]
    rows.append({"ticker": "069509", "quantity": 0.1234567, "avg_buy_price": 35000.123})
    put = client.put("/holdings", json={"holdings": rows, "revision": 2})
    assert put.status_code == 200, put.text
    before = _sha()
    for bad in ("0", "-1", "abc", "NaN", "Infinity", "1e999999", "1e400", "1e-400"):
        r = _cmd(
            client,
            base_revision=3,
            action="register",
            ticker="069508",
            account_group="일반",
            holding={"quantity": bad, "avg_buy_price": "1"},
        )
        assert r.status_code == 422, bad  # 형식 · 유한 · 양수는 그대로 검사
    assert _sha() == before


def test_unlimited_quantity_paths_still_reject_out_of_range_input(client):
    # 한도를 미루는 매도 · 전량매도 수량도 보유 호환 표현(float) 범위 밖이면 입력 오류(422 · 쓰기 0).
    _write_v1(V1_ROWS[:1])
    _, (pid,) = _ids(client)
    before = _sha()
    for action in ("sell", "sell_all"):
        for qty in ("1e1000000", "1e-1000000", "1e400"):
            r = _cmd(
                client,
                base_revision=0,
                action=action,
                position_id=pid,
                trade=_trade(price="1", qty=qty),
            )
            assert r.status_code == 422, (action, qty, r.text)
    assert _sha() == before


def test_new_quantity_limits_apply_only_to_newly_entered_values(client):
    # 한도(소수 6자리 · 정수부 15자리 미만)는 새로 입력한 수량에만. 잔량 0 으로 만드는 매도 ·
    # 정정에서 원래와 같은 수량은 예외(설계 §3 소급 금지).
    _write_v1([{"ticker": "069500", "quantity": 0.1234567, "avg_buy_price": 10000}])
    _, (pid,) = _ids(client)
    partial = _cmd(
        client,
        base_revision=0,
        action="sell",
        position_id=pid,
        trade=_trade(price="1", qty="0.1000001"),
    )
    assert partial.status_code == 422  # 잔량이 남는 매도에 새 입력 7자리
    whole = _cmd(
        client,
        base_revision=0,
        action="sell",
        position_id=pid,
        trade=_trade(price="1", qty="0.1234567"),
    )
    assert whole.status_code == 200  # 분할매도로 입력해도 잔량 전부면 전량매도와 같다
    rid = whole.json()["record"]["record_id"]
    changed = _cmd(
        client,
        base_revision=1,
        action="correct",
        supersedes_id=rid,
        trade=_trade(price="1", qty="0.1234561"),
    )
    assert changed.status_code == 422  # 바꾼 수량(잔량 남음)은 새 입력 한도
    ok = _cmd(
        client,
        base_revision=1,
        action="correct",
        supersedes_id=rid,
        trade=_trade(price="1", qty="0.1"),
    )
    assert ok.status_code == 200
    b = _cmd(
        client,
        base_revision=2,
        action="new_position",
        position_id=pid,
        ticker="069500",
        trade=_trade(qty="1"),
    )
    assert b.status_code == 409  # 줄이 아직 보유 중(정정으로 잔량 남음) — 재매수 아님
    buy = _cmd(
        client, base_revision=2, action="buy", position_id=pid, trade=_trade(qty="1")
    )
    bad = _cmd(
        client,
        base_revision=3,
        action="correct",
        supersedes_id=buy.json()["record"]["record_id"],
        trade=_trade(qty="1.1234567"),
    )
    assert bad.status_code == 422  # 매수 정정의 바꾼 수량도 새 입력 한도


def test_price_only_correction_keeps_accepted_quantity_even_if_no_longer_closing(
    client,
):
    # 원래 수량 예외만 받는 경우: 기존 정밀도 전량매도가 같은 기간 매수 정정으로 더는 잔량을
    # 0 으로 만들지 않게 된 뒤, 그 매도의 단가만 정정(수량 그대로) → 이미 받아들인 값이라 200.
    _write_v1([{"ticker": "069500", "quantity": 0.1234567, "avg_buy_price": 10000}])
    _, (pid,) = _ids(client)
    buy = _cmd(
        client,
        base_revision=0,
        action="buy",
        position_id=pid,
        trade=_trade("2026-10-06", qty="1"),
    )
    sell = _cmd(
        client,
        base_revision=1,
        action="sell_all",
        position_id=pid,
        trade=_trade("2026-10-07", price="11000", qty="1.1234567"),
    )
    assert buy.status_code == sell.status_code == 200
    bigger = _cmd(
        client,
        base_revision=2,
        action="correct",
        supersedes_id=buy.json()["record"]["record_id"],
        trade=_trade("2026-10-06", qty="2"),
    )
    assert (
        bigger.status_code == 200
    )  # 매도 1.1234567 은 이제 잔량을 0 으로 만들지 않는다(보유 1주)
    assert client.get("/holdings").json()["holdings"][0]["quantity"] == 1.0
    fixed = _cmd(
        client,
        base_revision=3,
        action="correct",
        supersedes_id=sell.json()["record"]["record_id"],
        trade=_trade("2026-10-07", price="12000", qty="1.1234567"),
    )
    assert fixed.status_code == 200, fixed.text
    moved = _cmd(
        client,
        base_revision=4,
        action="correct",
        supersedes_id=fixed.json()["record"]["record_id"],
        trade=_trade("2026-10-07", price="12000", qty="1.1234568"),
    )
    assert moved.status_code == 422  # 바꾼 수량(잔량 남음)은 새 입력 한도
