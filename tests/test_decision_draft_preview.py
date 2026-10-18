"""Decision Draft Preview — 서비스 + endpoint 자동 테스트.

지시문 §4 (저장 없음) / §7 (금지 표현) / §5 (응답 계약) 검증.
POC5-23(2026-10-18) — 글은 묶음 8개 · 자료는 화면 API 응답(`app/decision_preview_sources.py`).
화면 API 와의 실제 연결 검사는 `tests/test_poc5_23_decision_preview_bundles.py`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import pytest
from fastapi.testclient import TestClient

from app import api_decision_draft_preview, decision_preview_sources
from app.api import app
from app.api_holdings_market_evidence import (
    ConstituentsOverlapPayload,
    ExcessReturnPayload,
    HoldingEvidenceItem,
    HoldingSnapshot,
    HoldingsMarketEvidenceResponse,
    EvidenceSummary,
    NavDiscountPayload,
    ReturnsPayload,
    ShortTermMomentumPayload,
    TopnMatch,
)
from app.decision_draft_preview_service import (
    TARGET_KIND_CANDIDATE,
    TARGET_KIND_HOLDING,
    build_preview_text,
)
from app.decision_preview_sources import CandidateListQuery

SECTIONS = (
    "[대상]",
    "[시장]",
    "[가격 흐름 · PC 저장 종가]",
    "[KODEX200 동일 기간 비교]",
    "[거래량]",
    "[가격 흔들림]",
    "[중복 · 자료 상태]",
    "[AI에게 요청]",
)


@pytest.fixture
def tmp_db(tmp_path: Path) -> Path:
    from app.market_data_store import init_db

    db = tmp_path / "market_data.sqlite"
    init_db(db)
    return db


def _holding_item(**over: Any) -> dict[str, Any]:
    item = {
        "ticker": "069500",
        "name": "KODEX 200",
        "short_term_momentum": {
            "status": "ok",
            "return_5d_pct": -1.0,
            "return_10d_pct": -2.0,
            "return_20d_pct": -3.0,
            "excess_vs_kodex200_5d_pctp": 0.5,
            "excess_vs_kodex200_10d_pctp": None,
            "excess_vs_kodex200_20d_pctp": 1.2,
        },
        "price_dates": {
            "end_date": "2026-07-02",
            "start_date_5d": "2026-06-25",
            "start_date_20d": "2026-06-02",
            "comparison": "window_mismatch",
        },
        "decline_band": {
            "judgeable": True,
            "state": None,
            "label": None,
            "return_20d_pct_1dp": -3.0,
            "unjudged_reason": None,
        },
        "constituents_overlap": {
            "status": "constituents_unavailable",
            "overlap_with_market_core": [],
        },
        "nav_discount": {"status": "unavailable"},
        "stored_volume": None,
        "price_volatility": None,
        "same_period_kodex200": None,
    }
    item.update(over)
    return item


def _holding_evidence(
    item: Optional[dict[str, Any]] = None, **top: Any
) -> dict[str, Any]:
    ev = {
        "ticker": "069500",
        "name": "KODEX 200",
        "market_weight_pct": 15.5,
        "pnl_rate_pct": 3.2,
        "bundle": {
            "item": item or _holding_item(),
            "is_etf": True,
            "market_position": {
                "available": True,
                "regime_label": "하락장",
                "regime_streak_days": 2,
                "market_asof": "2026-07-02",
            },
            "reference_date": "2026-07-02",
            "constituents_asof": None,
        },
    }
    ev.update(top)
    return ev


def _candidate_evidence(**cand_over: Any) -> dict[str, Any]:
    cand = {
        "rank": 3,
        "ticker": "379800",
        "name": "KODEX 미국S&P500",
        "relative_upside_score": 78.4,
        "drawdown_20d": -0.04,
        "returns": {
            "one_month": {
                "return_pct": 4.0,
                "price_start_date": "2026-06-02",
                "price_end_date": "2026-07-02",
            }
        },
        "short_term_momentum": {
            "status": "ok",
            "return_5d_pct": 1.0,
            "return_10d_pct": 2.0,
            "return_20d_pct": 3.0,
            "excess_vs_kodex200_5d_pctp": 2.5,
            "excess_vs_kodex200_10d_pctp": 2.0,
            "excess_vs_kodex200_20d_pctp": 2.5,
            "end_date": "2026-07-02",
        },
        "data_quality": {
            "status": "warning",
            "daily_return_check": {"status": "unavailable"},
            "nav_discount": {"status": "unavailable"},
        },
        "same_period_kodex200": None,
    }
    cand.update(cand_over)
    return {
        "candidate": cand,
        "market_context": {
            "regime_code": "bear",
            "regime_label": "하락장",
            "asof": "2026-07-02",
            "regime_streak": {"streak_days": 2},
        },
        "basis": "one_month",
        "reference_date": "2026-07-02",
        "end_date": "2026-07-02",
        "stored_volume": None,
        "price_volatility": None,
        "direct_holding": {"held": False, "name": None},
        "overlap": {
            "candidate_asof": None,
            "candidate_available": False,
            "held_etf_count": 3,
            "pairs": [],
            "missing": [],
        },
    }


# ------- 서버 조립 함수 단위 테스트 -------


def test_build_preview_text_holding(tmp_db: Path) -> None:
    res = build_preview_text(
        target_kind=TARGET_KIND_HOLDING,
        ticker="069500",
        target_evidence=_holding_evidence(),
        db_path=tmp_db,
    )
    assert res.status == "ok"
    assert res.ticker == "069500"
    text = res.preview_text or ""
    for header in SECTIONS:
        assert header in text
    # 기존 정책 유지 — 평가 비중 · 손익.
    assert "평가비중 +15.50% · 손익률 +3.20%" in text
    # 시작일이 달라 비운 단기 차이는 사유로(줄 삭제 · 0 대입 없음).
    assert "10저장일 시작일 달라 비움" in text
    assert "20저장일 +1.20%p" in text
    # 묶음별 자료 없음 사유.
    assert (
        "구성종목 겹침: 확인 불가 — 이 ETF 의 구성종목 자료가 저장돼 있지 않습니다(겹침 없음이라는 뜻 아님)."
        in text
    )
    assert "NAV 괴리율: 자료 없음" in text
    assert "거래량 자료 없음" in text and "가격 흔들림 자료 없음" in text
    # 기준일 3종 분리.
    assert res.evidence_as_of.target_as_of_date == "2026-07-02"
    assert res.generated_at


def test_build_preview_text_candidate(tmp_db: Path) -> None:
    res = build_preview_text(
        target_kind=TARGET_KIND_CANDIDATE,
        ticker="379800",
        target_evidence=_candidate_evidence(),
        db_path=tmp_db,
    )
    assert res.status == "ok"
    text = res.preview_text or ""
    assert "후보 ETF · 현재 목록 3위(1개월 기준)" in text
    # REJECT 종료된 참고점수 · 폐기 스냅샷 고점 대비는 글에 넣지 않는다(POC5-23 판정 Q4 (a)).
    assert "78.4" not in text and "참고점수" not in text and "고점 대비" not in text
    assert "보유 ETF 와 구성종목 중복: 비교하지 않음" in text


def test_preview_forbidden_phrases_absent(tmp_db: Path) -> None:
    """지시문 §7 금지 표현 미포함."""
    for kind, ev in (
        (TARGET_KIND_CANDIDATE, _candidate_evidence()),
        (TARGET_KIND_HOLDING, _holding_evidence()),
    ):
        text = (
            build_preview_text(
                target_kind=kind, ticker="379800", target_evidence=ev, db_path=tmp_db
            ).preview_text
            or ""
        )
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
def stub_evidence(monkeypatch: pytest.MonkeyPatch, tmp_db: Path):
    """endpoint 내부 evidence loader 를 stub — 시장 참고는 tmp DB."""

    def stub_holding(ticker: str):
        return _holding_evidence() if ticker == "069500" else None

    def stub_candidate(ticker: str, query: CandidateListQuery):
        return _candidate_evidence() if ticker == "379800" else None

    monkeypatch.setattr(api_decision_draft_preview, "DEFAULT_DB_PATH", tmp_db)
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
    assert body["generated_at"]


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
    body = client.post(
        "/decision-draft/preview",
        json={"target_kind": "holding", "ticker": "999999"},
    ).json()
    assert body["status"] == "error"
    assert (
        body["message"] == "판단 근거 미리보기를 생성하지 못했습니다. 다시 시도하세요."
    )
    # 내부 정보 미노출.
    forbidden_keys = ("preview_text", "target_kind", "ticker", "evidence_as_of")
    for k in forbidden_keys:
        assert body.get(k) in (None, "")
    # 후보는 '현재 목록 조건에 없음' 사유(POC5-23 판정 §4).
    cand = client.post(
        "/decision-draft/preview",
        json={"target_kind": "candidate", "ticker": "999999", "basis": "three_month"},
    ).json()
    assert cand["status"] == "error"
    assert cand["message"] == (
        "현재 목록 조건에서 이 후보를 찾지 못했습니다. 목록을 다시 불러온 뒤 시도하세요."
    )


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
    # 응답 key 집합(POC5-23 — 생성 시각 선택 필드 하나 추가).
    allowed = {
        "status",
        "target_kind",
        "ticker",
        "preview_text",
        "evidence_as_of",
        "generated_at",
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


def test_load_holdings_evidence_returns_dict_or_none_in_normal_state() -> None:
    """정상 상태 스모크 — 실제 loader 를 호출해 예외 없이 dict / None 반환."""
    result = api_decision_draft_preview._load_holdings_evidence("999999")
    assert result is None or isinstance(result, dict)


def test_load_candidate_evidence_returns_dict_or_none_in_normal_state() -> None:
    result = api_decision_draft_preview._load_candidate_evidence(
        "999999", CandidateListQuery()
    )
    assert result is None or isinstance(result, dict)


def test_load_holdings_evidence_propagates_programmer_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FIX r3 — loader 안 프로그래머 오류 (ImportError / AttributeError) 는
    삼키지 않고 propagate.

    시뮬레이션: `app.holdings.load` 를 잠깐 제거하면 loader 안 `load_holdings()`
    호출이 AttributeError (또는 유사) 로 실패해야 한다.
    """
    import app.holdings as holdings_mod

    monkeypatch.delattr(holdings_mod, "load", raising=True)

    with pytest.raises((AttributeError, ImportError, TypeError)):
        api_decision_draft_preview._load_holdings_evidence("999999")


def test_load_candidate_evidence_propagates_programmer_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FIX r3 — 후보 loader 도 동일. 화면 시장 API 함수를 잠깐 제거하면 loader
    호출이 즉시 실패해야 한다.
    """
    monkeypatch.delattr(
        decision_preview_sources, "get_market_topn_latest", raising=True
    )

    with pytest.raises((AttributeError, ImportError, TypeError, NameError)):
        api_decision_draft_preview._load_candidate_evidence(
            "999999", CandidateListQuery()
        )


def test_endpoint_maintains_user_friendly_response_on_programmer_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FIX r3 — loader 가 프로그래머 오류를 propagate 해도, endpoint 는
    사용자 친화 실패 응답 (status="error" + 짧은 문구) 을 유지.
    """
    from app import api_decision_draft_preview as api_mod

    def raise_import_error(ticker: str):
        raise ImportError("simulated regression: bad symbol import")

    monkeypatch.setattr(api_mod, "_load_holdings_evidence", raise_import_error)

    client = TestClient(app)
    res = client.post(
        "/decision-draft/preview",
        json={"target_kind": "holding", "ticker": "069500"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "error"
    assert (
        body["message"] == "판단 근거 미리보기를 생성하지 못했습니다. 다시 시도하세요."
    )
    text = str(body)
    for banned in ("simulated regression", "ImportError", "traceback", "Traceback"):
        assert banned not in text


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


# ------- FIX r5 ~ r7: 보유 비중 · 손익(기존 정책) · 화면 응답 원천 -------


def _fake_market_quote(ticker: str, name: str, price: float):
    """market_cache.MarketQuote 스텁 — enrich_holdings 가 요구하는 최소 필드만."""
    from app.market_cache import MarketQuote

    return MarketQuote(
        ticker=ticker,
        name=name,
        current_price=price,
        price_asof="2026-07-03",
        price_source="TEST",
    )


def _write_holdings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, rows: str) -> None:
    from app import holdings as holdings_mod

    hfile = tmp_path / "holdings_latest.json"
    hfile.write_text('{"holdings": [' + rows + "]}", encoding="utf-8")
    monkeypatch.setattr(holdings_mod, "HOLDINGS_FILE", hfile, raising=True)


def _stub_quotes(monkeypatch: pytest.MonkeyPatch, quotes: dict) -> None:
    from app import market_cache

    monkeypatch.setattr(market_cache, "get_all", lambda: quotes, raising=True)


def _stub_screen_evidence(
    monkeypatch: pytest.MonkeyPatch,
    tmp_db: Path,
    ticker: str,
    name: str,
    excess_20d: Optional[float],
) -> None:
    """「보유와 비교」가 받는 보유 근거 응답(PC 사본)을 고정 — preview 는 이 값만 옮겨야 한다."""
    item = HoldingEvidenceItem(
        ticker=ticker,
        name=name,
        holding=HoldingSnapshot(quantity=1, avg_buy_price=1),
        topn_match=TopnMatch(status="not_in_current_topn"),
        returns=ReturnsPayload(status="unavailable"),
        excess_return=ExcessReturnPayload(status="unavailable"),
        short_term_momentum=ShortTermMomentumPayload(
            status="ok",
            return_5d_pct=1.0,
            return_10d_pct=1.0,
            return_20d_pct=1.0,
            excess_vs_kodex200_5d_pctp=0.1,
            excess_vs_kodex200_10d_pctp=0.1,
            excess_vs_kodex200_20d_pctp=excess_20d,
        ),
        constituents_overlap=ConstituentsOverlapPayload(
            status="constituents_unavailable"
        ),
        nav_discount=NavDiscountPayload(status="unavailable"),
    )
    resp = HoldingsMarketEvidenceResponse(
        status="ok",
        asof="2026-07-03",
        summary=EvidenceSummary(
            total_holdings_count=1,
            matched_topn_count=0,
            not_in_current_topn_count=1,
            evidence_unavailable_count=0,
            constituents_available_count=0,
            constituents_unavailable_count=1,
            nav_discount_unavailable_count=1,
        ),
        holdings=[item],
    )
    monkeypatch.setattr(
        decision_preview_sources, "get_holdings_market_evidence_latest", lambda: resp
    )
    monkeypatch.setattr(
        decision_preview_sources, "_etf_tickers", lambda db_path: {ticker}
    )
    monkeypatch.setattr(api_decision_draft_preview, "DEFAULT_DB_PATH", tmp_db)


def test_fix_r7_duplicate_ticker_uses_aggregated_values(
    tmp_path: Path, tmp_db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FIX r7 — 동일 ticker 2 row 도 화면 aggregateHoldingsByTicker 와 같은 종목 단위 집계.

    367760 row1 · row2: quantity=100, avg=10, price=15 → invested=2000, eval=3000 → pnl 50.0
    """
    _write_holdings(
        monkeypatch,
        tmp_path,
        '{"ticker": "367760", "name": "RISE 네트워크인프라",'
        ' "quantity": 100, "avg_buy_price": 10, "account_group": "일반"},'
        '{"ticker": "367760", "name": "RISE 네트워크인프라",'
        ' "quantity": 100, "avg_buy_price": 10, "account_group": "연금저축"}',
    )
    _stub_quotes(
        monkeypatch,
        {"367760": _fake_market_quote("367760", "RISE 네트워크인프라", 15.0)},
    )
    _stub_screen_evidence(monkeypatch, tmp_db, "367760", "RISE 네트워크인프라", 1.0)

    canonical = api_decision_draft_preview._load_holdings_evidence("367760")
    assert canonical is not None
    assert canonical["pnl_rate_pct"] == pytest.approx(50.0, abs=0.01)
    assert canonical["market_weight_pct"] == pytest.approx(100.0, abs=0.01)


def test_fix_r6_canonical_holding_matches_screen_values_079_and_5511(
    tmp_path: Path, tmp_db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FIX r6 — 화면 값 `market_weight_pct=0.79 / pnl_rate_pct=55.11` 이 preview 에 그대로."""
    _write_holdings(
        monkeypatch,
        tmp_path,
        '{"ticker": "0052D0", "name": "TIGER 코리아배당다우존스",'
        ' "quantity": 100, "avg_buy_price": 10},'
        '{"ticker": "DUMMY0", "name": "DUMMY", "quantity": 1, "avg_buy_price": 1}',
    )
    _stub_quotes(
        monkeypatch,
        {
            "0052D0": _fake_market_quote("0052D0", "TIGER 코리아배당다우존스", 15.511),
            "DUMMY0": _fake_market_quote("DUMMY0", "DUMMY", 194600.0),
        },
    )
    _stub_screen_evidence(
        monkeypatch, tmp_db, "0052D0", "TIGER 코리아배당다우존스", 1.0
    )

    canonical = api_decision_draft_preview._load_holdings_evidence("0052D0")
    assert canonical is not None
    assert canonical["market_weight_pct"] == pytest.approx(0.79, abs=0.01)
    assert canonical["pnl_rate_pct"] == pytest.approx(55.11, abs=0.01)

    text = (
        build_preview_text(
            target_kind=TARGET_KIND_HOLDING,
            ticker="0052D0",
            target_evidence=canonical,
            db_path=tmp_db,
        ).preview_text
        or ""
    )
    assert "0.79%" in text
    assert "55.11%" in text


def test_fix_r5_canonical_holding_evidence_includes_weight_and_pnl(
    tmp_path: Path, tmp_db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FIX r5 회귀 #1 — 평가비중 · 손익률 + 화면 응답의 단기 차이가 preview 에 그대로(단위 %p)."""
    _write_holdings(
        monkeypatch,
        tmp_path,
        '{"ticker": "0052D0", "name": "TIGER 코리아배당다우존스",'
        ' "quantity": 100, "avg_buy_price": 10000}',
    )
    _stub_quotes(
        monkeypatch,
        {"0052D0": _fake_market_quote("0052D0", "TIGER 코리아배당다우존스", 15511.0)},
    )
    _stub_screen_evidence(
        monkeypatch, tmp_db, "0052D0", "TIGER 코리아배당다우존스", 2.34
    )

    canonical = api_decision_draft_preview._load_holdings_evidence("0052D0")
    assert canonical is not None
    assert canonical["pnl_rate_pct"] == pytest.approx(55.11, abs=0.01)
    assert canonical["market_weight_pct"] == pytest.approx(100.0, abs=0.01)
    stm = canonical["bundle"]["item"]["short_term_momentum"]
    assert stm["excess_vs_kodex200_20d_pctp"] == pytest.approx(2.34, abs=0.01)

    text = (
        build_preview_text(
            target_kind=TARGET_KIND_HOLDING,
            ticker="0052D0",
            target_evidence=canonical,
            db_path=tmp_db,
        ).preview_text
        or ""
    )
    assert "55.11%" in text
    assert "100.00%" in text
    assert "20저장일 +2.34%p" in text


def test_fix_r5_missing_ex20_shows_unknown_not_hidden(
    tmp_path: Path, tmp_db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FIX r5 회귀 #2 — 20일 차이 값이 없으면 사유 표시, 줄 삭제 X."""
    _write_holdings(
        monkeypatch,
        tmp_path,
        '{"ticker": "0052D0", "name": "TIGER 코리아배당다우존스",'
        ' "quantity": 100, "avg_buy_price": 10000}',
    )
    _stub_quotes(
        monkeypatch,
        {"0052D0": _fake_market_quote("0052D0", "TIGER 코리아배당다우존스", 15511.0)},
    )
    _stub_screen_evidence(
        monkeypatch, tmp_db, "0052D0", "TIGER 코리아배당다우존스", None
    )

    canonical = api_decision_draft_preview._load_holdings_evidence("0052D0")
    text = (
        build_preview_text(
            target_kind=TARGET_KIND_HOLDING,
            ticker="0052D0",
            target_evidence=canonical,
            db_path=tmp_db,
        ).preview_text
        or ""
    )
    assert "단기 KODEX200 차이(저장일 수 기준)" in text
    assert "20저장일 시작일 달라 비움" in text


def test_fix_r5_preview_does_not_recompute_ex20_independently(
    tmp_path: Path, tmp_db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FIX r5 회귀 #3 — preview 는 화면 응답 원천만 사용(sentinel 7.77 만 등장)."""
    _write_holdings(
        monkeypatch,
        tmp_path,
        '{"ticker": "0052D0", "name": "TIGER 코리아배당다우존스",'
        ' "quantity": 100, "avg_buy_price": 10000}',
    )
    _stub_quotes(
        monkeypatch,
        {"0052D0": _fake_market_quote("0052D0", "TIGER 코리아배당다우존스", 15511.0)},
    )
    _stub_screen_evidence(
        monkeypatch, tmp_db, "0052D0", "TIGER 코리아배당다우존스", 7.77
    )

    canonical = api_decision_draft_preview._load_holdings_evidence("0052D0")
    text = (
        build_preview_text(
            target_kind=TARGET_KIND_HOLDING,
            ticker="0052D0",
            target_evidence=canonical,
            db_path=tmp_db,
        ).preview_text
        or ""
    )
    assert "+7.77%p" in text
    assert "-4.23" not in text
    assert (
        canonical["bundle"]["item"]["short_term_momentum"][
            "excess_vs_kodex200_20d_pctp"
        ]
        == 7.77
    )


def test_fix_r5_candidate_preview_regression_untouched(tmp_db: Path) -> None:
    """FIX r5 회귀 #5 — 후보 글은 화면 시장 응답의 단기 값을 그대로(참고점수 줄 없음)."""
    ev = _candidate_evidence(
        short_term_momentum={
            "status": "ok",
            "return_5d_pct": 1.0,
            "return_10d_pct": 1.0,
            "return_20d_pct": 1.0,
            "excess_vs_kodex200_5d_pctp": 1.0,
            "excess_vs_kodex200_10d_pctp": 1.0,
            "excess_vs_kodex200_20d_pctp": 1.11,
        },
        relative_upside_score=88.8,
    )
    text = (
        build_preview_text(
            target_kind=TARGET_KIND_CANDIDATE,
            ticker="379800",
            target_evidence=ev,
            db_path=tmp_db,
        ).preview_text
        or ""
    )
    assert "20저장일 +1.11%p" in text
    assert "88.8" not in text
