"""POC2 Step 2 — Naver 금융 비공식 JSON endpoint 어댑터.

설계자 결정:
- endpoint: https://m.stock.naver.com/api/stock/{ticker}/basic
- 1차 소스, 한국 종목/ETF 만
- 종목별 timeout 적용
- 단일 종목 실패는 격리 (다른 종목 진행)
- BeautifulSoup / desktop scraping / polling stream 금지
- pykrx / yfinance fallback 금지 (POC2 Step 2 한정)

이 모듈은 명시적 시장데이터 갱신 액션에서만 호출되어야 한다 (api 레이어 책임).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import httpx

from app.market_cache import MarketQuote

logger = logging.getLogger(__name__)

NAVER_BASIC_URL = "https://m.stock.naver.com/api/stock/{ticker}/basic"
DEFAULT_TIMEOUT_SEC = 5.0
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://m.stock.naver.com/",
    "Accept": "application/json, */*",
}


@dataclass
class FetchResult:
    """단일 종목 조회 결과. quote 가 None 이면 실패 (이유는 reason 에)."""

    ticker: str
    quote: Optional[MarketQuote]
    reason: Optional[str] = None


def _parse_price(raw: object) -> Optional[float]:
    """Naver 응답의 closePrice 는 '100,240' 형식 문자열. 콤마 제거 후 float."""
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    if not isinstance(raw, str):
        return None
    s = raw.replace(",", "").strip()
    if not s:
        return None
    try:
        n = float(s)
    except ValueError:
        return None
    if n <= 0:
        return None
    return n


def fetch_one(
    ticker: str,
    *,
    timeout: float = DEFAULT_TIMEOUT_SEC,
    client: Optional[httpx.Client] = None,
) -> FetchResult:
    """단일 ticker 조회. 실패 시 quote=None + reason. 예외 raise 안 함."""
    url = NAVER_BASIC_URL.format(ticker=ticker)
    try:
        if client is not None:
            resp = client.get(url, timeout=timeout, headers=DEFAULT_HEADERS)
        else:
            with httpx.Client(timeout=timeout, headers=DEFAULT_HEADERS) as c:
                resp = c.get(url)
    except httpx.TimeoutException:
        logger.warning(f"[market_naver] timeout ticker={ticker}")
        return FetchResult(ticker=ticker, quote=None, reason="timeout")
    except httpx.HTTPError as e:
        logger.warning(f"[market_naver] http error ticker={ticker}: {e}")
        return FetchResult(ticker=ticker, quote=None, reason=f"http_error:{e}")
    if resp.status_code != 200:
        return FetchResult(ticker=ticker, quote=None, reason=f"http_{resp.status_code}")
    try:
        data = resp.json()
    except ValueError:
        return FetchResult(ticker=ticker, quote=None, reason="json_decode_error")
    if not isinstance(data, dict):
        return FetchResult(ticker=ticker, quote=None, reason="unexpected_payload")
    name = data.get("stockName") if isinstance(data.get("stockName"), str) else None
    price = _parse_price(data.get("closePrice"))
    if price is None:
        return FetchResult(ticker=ticker, quote=None, reason="missing_price")
    asof = (
        data.get("localTradedAt")
        if isinstance(data.get("localTradedAt"), str)
        else None
    )
    quote = MarketQuote(
        ticker=ticker,
        name=name,
        current_price=price,
        price_asof=asof,
        price_source="naver",
    )
    return quote_result_ok(ticker, quote)


def quote_result_ok(ticker: str, quote: MarketQuote) -> FetchResult:
    return FetchResult(ticker=ticker, quote=quote, reason=None)


def fetch_many(
    tickers: list[str], *, timeout: float = DEFAULT_TIMEOUT_SEC
) -> list[FetchResult]:
    """여러 종목 순차 조회. 단일 실패는 격리.

    이번 단계는 동시성 도입 안 함 (단순 직렬). Naver 는 비공식 endpoint 라
    과도한 동시 호출을 피한다.
    """
    results: list[FetchResult] = []
    seen: set[str] = set()
    with httpx.Client(timeout=timeout, headers=DEFAULT_HEADERS) as client:
        for t in tickers:
            if t in seen:
                continue
            seen.add(t)
            results.append(fetch_one(t, timeout=timeout, client=client))
    return results
