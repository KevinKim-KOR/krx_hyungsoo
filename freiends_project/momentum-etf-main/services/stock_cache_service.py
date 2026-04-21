from __future__ import annotations

from typing import Any

from utils.stock_cache_meta_io import (
    delete_stock_cache_meta_doc,
    get_stock_cache_meta_doc,
    get_stock_cache_meta_docs,
    upsert_stock_cache_meta_doc,
)


def get_stock_cache_meta(ticker_type: str, ticker: str) -> dict[str, Any] | None:
    """종목 메타 캐시 문서를 반환한다."""

    return get_stock_cache_meta_doc(ticker_type, ticker)


def get_stock_cache_meta_map(ticker_type: str, tickers: list[str]) -> dict[str, dict[str, Any]]:
    """종목 메타 캐시 문서를 티커 기준 맵으로 반환한다."""

    return get_stock_cache_meta_docs(ticker_type, tickers)


def refresh_stock_meta_cache(
    ticker_type: str,
    ticker: str,
    *,
    country_code: str,
    name: str,
    meta_cache: dict[str, Any],
) -> None:
    """저빈도 ETF 메타 캐시를 저장한다."""

    upsert_stock_cache_meta_doc(
        ticker_type,
        ticker,
        country_code=country_code,
        name=name,
        meta_cache=meta_cache,
    )


def refresh_stock_holdings_cache(
    ticker_type: str,
    ticker: str,
    *,
    country_code: str,
    name: str,
    holdings_cache: dict[str, Any],
) -> None:
    """ETF 구성종목 캐시를 저장한다."""

    upsert_stock_cache_meta_doc(
        ticker_type,
        ticker,
        country_code=country_code,
        name=name,
        holdings_cache=holdings_cache,
    )


def refresh_stock_cache(
    ticker_type: str,
    ticker: str,
    *,
    country_code: str,
    name: str,
    meta_cache: dict[str, Any] | None = None,
    holdings_cache: dict[str, Any] | None = None,
) -> None:
    """종목 메타 캐시와 구성종목 캐시를 함께 저장한다."""

    if meta_cache is None and holdings_cache is None:
        raise ValueError("meta_cache 또는 holdings_cache 중 하나는 반드시 필요합니다.")

    upsert_stock_cache_meta_doc(
        ticker_type,
        ticker,
        country_code=country_code,
        name=name,
        meta_cache=meta_cache,
        holdings_cache=holdings_cache,
    )


def delete_stock_cache(ticker_type: str, ticker: str) -> None:
    """종목 메타 캐시 문서를 삭제한다."""

    delete_stock_cache_meta_doc(ticker_type, ticker)
