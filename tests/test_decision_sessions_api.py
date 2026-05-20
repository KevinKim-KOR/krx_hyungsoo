"""Decision Evidence FastAPI 엔드포인트 통합 테스트 (POC2 — AI 투자세션 기록 1차)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import api as api_module
from app import api_decision_sessions, decision_evidence_store


def _payload(**override):
    base = dict(
        asof="2026-05-15",
        source_screen="market_discovery",
        filters={
            "exclude_inverse": True,
            "exclude_leveraged": True,
            "exclude_synthetic": True,
            "exclude_futures": True,
        },
        candidate_snapshot=[
            {
                "rank": 1,
                "ticker": "139260",
                "name": "TIGER 200 IT",
                "daily_return_pct": -3.73,
                "one_month_return_pct": 49.87,
                "three_month_return_pct": 82.05,
                "tags": [],
            }
        ],
        question_text="AI 에게 보낸 질문 전문",
        answer_text="AI 답변 전문",
        user_memo="사용자 메모",
        user_verdict="needs_constituents",
        next_checks=["KODEX200 대비 초과수익 확인"],
        linked_market_refresh_id=None,
    )
    base.update(override)
    return base


@pytest.fixture
def api_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    """endpoint 가 사용하는 DB 경로를 tmp 로 교체."""
    fake_db = tmp_path / "decision_evidence.sqlite"
    monkeypatch.setattr(decision_evidence_store, "DEFAULT_DB_PATH", fake_db)
    monkeypatch.setattr(api_decision_sessions, "DEFAULT_DB_PATH", fake_db)
    return TestClient(api_module.app)


def test_post_decision_sessions_stores_full_payload(api_client, tmp_path: Path):
    res = api_client.post("/decision/sessions", json=_payload())
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["id"].startswith("decision_")
    assert body["created_at"]


def test_post_decision_sessions_round_trip_detail(api_client):
    res = api_client.post("/decision/sessions", json=_payload())
    rid = res.json()["id"]

    detail = api_client.get(f"/decision/sessions/{rid}").json()
    assert detail["status"] == "ok"
    rec = detail["record"]
    assert rec["question_text"] == "AI 에게 보낸 질문 전문"
    assert rec["answer_text"] == "AI 답변 전문"
    assert rec["user_memo"] == "사용자 메모"
    assert rec["user_verdict"] == "needs_constituents"
    assert rec["candidate_snapshot"][0]["ticker"] == "139260"
    assert rec["filters"]["exclude_inverse"] is True
    assert rec["next_checks"] == ["KODEX200 대비 초과수익 확인"]


def test_post_decision_sessions_rejects_invalid_user_verdict(api_client):
    bad = _payload(user_verdict="buy_now")
    res = api_client.post("/decision/sessions", json=bad)
    # FastAPI Literal 검증 → 422.
    assert res.status_code == 422


def test_post_decision_sessions_rejects_empty_candidate_snapshot(api_client):
    bad = _payload(candidate_snapshot=[])
    res = api_client.post("/decision/sessions", json=bad)
    # store-level DecisionValidationError → 422.
    assert res.status_code == 422


def test_post_decision_sessions_requires_question_and_answer(api_client):
    res_q = api_client.post("/decision/sessions", json=_payload(question_text=""))
    res_a = api_client.post("/decision/sessions", json=_payload(answer_text=""))
    assert res_q.status_code == 422
    assert res_a.status_code == 422


def test_post_decision_sessions_rejects_incomplete_filters(api_client):
    """검증자 B-1 NOTE 반영 — filters 의 4 필드 중 하나라도 누락이면 422.

    default True 로 덮으면 실제 적용 필터와 저장 snapshot 이 어긋날 수 있어
    fail-loud 로 차단한다.
    """
    # 빈 filters dict.
    res_empty = api_client.post("/decision/sessions", json=_payload(filters={}))
    assert res_empty.status_code == 422

    # 일부 필드만 누락.
    partial = {"exclude_inverse": True, "exclude_leveraged": True}
    res_partial = api_client.post("/decision/sessions", json=_payload(filters=partial))
    assert res_partial.status_code == 422


def test_get_decision_sessions_lists_recent_first(api_client):
    api_client.post("/decision/sessions", json=_payload(asof="2026-05-13"))
    api_client.post("/decision/sessions", json=_payload(asof="2026-05-14"))
    api_client.post("/decision/sessions", json=_payload(asof="2026-05-15"))

    res = api_client.get("/decision/sessions?limit=10")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert len(body["records"]) == 3
    # 최신 asof 가 먼저 (created_at DESC).
    assert body["records"][0]["asof"] == "2026-05-15"
    # 요약 + count 필드 포함.
    assert "summary" in body["records"][0]
    assert body["records"][0]["candidate_count"] == 1


def test_get_decision_session_detail_not_found(api_client):
    res = api_client.get("/decision/sessions/decision_unknown_id")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "not_found"
    assert body["record"] is None
    assert body["message"] == "Decision session not found."


def test_decision_db_is_separate_from_market_db(api_client, tmp_path: Path):
    """AC-15 — decision_evidence.sqlite 는 market_data.sqlite 와 분리된다."""
    from app import market_data_store

    # tmp DB 경로 (test fixture 가 patch 한 것) 와 market_data_store 의 기본 경로가
    # 서로 다른 파일이어야 한다.
    assert decision_evidence_store.DEFAULT_DB_PATH != market_data_store.DEFAULT_DB_PATH
    # market_data_store 기본 경로 (운영 경로) 는 state/market/market_data.sqlite.
    assert "market" in str(market_data_store.DEFAULT_DB_PATH).replace("\\", "/")
    # decision evidence 의 운영 경로는 state/decision/decision_evidence.sqlite.
    # (fixture 에서 monkeypatch 된 tmp 가 아니라 import 시점의 모듈 상수를 본다)
    import importlib

    fresh = importlib.import_module("app.decision_evidence_store")
    # patch 가 그대로일 수 있어 reload 후 확인 — 모듈 정의 상의 상수만 검사.
    importlib.reload(fresh)
    assert "decision" in str(fresh.DEFAULT_DB_PATH).replace("\\", "/")
    assert "decision_evidence.sqlite" in str(fresh.DEFAULT_DB_PATH).replace("\\", "/")


def test_post_decision_sessions_accepts_default_user_verdict(api_client):
    # user_verdict 미지정 시 default "hold".
    p = _payload()
    p.pop("user_verdict")
    res = api_client.post("/decision/sessions", json=p)
    assert res.status_code == 200
    rid = res.json()["id"]
    detail = api_client.get(f"/decision/sessions/{rid}").json()
    assert detail["record"]["user_verdict"] == "hold"
