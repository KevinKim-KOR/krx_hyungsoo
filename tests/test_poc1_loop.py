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

from app import api, delivery, holdings as holdings_module, market_cache, store
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
    # POC2 Step 2: market cache 도 격리 (개발자 로컬에 캐시가 있어도 테스트는 항상 빈 상태부터)
    monkeypatch.setattr(market_cache, "CACHE_DIR", Path(tmp_path) / "market_cache")
    monkeypatch.setattr(
        market_cache,
        "CACHE_FILE",
        Path(tmp_path) / "market_cache" / "market_latest.json",
    )
    market_cache.reset_for_test()
    yield
    market_cache.reset_for_test()


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


def test_draft_message_is_holdings_draft_detection():
    from app import draft_message

    # holdings 식별 (quantity 또는 avg_buy_price 가 첫 항목에 있으면 True)
    assert draft_message.is_holdings_draft(
        {"recommendations": [{"ticker": "069500", "quantity": 10}]}
    )
    assert draft_message.is_holdings_draft(
        {"recommendations": [{"ticker": "069500", "avg_buy_price": 38500}]}
    )
    # 샘플 형태 (score 만)
    assert not draft_message.is_holdings_draft(
        {"recommendations": [{"ticker": "069500", "score": 0.5, "action": "HOLD"}]}
    )
    assert not draft_message.is_holdings_draft({"recommendations": []})
    assert not draft_message.is_holdings_draft(None)
    assert not draft_message.is_holdings_draft({})


def test_draft_message_build_renders_readable_lines():
    from app import draft_message

    payload = {
        "title": "보유 종목 기반 초안 (2026-04-25)",
        "asof": "2026-04-25T00:00:00+00:00",
        "note": "holdings 항목 2건 기준 자동 생성. 추천 판단 없이 보유 현황 기준입니다.",
        "recommendations": [
            {
                "ticker": "0013P0",
                "name": "RISE 미국은행TOP10",
                "quantity": 5,
                "avg_buy_price": 10050,
                "invested_amount": 50250,
                "buy_weight_pct": 47.6,
                "action": "HOLD",
                "reason": "보유 종목 현황 (이번 단계는 추천 판단 없이 HOLD 고정)",
            },
            {
                "ticker": "0015B0",
                "quantity": 5,
                "avg_buy_price": 11063,
                "invested_amount": 55315,
                "buy_weight_pct": 52.4,
                "action": "HOLD",
            },
        ],
    }
    msg = draft_message.build_message_text("run_xxx", payload)

    # raw JSON 노출 금지
    assert "[{" not in msg
    assert '"ticker"' not in msg
    assert "recommendations:" not in msg

    # 헤더 / run_id / 제목 / 보유 종목 섹션
    assert "POC2 holdings 승인 처리" in msg
    assert "run_id: run_xxx" in msg
    assert "보유 종목 기반 초안" in msg
    assert "보유 종목:" in msg

    # 항목 헤더 + 한국어 라벨 + 콤마 / % 포맷
    assert "1. RISE 미국은행TOP10 (0013P0)" in msg
    assert "2. 0015B0" in msg  # name 없으면 ticker 단독
    assert "수량: 5" in msg
    assert "평균 매입단가: 10,050원" in msg
    assert "매입금액: 50,250원" in msg
    assert "매입비중: 47.6%" in msg
    assert "판단: HOLD" in msg

    # 두번째 항목은 reason 누락 — 해당 줄 자체가 생략되어야 함
    assert msg.count("사유:") == 1


def test_draft_message_omits_missing_fields():
    from app import draft_message

    # quantity 만 있는 최소 항목 — 다른 줄은 모두 생략
    payload = {
        "title": "최소",
        "asof": "x",
        "note": "",
        "recommendations": [{"ticker": "069500", "quantity": 10}],
    }
    msg = draft_message.build_message_text("run_min", payload)
    assert "수량: 10" in msg
    # 미존재 필드는 'undefined' / 'None' 으로 나오지 않음
    assert "undefined" not in msg
    assert "None" not in msg
    assert "평균 매입단가:" not in msg
    assert "매입금액:" not in msg
    assert "매입비중:" not in msg


def test_draft_message_returns_empty_for_non_holdings():
    from app import draft_message

    # 샘플 형태(score) 는 빈 문자열 반환 (호출자가 raw fallback 결정)
    payload = {
        "title": "샘플",
        "note": "",
        "recommendations": [{"ticker": "069500", "score": 0.5, "action": "HOLD"}],
    }
    msg = draft_message.build_message_text("run_sample", payload)
    assert msg == ""


def test_handoff_artifact_message_text_for_holdings_payload(tmp_path, monkeypatch):
    # delivery.deliver 가 holdings draft 를 보낼 때 사용하는 빌더 + 저장 흐름을
    # 단위 단위로 검증. autouse 의 deliver-stub 영향을 받지 않도록 직접 호출.
    from app import draft_message
    from app.models import Run
    import json as _json

    monkeypatch.setattr(store, "HANDOFF_STAGING_DIR", tmp_path / "stg")

    holdings_payload = {
        "title": "보유 종목 기반 초안 (test)",
        "asof": "2026-04-25T00:00:00+00:00",
        "note": "test note",
        "recommendations": [
            {
                "ticker": "069500",
                "name": "KODEX 200",
                "quantity": 10,
                "avg_buy_price": 38500,
                "invested_amount": 385000,
                "buy_weight_pct": 100.0,
                "action": "HOLD",
                "reason": "보유 종목 현황",
            }
        ],
    }
    run = Run(
        run_id="run_step1a_test",
        asof="2026-04-25T00:00:00+00:00",
        status="DELIVERING",
        draft_payload=holdings_payload,
    )
    # delivery.deliver 의 핵심 분기 재현:
    assert draft_message.is_holdings_draft(run.draft_payload)
    msg = draft_message.build_message_text(run.run_id, run.draft_payload or {})
    path = store.write_handoff_artifact(run, "2026-04-25T00:00:01+00:00", msg)

    body = _json.loads(path.read_text(encoding="utf-8"))
    assert "message_text" in body
    assert "POC2 holdings 승인 처리" in body["message_text"]
    assert "KODEX 200 (069500)" in body["message_text"]
    # draft_payload 는 그대로 유지
    assert body["draft_payload"] == holdings_payload
    # raw recommendations JSON 이 message_text 에 포함되지 않음
    assert "[{" not in body["message_text"]
    assert '"ticker"' not in body["message_text"]


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

    # 항목 필수 필드 확인 (score 는 없어야 함, action 은 모두 HOLD)
    # POC2 Step 2: 시세가 없으면 8 키 그대로(Step 1 호환). 누락 사유 flag 도 추가하지 않음.
    # 시세가 있을 때만 시세 필드(current_price 등) 가 키로 추가된다.
    expected_keys = {
        "ticker",
        "name",
        "quantity",
        "avg_buy_price",
        "invested_amount",
        "buy_weight_pct",
        "action",
        "reason",
    }
    for r_item in recs:
        assert set(r_item.keys()) == expected_keys
        assert r_item["action"] == "HOLD"
        assert "score" not in r_item
        # 시세 미주입 → 시세 필드 자체가 키로 존재하지 않아야 한다 (raw JSON 에서도 None 노출 금지).
        assert "current_price" not in r_item
        assert "eval_amount" not in r_item
        assert "pnl_amount" not in r_item
        assert "pnl_rate_pct" not in r_item
        assert "market_weight_pct" not in r_item
        # draft_payload 는 지시문 허용 필드(시세/평가/시장비중) 만 포함한다.
        # price_missing / calc_missing 메타 flag 는 enrichment API 응답 전용.
        assert "price_missing" not in r_item
        assert "calc_missing" not in r_item

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


# ─── POC2 Step 2: market cache + enrich + endpoints ────────────────────
# market_cache 격리는 autouse 의 _isolated_store 가 처리한다.


def test_market_cache_atomic_write_and_reload():
    from app import market_cache

    q1 = market_cache.MarketQuote(
        ticker="069500",
        name="KODEX 200",
        current_price=100240.0,
        price_asof="2026-04-27T16:10:16+09:00",
        price_source="naver",
    )
    market_cache.upsert_many([q1])

    # 메모리 + 디스크 모두에 반영
    assert market_cache.get("069500") is not None
    assert market_cache.CACHE_FILE.exists()

    # 메모리 리셋 후 디스크에서 재로드되는지 확인
    market_cache.reset_for_test()
    reloaded = market_cache.get("069500")
    assert reloaded is not None
    assert reloaded.current_price == 100240.0
    assert reloaded.name == "KODEX 200"


def test_market_cache_rejects_bad_price_on_load(tmp_path):
    """디스크에 저장된 음수/0 가격은 로드 시 None 으로 정규화."""
    import json
    from app import market_cache

    market_cache.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    market_cache.CACHE_FILE.write_text(
        json.dumps(
            {
                "updated_at": "x",
                "items": {
                    "069500": {
                        "ticker": "069500",
                        "name": "K200",
                        "current_price": -1,
                        "price_asof": None,
                        "price_source": "naver",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    market_cache.reset_for_test()
    quote = market_cache.get("069500")
    assert quote is not None
    assert quote.current_price is None  # 정규화됨


def test_naver_parse_price_handles_comma_string():
    from app import market_naver

    assert market_naver._parse_price("100,240") == 100240.0
    assert market_naver._parse_price(38500) == 38500.0
    assert market_naver._parse_price("0") is None
    assert market_naver._parse_price(None) is None
    assert market_naver._parse_price("") is None
    assert market_naver._parse_price("abc") is None


def test_naver_fetch_one_handles_http_error(monkeypatch):
    """fetch_one 이 예외를 raise 하지 않고 FetchResult 로 캡슐화하는지 확인."""
    import httpx
    from app import market_naver

    class _BoomClient:
        def get(self, *args, **kwargs):
            raise httpx.TimeoutException("boom", request=None)

    result = market_naver.fetch_one("069500", client=_BoomClient())
    assert result.quote is None
    assert result.reason == "timeout"
    assert result.ticker == "069500"


def test_naver_fetch_one_handles_non_200(monkeypatch):
    from app import market_naver

    class _Resp:
        status_code = 500

        def json(self):
            return {}

    class _Client:
        def get(self, *args, **kwargs):
            return _Resp()

    result = market_naver.fetch_one("069500", client=_Client())
    assert result.quote is None
    assert result.reason == "http_500"


def test_naver_fetch_one_parses_real_payload_shape():
    """Naver 실 응답 shape 모킹 — closePrice 콤마 / stockName / localTradedAt 매핑."""
    from app import market_naver

    class _Resp:
        status_code = 200

        def json(self):
            return {
                "stockName": "RISE 미국은행TOP10",
                "closePrice": "11,920",
                "localTradedAt": "2026-04-27T16:10:16+09:00",
            }

    class _Client:
        def get(self, *args, **kwargs):
            return _Resp()

    result = market_naver.fetch_one("0013P0", client=_Client())
    assert result.quote is not None
    assert result.quote.ticker == "0013P0"
    assert result.quote.name == "RISE 미국은행TOP10"
    assert result.quote.current_price == 11920.0
    assert result.quote.price_asof == "2026-04-27T16:10:16+09:00"
    assert result.quote.price_source == "naver"
    assert result.reason is None


def test_holdings_enrich_full_calculation():
    """모든 시세가 캐시에 있을 때: eval/pnl/시장비중 계산 + price_missing False."""
    from app.holdings import Holding
    from app.holdings_enrich import enrich_holdings
    from app.market_cache import MarketQuote

    holdings = [
        Holding(ticker="069500", name="KODEX 200", quantity=10, avg_buy_price=38500),
        Holding(ticker="091160", quantity=5, avg_buy_price=22000),
    ]
    quotes = {
        "069500": MarketQuote(
            ticker="069500",
            name="KODEX 200",
            current_price=40000.0,
            price_asof="2026-04-27",
            price_source="naver",
        ),
        "091160": MarketQuote(
            ticker="091160",
            name="KODEX 코스닥150",
            current_price=20000.0,  # 손실 (avg=22000)
            price_asof="2026-04-27",
            price_source="naver",
        ),
    }
    enriched = enrich_holdings(holdings, quotes)
    assert len(enriched) == 2

    # 첫 종목: eval=400000, pnl=400000-385000=15000, rate=15000/385000*100
    e0 = enriched[0]
    assert e0.eval_amount == 400000.0
    assert e0.pnl_amount == 15000.0
    assert round(e0.pnl_rate_pct or 0, 2) == round(15000 / 385000 * 100, 2)
    assert e0.price_missing is False
    assert e0.calc_missing is False

    # 둘째 종목: 손실 — pnl 음수
    e1 = enriched[1]
    assert e1.eval_amount == 100000.0  # 5 * 20000
    assert e1.pnl_amount == -10000.0  # 100000 - 110000
    assert (e1.pnl_rate_pct or 0) < 0

    # 시장비중 합계 = 100% (반올림 오차 1pp 내 허용)
    total_mw = (e0.market_weight_pct or 0) + (e1.market_weight_pct or 0)
    assert abs(total_mw - 100.0) < 0.01

    # holdings name 미입력 종목은 quote.name 으로 폴백
    assert e1.name == "KODEX 코스닥150"


def test_holdings_enrich_partial_cache_marks_missing():
    """일부 종목만 캐시에 있을 때: 없는 종목은 price_missing=True, 시세 필드 None."""
    from app.holdings import Holding
    from app.holdings_enrich import enrich_holdings, to_recommendation_dict
    from app.market_cache import MarketQuote

    holdings = [
        Holding(ticker="069500", quantity=10, avg_buy_price=38500),
        Holding(ticker="091160", quantity=5, avg_buy_price=22000),  # 캐시 없음
    ]
    quotes = {
        "069500": MarketQuote(
            ticker="069500",
            name="KODEX 200",
            current_price=40000.0,
            price_asof=None,
            price_source="naver",
        )
    }
    enriched = enrich_holdings(holdings, quotes)
    assert enriched[0].price_missing is False
    assert enriched[1].price_missing is True
    assert enriched[1].current_price is None
    assert enriched[1].eval_amount is None
    assert enriched[1].pnl_amount is None
    assert enriched[1].market_weight_pct is None  # eval_amount 없으니 시장비중도 None

    # to_recommendation_dict 결과에서 None 인 시세 필드는 키 자체가 생략된다.
    # price_missing / calc_missing 메타 flag 는 draft_payload 에 포함되지 않는다
    # (지시문 허용 필드 외 변경 금지 — UI/메시지 렌더러는 키 존재 여부로 판단).
    rec1 = to_recommendation_dict(enriched[1])
    assert "current_price" not in rec1
    assert "eval_amount" not in rec1
    assert "pnl_amount" not in rec1
    assert "market_weight_pct" not in rec1
    assert "price_missing" not in rec1
    assert "calc_missing" not in rec1
    # 그러나 EnrichedHolding 객체 자체에는 flag 가 유지된다 (enrich API 응답용)
    assert enriched[1].price_missing is True


def test_holdings_enrich_empty_cache_keeps_step1_compatibility():
    """캐시가 완전히 비어도 invested_amount + buy_weight_pct 는 계산되어야 (Step1 호환)."""
    from app.holdings import Holding
    from app.holdings_enrich import enrich_holdings

    holdings = [
        Holding(ticker="069500", quantity=10, avg_buy_price=38500),
        Holding(ticker="091160", quantity=5, avg_buy_price=22000),
    ]
    enriched = enrich_holdings(holdings, {})
    assert enriched[0].invested_amount == 385000.0
    assert enriched[1].invested_amount == 110000.0
    # 매입비중은 항상 계산 가능 (invested_total > 0)
    assert enriched[0].buy_weight_pct is not None
    assert enriched[1].buy_weight_pct is not None
    # 모든 종목 price_missing=True
    assert all(e.price_missing for e in enriched)


def test_market_refresh_endpoint_does_not_call_naver_on_get(client, monkeypatch):
    """GET /holdings/enriched 는 절대 Naver fetch 를 트리거하지 않는다."""
    from app import market_naver

    call_count = {"n": 0}

    def _spy(tickers, **kw):
        call_count["n"] += 1
        return []

    monkeypatch.setattr(market_naver, "fetch_many", _spy)

    client.put("/holdings", json={"holdings": _VALID_HOLDINGS})
    # GET /holdings/enriched 호출 — 캐시 없어도 fetch 안 함
    r = client.get("/holdings/enriched")
    assert r.status_code == 200
    assert call_count["n"] == 0
    items = r.json()["items"]
    assert all(it["price_missing"] is True for it in items)


def test_market_refresh_endpoint_calls_naver_only_on_post(client, monkeypatch):
    """POST /market/refresh 만 Naver fetch 를 트리거하고 캐시에 반영."""
    from app import market_cache, market_naver

    def _fake_fetch_many(tickers, **kw):
        results = []
        for t in tickers:
            results.append(
                market_naver.FetchResult(
                    ticker=t,
                    quote=market_cache.MarketQuote(
                        ticker=t,
                        name=f"name_{t}",
                        current_price=12345.0,
                        price_asof="2026-04-27T00:00:00+09:00",
                        price_source="naver",
                    ),
                    reason=None,
                )
            )
        return results

    monkeypatch.setattr(market_naver, "fetch_many", _fake_fetch_many)

    client.put("/holdings", json={"holdings": _VALID_HOLDINGS})
    r = client.post("/market/refresh")
    assert r.status_code == 200
    body = r.json()
    assert body["ok_count"] == 2
    assert body["fail_count"] == 0
    assert len(body["items"]) == 2

    # 이후 GET /holdings/enriched 가 시세 반영된 결과 반환
    r2 = client.get("/holdings/enriched")
    items = r2.json()["items"]
    assert all(it["price_missing"] is False for it in items)
    assert all(it["current_price"] == 12345.0 for it in items)


def test_market_refresh_isolates_per_ticker_failure(client, monkeypatch):
    """단일 종목 실패는 나머지 진행을 막지 않는다."""
    from app import market_cache, market_naver

    def _fake_fetch_many(tickers, **kw):
        results = []
        for t in tickers:
            if t == "091160":
                results.append(
                    market_naver.FetchResult(ticker=t, quote=None, reason="timeout")
                )
            else:
                results.append(
                    market_naver.FetchResult(
                        ticker=t,
                        quote=market_cache.MarketQuote(
                            ticker=t,
                            name="X",
                            current_price=999.0,
                            price_asof=None,
                            price_source="naver",
                        ),
                        reason=None,
                    )
                )
        return results

    monkeypatch.setattr(market_naver, "fetch_many", _fake_fetch_many)
    client.put("/holdings", json={"holdings": _VALID_HOLDINGS})
    r = client.post("/market/refresh")
    body = r.json()
    assert body["ok_count"] == 1
    assert body["fail_count"] == 1
    assert any(
        f["ticker"] == "091160" and f["reason"] == "timeout" for f in body["failures"]
    )


def test_market_refresh_blocks_on_empty_holdings_422(client):
    r = client.post("/market/refresh")
    assert r.status_code == 422


def test_generate_from_holdings_uses_cached_market_data(client, monkeypatch):
    """캐시에 시세가 있으면 generate-from-holdings 가 자동으로 enrich 한다 (외부 fetch 없이)."""
    from app import market_cache, market_naver

    # 1. holdings 저장
    client.put("/holdings", json={"holdings": _VALID_HOLDINGS})

    # 2. market_cache 에 직접 시세 주입 (Naver fetch 모킹 없음)
    market_cache.upsert_many(
        [
            market_cache.MarketQuote(
                ticker="069500",
                name="KODEX 200",
                current_price=40000.0,
                price_asof="2026-04-27",
                price_source="naver",
            )
        ]
    )

    # 3. generate-from-holdings 호출. fetch_many 가 호출되면 안 됨.
    sentinel = {"called": False}

    def _spy(tickers, **kw):
        sentinel["called"] = True
        return []

    monkeypatch.setattr(market_naver, "fetch_many", _spy)

    r = client.post("/runs/generate-from-holdings")
    assert r.status_code == 200
    assert sentinel["called"] is False

    recs = r.json()["draft_payload"]["recommendations"]
    # 캐시에 있는 069500 은 시세 필드 포함
    rec0 = next(rc for rc in recs if rc["ticker"] == "069500")
    assert rec0["current_price"] == 40000.0
    assert rec0["eval_amount"] == 400000.0
    assert rec0["pnl_amount"] == 400000.0 - 385000.0
    # price_missing / calc_missing 메타 flag 는 draft_payload 에 없다
    assert "price_missing" not in rec0
    assert "calc_missing" not in rec0

    # 캐시에 없는 091160 은 시세 필드 키 자체가 생략됨 (UI/메시지가 키 존재로 판단)
    rec1 = next(rc for rc in recs if rc["ticker"] == "091160")
    assert "current_price" not in rec1
    assert "eval_amount" not in rec1
    assert "price_missing" not in rec1


def test_draft_message_includes_market_lines_when_present():
    """draft_message 가 enrich 된 payload 에서 현재가/평가금액/평가손익/평가수익률/시장비중을 표시."""
    from app import draft_message

    payload = {
        "title": "보유 종목 기반 초안 (test)",
        "asof": "x",
        "note": "n",
        "recommendations": [
            {
                "ticker": "069500",
                "name": "KODEX 200",
                "quantity": 10,
                "avg_buy_price": 38500,
                "invested_amount": 385000,
                "buy_weight_pct": 100.0,
                "current_price": 40000,
                "eval_amount": 400000,
                "pnl_amount": 15000,
                "pnl_rate_pct": 3.9,
                "market_weight_pct": 100.0,
                "action": "HOLD",
                "reason": "보유 종목 현황",
            }
        ],
    }
    msg = draft_message.build_message_text("run_x", payload)
    assert "현재가: 40,000원" in msg
    assert "평가금액: 400,000원" in msg
    assert "평가손익: 15,000원" in msg
    assert "평가수익률: 3.9%" in msg
    assert "시장비중: 100%" in msg
    # "실시간" 이라는 단어는 사용하지 않는다 (지시문 금지어)
    assert "실시간" not in msg


def test_draft_message_shows_price_missing_marker_by_key_absence():
    """current_price 키 자체가 없는 holdings 항목은 [시세 미확인] 표시."""
    from app import draft_message

    payload = {
        "title": "x",
        "asof": "x",
        "note": "",
        "recommendations": [
            {
                "ticker": "069500",
                "name": "KODEX 200",
                "quantity": 10,
                "avg_buy_price": 38500,
                "invested_amount": 385000,
                "buy_weight_pct": 100.0,
                "action": "HOLD",
            }
        ],
    }
    msg = draft_message.build_message_text("run_x", payload)
    assert "[시세 미확인]" in msg
    # 시세/평가 줄은 표시되지 않음
    assert "현재가:" not in msg
    assert "평가금액:" not in msg
    # undefined / null / NaN 노출 금지
    assert "undefined" not in msg
    assert "None" not in msg
    assert "NaN" not in msg


def test_market_cache_preserves_other_tickers_after_restart_partial_refresh():
    """서버 재시작 직후 일부 종목만 fetch 성공해도 기존 디스크 캐시의 타 종목이 유실되지 않는다.

    재현 시나리오 (Codex REJECTED 지적):
    1. 캐시에 069500, 091160 2건 존재
    2. 서버 재시작 시뮬레이션 (메모리 리셋)
    3. POST /market/refresh 가 069500 만 성공 (091160 은 timeout 등으로 실패)
    4. upsert_many([069500]) 호출
    5. 디스크에 091160 의 기존 값이 그대로 보존되어야 한다.
    """
    from app import market_cache

    # 1) 초기 캐시 2건 작성
    market_cache.upsert_many(
        [
            market_cache.MarketQuote(
                ticker="069500",
                name="KODEX 200",
                current_price=100000.0,
                price_asof="2026-04-27",
                price_source="naver",
            ),
            market_cache.MarketQuote(
                ticker="091160",
                name="KODEX 코스닥150",
                current_price=22000.0,
                price_asof="2026-04-27",
                price_source="naver",
            ),
        ]
    )
    assert market_cache.get("069500") is not None
    assert market_cache.get("091160") is not None

    # 2) 서버 재시작 시뮬레이션 — 메모리 리셋 (디스크는 그대로)
    market_cache.reset_for_test()

    # 3) refresh 가 069500 만 성공한 상황 — 새 가격으로 upsert
    market_cache.upsert_many(
        [
            market_cache.MarketQuote(
                ticker="069500",
                name="KODEX 200",
                current_price=101000.0,  # 갱신값
                price_asof="2026-04-28",
                price_source="naver",
            )
        ]
    )

    # 4) 091160 의 기존 캐시가 보존되어야 한다 (메모리 + 디스크 모두)
    assert market_cache.get("069500").current_price == 101000.0  # 갱신됨
    assert market_cache.get("091160") is not None  # 보존됨
    assert market_cache.get("091160").current_price == 22000.0  # 기존값 유지

    # 5) 한 번 더 재시작 시뮬레이션 → 디스크 재로드도 동일해야 함
    market_cache.reset_for_test()
    assert market_cache.get("069500").current_price == 101000.0
    assert market_cache.get("091160") is not None
    assert market_cache.get("091160").current_price == 22000.0


def test_market_cache_rolls_back_on_disk_write_failure(monkeypatch):
    """디스크 쓰기 실패 시 메모리 캐시가 직전 스냅샷으로 원복되어 디스크와 일관."""
    from app import market_cache

    # 1) 정상 쓰기 1건 — 캐시 + 디스크에 q1 존재
    q1 = market_cache.MarketQuote(
        ticker="069500",
        name="KODEX 200",
        current_price=100240.0,
        price_asof=None,
        price_source="naver",
    )
    market_cache.upsert_many([q1])
    assert market_cache.get("069500") is not None

    # 2) 쓰기 실패 주입 — _atomic_write 가 raise
    def _boom(path, text):
        raise OSError("disk write failure injected")

    monkeypatch.setattr(market_cache, "_atomic_write", _boom)

    q2 = market_cache.MarketQuote(
        ticker="091160",
        name="KODEX 코스닥150",
        current_price=22000.0,
        price_asof=None,
        price_source="naver",
    )
    with pytest.raises(OSError):
        market_cache.upsert_many([q2])

    # 3) 메모리 롤백 검증 — q1 만 존재하고 q2 는 들어있지 않아야 함
    assert market_cache.get("069500") is not None  # 직전 값 유지
    assert market_cache.get("091160") is None  # 실패한 신규 값은 메모리에서도 제거됨

    # 4) 디스크 재로드 시에도 일관 — 메모리 리셋 후 디스크 다시 읽었을 때 q1 만
    market_cache.reset_for_test()
    assert market_cache.get("069500") is not None
    assert market_cache.get("091160") is None
