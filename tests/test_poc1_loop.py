"""POC 1단계 Acceptance Criteria 검증 테스트.

원칙:
- 테스트 제어 플래그를 draft_payload 에 섞지 않는다.
- draft 생성 실패는 input_data 에 필수 키를 의도적으로 누락시켜 재현한다.
- 외부 전달 실패는 delivery.deliver 를 monkeypatch 하여 재현한다.
- POC1 Step 3 (실 OCI 연결) 이후: deliver 와 fetch_outbox_result 모두
  monkeypatch 해야 실 SSH/SCP 호출 없이 테스트가 동작한다.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import api, delivery, holdings as holdings_module, store
from app.models import TERMINAL_STATES
from app.state import InvalidTransition, validate_transition

_VALID_INPUT = {
    "title": "테스트 초안",
    "recommendations": [{"ticker": "069500", "score": 0.5, "action": "HOLD"}],
    "note": "테스트 본문",
}


@pytest.fixture(autouse=True)
def _isolated_store(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "STORE_DIR", Path(tmp_path) / "runs")
    monkeypatch.setattr(store, "HANDOFF_STAGING_DIR", Path(tmp_path) / "handoff")
    monkeypatch.setattr(
        store, "HANDOFF_PROCESSED_DIR", Path(tmp_path) / "handoff_processed"
    )
    # POC2 Step 1: holdings 저장 경로도 격리
    monkeypatch.setattr(holdings_module, "HOLDINGS_DIR", Path(tmp_path) / "holdings")
    monkeypatch.setattr(
        holdings_module,
        "HOLDINGS_FILE",
        Path(tmp_path) / "holdings" / "holdings_latest.json",
    )


@pytest.fixture(autouse=True)
def _stub_oci_calls(monkeypatch):
    """기본 stub: deliver 는 무동작 성공, outbox 는 결과 없음(DELIVERING 유지).

    개별 테스트가 필요시 monkeypatch.setattr 로 override.
    실 SCP/SSH 호출이 테스트 환경에서 발생하지 않도록 보장한다.
    """
    monkeypatch.setattr(delivery, "deliver", lambda run: None)
    monkeypatch.setattr(delivery, "fetch_outbox_result", lambda run_id: None)


@pytest.fixture
def client() -> TestClient:
    return TestClient(api.app)


def _generate(client: TestClient, input_data: dict) -> tuple[int, dict]:
    r = client.post("/runs/generate", json={"input_data": input_data})
    try:
        return r.status_code, r.json()
    except ValueError:
        return r.status_code, {}


def test_ac1_generate_success_yields_pending_approval(client):
    status, body = _generate(client, _VALID_INPUT)
    assert status == 200
    assert body["status"] == "PENDING_APPROVAL"
    assert body["draft_payload"] is not None
    assert body["run_id"].startswith("run_")
    # 운영 payload 에 테스트 제어 흔적 없음 확인
    assert "_simulate_draft_failure" not in body["draft_payload"]
    assert "_simulate_delivery_failure" not in body["draft_payload"]


def test_ac2_generate_failure_yields_failed(client):
    bad_input = {"title": "x", "recommendations": []}
    status, body = _generate(client, bad_input)
    assert status == 200
    assert body["status"] == "FAILED"
    assert body["draft_payload"] is None


def test_ac3_failed_payload_is_null_safe(client):
    status, body = _generate(client, {"title": "x", "recommendations": []})
    assert status == 200
    assert (body["draft_payload"] or {}) == {}


def test_ac4_reject_blocks_delivery(client):
    _, body = _generate(client, _VALID_INPUT)
    run_id = body["run_id"]
    r = client.post(f"/runs/{run_id}/reject")
    assert r.status_code == 200
    assert r.json()["status"] == "REJECTED"

    r2 = client.post(f"/runs/{run_id}/approve")
    assert r2.status_code == 409


def test_ac5_approve_response_is_delivering(client):
    # Approve 응답은 즉시 DELIVERING. 실제 전달은 BackgroundTasks 위임.
    _, body = _generate(client, _VALID_INPUT)
    run_id = body["run_id"]
    r = client.post(f"/runs/{run_id}/approve")
    assert r.status_code == 200
    assert r.json()["status"] == "DELIVERING"


def test_ac6_oci_outbox_completed_propagates(client, monkeypatch):
    # OCI outbox 가 COMPLETED 결과를 돌려주면 GET 시 reconciliation 이 일어나
    # 로컬 status 가 COMPLETED 로 업데이트된다.
    _, body = _generate(client, _VALID_INPUT)
    run_id = body["run_id"]
    client.post(f"/runs/{run_id}/approve")

    # 첫 GET: outbox 결과 없음 → DELIVERING 유지 (default stub)
    r1 = client.get(f"/runs/{run_id}").json()
    assert r1["status"] == "DELIVERING"

    # 다음 GET: outbox 가 COMPLETED 결과 반환
    monkeypatch.setattr(
        delivery,
        "fetch_outbox_result",
        lambda rid: {
            "run_id": rid,
            "status": "COMPLETED",
            "processed_at": "2026-04-25T00:00:00Z",
            "telegram_message_id": "12345",
        },
    )
    r2 = client.get(f"/runs/{run_id}").json()
    assert r2["status"] == "COMPLETED"


def test_ac7_oci_outbox_failed_propagates(client, monkeypatch):
    _, body = _generate(client, _VALID_INPUT)
    run_id = body["run_id"]
    client.post(f"/runs/{run_id}/approve")

    monkeypatch.setattr(
        delivery,
        "fetch_outbox_result",
        lambda rid: {
            "run_id": rid,
            "status": "FAILED",
            "processed_at": "2026-04-25T00:00:00Z",
            "reason": "telegram_api_error",
        },
    )
    final = client.get(f"/runs/{run_id}").json()
    assert final["status"] == "FAILED"


def test_ac7b_scp_failure_marks_failed(client, monkeypatch):
    # SCP 자체가 실패하면 BackgroundTasks 가 즉시 FAILED 저장.
    def _boom(run):
        raise delivery.DeliveryError("scp injected failure")

    monkeypatch.setattr(delivery, "deliver", _boom)

    _, body = _generate(client, _VALID_INPUT)
    run_id = body["run_id"]
    r = client.post(f"/runs/{run_id}/approve")
    assert r.status_code == 200
    assert r.json()["status"] == "DELIVERING"

    final = client.get(f"/runs/{run_id}").json()
    assert final["status"] == "FAILED"


def test_ac8_terminal_states_block_reuse(client, monkeypatch):
    # COMPLETED — outbox 결과로 도달
    monkeypatch.setattr(
        delivery,
        "fetch_outbox_result",
        lambda rid: {
            "run_id": rid,
            "status": "COMPLETED",
            "processed_at": "2026-04-25T00:00:00Z",
        },
    )
    _, b1 = _generate(client, _VALID_INPUT)
    client.post(f"/runs/{b1['run_id']}/approve")
    assert client.get(f"/runs/{b1['run_id']}").json()["status"] == "COMPLETED"
    r = client.post(f"/runs/{b1['run_id']}/approve")
    assert r.status_code == 409
    r = client.post(f"/runs/{b1['run_id']}/reject")
    assert r.status_code == 409

    # REJECTED
    monkeypatch.setattr(delivery, "fetch_outbox_result", lambda rid: None)
    _, b2 = _generate(client, _VALID_INPUT)
    client.post(f"/runs/{b2['run_id']}/reject")
    r = client.post(f"/runs/{b2['run_id']}/approve")
    assert r.status_code == 409

    # FAILED — SCP 실패 경로
    def _boom(run):
        raise delivery.DeliveryError("injected for test")

    monkeypatch.setattr(delivery, "deliver", _boom)
    _, b3 = _generate(client, _VALID_INPUT)
    client.post(f"/runs/{b3['run_id']}/approve")
    assert client.get(f"/runs/{b3['run_id']}").json()["status"] == "FAILED"
    r = client.post(f"/runs/{b3['run_id']}/approve")
    assert r.status_code == 409
    monkeypatch.undo()

    # FAILED — draft input 실패 경로
    _, b4 = _generate(client, {"title": "x", "recommendations": []})
    r = client.post(f"/runs/{b4['run_id']}/approve")
    assert r.status_code == 409


def test_ac9_new_attempt_requires_new_run_id(client):
    _, b1 = _generate(client, _VALID_INPUT)
    _, b2 = _generate(client, _VALID_INPUT)
    assert b1["run_id"] != b2["run_id"]


def test_ac10_status_values_are_from_fixed_set(client):
    allowed = {"PENDING_APPROVAL", "REJECTED", "DELIVERING", "FAILED", "COMPLETED"}
    _, b1 = _generate(client, _VALID_INPUT)
    assert b1["status"] in allowed
    r = client.post(f"/runs/{b1['run_id']}/approve")
    assert r.json()["status"] in allowed
    final = client.get(f"/runs/{b1['run_id']}").json()
    assert final["status"] in allowed


def test_generate_empty_input_yields_failed(client):
    r = client.post("/runs/generate", json={"input_data": {}})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "FAILED"
    assert body["draft_payload"] is None


def test_state_machine_no_approved_state():
    with pytest.raises(InvalidTransition):
        validate_transition("PENDING_APPROVAL", "APPROVED")  # type: ignore[arg-type]


def test_state_machine_terminal_blocks_all():
    for t in TERMINAL_STATES:
        with pytest.raises(InvalidTransition):
            validate_transition(t, "DELIVERING")
        with pytest.raises(InvalidTransition):
            validate_transition(t, "COMPLETED")


def test_outbox_config_error_marks_failed(client, monkeypatch):
    # 환경변수 누락(DeliveryConfigError) 이 reconciliation 단계에서 발생하면
    # silent swallow 하지 않고 즉시 FAILED 로 종결한다.
    _, body = _generate(client, _VALID_INPUT)
    run_id = body["run_id"]
    client.post(f"/runs/{run_id}/approve")

    def _raise_config(rid):
        raise delivery.DeliveryConfigError("OCI_SSH_TARGET 미설정")

    monkeypatch.setattr(delivery, "fetch_outbox_result", _raise_config)
    r = client.get(f"/runs/{run_id}").json()
    assert r["status"] == "FAILED"


def test_outbox_invalid_status_keeps_delivering(client, monkeypatch):
    # outbox 가 비정상 status 를 돌려줘도 reconciliation 무시 → DELIVERING 유지
    _, body = _generate(client, _VALID_INPUT)
    run_id = body["run_id"]
    client.post(f"/runs/{run_id}/approve")
    monkeypatch.setattr(
        delivery,
        "fetch_outbox_result",
        lambda rid: {"run_id": rid, "status": "WEIRD"},
    )
    r = client.get(f"/runs/{run_id}").json()
    assert r["status"] == "DELIVERING"


def test_handoff_artifact_writes_minimal_contract(tmp_path, monkeypatch):
    # write_handoff_artifact 가 설계자 결정 규약(run_id/asof/draft_payload+approved_at)
    # 만 포함하고 다른 키를 추가하지 않는지 확인.
    monkeypatch.setattr(store, "HANDOFF_STAGING_DIR", tmp_path / "stg")
    from app.models import Run

    run = Run(
        run_id="run_test_001",
        asof="2026-04-25T00:00:00+00:00",
        status="DELIVERING",
        draft_payload={"title": "T", "note": "N", "recommendations": []},
    )
    path = store.write_handoff_artifact(run, "2026-04-25T00:00:01+00:00")
    import json

    data = json.loads(path.read_text(encoding="utf-8"))
    assert set(data.keys()) == {"run_id", "asof", "approved_at", "draft_payload"}
    assert data["run_id"] == "run_test_001"
    assert data["draft_payload"]["title"] == "T"


# ─── POC2 Step 1: holdings 기반 draft 생성 ─────────────────────────────

_VALID_HOLDINGS = [
    {"ticker": "069500", "name": "KODEX 200", "quantity": 10, "avg_buy_price": 38500},
    {"ticker": "091160", "quantity": 5, "avg_buy_price": 22000},  # name 생략
]


def test_holdings_put_get_roundtrip(client):
    """PUT /holdings 후 GET /holdings 가 동일 데이터 반환 + 서버 재시작 후에도 유지."""
    r = client.put("/holdings", json={"holdings": _VALID_HOLDINGS})
    assert r.status_code == 200
    body = r.json()
    assert len(body["holdings"]) == 2
    assert body["holdings"][0]["ticker"] == "069500"
    assert body["holdings"][1]["name"] is None  # 미입력은 None 으로 정규화

    # 별도 GET 으로도 동일하게 조회 (= 서버 재시작 시뮬레이션: 메모리 의존 없음)
    r2 = client.get("/holdings")
    assert r2.status_code == 200
    body2 = r2.json()
    assert len(body2["holdings"]) == 2
    assert body2["holdings"][0]["quantity"] == 10
    assert body2["holdings"][0]["avg_buy_price"] == 38500


def test_holdings_persists_across_new_client(client):
    """동일 tmp_path 에서 새 TestClient 를 만들어도 파일에서 다시 로드됨."""
    client.put("/holdings", json={"holdings": _VALID_HOLDINGS})
    fresh = TestClient(api.app)
    r = fresh.get("/holdings")
    assert r.status_code == 200
    assert len(r.json()["holdings"]) == 2


def test_holdings_empty_get_returns_empty(client):
    r = client.get("/holdings")
    assert r.status_code == 200
    assert r.json() == {"holdings": []}


def test_holdings_validation_blocks_run_creation_422(client):
    """E항: 단순 입력 오류는 422 로 차단되고 run_id 가 만들어지지 않는다."""
    # 빈 리스트
    r = client.put("/holdings", json={"holdings": []})
    assert r.status_code == 422

    # quantity 음수
    r = client.put(
        "/holdings",
        json={"holdings": [{"ticker": "069500", "quantity": -1, "avg_buy_price": 100}]},
    )
    assert r.status_code == 422

    # ticker 빈 문자열
    r = client.put(
        "/holdings",
        json={"holdings": [{"ticker": "  ", "quantity": 1, "avg_buy_price": 100}]},
    )
    assert r.status_code == 422

    # ticker 중복
    r = client.put(
        "/holdings",
        json={
            "holdings": [
                {"ticker": "069500", "quantity": 1, "avg_buy_price": 100},
                {"ticker": "069500", "quantity": 2, "avg_buy_price": 200},
            ]
        },
    )
    assert r.status_code == 422

    # 422 응답 후에도 runs 가 생성되지 않았는지 확인
    runs = client.get("/runs").json()
    assert runs == []


def test_generate_from_empty_holdings_blocks_run_creation_422(client):
    """holdings 가 비어있을 때 generate-from-holdings 는 422. FAILED run 만들지 않음."""
    # 빈 상태에서 호출
    r = client.post("/runs/generate-from-holdings")
    assert r.status_code == 422
    runs = client.get("/runs").json()
    assert runs == []


def test_generate_from_holdings_creates_pending_approval(client):
    """holdings 기반 draft 가 PENDING_APPROVAL 로 생성되고 payload 가 운영 계약을 만족."""
    client.put("/holdings", json={"holdings": _VALID_HOLDINGS})
    r = client.post("/runs/generate-from-holdings")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "PENDING_APPROVAL"
    assert body["run_id"].startswith("run_")

    payload = body["draft_payload"]
    assert payload is not None
    assert "title" in payload and "보유 종목 기반" in payload["title"]
    assert "asof" in payload
    assert "note" in payload
    recs = payload["recommendations"]
    assert isinstance(recs, list) and len(recs) == 2

    # 항목 필드 6종 확인 (score 는 없어야 함, action 은 모두 HOLD)
    for r_item in recs:
        assert set(r_item.keys()) == {
            "ticker",
            "name",
            "quantity",
            "avg_buy_price",
            "invested_amount",
            "buy_weight_pct",
            "action",
            "reason",
        }
        assert r_item["action"] == "HOLD"
        assert "score" not in r_item

    # 매입금액 / 비중 자동 계산 검증
    expected_invested_0 = 10 * 38500  # 385000
    expected_invested_1 = 5 * 22000  # 110000
    expected_total = expected_invested_0 + expected_invested_1  # 495000
    assert recs[0]["invested_amount"] == expected_invested_0
    assert recs[1]["invested_amount"] == expected_invested_1
    assert recs[0]["buy_weight_pct"] == round(
        expected_invested_0 / expected_total * 100, 2
    )

    # 종목명 미입력은 ticker 로 표시
    assert recs[0]["name"] == "KODEX 200"
    assert recs[1]["name"] == "091160"


def test_generate_from_holdings_then_approval_loop_works(client):
    """holdings 기반 draft 가 기존 승인 루프를 그대로 통과한다 (Approve 기존 경로 재사용)."""
    client.put("/holdings", json={"holdings": _VALID_HOLDINGS})
    r = client.post("/runs/generate-from-holdings")
    run_id = r.json()["run_id"]

    # Approve → DELIVERING (기존 Step 3 BackgroundTasks 흐름 재사용)
    r2 = client.post(f"/runs/{run_id}/approve")
    assert r2.status_code == 200
    assert r2.json()["status"] == "DELIVERING"


def test_holdings_validation_does_not_create_failed_run(client):
    """잘못된 holdings 로 generate 시도해도 FAILED run 이 만들어지지 않는다."""
    # 검증 통과하는 holdings 저장 안 한 상태에서 generate 호출 → 422
    r = client.post("/runs/generate-from-holdings")
    assert r.status_code == 422
    # store 에 어떤 run 도 만들어지지 않음
    assert client.get("/runs").json() == []
