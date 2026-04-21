from __future__ import annotations

import re
from typing import Any

import requests

from utils.db_manager import get_db_connection
from utils.normalization import (
    normalize_nullable_number,
    normalize_number,
    normalize_text,
    to_iso_string,
)

_POOL_NAME_PREFIX_PATTERN = re.compile(r"^\d+\.\s*")


def _strip_pool_name_prefix(value: str) -> str:
    return _POOL_NAME_PREFIX_PATTERN.sub("", str(value or "").strip())


def _load_ticker_pool_map() -> dict[str, list[str]]:
    from utils.stock_list_io import get_etfs
    from utils.ticker_registry import load_ticker_type_configs

    ticker_pool_map: dict[str, list[str]] = {}

    for config in load_ticker_type_configs():
        ticker_type = str(config.get("ticker_type") or "").strip().lower()
        pool_name = _strip_pool_name_prefix(str(config.get("name") or ticker_type))
        if not ticker_type or not pool_name:
            continue

        for item in get_etfs(ticker_type):
            ticker = normalize_text(item.get("ticker")).upper()
            if not ticker:
                continue
            ticker_pool_map.setdefault(ticker, [])
            if pool_name not in ticker_pool_map[ticker]:
                ticker_pool_map[ticker].append(pool_name)

    return ticker_pool_map


def _load_kor_etf_realtime_snapshot(tickers: list[str]) -> dict[str, dict[str, float | None]]:
    if not tickers:
        return {}

    response = requests.get(
        "https://finance.naver.com/api/sise/etfItemList.nhn",
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0.0.0 Safari/537.36"
            ),
            "Referer": "https://finance.naver.com/sise/etfList.nhn",
            "Accept": "application/json, text/plain, */*",
        },
        timeout=20,
    )
    response.raise_for_status()

    payload = response.json()
    items = payload.get("result", {}).get("etfItemList")
    if not isinstance(items, list):
        raise ValueError("네이버 ETF 실시간 스냅샷 응답 형식이 올바르지 않습니다.")

    ticker_set = {ticker.upper() for ticker in tickers if ticker}
    snapshot: dict[str, dict[str, float | None]] = {}

    for item in items:
        code = str(item.get("itemcode") or "").strip().upper()
        if not code or code not in ticker_set:
            continue

        now_val = normalize_nullable_number(item.get("nowVal"))
        nav = normalize_nullable_number(item.get("nav"))
        change_rate = normalize_nullable_number(item.get("changeRate"))
        three_month_earn_rate = normalize_nullable_number(item.get("threeMonthEarnRate"))
        deviation = ((now_val / nav) - 1) * 100 if now_val is not None and nav not in (None, 0) else None

        snapshot[code] = {
            "changeRate": change_rate,
            "nowVal": now_val,
            "nav": nav,
            "deviation": deviation,
            "threeMonthEarnRate": three_month_earn_rate,
        }

    return snapshot


def load_market_data() -> dict[str, Any]:
    db = get_db_connection()
    if db is None:
        raise RuntimeError("MongoDB 연결에 실패했습니다.")

    doc = db.etf_market_master.find_one({"master_id": "kor_etf_market"}) or {}
    rows = doc.get("rows") or []
    if not rows:
        raise RuntimeError("ETF 마켓 캐시가 없습니다. stock_meta_cache_updater를 먼저 실행하세요.")

    normalized_rows = [
        {
            "ticker": normalize_text(row.get("티커")),
            "name": normalize_text(row.get("종목명")),
            "ticker_pools": "",
            "listed_at": normalize_text(row.get("상장일")),
            "prev_volume": int(normalize_number(row.get("전일거래량"))),
            "market_cap": int(normalize_number(row.get("시가총액"))),
        }
        for row in rows
    ]

    ticker_pool_map = _load_ticker_pool_map()
    snapshot = _load_kor_etf_realtime_snapshot([row["ticker"] for row in normalized_rows if row["ticker"]])

    from utils.portfolio_io import load_all_holding_tickers
    held_tickers = load_all_holding_tickers()

    return {
        "updated_at": to_iso_string(doc.get("updated_at")),
        "rows": [
            {
                **row,
                "ticker_pools": ", ".join(ticker_pool_map.get(row["ticker"], [])),
                "is_held": row["ticker"] in held_tickers,
                "daily_change_pct": snapshot.get(row["ticker"], {}).get("changeRate"),
                "current_price": snapshot.get(row["ticker"], {}).get("nowVal"),
                "nav": snapshot.get(row["ticker"], {}).get("nav"),
                "deviation": snapshot.get(row["ticker"], {}).get("deviation"),
                "return_3m_pct": snapshot.get(row["ticker"], {}).get("threeMonthEarnRate"),
            }
            for row in normalized_rows
        ],
    }
