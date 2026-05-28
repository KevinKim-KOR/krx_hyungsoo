"""Decision Evidence FastAPI 엔드포인트 통합 테스트.

2026-05-21 갱신 (AI Sessions / Context Bridge):
- 3 분리 답변 필드 + has_* 플래그.
- 최소 1개 답변 필수 검증.
"""

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
        gpt_answer_text="GPT 답변 전문",
        gemini_answer_text="",
        claude_answer_text="",
        user_memo="사용자 메모",
        user_verdict="needs_constituents",
        next_checks=["KODEX200 대비 초과수익 확인"],
        linked_market_refresh_id=None,
    )
    base.update(override)
    return base


@pytest.fixture
def api_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    fake_db = tmp_path / "decision_evidence.sqlite"
    monkeypatch.setattr(decision_evidence_store, "DEFAULT_DB_PATH", fake_db)
    monkeypatch.setattr(api_decision_sessions, "DEFAULT_DB_PATH", fake_db)
    return TestClient(api_module.app)


def test_post_decision_sessions_stores_full_payload(api_client):
    res = api_client.post("/decision/sessions", json=_payload())
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["id"].startswith("decision_")
    assert body["created_at"]


def test_post_decision_sessions_round_trip_three_answers(api_client):
    p = _payload(
        gpt_answer_text="GPT 답변 전문",
        gemini_answer_text="Gemini 답변 전문",
        claude_answer_text="Claude 답변 전문",
    )
    res = api_client.post("/decision/sessions", json=p)
    rid = res.json()["id"]

    detail = api_client.get(f"/decision/sessions/{rid}").json()
    assert detail["status"] == "ok"
    rec = detail["record"]
    assert rec["question_text"] == "AI 에게 보낸 질문 전문"
    assert rec["gpt_answer_text"] == "GPT 답변 전문"
    assert rec["gemini_answer_text"] == "Gemini 답변 전문"
    assert rec["claude_answer_text"] == "Claude 답변 전문"
    assert rec["user_verdict"] == "needs_constituents"
    assert rec["candidate_snapshot"][0]["ticker"] == "139260"
    assert rec["filters"]["exclude_inverse"] is True
    assert rec["next_checks"] == ["KODEX200 대비 초과수익 확인"]


def test_post_decision_sessions_rejects_invalid_user_verdict(api_client):
    bad = _payload(user_verdict="buy_now")
    res = api_client.post("/decision/sessions", json=bad)
    assert res.status_code == 422


def test_post_decision_sessions_rejects_empty_candidate_snapshot(api_client):
    bad = _payload(candidate_snapshot=[])
    res = api_client.post("/decision/sessions", json=bad)
    assert res.status_code == 422


def test_post_decision_sessions_requires_question(api_client):
    res_q = api_client.post("/decision/sessions", json=_payload(question_text=""))
    assert res_q.status_code == 422


def test_post_decision_sessions_rejects_all_empty_answers(api_client):
    """3개 답변 모두 비어있으면 422."""
    bad = _payload(
        gpt_answer_text="",
        gemini_answer_text="",
        claude_answer_text="",
    )
    res = api_client.post("/decision/sessions", json=bad)
    assert res.status_code == 422


def test_post_decision_sessions_accepts_only_gemini(api_client):
    """답변 중 1개만 있어도 통과."""
    p = _payload(
        gpt_answer_text="",
        gemini_answer_text="Gemini 답변",
        claude_answer_text="",
    )
    res = api_client.post("/decision/sessions", json=p)
    assert res.status_code == 200


def test_post_decision_sessions_rejects_incomplete_filters(api_client):
    """filters 4 필드 중 누락 → 422 (snapshot 정합성 fail-loud)."""
    res_empty = api_client.post("/decision/sessions", json=_payload(filters={}))
    assert res_empty.status_code == 422
    partial = {"exclude_inverse": True, "exclude_leveraged": True}
    res_partial = api_client.post("/decision/sessions", json=_payload(filters=partial))
    assert res_partial.status_code == 422


def test_get_decision_sessions_includes_has_answer_flags(api_client):
    api_client.post(
        "/decision/sessions",
        json=_payload(
            gpt_answer_text="GPT", gemini_answer_text="", claude_answer_text=""
        ),
    )
    api_client.post(
        "/decision/sessions",
        json=_payload(
            gpt_answer_text="",
            gemini_answer_text="Gemini",
            claude_answer_text="Claude",
        ),
    )

    res = api_client.get("/decision/sessions?limit=10")
    body = res.json()
    assert body["status"] == "ok"
    assert len(body["records"]) == 2

    latest, earlier = body["records"]
    assert latest["has_gpt_answer"] is False
    assert latest["has_gemini_answer"] is True
    assert latest["has_claude_answer"] is True
    assert earlier["has_gpt_answer"] is True
    assert earlier["has_gemini_answer"] is False
    assert earlier["has_claude_answer"] is False


def test_get_decision_sessions_lists_recent_first(api_client):
    api_client.post("/decision/sessions", json=_payload(asof="2026-05-13"))
    api_client.post("/decision/sessions", json=_payload(asof="2026-05-14"))
    api_client.post("/decision/sessions", json=_payload(asof="2026-05-15"))

    res = api_client.get("/decision/sessions?limit=10")
    body = res.json()
    assert len(body["records"]) == 3
    assert body["records"][0]["asof"] == "2026-05-15"
    assert body["records"][0]["candidate_count"] == 1


def test_get_decision_session_detail_not_found(api_client):
    res = api_client.get("/decision/sessions/decision_unknown_id")
    body = res.json()
    assert body["status"] == "not_found"
    assert body["record"] is None
    assert body["message"] == "Decision session not found."


def test_decision_db_is_separate_from_market_db(api_client):
    """AC-17 — decision_evidence.sqlite 는 market_data.sqlite 와 분리."""
    import importlib

    from app import market_data_store

    assert decision_evidence_store.DEFAULT_DB_PATH != market_data_store.DEFAULT_DB_PATH
    fresh = importlib.import_module("app.decision_evidence_store")
    importlib.reload(fresh)
    assert "decision" in str(fresh.DEFAULT_DB_PATH).replace("\\", "/")
    assert "decision_evidence.sqlite" in str(fresh.DEFAULT_DB_PATH).replace("\\", "/")


def test_post_decision_sessions_accepts_default_user_verdict(api_client):
    p = _payload()
    p.pop("user_verdict")
    res = api_client.post("/decision/sessions", json=p)
    assert res.status_code == 200
    rid = res.json()["id"]
    detail = api_client.get(f"/decision/sessions/{rid}").json()
    assert detail["record"]["user_verdict"] == "hold"


# ─── market_context_snapshot 저장/조회 (2026-05-22) ─────────────────


def test_post_decision_sessions_stores_market_context_snapshot(api_client):
    p = _payload(
        market_context_snapshot={
            "regime_label": "상승장",
            "regime_code": "bull",
            "primary_benchmark": "KODEX200",
            "kodex200": {
                "return_20d_pct": 3.2,
                "return_60d_pct": 6.1,
                "ma20_position": "above",
                "ma60_position": "above",
            },
            "kospi": {
                "status": "ok",
                "return_20d_pct": 2.7,
                "return_60d_pct": 5.4,
            },
        }
    )
    res = api_client.post("/decision/sessions", json=p)
    assert res.status_code == 200
    rid = res.json()["id"]

    detail = api_client.get(f"/decision/sessions/{rid}").json()
    rec = detail["record"]
    snap = rec["market_context_snapshot"]
    assert snap["regime_label"] == "상승장"
    assert snap["regime_code"] == "bull"
    assert snap["primary_benchmark"] == "KODEX200"
    assert snap["kodex200"]["return_20d_pct"] == 3.2
    assert snap["kospi"]["return_60d_pct"] == 5.4


def test_post_decision_sessions_without_market_context_snapshot_defaults_to_empty(
    api_client,
):
    """기존 payload (market_context_snapshot 미포함) 도 저장 가능 — 회귀 보호."""
    p = _payload()
    assert "market_context_snapshot" not in p
    res = api_client.post("/decision/sessions", json=p)
    assert res.status_code == 200
    rid = res.json()["id"]
    detail = api_client.get(f"/decision/sessions/{rid}").json()
    assert detail["record"]["market_context_snapshot"] == {}


# ─── constituent_snapshot / overlap_snapshot 저장/조회 (2026-05-27) ───


def test_post_decision_sessions_stores_constituent_and_overlap_snapshots(api_client):
    constituent_snap = {
        "asof": "2026-05-26",
        "top_k": 10,
        "items": [
            {
                "etf_ticker": "139260",
                "etf_name": "TIGER 200 IT",
                "status": "ok",
                "source": "pykrx/get_etf_portfolio_deposit_file",
                "top_holdings": [
                    {
                        "rank": 1,
                        "ticker": "005930",
                        "name": "삼성전자",
                        "weight_pct": 25.1,
                    }
                ],
                "concentration": {
                    "top1_weight_pct": 25.1,
                    "top3_weight_pct": 52.4,
                    "top5_weight_pct": 66.2,
                    "top10_weight_pct": 82.0,
                },
            }
        ],
    }
    overlap_snap = {
        "matrix": [
            {
                "left_ticker": "139260",
                "right_ticker": "363580",
                "common_count_top10": 7,
                "weighted_overlap_pct": 63.2,
            }
        ],
        "repeated_core": [
            {"ticker": "005930", "name": "삼성전자", "appears_in_etf_count": 5}
        ],
    }
    p = _payload(
        constituent_snapshot=constituent_snap,
        overlap_snapshot=overlap_snap,
    )
    res = api_client.post("/decision/sessions", json=p)
    assert res.status_code == 200
    rid = res.json()["id"]

    detail = api_client.get(f"/decision/sessions/{rid}").json()
    rec = detail["record"]
    assert rec["constituent_snapshot"]["items"][0]["etf_ticker"] == "139260"
    assert (
        rec["constituent_snapshot"]["items"][0]["concentration"]["top1_weight_pct"]
        == 25.1
    )
    assert rec["overlap_snapshot"]["matrix"][0]["weighted_overlap_pct"] == 63.2
    assert rec["overlap_snapshot"]["repeated_core"][0]["ticker"] == "005930"


def test_post_decision_sessions_without_constituent_overlap_defaults_to_empty(
    api_client,
):
    """기존 payload 호환성 — constituent/overlap 미포함 시 빈 dict 로 응답."""
    p = _payload()
    assert "constituent_snapshot" not in p
    assert "overlap_snapshot" not in p
    res = api_client.post("/decision/sessions", json=p)
    rid = res.json()["id"]
    detail = api_client.get(f"/decision/sessions/{rid}").json()
    assert detail["record"]["constituent_snapshot"] == {}
    assert detail["record"]["overlap_snapshot"] == {}
