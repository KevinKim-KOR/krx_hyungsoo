"""Decision Draft Preview v1 — 서비스 + endpoint 자동 테스트.

지시문 §4 (저장 없음) / §7 (금지 표현) / §5 (응답 계약) 검증.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import api_decision_draft_preview
from app.api import app
from app.decision_draft_preview_service import (
    TARGET_KIND_CANDIDATE,
    TARGET_KIND_HOLDING,
    build_preview_text,
)

# ------- 서버 조립 함수 단위 테스트 -------


def test_build_preview_text_holding(tmp_path: Path) -> None:
    db = tmp_path / "market_data.sqlite"
    from app.market_data_store import init_db

    init_db(db)
    holding = {
        "ticker": "069500",
        "name": "KODEX 200",
        "market_weight_pct": 15.5,
        "pnl_rate_pct": 3.2,
        "short_term_momentum": {
            "excess_vs_kodex200_20d_pctp": 1.2,
            "end_date": "2026-07-02",
        },
        "data_quality": {"status": "ok"},
        "overlap": {"status": "not_loaded"},
    }
    res = build_preview_text(
        target_kind=TARGET_KIND_HOLDING,
        ticker="069500",
        target_evidence=holding,
        db_path=db,
    )
    assert res.status == "ok"
    assert res.ticker == "069500"
    assert res.preview_text is not None
    # 필수 5 섹션 존재.
    for header in (
        "1. 대상과 검토 맥락",
        "2. 확인된 근거",
        "3. 시장 참고",
        "4. 주의·미확인 사항",
        "5. AI에게 추가로 물어볼 질문",
    ):
        assert header in res.preview_text
    # not_loaded → 자동 조회하지 않고 문구 표시.
    assert "구성종목 중복" in res.preview_text
    # 기준일 3종 분리 표시.
    assert res.evidence_as_of.target_as_of_date == "2026-07-02"


def test_build_preview_text_candidate(tmp_path: Path) -> None:
    db = tmp_path / "market_data.sqlite"
    from app.market_data_store import init_db

    init_db(db)
    candidate = {
        "ticker": "379800",
        "name": "KODEX 미국S&P500",
        "relative_upside_score": 78.4,
        "short_term_momentum": {
            "excess_vs_kodex200_20d_pctp": 2.5,
            "end_date": "2026-07-02",
        },
        "drawdown_20d": -0.04,
        "data_quality": {"status": "warning"},
    }
    res = build_preview_text(
        target_kind=TARGET_KIND_CANDIDATE,
        ticker="379800",
        target_evidence=candidate,
        db_path=db,
    )
    assert res.status == "ok"
    assert "후보 ETF" in res.preview_text
    assert "78.4" in res.preview_text


def test_preview_forbidden_phrases_absent(tmp_path: Path) -> None:
    """지시문 §7 금지 표현 미포함."""
    db = tmp_path / "market_data.sqlite"
    from app.market_data_store import init_db

    init_db(db)
    candidate = {
        "ticker": "379800",
        "name": "TEST",
        "relative_upside_score": 50.0,
        "short_term_momentum": {},
        "drawdown_20d": None,
    }
    res = build_preview_text(
        target_kind=TARGET_KIND_CANDIDATE,
        ticker="379800",
        target_evidence=candidate,
        db_path=db,
    )
    text = res.preview_text or ""
    for phrase in (
        "지금 매수",
        "지금 매도",
        "반드시 유지",
        "위험이 높습니다",
        "위험이 낮습니다",
        "시장 전환이 예상",
    ):
        assert phrase not in text


def test_build_preview_text_invalid_kind() -> None:
    res = build_preview_text(
        target_kind="unknown",
        ticker="069500",
        target_evidence={},
    )
    assert res.status == "error"


def test_build_preview_text_empty_ticker() -> None:
    res = build_preview_text(
        target_kind=TARGET_KIND_HOLDING,
        ticker="",
        target_evidence={"ticker": "", "name": ""},
    )
    assert res.status == "error"


# ------- endpoint 통합 테스트 -------


@pytest.fixture
def stub_evidence(monkeypatch: pytest.MonkeyPatch):
    """endpoint 내부 evidence loader 를 stub — SQLite 초기화 불필요."""

    def stub_holding(ticker: str):
        if ticker == "069500":
            return {
                "ticker": "069500",
                "name": "KODEX 200",
                "market_weight_pct": 15.5,
                "pnl_rate_pct": 3.2,
                "short_term_momentum": {"end_date": "2026-07-02"},
                "data_quality": {"status": "ok"},
                "overlap": {"status": "not_loaded"},
            }
        return None

    def stub_candidate(ticker: str):
        if ticker == "379800":
            return {
                "ticker": "379800",
                "name": "TEST",
                "relative_upside_score": 78.4,
                "short_term_momentum": {"end_date": "2026-07-02"},
                "drawdown_20d": -0.04,
            }
        return None

    monkeypatch.setattr(
        api_decision_draft_preview, "_load_holdings_evidence", stub_holding
    )
    monkeypatch.setattr(
        api_decision_draft_preview, "_load_candidate_evidence", stub_candidate
    )
    return None


def test_endpoint_holding_ok(stub_evidence) -> None:
    client = TestClient(app)
    res = client.post(
        "/decision-draft/preview",
        json={"target_kind": "holding", "ticker": "069500"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["ticker"] == "069500"
    assert body["preview_text"]
    assert "evidence_as_of" in body
    assert body["evidence_as_of"]["target_as_of_date"] == "2026-07-02"


def test_endpoint_candidate_ok(stub_evidence) -> None:
    client = TestClient(app)
    res = client.post(
        "/decision-draft/preview",
        json={"target_kind": "candidate", "ticker": "379800"},
    )
    body = res.json()
    assert body["status"] == "ok"
    assert body["target_kind"] == "candidate"


def test_endpoint_unknown_ticker_returns_short_error(stub_evidence) -> None:
    client = TestClient(app)
    res = client.post(
        "/decision-draft/preview",
        json={"target_kind": "holding", "ticker": "999999"},
    )
    body = res.json()
    assert body["status"] == "error"
    assert (
        body["message"] == "판단 근거 미리보기를 생성하지 못했습니다. 다시 시도하세요."
    )
    # 내부 정보 미노출.
    forbidden_keys = ("preview_text", "target_kind", "ticker", "evidence_as_of")
    for k in forbidden_keys:
        assert body.get(k) in (None, "")


def test_endpoint_invalid_kind_returns_short_error(stub_evidence) -> None:
    client = TestClient(app)
    res = client.post(
        "/decision-draft/preview",
        json={"target_kind": "invalid", "ticker": "069500"},
    )
    body = res.json()
    assert body["status"] == "error"


def test_endpoint_response_does_not_leak_internals(stub_evidence) -> None:
    """지시문 §5.3 응답 금지 정보 미노출."""
    client = TestClient(app)
    body = client.post(
        "/decision-draft/preview",
        json={"target_kind": "holding", "ticker": "069500"},
    ).json()
    # 응답 key 집합.
    allowed = {
        "status",
        "target_kind",
        "ticker",
        "preview_text",
        "evidence_as_of",
        "message",
    }
    assert set(body.keys()) - allowed == set()
    # preview_text 안에 LLM 관련 표현 미포함.
    text = body.get("preview_text") or ""
    for banned in ("LLM", "prompt", "openai", "anthropic", "model"):
        assert banned.lower() not in text.lower()


def test_endpoint_does_not_touch_pending_draft(
    stub_evidence, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC-2 — preview 호출이 기존 PENDING 저장 경로를 건드리지 않는다."""
    from app import store

    save_calls: list = []

    def fake_save(*args, **kwargs):
        save_calls.append((args, kwargs))

    monkeypatch.setattr(store, "save", fake_save)
    client = TestClient(app)
    client.post(
        "/decision-draft/preview",
        json={"target_kind": "holding", "ticker": "069500"},
    )
    assert save_calls == []


def test_endpoint_does_not_call_external_price_sources(
    stub_evidence, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC-8 — preview 는 외부 시세 호출을 시작하지 않는다."""
    import FinanceDataReader as fdr

    calls: list = []

    def fake_reader(*args, **kwargs):
        calls.append((args, kwargs))
        raise RuntimeError("preview should not fetch external prices")

    monkeypatch.setattr(fdr, "DataReader", fake_reader)
    client = TestClient(app)
    body = client.post(
        "/decision-draft/preview",
        json={"target_kind": "holding", "ticker": "069500"},
    ).json()
    assert body["status"] == "ok"
    assert calls == []
