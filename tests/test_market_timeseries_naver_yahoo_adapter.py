"""Naver/FDR primary + Yahoo/FDR secondary adapter — fixture 기반 테스트.

외부 네트워크 호출 없이 stub fetcher 로 검증한다.
"""

from __future__ import annotations

from datetime import date
from typing import Iterable

import pandas as pd

from app.market_timeseries_naver_yahoo_adapter import (
    PRICE_BASIS,
    SOURCE_NAVER,
    SOURCE_YAHOO,
    build_naver_symbol,
    build_yahoo_symbol,
    fetch_ticker_prices,
)


def _df(rows: Iterable[tuple[str, float]]) -> pd.DataFrame:
    idx = pd.to_datetime([r[0] for r in rows])
    return pd.DataFrame({"Close": [r[1] for r in rows]}, index=idx)


def test_symbol_builders_are_source_explicit() -> None:
    """FIX r1 — 호출 식별자는 NAVER: / YAHOO: prefix 로 소스 명시."""
    assert build_naver_symbol("069500") == "NAVER:069500"
    assert build_yahoo_symbol("069500") == "YAHOO:069500.KS"


def test_naver_primary_returns_rows() -> None:
    calls: list[tuple[str, date, date]] = []

    def fetcher(symbol: str, start: date, end: date):
        calls.append((symbol, start, end))
        return _df([("2024-10-29", 100.0), ("2024-10-30", 101.0)])

    result = fetch_ticker_prices(
        "069500",
        start=date(2024, 10, 29),
        end=date(2024, 10, 30),
        price_fetcher=fetcher,
    )
    assert result.source == SOURCE_NAVER
    assert result.yahoo_attempted is False
    assert len(result.rows) == 2
    # FIX r1 — Primary 호출 시 FDR 에 NAVER: prefix 를 명시했는지 확인.
    assert calls == [("NAVER:069500", date(2024, 10, 29), date(2024, 10, 30))]


def test_yahoo_fallback_used_when_naver_empty() -> None:
    calls: list[str] = []

    def fetcher(symbol: str, start: date, end: date):
        calls.append(symbol)
        if symbol == "NAVER:069500":
            return _df([])  # naver empty
        return _df([("2024-10-29", 100.0)])  # yahoo returns

    result = fetch_ticker_prices(
        "069500",
        start=date(2024, 10, 29),
        end=date(2024, 10, 30),
        price_fetcher=fetcher,
    )
    assert result.source == SOURCE_YAHOO
    assert result.yahoo_attempted is True
    # FIX r1 — Secondary 호출 시 YAHOO: prefix + .KS suffix 를 명시.
    assert calls == ["NAVER:069500", "YAHOO:069500.KS"]


def test_yahoo_fallback_used_when_naver_raises() -> None:
    def fetcher(symbol: str, start: date, end: date):
        if symbol == "NAVER:069500":
            raise RuntimeError("naver_unavailable")
        return _df([("2024-10-29", 100.0)])

    result = fetch_ticker_prices(
        "069500",
        start=date(2024, 10, 29),
        end=date(2024, 10, 30),
        price_fetcher=fetcher,
    )
    assert result.source == SOURCE_YAHOO
    assert result.yahoo_attempted is True


def test_both_sources_empty_records_error() -> None:
    def fetcher(symbol: str, start: date, end: date):
        return _df([])

    result = fetch_ticker_prices(
        "069500",
        start=date(2024, 10, 29),
        end=date(2024, 10, 30),
        price_fetcher=fetcher,
    )
    assert result.rows == []
    assert result.error is not None
    assert "naver" in result.error and "yahoo" in result.error
    assert result.yahoo_attempted is True


def test_yahoo_only_attempted_once_per_call() -> None:
    calls: list[str] = []

    def fetcher(symbol: str, start: date, end: date):
        calls.append(symbol)
        return _df([])

    fetch_ticker_prices(
        "069500",
        start=date(2024, 10, 29),
        end=date(2024, 10, 30),
        price_fetcher=fetcher,
    )
    # 지시문: 자동 재시도 없음. NAVER: 1회 + YAHOO: 1회 = 총 2회.
    assert calls == ["NAVER:069500", "YAHOO:069500.KS"]


def test_price_basis_constant() -> None:
    assert PRICE_BASIS == "SOURCE_CLOSE"
