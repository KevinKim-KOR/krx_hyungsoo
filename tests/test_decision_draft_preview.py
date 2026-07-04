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


def test_load_holdings_evidence_returns_dict_or_none_in_normal_state() -> None:
    """정상 상태 스모크 — 실제 loader 를 호출해 예외 없이 dict / None 반환.

    이 테스트만으로는 import 오타를 잡지 못하지만 (broad except 없이도 loader
    가 존재 데이터에 대해 정상 반환하는지 확인), 아래 회귀 재현 테스트와
    함께 봤을 때 loader 가 실제로 실행 가능함을 보증한다.
    """
    result = api_decision_draft_preview._load_holdings_evidence("999999")
    assert result is None or isinstance(result, dict)


def test_load_candidate_evidence_returns_dict_or_none_in_normal_state() -> None:
    result = api_decision_draft_preview._load_candidate_evidence("999999")
    assert result is None or isinstance(result, dict)


def test_load_holdings_evidence_propagates_programmer_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FIX r3 — loader 안 프로그래머 오류 (ImportError / AttributeError) 는
    삼키지 않고 propagate. 이 테스트가 있으면 `from app.holdings import
    load_holdings_from_file` 같은 심볼 오타 재도입 시 loader 직접 호출에서
    즉시 예외가 발생함을 확인.

    시뮬레이션: `app.holdings.load` 를 잠깐 제거하면 loader 안 `load_holdings()`
    호출이 AttributeError (또는 유사) 로 실패해야 한다.
    """
    import app.holdings as holdings_mod

    # 실제 load 를 삭제해 loader 안 `load_holdings()` 호출이 실패하도록.
    monkeypatch.delattr(holdings_mod, "load", raising=True)

    with pytest.raises((AttributeError, ImportError, TypeError)):
        api_decision_draft_preview._load_holdings_evidence("999999")


def test_load_candidate_evidence_propagates_programmer_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FIX r3 — 후보 loader 도 동일. `compute_topn` 을 잠깐 제거하면 loader
    호출이 즉시 실패해야 한다.
    """
    import app.market_topn as topn_mod

    monkeypatch.delattr(topn_mod, "compute_topn", raising=True)

    with pytest.raises((AttributeError, ImportError, TypeError)):
        api_decision_draft_preview._load_candidate_evidence("999999")


def test_endpoint_maintains_user_friendly_response_on_programmer_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FIX r3 — loader 가 프로그래머 오류를 propagate 해도, endpoint 는
    사용자 친화 실패 응답 (status="error" + 짧은 문구) 을 유지.

    응답 body 에 traceback / 심볼 정보 미노출.
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
    # 내부 traceback / 심볼 정보 미노출.
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


# ------- FIX r5: canonical evidence 원천·의미 화면 정합 회귀 -------


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


def _seed_holdings_and_cache(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """holdings 파일 + market_cache stub → _load_holdings_evidence 가 실제 canonical
    조립을 수행하도록 한다.
    """
    from app import holdings as holdings_mod
    from app import market_cache

    # holdings 파일 (0052D0 하나) — TIGER 코리아배당다우존스.
    hfile = tmp_path / "holdings_latest.json"
    hfile.write_text(
        '{"holdings": [{"ticker": "0052D0", "name": "TIGER 코리아배당다우존스",'
        ' "quantity": 100, "avg_buy_price": 10000}]}',
        encoding="utf-8",
    )
    monkeypatch.setattr(holdings_mod, "HOLDINGS_FILE", hfile, raising=True)

    # market_cache — 시세 있는 상태 (평가비중 / 손익률 계산 가능).
    def fake_get_all():
        return {
            "0052D0": _fake_market_quote("0052D0", "TIGER 코리아배당다우존스", 15511.0)
        }

    monkeypatch.setattr(market_cache, "get_all", fake_get_all, raising=True)


def test_fix_r7_duplicate_ticker_uses_aggregated_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FIX r7 — 동일 ticker 가 holdings 파일에 2 row 로 존재해도 preview 는
    화면 aggregateHoldingsByTicker 와 동일하게 ticker 단위로 집계된 값을 사용.

    구성 (367760 실제 케이스 재현 아이디어 — 2 row 로 집계됨):
      367760 row1: quantity=100, avg=10, price=15 → invested=1000, eval=1500
      367760 row2: quantity=100, avg=10, price=15 → invested=1000, eval=1500
      → 그룹 집계: invested=2000, eval=3000, pnl_rate=(3000/2000-1)*100=50.0

    raw 마지막 row 만 선택하면 그룹이 아닌 개별 row 기준 계산이 되어 값이
    달라진다. 화면 집계와 preview 값이 반드시 일치해야 한다.
    """
    from app import holdings as holdings_mod
    from app import market_cache

    # 실제 보유 파일과 동일한 구조 재현 — 같은 ticker 를 다른 account_group 으로
    # 두 row 로 저장 (holdings validator 는 이 조합을 허용).
    hfile = tmp_path / "holdings_latest.json"
    hfile.write_text(
        '{"holdings": ['
        '{"ticker": "367760", "name": "RISE 네트워크인프라",'
        ' "quantity": 100, "avg_buy_price": 10, "account_group": "일반"},'
        '{"ticker": "367760", "name": "RISE 네트워크인프라",'
        ' "quantity": 100, "avg_buy_price": 10, "account_group": "연금저축"}'
        "]}",
        encoding="utf-8",
    )
    monkeypatch.setattr(holdings_mod, "HOLDINGS_FILE", hfile, raising=True)

    def fake_get_all():
        return {"367760": _fake_market_quote("367760", "RISE 네트워크인프라", 15.0)}

    monkeypatch.setattr(market_cache, "get_all", fake_get_all, raising=True)

    def stub_topn(**kwargs):
        return {"status": "ok", "asof": "2026-07-03", "candidates": []}

    def stub_build_evidence(**kwargs):
        return {
            "status": "ok",
            "asof": "2026-07-03",
            "holdings": [
                {
                    "ticker": "367760",
                    "name": "RISE 네트워크인프라",
                    "short_term_momentum": {},
                    "data_quality": {"status": "ok"},
                    "overlap": {"status": "not_loaded"},
                }
            ],
        }

    from app import holdings_market_evidence, market_topn

    monkeypatch.setattr(market_topn, "compute_topn", stub_topn, raising=True)
    monkeypatch.setattr(
        holdings_market_evidence,
        "build_holdings_market_evidence",
        stub_build_evidence,
        raising=True,
    )

    canonical = api_decision_draft_preview._load_holdings_evidence("367760")
    assert canonical is not None
    # 집계 기준: invested=2000, eval=3000 → pnl_rate=50.0
    # 총 자산 대비 100% (다른 종목 없음).
    assert canonical["pnl_rate_pct"] == pytest.approx(50.0, abs=0.01)
    assert canonical["market_weight_pct"] == pytest.approx(100.0, abs=0.01)


def test_fix_r6_canonical_holding_matches_screen_values_079_and_5511(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FIX r6 (설계자 요구 명시 검증) — 화면 값 `market_weight_pct=0.79 /
    pnl_rate_pct=55.11` 이 preview 에 그대로 나타나는 회귀.

    구성: 두 종목 holdings 파일로 총 자산 대비 0052D0 비중을 0.79% 로 맞춤.
      0052D0: quantity=100, avg=10, price=15.511  → invested=1000, eval=1551.1,
              pnl_rate=(1551.1/1000-1)*100 = 55.11
      DUMMY : quantity=1,   avg=1,  price=194600  → invested=1,    eval=194600
      total eval = 196151.1  → 0052D0 market_weight = 1551.1/196151.1*100 ≈ 0.79
    """
    from app import holdings as holdings_mod
    from app import market_cache

    hfile = tmp_path / "holdings_latest.json"
    hfile.write_text(
        '{"holdings": ['
        '{"ticker": "0052D0", "name": "TIGER 코리아배당다우존스",'
        ' "quantity": 100, "avg_buy_price": 10},'
        '{"ticker": "DUMMY0", "name": "DUMMY",'
        ' "quantity": 1, "avg_buy_price": 1}'
        "]}",
        encoding="utf-8",
    )
    monkeypatch.setattr(holdings_mod, "HOLDINGS_FILE", hfile, raising=True)

    def fake_get_all():
        return {
            "0052D0": _fake_market_quote("0052D0", "TIGER 코리아배당다우존스", 15.511),
            "DUMMY0": _fake_market_quote("DUMMY0", "DUMMY", 194600.0),
        }

    monkeypatch.setattr(market_cache, "get_all", fake_get_all, raising=True)

    def stub_topn(**kwargs):
        return {"status": "ok", "asof": "2026-07-03", "candidates": []}

    def stub_build_evidence(**kwargs):
        return {
            "status": "ok",
            "asof": "2026-07-03",
            "holdings": [
                {
                    "ticker": "0052D0",
                    "name": "TIGER 코리아배당다우존스",
                    "short_term_momentum": {},
                    "data_quality": {"status": "ok"},
                    "overlap": {"status": "not_loaded"},
                }
            ],
        }

    from app import holdings_market_evidence, market_topn

    monkeypatch.setattr(market_topn, "compute_topn", stub_topn, raising=True)
    monkeypatch.setattr(
        holdings_market_evidence,
        "build_holdings_market_evidence",
        stub_build_evidence,
        raising=True,
    )

    canonical = api_decision_draft_preview._load_holdings_evidence("0052D0")
    assert canonical is not None
    # 설계자 요구 값과 정확히 일치 (round 2 자릿수).
    assert canonical["market_weight_pct"] == pytest.approx(0.79, abs=0.01)
    assert canonical["pnl_rate_pct"] == pytest.approx(55.11, abs=0.01)

    from app.decision_draft_preview_service import build_preview_text

    result = build_preview_text(
        target_kind=TARGET_KIND_HOLDING,
        ticker="0052D0",
        target_evidence=canonical,
    )
    text = result.preview_text or ""
    assert "0.79%" in text
    assert "55.11%" in text


def test_fix_r5_canonical_holding_evidence_includes_weight_and_pnl(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FIX r5 회귀 #1 — enrich_holdings 결과의 평가비중·손익률이 preview 에 그대로."""
    _seed_holdings_and_cache(monkeypatch, tmp_path)

    # compute_topn / build_holdings_market_evidence 는 실제 SQLite 를 요구하므로
    # stub — 20d 초과값이 있는 상태를 fixture 로 주입.
    def stub_topn(**kwargs):
        return {"status": "ok", "asof": "2026-07-03", "candidates": []}

    def stub_build_evidence(**kwargs):
        return {
            "status": "ok",
            "asof": "2026-07-03",
            "holdings": [
                {
                    "ticker": "0052D0",
                    "name": "TIGER 코리아배당다우존스",
                    "short_term_momentum": {
                        "excess_vs_kodex200_20d_pctp": 2.34,
                        "end_date": "2026-07-03",
                    },
                    "data_quality": {"status": "ok"},
                    "overlap": {"status": "not_loaded"},
                }
            ],
        }

    from app import holdings_market_evidence, market_topn

    monkeypatch.setattr(market_topn, "compute_topn", stub_topn, raising=True)
    monkeypatch.setattr(
        holdings_market_evidence,
        "build_holdings_market_evidence",
        stub_build_evidence,
        raising=True,
    )

    canonical = api_decision_draft_preview._load_holdings_evidence("0052D0")
    assert canonical is not None
    # enrich_holdings 계산 결과: eval=100*15511=1551100, invested=1000000,
    #   pnl_rate=(1551100/1000000-1)*100=55.11 (round 2)
    #   market_weight 단일 종목 100.00
    assert canonical["pnl_rate_pct"] == pytest.approx(55.11, abs=0.01)
    assert canonical["market_weight_pct"] == pytest.approx(100.0, abs=0.01)
    # short_term_momentum 은 build_holdings_market_evidence 원천 그대로.
    stm = canonical.get("short_term_momentum") or {}
    assert stm.get("excess_vs_kodex200_20d_pctp") == pytest.approx(2.34, abs=0.01)

    # preview_text 안에도 그대로 노출되는지.
    from app.decision_draft_preview_service import build_preview_text

    result = build_preview_text(
        target_kind=TARGET_KIND_HOLDING,
        ticker="0052D0",
        target_evidence=canonical,
    )
    text = result.preview_text or ""
    assert "55.11%" in text
    assert "100.00%" in text
    assert "+2.34%" in text


def test_fix_r5_missing_ex20_shows_unknown_not_hidden(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FIX r5 회귀 #2 — 20일 KODEX 초과값이 없으면 미확인 표시, 라인 삭제 X."""
    _seed_holdings_and_cache(monkeypatch, tmp_path)

    def stub_topn(**kwargs):
        return {"status": "ok", "asof": "2026-07-03", "candidates": []}

    def stub_build_evidence(**kwargs):
        return {
            "status": "ok",
            "asof": "2026-07-03",
            "holdings": [
                {
                    "ticker": "0052D0",
                    "name": "TIGER 코리아배당다우존스",
                    "short_term_momentum": {},  # ex_20 없음
                    "data_quality": {"status": "ok"},
                    "overlap": {"status": "not_loaded"},
                }
            ],
        }

    from app import holdings_market_evidence, market_topn

    monkeypatch.setattr(market_topn, "compute_topn", stub_topn, raising=True)
    monkeypatch.setattr(
        holdings_market_evidence,
        "build_holdings_market_evidence",
        stub_build_evidence,
        raising=True,
    )

    canonical = api_decision_draft_preview._load_holdings_evidence("0052D0")
    from app.decision_draft_preview_service import build_preview_text

    result = build_preview_text(
        target_kind=TARGET_KIND_HOLDING,
        ticker="0052D0",
        target_evidence=canonical,
    )
    text = result.preview_text or ""
    # 라인 존재 + "미확인" 표기.
    assert "KODEX200 대비 20거래일 초과: 미확인" in text


def test_fix_r5_preview_does_not_recompute_ex20_independently(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FIX r5 회귀 #3 — preview 는 build_holdings_market_evidence 원천만 사용.

    stub 이 반환하지 않은 다른 값 (예: -4.23) 이 preview_text 에 등장하면 실패.
    (독자 계산 경로가 있으면 이 assert 가 잡는다.)
    """
    _seed_holdings_and_cache(monkeypatch, tmp_path)

    def stub_topn(**kwargs):
        return {"status": "ok", "asof": "2026-07-03", "candidates": []}

    def stub_build_evidence(**kwargs):
        # 명확한 sentinel 값. preview 가 canonical 원천만 사용하면 이 값만 등장.
        return {
            "status": "ok",
            "asof": "2026-07-03",
            "holdings": [
                {
                    "ticker": "0052D0",
                    "name": "TIGER 코리아배당다우존스",
                    "short_term_momentum": {
                        "excess_vs_kodex200_20d_pctp": 7.77,
                        "end_date": "2026-07-03",
                    },
                    "data_quality": {"status": "ok"},
                    "overlap": {"status": "not_loaded"},
                }
            ],
        }

    from app import holdings_market_evidence, market_topn

    monkeypatch.setattr(market_topn, "compute_topn", stub_topn, raising=True)
    monkeypatch.setattr(
        holdings_market_evidence,
        "build_holdings_market_evidence",
        stub_build_evidence,
        raising=True,
    )

    canonical = api_decision_draft_preview._load_holdings_evidence("0052D0")
    from app.decision_draft_preview_service import build_preview_text

    result = build_preview_text(
        target_kind=TARGET_KIND_HOLDING,
        ticker="0052D0",
        target_evidence=canonical,
    )
    text = result.preview_text or ""
    # canonical sentinel 만 등장.
    assert "+7.77%" in text
    # -4.23% 같은 독자 계산 결과가 등장하면 안 됨 (사용자 지적의 회귀 시나리오).
    assert "-4.23" not in text
    # 그리고 실제로 canonical 값이 short_term_momentum 원천에서 왔음을 확인.
    assert canonical["short_term_momentum"]["excess_vs_kodex200_20d_pctp"] == 7.77


def test_fix_r5_candidate_preview_regression_untouched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FIX r5 회귀 #5 — 후보 preview 는 영향 없음."""
    from app.decision_draft_preview_service import build_preview_text

    candidate = {
        "ticker": "379800",
        "name": "TEST",
        "relative_upside_score": 88.8,
        "short_term_momentum": {"excess_vs_kodex200_20d_pctp": 1.11},
        "drawdown_20d": -0.02,
        "data_quality": {"status": "ok"},
    }
    result = build_preview_text(
        target_kind=TARGET_KIND_CANDIDATE,
        ticker="379800",
        target_evidence=candidate,
    )
    text = result.preview_text or ""
    assert "88.8" in text
    assert "+1.11%" in text
