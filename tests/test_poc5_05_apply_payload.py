"""POC5-05 — OCI 적용 payload(허용 5필드) · 미적용 판정 · PC 소비자(exporter) 테스트.

설계 개정 2 §7 · §11-3 · PLAN §2-5:
  - 이력 포함 문서를 적용해도 전송 바이트 = 허용 5필드 payload(개인 이력 · 줄 ID 0).
  - 이력만 바뀐 두 문서의 payload hash 는 같다.
  - pending_apply: 성공 뒤 이력만 변경 → false · 보유 변경 → true · 성공 기록 없음 → null ·
    APPLY_FAILED 뒤에도 마지막 성공 hash 유지 · 응답에 hash 값 없음.
  - exporter: 행에 position_id 가 있어도 PUSH-2 package 생성.

실제 OCI 접속 0 — subprocess(_run) · 환경변수를 fake 로 바꾼다(test_holdings_oci_apply.py 방식).
PC 보유 파일 · 적용 상태 파일은 모두 tmp 다(conftest 가 holdings.HOLDINGS_FILE 을 tmp 로 격리).
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.holdings as holdings_module
import app.holdings_book as holdings_book
import app.holdings_oci_apply as mod
from app.api_holdings_oci_apply import router as apply_router
from app.holdings import Holding, serialize_payload, validate_holdings

# 허용 5필드 — 기존 save()(asdict(Holding))의 키 순서 그대로.
_FIELD_ORDER = ("ticker", "quantity", "avg_buy_price", "name", "account_group")
_ALLOWED = set(_FIELD_ORDER)

_P1, _C1 = (
    "11111111-1111-4111-8111-111111111111",
    "22222222-2222-4222-8222-222222222222",
)
_P2, _C2 = (
    "33333333-3333-4333-8333-333333333333",
    "44444444-4444-4444-8444-444444444444",
)
_POSITIONS = [
    {
        "position_id": _P1,
        "ticker": "069500",
        "account_group": "ISA",
        "name": "KODEX 200",
    },
    {"position_id": _P2, "ticker": "005930", "account_group": "일반", "name": None},
]


def _rec(rid, kind, pid, cid, payload, supersedes=None):
    return {
        "record_id": rid,
        "request_id": None,
        "request_hash": None,
        "recorded_at": "2026-10-08T10:00:00+09:00",
        "kind": kind,
        "position_id": pid,
        "cycle_id": cid,
        "supersedes_id": supersedes,
        "payload": payload,
    }


def _trade_payload(day, price, qty, seq=0, memo=None):
    amount = holdings_book.exact_product(price, qty)
    return {
        "trade_date": day,
        "trade_time": None,
        "price": price,
        "quantity": qty,
        "amount": amount,
        "memo": memo,
        "seq": seq,
    }


def _doc(records, positions=None, revision=4) -> dict[str, Any]:
    """이력(records)으로 holdings 를 계산한 일관된 이력 문서(POC5-05 정본 규칙)."""
    doc = {
        "schema_version": 2,
        "revision": revision,
        "holdings": [],
        "personal_trade_history": {
            "positions": copy.deepcopy(positions or _POSITIONS),
            "records": copy.deepcopy(records),
        },
    }
    doc["holdings"] = holdings_book.compute(doc)["holdings"]
    return doc


_RECORDS = [
    _rec(
        "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        "REGISTER",
        _P1,
        _C1,
        {"quantity": "15", "avg_buy_price": "10666.67"},
    ),
    _rec(
        "55555555-5555-4555-8555-555555555555",
        "SELL",
        _P1,
        _C1,
        _trade_payload("2026-10-07", "13000", "6", memo="MEMO_PRIVATE_XYZ"),
    ),
    _rec(
        "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        "REGISTER",
        _P2,
        _C2,
        {"quantity": "3", "avg_buy_price": "70000"},
    ),
]
_HISTORY_DOC: dict[str, Any] = _doc(_RECORDS)
assert [h["quantity"] for h in _HISTORY_DOC["holdings"]] == [9.0, 3.0]
assert _HISTORY_DOC["holdings"][0]["avg_buy_price"] == 10666.67


def _five_field_payload(doc: dict[str, Any]) -> bytes:
    rows = [{k: r.get(k) for k in _ALLOWED} for r in doc["holdings"]]
    return serialize_payload(validate_holdings(rows))


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    """적용 상태 파일 tmp · PC 보유 파일 = 기본 경로(holdings.HOLDINGS_FILE · conftest tmp)."""
    monkeypatch.setattr(
        mod, "_LOCAL_APPLY_STATUS", tmp_path / "holdings_apply_status_latest.json"
    )
    monkeypatch.setattr(mod, "_LOCAL_HOLDINGS", None)
    monkeypatch.setattr(mod, "require_env", lambda _k: "oci-krx")


def _write_pc(doc: dict[str, Any] | bytes) -> Path:
    f = holdings_module.HOLDINGS_FILE
    f.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(doc, bytes):
        f.write_bytes(doc)
    else:
        f.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
    return f


class _FakeOci:
    """scp 로 받은 바이트를 그대로 '원격' 에 두고 sha256sum 은 그 바이트로 계산한다."""

    def __init__(self, fail_scp: bool = False) -> None:
        self.fail_scp = fail_scp
        self.sent: bytes | None = None
        self.scp_src: Path | None = None
        self.calls: list[list[str]] = []

    def __call__(self, cmd: list[str], timeout: int) -> tuple[int, str, str]:
        self.calls.append(cmd)
        joined = " ".join(cmd)
        if cmd[0] == "scp":
            if self.fail_scp:
                return 1, "", "scp error"
            self.scp_src = Path(cmd[-2])
            self.sent = self.scp_src.read_bytes()
            return 0, "", ""
        if "sha256sum" in joined:
            return 0, hashlib.sha256(self.sent or b"").hexdigest(), ""
        return 0, "", ""


def _apply(monkeypatch, fake: _FakeOci) -> mod.HoldingsApplyResult:
    monkeypatch.setattr(mod, "_run", fake)
    return mod.apply_holdings_to_oci()


def _status_client() -> TestClient:
    app = FastAPI()
    app.include_router(apply_router)
    return TestClient(app)


# ── 전송 payload ─────────────────────────────────────────────────────────────


def test_default_path_is_holdings_file_at_call_time(monkeypatch):
    # 기본(_LOCAL_HOLDINGS=None)은 호출 때의 holdings.HOLDINGS_FILE(conftest tmp)을 읽는다.
    assert mod._local_holdings_path() == holdings_module.HOLDINGS_FILE
    _write_pc(_HISTORY_DOC)
    assert (
        mod.current_payload_sha256()
        == hashlib.sha256(_five_field_payload(_HISTORY_DOC)).hexdigest()
    )


def test_history_document_sends_only_five_field_payload(monkeypatch):
    _write_pc(_HISTORY_DOC)
    fake = _FakeOci()
    result = _apply(monkeypatch, fake)

    expected = _five_field_payload(_HISTORY_DOC)
    assert result.status == mod.STATUS_OCI_APPLIED
    assert fake.sent == expected
    assert result.content_sha256 == hashlib.sha256(expected).hexdigest()
    for leaked in (
        b"personal_trade_history",
        b"position_id",
        b"cycle_id",
        b"schema_version",
        b"revision",
        b"MEMO_PRIVATE_XYZ",
        b"record_id",
    ):
        assert leaked not in fake.sent
    sent_doc = json.loads(fake.sent)
    assert set(sent_doc) == {"holdings"}
    assert all(set(r) == _ALLOWED for r in sent_doc["holdings"])
    # PC 임시 파일은 전송 뒤 지운다 · 원본 PC 문서는 그대로다.
    assert fake.scp_src is not None and not fake.scp_src.exists()
    assert fake.scp_src != holdings_module.HOLDINGS_FILE
    assert json.loads(holdings_module.HOLDINGS_FILE.read_text("utf-8")) == _HISTORY_DOC


def test_temp_payload_removed_even_when_scp_fails(monkeypatch):
    _write_pc(_HISTORY_DOC)
    seen: list[Path] = []

    def _fake(cmd, timeout):
        if cmd[0] == "scp":
            seen.append(Path(cmd[-2]))
            assert seen[-1].read_bytes() == _five_field_payload(_HISTORY_DOC)
            return 1, "", "scp error"
        return 0, "", ""

    monkeypatch.setattr(mod, "_run", _fake)
    result = mod.apply_holdings_to_oci()
    assert result.status == mod.STATUS_APPLY_FAILED
    assert len(seen) == 1 and not seen[0].exists()


def test_history_only_change_keeps_payload_sha(monkeypatch):
    _write_pc(_HISTORY_DOC)
    sha_a = mod.current_payload_sha256()

    # 이력만 바뀜: 메모 정정 + 매수 1건 기록 뒤 취소(보유는 같다) · revision 증가.
    recs = copy.deepcopy(_RECORDS)
    recs[1]["payload"]["memo"] = "다른 메모"
    rid = "66666666-6666-4666-8666-666666666666"
    recs.append(
        _rec(rid, "BUY", _P1, _C1, _trade_payload("2026-10-08", "1", "1", seq=0))
    )
    recs.append(_rec("77777777-7777-4777-8777-777777777777", "VOID", _P1, _C1, {}, rid))
    doc_b = _doc(recs, revision=5)
    _write_pc(doc_b)
    sha_b = mod.current_payload_sha256()

    assert sha_a is not None and sha_a == sha_b
    assert mod._build_payload(json.dumps(_HISTORY_DOC).encode())[0] == (
        mod._build_payload(json.dumps(doc_b).encode())[0]
    )


def test_history_document_allows_coincident_triple_on_pc_but_blocks_apply(
    monkeypatch,
):
    # 이력 포함 문서는 줄 ID 로 계산해 평단이 우연히 같아진 두 줄을 PC 에서 읽는다.
    # 그대로 보내면 OCI loader(5필드 문서 · 삼중조합 중복 거절)가 읽지 못하므로 전송 0.
    p3 = "88888888-8888-4888-8888-888888888888"
    positions = _POSITIONS + [{**_POSITIONS[0], "position_id": p3}]
    recs = _RECORDS + [
        _rec(
            "99999999-9999-4999-8999-999999999999",
            "REGISTER",
            p3,
            "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
            {"quantity": "9", "avg_buy_price": "10666.67"},
        ),
    ]
    _write_pc(_doc(recs, positions))
    assert len(holdings_module.load()) == 3

    fake = _FakeOci()
    result = _apply(monkeypatch, fake)
    assert result.status == mod.STATUS_APPLY_FAILED
    assert fake.calls == []


def test_holdings_inconsistent_with_history_is_corrupt_not_empty(monkeypatch):
    # 검증자 r1: 이력에 잔량이 남았는데 holdings 만 빈 배열 → 정상 빈 보유가 아니라 손상.
    doc = copy.deepcopy(_HISTORY_DOC)
    doc["holdings"] = []
    _write_pc(doc)
    payload, err = mod._build_payload(json.dumps(doc).encode())
    assert payload is None and "매매 이력과 맞지 않습니다" in err
    fake = _FakeOci()
    assert _apply(monkeypatch, fake).status == mod.STATUS_APPLY_FAILED
    assert fake.calls == []  # 전송 0 · OCI 보유를 비우지 않는다
    assert mod.current_payload_sha256() is None
    with pytest.raises(holdings_module.HoldingsValidationError):
        holdings_module.load()
    changed = copy.deepcopy(_HISTORY_DOC)
    changed["holdings"][1]["quantity"] = 4.0  # 이력 없이 수량만 바꾼 문서도 손상
    _write_pc(changed)
    assert _apply(monkeypatch, _FakeOci()).status == mod.STATUS_APPLY_FAILED


# ── pending_apply (GET /holdings/apply/status) ───────────────────────────────


def test_pending_null_without_success_record():
    client = _status_client()
    _write_pc(_HISTORY_DOC)
    body = client.get("/holdings/apply/status").json()
    assert body["has_record"] is False
    assert body["pending_apply"] is None


def test_pending_false_after_success_then_history_only_change(monkeypatch):
    _write_pc(_HISTORY_DOC)
    result = _apply(monkeypatch, _FakeOci())
    assert result.status == mod.STATUS_OCI_APPLIED

    recs = copy.deepcopy(_RECORDS)
    recs[1]["payload"]["memo"] = "정정"  # 매도 기록의 메모만(이력만 바뀜)
    _write_pc(_doc(recs, revision=9))

    res = _status_client().get("/holdings/apply/status")
    body = res.json()
    assert body["has_record"] is True
    assert body["pending_apply"] is False
    # 응답에 hash 값 자체 · 원격 경로는 없다.
    assert not any("sha" in k for k in body)
    assert result.content_sha256 not in res.text
    assert mod._REMOTE_DIR not in res.text


def test_pending_true_after_holdings_change(monkeypatch):
    _write_pc(_HISTORY_DOC)
    _apply(monkeypatch, _FakeOci())

    def adj(pid, cid, qty, avg):
        body = {
            "effective_date": "2026-10-08",
            "seq": 0,
            "quantity": qty,
            "avg_buy_price": avg,
            "before": {},
        }
        return _rec(
            f"dddddddd-dddd-4ddd-8ddd-{pid[-12:]}", "ADJUSTMENT", pid, cid, body
        )

    _write_pc(_doc(_RECORDS + [adj(_P2, _C2, "4", "70000")], revision=5))
    assert (
        _status_client().get("/holdings/apply/status").json()["pending_apply"] is True
    )

    # 정상 빈 보유(전량매도)도 보유 변경이다.
    doc_c = _doc(
        _RECORDS + [adj(_P1, _C1, "0", "10666.67"), adj(_P2, _C2, "0", "70000")],
        revision=6,
    )
    assert doc_c["holdings"] == []
    _write_pc(doc_c)
    assert (
        _status_client().get("/holdings/apply/status").json()["pending_apply"] is True
    )


def test_last_success_kept_after_apply_failed(monkeypatch):
    _write_pc(_HISTORY_DOC)
    ok = _apply(monkeypatch, _FakeOci())
    ok_rec = mod.read_apply_status()
    assert ok_rec["last_applied_sha256"] == ok.content_sha256

    failed = _apply(monkeypatch, _FakeOci(fail_scp=True))
    assert failed.status == mod.STATUS_APPLY_FAILED
    rec = mod.read_apply_status()
    assert rec["status"] == mod.STATUS_APPLY_FAILED
    assert rec["last_applied_sha256"] == ok.content_sha256
    assert rec["last_applied_at"] == ok_rec["last_applied_at"]
    # 보유가 같으므로 미적용 아님 · 실패 기록이 판정을 지우지 않는다.
    body = _status_client().get("/holdings/apply/status").json()
    assert body["status"] == mod.STATUS_APPLY_FAILED
    assert body["pending_apply"] is False

    # 로컬 검증 실패(전송 0)로 덮어써도 마지막 성공은 유지된다.
    _write_pc(b"{ broken")
    assert _apply(monkeypatch, _FakeOci()).status == mod.STATUS_APPLY_FAILED
    assert mod.read_apply_status()["last_applied_sha256"] == ok.content_sha256
    # PC 문서를 읽을 수 없으면 '확인 안 됨'.
    assert (
        _status_client().get("/holdings/apply/status").json()["pending_apply"] is None
    )


def test_pending_null_when_pc_file_missing_after_success(monkeypatch):
    _write_pc(_HISTORY_DOC)
    _apply(monkeypatch, _FakeOci())
    holdings_module.HOLDINGS_FILE.unlink()
    body = _status_client().get("/holdings/apply/status").json()
    assert body["has_record"] is True
    assert body["pending_apply"] is None


def test_legacy_record_success_hash_carries_over(monkeypatch):
    # 구 기록(last_applied_sha256 없음): OCI_APPLIED 의 content_sha256 = 파일 바이트 hash.
    # 기존 save 형식 파일은 payload 와 바이트가 같아 그대로 이어진다.
    legacy_rows = [
        {k: r.get(k) for k in _FIELD_ORDER} for r in _HISTORY_DOC["holdings"]
    ]
    legacy_file = _write_pc({"holdings": legacy_rows})
    legacy_sha = hashlib.sha256(legacy_file.read_bytes()).hexdigest()
    mod._LOCAL_APPLY_STATUS.write_text(
        json.dumps(
            {
                "kind": "holdings_latest",
                "status": mod.STATUS_OCI_APPLIED,
                "oci_verified": True,
                "applied_at": "2026-10-01T07:00:00+00:00",
                "content_sha256": legacy_sha,
                "message": "보유 종목을 OCI 에 적용했습니다.",
                "recorded_at": "2026-10-01T07:00:01+00:00",
            }
        ),
        encoding="utf-8",
    )
    assert (
        _status_client().get("/holdings/apply/status").json()["pending_apply"] is False
    )

    # v2 문서로 바뀌어도(이력 추가) 현재 보유가 같으면 미적용 아님.
    _write_pc(_HISTORY_DOC)
    assert (
        _status_client().get("/holdings/apply/status").json()["pending_apply"] is False
    )

    # 이후 실패 기록이 덮어써도 구 성공 hash · 시각을 이어받는다.
    _apply(monkeypatch, _FakeOci(fail_scp=True))
    rec = mod.read_apply_status()
    assert rec["last_applied_sha256"] == legacy_sha
    assert rec["last_applied_at"] == "2026-10-01T07:00:00+00:00"


def test_legacy_failed_record_without_success_is_null():
    _write_pc(_HISTORY_DOC)
    mod._LOCAL_APPLY_STATUS.write_text(
        json.dumps(
            {
                "status": mod.STATUS_APPLY_FAILED,
                "applied_at": None,
                "content_sha256": "abc",
            }
        ),
        encoding="utf-8",
    )
    body = _status_client().get("/holdings/apply/status").json()
    assert body["has_record"] is True
    assert body["pending_apply"] is None


# ── PC 소비자: three_push_package_exporter ──────────────────────────────────


def _stub_exporter_builders(monkeypatch) -> dict[str, Any]:
    import app.draft as draft_mod
    import app.draft_message as draft_message_mod

    captured: dict[str, Any] = {}

    def _fake_payload(holdings, market_quotes=None):
        captured["holdings"] = holdings
        return {
            "runtime_package": {
                "generation_status": {"status": "ok"},
                "message_contract": {"message_text": ""},
            }
        }

    monkeypatch.setattr(draft_mod, "_build_holdings_payload", _fake_payload)
    monkeypatch.setattr(draft_message_mod, "build_message_text", lambda rid, p: "msg")
    return captured


def test_exporter_reads_rows_with_position_id(monkeypatch):
    from app.three_push_package_exporter import build_holdings_briefing_package

    captured = _stub_exporter_builders(monkeypatch)
    _write_pc(_HISTORY_DOC)
    rp = build_holdings_briefing_package()
    assert rp["message_contract"]["message_text"] == "msg"
    holdings = captured["holdings"]
    assert all(isinstance(h, Holding) for h in holdings)
    assert [h.ticker for h in holdings] == ["069500", "005930"]


def test_exporter_keeps_missing_and_empty_errors(monkeypatch):
    from app.three_push_package_exporter import build_holdings_briefing_package

    _stub_exporter_builders(monkeypatch)
    with pytest.raises(RuntimeError, match="holdings 파일 없음"):
        build_holdings_briefing_package()
    _write_pc({"holdings": []})
    with pytest.raises(RuntimeError, match="0건"):
        build_holdings_briefing_package()


class _MismatchAfterReplace(_FakeOci):
    """교체 뒤 재확인 sha256sum 만 다른 값을 돌려준다 → OUT_OF_SYNC."""

    def __init__(self) -> None:
        super().__init__()
        self.sha_calls = 0

    def __call__(self, cmd: list[str], timeout: int) -> tuple[int, str, str]:
        if "sha256sum" in " ".join(cmd):
            self.sha_calls += 1
            if self.sha_calls >= 2:
                return 0, "0" * 64, ""
        return super().__call__(cmd, timeout)


def test_pending_null_when_last_attempt_out_of_sync(monkeypatch):
    # OCI 내용이 확인되지 않은 상태(교체 뒤 불일치)에서는 '미적용 아님' 으로 보이지 않는다.
    _write_pc(_HISTORY_DOC)
    assert _apply(monkeypatch, _FakeOci()).status == mod.STATUS_OCI_APPLIED
    assert _apply(monkeypatch, _MismatchAfterReplace()).status == mod.STATUS_OUT_OF_SYNC
    body = _status_client().get("/holdings/apply/status").json()
    assert body["status"] == mod.STATUS_OUT_OF_SYNC
    assert body["pending_apply"] is None


def test_status_keeps_last_success_time_after_failed_attempt(monkeypatch):
    _write_pc(_HISTORY_DOC)
    _apply(monkeypatch, _FakeOci())
    ok_at = mod.read_apply_status()["last_applied_at"]
    assert (
        _apply(monkeypatch, _FakeOci(fail_scp=True)).status == mod.STATUS_APPLY_FAILED
    )
    body = _status_client().get("/holdings/apply/status").json()
    assert body["status"] == mod.STATUS_APPLY_FAILED
    assert (
        body["last_applied_at"] == ok_at and ok_at
    )  # 실패가 마지막 성공 시각을 지우지 않는다
