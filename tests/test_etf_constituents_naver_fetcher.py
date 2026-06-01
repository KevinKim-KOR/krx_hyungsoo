"""Naver Stock ETFComponent fetcher 단위 테스트 (POC2 — 2026-05-31).

HTTP 호출 (_naver_http_get) 은 monkeypatch 로 stub. 응답 parsing / weight 변환
/ effective_asof / 해외 종목 reuters/isin 추출 검증.
"""

from __future__ import annotations

import json

import pytest

from app import etf_constituents_fetcher as fetcher_mod
from app.etf_constituents_fetcher import (
    NAVER_STOCK_SOURCE,
    _build_constituent_key,
    _coerce_weight_string,
    naver_stock_etf_component_fetcher,
)


def _domestic_items():
    return [
        {
            "itemCode": "069500",
            "componentItemCode": "005930",
            "componentIsinCode": "KR7005930003",
            "componentReutersCode": None,
            "componentName": "삼성전자",
            "componentMarketType": "0",
            "weight": "32.33",
            "referenceDate": "2026-05-29",
        },
        {
            "itemCode": "069500",
            "componentItemCode": "000660",
            "componentIsinCode": "KR7000660001",
            "componentReutersCode": None,
            "componentName": "SK하이닉스",
            "componentMarketType": "0",
            "weight": "25.61",
            "referenceDate": "2026-05-29",
        },
    ]


def _overseas_item():
    return [
        {
            "itemCode": "411420",
            "componentItemCode": None,
            "componentIsinCode": "US11135F1012",
            "componentReutersCode": "AVGO.O",
            "componentName": "브로드컴",
            "componentMarketType": "2",
            "weight": "9.14",
            "referenceDate": "2026-05-29",
        }
    ]


def _stub_http_get(items_or_status):
    """items: list[dict] → 200 / JSON. int → http_status, empty body."""

    def fn(url, timeout=10):  # noqa: ARG001
        if isinstance(items_or_status, int):
            return items_or_status, ""
        return 200, json.dumps(items_or_status, ensure_ascii=False)

    return fn


def test_naver_fetcher_domestic_ok(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        fetcher_mod, "_naver_http_get", _stub_http_get(_domestic_items())
    )
    result = naver_stock_etf_component_fetcher("069500", "2026-05-27", top_k=10)
    assert result.status == "ok"
    assert result.source == NAVER_STOCK_SOURCE
    assert result.effective_asof == "2026-05-29"
    assert len(result.constituents) == 2
    # 비중 내림차순 정렬 (32.33 > 25.61).
    assert result.constituents[0].constituent_ticker == "005930"
    assert result.constituents[0].weight_pct == 32.33
    assert result.constituents[0].market_type == "0"
    assert result.constituents[0].constituent_isin == "KR7005930003"
    assert result.constituents[1].constituent_ticker == "000660"


def test_naver_fetcher_overseas_preserves_reuters_isin(monkeypatch):
    monkeypatch.setattr(
        fetcher_mod, "_naver_http_get", _stub_http_get(_overseas_item())
    )
    result = naver_stock_etf_component_fetcher("411420", "2026-05-27", top_k=10)
    assert result.status == "ok"
    c = result.constituents[0]
    # 해외형 — componentItemCode null → constituent_ticker None.
    assert c.constituent_ticker is None
    assert c.constituent_reuters_code == "AVGO.O"
    assert c.constituent_isin == "US11135F1012"
    assert c.market_type == "2"


def test_naver_fetcher_http_404_unavailable(monkeypatch):
    monkeypatch.setattr(fetcher_mod, "_naver_http_get", _stub_http_get(404))
    result = naver_stock_etf_component_fetcher("XXXXXX", "2026-05-27", top_k=10)
    assert result.status == "unavailable"
    assert result.source == NAVER_STOCK_SOURCE
    assert "http_status_404" in (result.message or "")


def test_naver_fetcher_empty_response_unavailable(monkeypatch):
    monkeypatch.setattr(fetcher_mod, "_naver_http_get", _stub_http_get([]))
    result = naver_stock_etf_component_fetcher("069500", "2026-05-27", top_k=10)
    assert result.status == "unavailable"


def test_naver_fetcher_invalid_weight_excluded(monkeypatch):
    items = [
        {
            "componentItemCode": "005930",
            "componentName": "삼성전자",
            "weight": "32.33",
            "referenceDate": "2026-05-29",
        },
        {
            "componentItemCode": "000660",
            "componentName": "SK하이닉스",
            "weight": "-",  # 변환 불가 → 제외.
            "referenceDate": "2026-05-29",
        },
        {
            "componentItemCode": "035420",
            "componentName": "NAVER",
            "weight": None,  # None → 제외.
            "referenceDate": "2026-05-29",
        },
    ]
    monkeypatch.setattr(fetcher_mod, "_naver_http_get", _stub_http_get(items))
    result = naver_stock_etf_component_fetcher("069500", "2026-05-27", top_k=10)
    assert result.status == "ok"
    # 1건만 정상 weight → 1건만 결과 (지시문 §6.1 — 0 임의 대체 금지).
    assert len(result.constituents) == 1
    assert result.constituents[0].constituent_ticker == "005930"


def test_naver_fetcher_top_k_truncation(monkeypatch):
    items = [
        {
            "componentItemCode": f"{i:06d}",
            "componentName": f"S{i}",
            "weight": str(20.0 - i * 0.1),  # 내림차순 정렬되어야 정상 trim.
            "referenceDate": "2026-05-29",
        }
        for i in range(15)
    ]
    monkeypatch.setattr(fetcher_mod, "_naver_http_get", _stub_http_get(items))
    result = naver_stock_etf_component_fetcher("X", "2026-05-27", top_k=10)
    assert len(result.constituents) == 10
    # rank 1 의 weight 가 가장 큼.
    assert result.constituents[0].weight_pct == 20.0


def test_coerce_weight_string_variants():
    assert _coerce_weight_string("32.33") == 32.33
    assert _coerce_weight_string(25) == 25.0
    assert _coerce_weight_string(None) is None
    assert _coerce_weight_string("") is None
    assert _coerce_weight_string("-") is None
    assert _coerce_weight_string("abc") is None


def test_build_constituent_key_priority():
    # 국내 — item_code 우선.
    assert (
        _build_constituent_key("005930", None, "KR7005930003", "삼성전자") == "005930"
    )
    # 해외 — item_code 없으면 reuters.
    assert (
        _build_constituent_key(None, "AVGO.O", "US11135F1012", "브로드컴") == "AVGO.O"
    )
    # reuters 도 없으면 isin.
    assert (
        _build_constituent_key(None, None, "US11135F1012", "브로드컴") == "US11135F1012"
    )
    # 모두 없으면 name 기반.
    assert _build_constituent_key(None, None, None, "테스트")  # truthy
    assert _build_constituent_key(None, None, None, "테스트").startswith("name:")
    # 진짜 모두 없으면 None.
    assert _build_constituent_key(None, None, None, None) is None
    assert _build_constituent_key("", "", "", "") is None
