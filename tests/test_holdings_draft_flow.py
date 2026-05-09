"""POC2 Step 5D-2 Cleanup — holdings draft 핵심 흐름 (Step1/1A/2D).

분리 출처: tests/test_holdings_draft_flow.py (Step 5D-2 이전 단일 파일).
테스트 의미 / 검증 강도 / 동작은 분리 전과 동일.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app import api

from tests._helpers import (
    _VALID_HOLDINGS,
    _VALID_HOLDINGS_FOR_2D,
    _VALID_INPUT,
    _generate,
)


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

    # (ticker, account_group, avg_buy_price) 삼중 중복 — Step 2C 정책으로 차단
    r = client.put(
        "/holdings",
        json={
            "holdings": [
                {
                    "ticker": "069500",
                    "quantity": 1,
                    "avg_buy_price": 100,
                    "account_group": "일반",
                },
                {
                    "ticker": "069500",
                    "quantity": 2,
                    "avg_buy_price": 100,
                    "account_group": "일반",
                },
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
    # POC2 Step 2: 시세가 없으면 8 키(Step 1 호환) + Step 2C 추가 키 2개.
    # 시세가 있을 때만 시세 필드(current_price 등) 가 키로 추가된다.
    # Step 2C: account_group(표시/그룹용 라벨) + source_index(UI key 안정성) 가 항상 포함.
    expected_keys = {
        "ticker",
        "name",
        "quantity",
        "avg_buy_price",
        "invested_amount",
        "buy_weight_pct",
        "action",
        "reason",
        "account_group",
        "source_index",
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


def test_step2d_generate_from_holdings_persists_message_text(client):
    """신규 run 은 generate 시점에 백엔드가 message_text 를 빌드해 Run 에 저장하고,
    GET /runs/{id} 응답에 포함된다."""
    client.put("/holdings", json={"holdings": _VALID_HOLDINGS_FOR_2D})
    r = client.post("/runs/generate-from-holdings")
    assert r.status_code == 200
    body = r.json()
    assert "message_text" in body
    assert isinstance(body["message_text"], str)
    assert len(body["message_text"]) > 0
    # 운영 흐름의 핵심 토큰이 포함되어야 함 (Step 2B 정책의 헤더)
    assert "POC2 holdings 승인 처리" in body["message_text"]
    assert body["run_id"] in body["message_text"]

    # 같은 run_id 로 GET 했을 때도 동일 message_text
    rid = body["run_id"]
    r2 = client.get(f"/runs/{rid}")
    assert r2.status_code == 200
    body2 = r2.json()
    assert body2["message_text"] == body["message_text"]


def test_step2d_generate_sample_no_message_text_for_non_holdings(client):
    """샘플(비-holdings) 초안은 message_text 가 None — 프론트는 정적 fallback 표시."""
    status, body = _generate(client, _VALID_INPUT)
    assert status == 200
    # holdings 식별 불가 payload → build_message_text 가 빈 문자열 반환 → Run.message_text=None
    assert body.get("message_text") in (None, "")
