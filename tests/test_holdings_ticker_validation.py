"""POC3-08 (A) — 종목코드 형식검증 + etf_master 종목명 자동조회.

- PUT /holdings 는 strict_ticker=True — 영숫자 6자가 아니면 422(오타 저장 차단).
  ETF 실존 여부는 막지 않는다(개별주 허용).
- GET /holdings/etf-name?ticker= 는 etf_master 종목명 조회(읽기 전용).
  found=false 는 개별주/미등록 — 저장 차단이 아니라 프론트 경고용.
- 로드 경로(strict_ticker 기본 False)는 기존 비정형 값도 읽기 허용(하위호환).

경로 격리: conftest 의 autouse _isolated_store 가 HOLDINGS_FILE 을 tmp 로 돌린다.
etf-name 은 market_data_store.get_etf_name 을 monkeypatch 해 live sqlite 비의존.
"""

from __future__ import annotations

from app import holdings as holdings_module
from app.holdings import HoldingsValidationError, validate_holdings


def _h(ticker: str) -> dict:
    return {"ticker": ticker, "quantity": 1, "avg_buy_price": 100}


# ─── PUT /holdings strict_ticker 게이트 ──────────────────────────────


def test_put_blocks_malformed_ticker_111(client):
    r = client.put("/holdings", json={"holdings": [_h("111")]})
    assert r.status_code == 422
    assert "형식" in r.json()["detail"]


def test_put_blocks_garbage_ticker(client):
    r = client.put("/holdings", json={"holdings": [_h("dasdasd")]})
    assert r.status_code == 422


def test_put_allows_etf_ticker(client):
    r = client.put("/holdings", json={"holdings": [_h("069500")]})
    assert r.status_code == 200


def test_put_allows_individual_stock_005930(client):
    """개별주(삼성전자)는 etf_master 에 없어도 형식만 맞으면 저장 허용."""
    r = client.put("/holdings", json={"holdings": [_h("005930")]})
    assert r.status_code == 200


def test_put_allows_alphanumeric_etf_code(client):
    """영숫자 6자 ETF 코드(0005G0)도 허용."""
    r = client.put("/holdings", json={"holdings": [_h("0005G0")]})
    assert r.status_code == 200


# ─── validate_holdings 단위: strict vs lenient ───────────────────────


def test_validate_strict_blocks_short_ticker():
    try:
        validate_holdings([_h("111")], strict_ticker=True)
        assert False, "111 은 strict 에서 차단돼야 함"
    except HoldingsValidationError:
        pass


def test_validate_lenient_allows_legacy_ticker():
    """로드 경로(기본 lenient)는 기존 비정형 값도 읽기 허용(하위호환)."""
    out = validate_holdings([_h("111")])
    assert out[0].ticker == "111"


def test_load_backward_compat_with_legacy_ticker(tmp_path, monkeypatch):
    """이미 저장된 비정형 ticker 파일도 load() 는 raise 하지 않는다."""
    import json

    hdir = tmp_path / "holdings"
    hdir.mkdir()
    hfile = hdir / "holdings_latest.json"
    hfile.write_text(
        json.dumps({"holdings": [_h("111"), _h("069500")]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(holdings_module, "HOLDINGS_DIR", hdir)
    monkeypatch.setattr(holdings_module, "HOLDINGS_FILE", hfile)
    loaded = holdings_module.load()
    assert len(loaded) == 2
    assert loaded[0].ticker == "111"


# ─── GET /holdings/etf-name 조회 ─────────────────────────────────────


def test_etf_name_found(client, monkeypatch):
    from app import market_data_store

    monkeypatch.setattr(
        market_data_store,
        "get_etf_name",
        lambda t: "KODEX 200" if t == "069500" else None,
    )
    r = client.get("/holdings/etf-name", params={"ticker": "069500"})
    assert r.status_code == 200
    body = r.json()
    assert body["found"] is True
    assert body["name"] == "KODEX 200"


def test_etf_name_not_found_for_individual_stock(client, monkeypatch):
    from app import market_data_store

    monkeypatch.setattr(market_data_store, "get_etf_name", lambda t: None)
    r = client.get("/holdings/etf-name", params={"ticker": "005930"})
    assert r.status_code == 200
    body = r.json()
    assert body["found"] is False
    assert body["name"] is None


def test_etf_name_normalizes_lowercase(client, monkeypatch):
    from app import market_data_store

    seen = {}

    def _fake(t):
        seen["t"] = t
        return "IBK K-AI반도체코어위크"

    monkeypatch.setattr(market_data_store, "get_etf_name", _fake)
    r = client.get("/holdings/etf-name", params={"ticker": "0005g0"})
    assert r.status_code == 200
    # 대문자로 정규화되어 조회된다.
    assert seen["t"] == "0005G0"
    assert r.json()["ticker"] == "0005G0"
