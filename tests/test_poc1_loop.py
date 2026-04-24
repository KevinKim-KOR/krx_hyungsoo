"""POC 1단계 Acceptance Criteria 검증 테스트.

원칙:
- 테스트 제어 플래그를 draft_payload 에 섞지 않는다.
- draft 생성 실패는 input_data 에 필수 키를 의도적으로 누락시켜 재현한다.
- 외부 전달 실패는 delivery.deliver 를 monkeypatch 하여 재현한다.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import api, delivery, store
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
    # 필수 키 "note" 누락 → sample_draft 에서 실패 → FAILED run 저장
    bad_input = {"title": "x", "recommendations": []}
    status, body = _generate(client, bad_input)
    assert status == 200
    assert body["status"] == "FAILED"
    assert body["draft_payload"] is None


def test_ac3_failed_payload_is_null_safe(client):
    status, body = _generate(client, {"title": "x", "recommendations": []})
    assert status == 200
    # UI 는 (payload or {}) 패턴으로 읽어도 깨지지 않아야 한다.
    assert (body["draft_payload"] or {}) == {}


def test_ac4_reject_blocks_delivery(client):
    _, body = _generate(client, _VALID_INPUT)
    run_id = body["run_id"]
    r = client.post(f"/runs/{run_id}/reject")
    assert r.status_code == 200
    assert r.json()["status"] == "REJECTED"

    # Reject 된 run 은 approve 불가
    r2 = client.post(f"/runs/{run_id}/approve")
    assert r2.status_code == 409


def test_ac5_approve_response_is_delivering(client):
    # Approve 응답은 즉시 DELIVERING 을 반환해야 한다 (AC 7).
    # 실제 전달은 BackgroundTasks 로 비동기 실행되며 응답 이후 완료.
    _, body = _generate(client, _VALID_INPUT)
    run_id = body["run_id"]
    r = client.post(f"/runs/{run_id}/approve")
    assert r.status_code == 200
    assert r.json()["status"] == "DELIVERING"


def test_ac6_final_status_is_completed_after_background(client):
    # BackgroundTasks 완료 후 GET 조회 시 COMPLETED (AC 8, 9).
    # starlette TestClient 는 요청 종료 직전에 background task 를 실행하므로
    # 후속 GET 시점에서는 최종 상태가 관측 가능하다.
    _, body = _generate(client, _VALID_INPUT)
    run_id = body["run_id"]
    client.post(f"/runs/{run_id}/approve")
    final = client.get(f"/runs/{run_id}").json()
    assert final["status"] == "COMPLETED"


def test_ac7_delivery_failure_yields_failed(client, monkeypatch):
    # BackgroundTasks 에서 deliver 호출. monkeypatch 로 실패 주입.
    def _boom(run):
        raise delivery.DeliveryError("injected for test")

    monkeypatch.setattr(delivery, "deliver", _boom)

    _, body = _generate(client, _VALID_INPUT)
    run_id = body["run_id"]
    r = client.post(f"/runs/{run_id}/approve")
    assert r.status_code == 200
    # 응답 시점은 DELIVERING. 최종 상태는 background 이후 FAILED.
    assert r.json()["status"] == "DELIVERING"

    final = client.get(f"/runs/{run_id}").json()
    assert final["status"] == "FAILED"


def test_ac8_terminal_states_block_reuse(client, monkeypatch):
    # COMPLETED 는 approve 재요청 차단 (background 완료 후 terminal 도달)
    _, b1 = _generate(client, _VALID_INPUT)
    client.post(f"/runs/{b1['run_id']}/approve")
    # background 완료 확인 (terminal 도달 보장)
    assert client.get(f"/runs/{b1['run_id']}").json()["status"] == "COMPLETED"
    r = client.post(f"/runs/{b1['run_id']}/approve")
    assert r.status_code == 409
    r = client.post(f"/runs/{b1['run_id']}/reject")
    assert r.status_code == 409

    # REJECTED
    _, b2 = _generate(client, _VALID_INPUT)
    client.post(f"/runs/{b2['run_id']}/reject")
    r = client.post(f"/runs/{b2['run_id']}/approve")
    assert r.status_code == 409

    # FAILED (delivery failure) — monkeypatch 로 실패 주입
    def _boom(run):
        raise delivery.DeliveryError("injected for test")

    monkeypatch.setattr(delivery, "deliver", _boom)
    _, b3 = _generate(client, _VALID_INPUT)
    client.post(f"/runs/{b3['run_id']}/approve")
    # background 에서 FAILED 로 전이됐는지 확인
    assert client.get(f"/runs/{b3['run_id']}").json()["status"] == "FAILED"
    r = client.post(f"/runs/{b3['run_id']}/approve")
    assert r.status_code == 409
    monkeypatch.undo()

    # FAILED (draft input 실패) 도 재실행 금지
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
    # 원 지시: GenerateDraft 실패 → FAILED 단일 규칙.
    # 빈 dict 는 sample_draft 필수 키 누락으로 해석되어 FAILED run 으로 저장된다.
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
