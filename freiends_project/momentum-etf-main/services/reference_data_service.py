from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

from utils.kis_market import load_cached_kis_domestic_etf_master
from utils.stock_list_io import get_listing_date as load_listing_date
from utils.stock_meta_updater import fetch_stock_info as load_stock_reference_info


def get_kor_etf_master() -> tuple[pd.DataFrame, datetime | None]:
    """국내 ETF 마스터 캐시를 반환한다."""

    return load_cached_kis_domestic_etf_master()


def get_stock_reference_info(ticker: str, country_code: str) -> dict[str, Any] | None:
    """단일 종목의 참조 메타데이터를 반환한다."""

    return load_stock_reference_info(ticker, country_code)


def get_listing_date(country_code: str, ticker: str) -> str | None:
    """종목의 상장일을 반환한다."""

    return load_listing_date(country_code, ticker)


__all__ = [
    "get_kor_etf_master",
    "get_listing_date",
    "get_stock_reference_info",
]
