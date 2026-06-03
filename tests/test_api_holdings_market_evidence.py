"""POC2 — GET /holdings/market-evidence/latest API 통합 테스트 (2026-06-03).

지시문 §5.1 / §5.2 / AC-2. 외부 fetch 0건. holdings 비어있어도 200.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import (
    api as api_module,
    api_holdings_market_evidence,
    api_market_topn,
    etf_constituents_store,
    etf_nav_store,
    market_data_store,
    market_refresh_service,
)
from app.market_data_store import (
    EtfDailyPriceRow,
    EtfMasterRow,
    upsert_daily_prices,
    upsert_etf_master,
)


@pytest.fixture
def api_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    fake_db = tmp_path / "market_data.sqlite"
    # compute_topn / NAV / constituents / api router 4개 위치의 DEFAULT_DB_PATH 격리.
    monkeypatch.setattr(api_market_topn, "DEFAULT_DB_PATH", fake_db)
    monkeypatch.setattr(market_data_store, "DEFAULT_DB_PATH", fake_db)
    monkeypatch.setattr(etf_constituents_store, "DEFAULT_DB_PATH", fake_db)
    monkeypatch.setattr(etf_nav_store, "DEFAULT_DB_PATH", fake_db)
    monkeypatch.setattr(api_holdings_market_evidence, "MARKET_DB_PATH", fake_db)
    market_refresh_service.reset_state_for_testing()
    return TestClient(api_module.app)


def _seed_history(
    db: Path, ticker: str, name: str, end: date, closes: list[float]
) -> None:
    upsert_etf_master(
        [EtfMasterRow(ticker, name, "1", 100.0, 1000, 5000.0)],
        source="TestSource",
        db_path=db,
    )
    rows: list[EtfDailyPriceRow] = []
    for i, close in enumerate(closes):
        d = (end - timedelta(days=len(closes) - i - 1)).isoformat()
        rows.append(EtfDailyPriceRow(ticker, d, close, close, close, close, 0, 0))
    upsert_daily_prices(rows, source="TestSource", db_path=db)


def _put_holdings(client: TestClient, payload: list[dict]) -> None:
    res = client.put("/holdings", json={"holdings": payload})
    assert res.status_code == 200, res.text


def test_endpoint_returns_200_for_empty_holdings(api_client: TestClient) -> None:
    """holdings 빈 상태 → 200 + 빈 응답 (지시문 §4.1 — 기존 빈 상태 유지)."""
    res = api_client.get("/holdings/market-evidence/latest")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["holdings"] == []
    assert body["summary"]["total_holdings_count"] == 0


def test_endpoint_returns_evidence_for_loaded_holdings(api_client: TestClient) -> None:
    """holdings 있고 market topn 가능 → 200 + summary 카운트."""
    end = date(2026, 5, 30)
    db = api_market_topn.DEFAULT_DB_PATH
    _seed_history(db, "069500", "KODEX 200", end, [100.0 + i * 0.5 for i in range(25)])
    _put_holdings(
        api_client,
        [
            {
                "ticker": "069500",
                "name": "KODEX 200",
                "quantity": 5,
                "avg_buy_price": 84000,
            }
        ],
    )
    res = api_client.get("/holdings/market-evidence/latest")
    assert res.status_code == 200
    body = res.json()
    assert body["summary"]["total_holdings_count"] == 1
    item = body["holdings"][0]
    assert item["ticker"] == "069500"
    assert item["topn_match"]["status"] in {
        "matched_topn_candidate",
        "not_in_current_topn",
        "unavailable",
    }
    # nav_discount 는 cache 미입력이므로 unavailable.
    assert item["nav_discount"]["status"] == "unavailable"


def test_endpoint_does_not_call_external_fetchers(
    api_client: TestClient, monkeypatch
) -> None:
    """read-only API 가 외부 호출을 트리거하지 않는다 (지시문 §5.1)."""
    from app import market_data_fdr, market_naver

    def boom(*args, **kwargs):
        raise AssertionError("외부 fetch 호출 — read-only API 정책 위반")

    monkeypatch.setattr(market_data_fdr, "refresh_etf_universe", boom)
    monkeypatch.setattr(market_data_fdr, "refresh_price_history", boom)
    monkeypatch.setattr(market_naver, "fetch_many", boom)
    _put_holdings(
        api_client,
        [
            {
                "ticker": "069500",
                "name": "KODEX 200",
                "quantity": 5,
                "avg_buy_price": 84000,
            }
        ],
    )
    res = api_client.get("/holdings/market-evidence/latest")
    assert res.status_code == 200


def test_endpoint_response_has_no_buy_sell_language(api_client: TestClient) -> None:
    """evidence_notes 와 warnings 에 매수/매도/교체 어휘 X (지시문 §5.10 / AC-11)."""
    _put_holdings(
        api_client,
        [
            {
                "ticker": "069500",
                "name": "KODEX 200",
                "quantity": 5,
                "avg_buy_price": 84000,
            }
        ],
    )
    res = api_client.get("/holdings/market-evidence/latest")
    body = res.json()
    text_blob = ""
    for h in body["holdings"]:
        text_blob += " ".join(h.get("evidence_notes") or [])
    text_blob += " ".join(body.get("warnings") or [])
    forbidden = ["매수", "매도", "교체", "진입", "탈락", "비중 확대", "비중 축소"]
    for word in forbidden:
        assert word not in text_blob, f"응답에 '{word}' 어휘 포함 — 금지"
