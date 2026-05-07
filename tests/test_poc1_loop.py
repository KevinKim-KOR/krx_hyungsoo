"""POC 1단계 Acceptance Criteria 검증 테스트.

원칙:
- 테스트 제어 플래그를 draft_payload 에 섞지 않는다.
- draft 생성 실패는 input_data 에 필수 키를 의도적으로 누락시켜 재현한다.
- 외부 전달 실패는 delivery.deliver 를 monkeypatch 하여 재현한다.
- POC1 Step 3 (실 OCI 연결) 이후: deliver 와 fetch_outbox_result 모두
  monkeypatch 해야 실 SSH/SCP 호출 없이 테스트가 동작한다.

POC2 Step 5D Cleanup:
이 파일은 더 이상 모든 STEP 의 회귀 테스트를 담지 않는다.
POC1 승인 루프 핵심(상태 모델 / outbox reconciliation / handoff artifact 계약)만 유지.
나머지 STEP 별 테스트는 다음 파일들로 분리되었다:
- tests/test_holdings_draft_flow.py — holdings / market / enrich / message_text Step2B/C/D
- tests/test_factor_signals.py — Step3 보유 비중 영향 factor
- tests/test_momentum_holdings.py — Step5B holdings mode momentum_result
- tests/test_universe_seed.py — Step5C universe mode seed / artifact / endpoint

공통 fixture 는 tests/conftest.py, 헬퍼는 tests/_helpers.py.
"""

from __future__ import annotations

import pytest

from app import delivery, store
from app.models import TERMINAL_STATES
from app.state import InvalidTransition, validate_transition

from tests._helpers import _VALID_INPUT, _generate


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
    # POC2 Step 1A: message_text 가 None 일 때는 키 자체가 생략됨 (4 키 그대로)
    assert set(data.keys()) == {"run_id", "asof", "approved_at", "draft_payload"}
    assert data["run_id"] == "run_test_001"
    assert data["draft_payload"]["title"] == "T"


def test_handoff_artifact_with_message_text_top_level(tmp_path, monkeypatch):
    # POC2 Step 1A: message_text 를 넘기면 top-level 5번째 키로 들어간다.
    monkeypatch.setattr(store, "HANDOFF_STAGING_DIR", tmp_path / "stg")
    from app.models import Run

    run = Run(
        run_id="run_test_002",
        asof="2026-04-25T00:00:00+00:00",
        status="DELIVERING",
        draft_payload={"title": "T", "note": "N", "recommendations": []},
    )
    msg = "✅ POC2 holdings 승인 처리\nrun_id: run_test_002"
    path = store.write_handoff_artifact(run, "2026-04-25T00:00:01+00:00", msg)
    import json

    data = json.loads(path.read_text(encoding="utf-8"))
    assert set(data.keys()) == {
        "run_id",
        "asof",
        "approved_at",
        "draft_payload",
        "message_text",
    }
    assert data["message_text"] == msg


# ─── POC2 Step 1A: draft_message ───────────────────────────────────────
