"""POC2 Step 5D-2 Cleanup — market_cache + Naver fetch + holdings_enrich (Step2).

분리 출처: tests/test_holdings_draft_flow.py (Step 5D-2 이전 단일 파일).
테스트 의미 / 검증 강도 / 동작은 분리 전과 동일.
"""

from __future__ import annotations

import pytest

from app import market_cache

from tests._helpers import _VALID_HOLDINGS


def test_market_cache_atomic_write_and_reload():

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
    """POST /holdings/market/refresh 만 Naver fetch 를 트리거하고 캐시에 반영."""
    from app import market_naver

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
    r = client.post("/holdings/market/refresh")
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
    from app import market_naver

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
    r = client.post("/holdings/market/refresh")
    body = r.json()
    assert body["ok_count"] == 1
    assert body["fail_count"] == 1
    assert any(
        f["ticker"] == "091160" and f["reason"] == "timeout" for f in body["failures"]
    )


def test_market_refresh_blocks_on_empty_holdings_422(client):
    r = client.post("/holdings/market/refresh")
    assert r.status_code == 422


def test_generate_from_holdings_uses_cached_market_data(client, monkeypatch):
    """캐시에 시세가 있으면 generate-from-holdings 가 자동으로 enrich 한다 (외부 fetch 없이)."""
    from app import market_naver

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


def test_market_cache_preserves_other_tickers_after_restart_partial_refresh():
    """서버 재시작 직후 일부 종목만 fetch 성공해도 기존 디스크 캐시의 타 종목이 유실되지 않는다.

    재현 시나리오 (Codex REJECTED 지적):
    1. 캐시에 069500, 091160 2건 존재
    2. 서버 재시작 시뮬레이션 (메모리 리셋)
    3. POST /holdings/market/refresh 가 069500 만 성공 (091160 은 timeout 등으로 실패)
    4. upsert_many([069500]) 호출
    5. 디스크에 091160 의 기존 값이 그대로 보존되어야 한다.
    """

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


# ─── POC2 Step 2C: holdings UI compaction + account grouping ─────────
