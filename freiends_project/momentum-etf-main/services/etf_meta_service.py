from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import pandas as pd
import requests

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
NAVER_ETF_BASE_URL = "https://stock.naver.com/api/domestic/detail/{ticker}/ETFBase"
NAVER_ETF_DIVIDEND_URL = "https://stock.naver.com/api/domestic/detail/{ticker}/ETFDividend"
_NAVER_ETF_INFO_CACHE: dict[str, dict[str, Any]] = {}
_NAVER_ETF_INFO_TTL_SECONDS = 300


def _normalize_ticker(ticker: str) -> str:
    return str(ticker or "").strip().upper()


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, str):
        normalized = value.replace(",", "").strip()
        if not normalized or normalized == "-":
            return None
        value = normalized
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(parsed):
        return None
    return float(parsed)


def _normalize_listed_date(value: Any) -> str | None:
    normalized = str(value or "").strip()
    if not normalized:
        return None
    if len(normalized) == 8 and normalized.isdigit():
        return f"{normalized[:4]}-{normalized[4:6]}-{normalized[6:8]}"
    return normalized


def _is_cache_alive(cache_entry: dict[str, Any] | None, now: datetime) -> bool:
    if not cache_entry:
        return False
    expires_at = cache_entry.get("expires_at")
    if not isinstance(expires_at, datetime):
        return False
    return now < expires_at


def _create_naver_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": DEFAULT_USER_AGENT,
            "Referer": "https://stock.naver.com/",
            "Accept": "application/json, text/plain, */*",
        }
    )
    return session


def _fetch_naver_json(session: requests.Session, url: str) -> dict[str, Any]:
    response = session.get(url, timeout=15)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError(f"네이버 ETF 메타 응답 형식이 올바르지 않습니다: {url}")
    return payload


def fetch_korean_etf_info_from_naver(ticker: str) -> dict[str, Any]:
    normalized_ticker = _normalize_ticker(ticker)
    if not normalized_ticker:
        raise ValueError("ETF 티커가 필요합니다.")

    cache_key = f"naver-etf-info:{normalized_ticker}"
    now = datetime.now()
    cached_entry = _NAVER_ETF_INFO_CACHE.get(cache_key)
    if _is_cache_alive(cached_entry, now):
        return dict(cached_entry["data"])

    session = _create_naver_session()
    base_payload = _fetch_naver_json(session, NAVER_ETF_BASE_URL.format(ticker=normalized_ticker))
    dividend_payload = _fetch_naver_json(session, NAVER_ETF_DIVIDEND_URL.format(ticker=normalized_ticker))

    document = {
        "ticker": normalized_ticker,
        "source": "naver_etf_meta",
        "reference_date": str(dividend_payload.get("referenceDate") or "").strip() or None,
        "dividend_yield_ttm": _to_float(dividend_payload.get("dividendYieldTtm")),
        "dividend_per_share_ttm": _to_float(dividend_payload.get("dividendPerShareTtm")),
        "recent_ex_dividend_at": str(dividend_payload.get("recentExDividendAt") or "").strip() or None,
        "expense_ratio": _to_float(base_payload.get("fundPay")),
        "total_net_assets": _to_float(base_payload.get("totalNetAssets")),
        "listed_date": _normalize_listed_date(base_payload.get("listedDate")),
        "issue_name": str(base_payload.get("issueName") or "").strip() or None,
        "base_index": str(base_payload.get("etfBaseIdx") or "").strip() or None,
        "fetched_at": now.isoformat(),
    }
    _NAVER_ETF_INFO_CACHE[cache_key] = {
        "data": dict(document),
        "expires_at": now + timedelta(seconds=_NAVER_ETF_INFO_TTL_SECONDS),
    }
    return document


def fetch_korean_etf_info_map(tickers: list[str]) -> dict[str, dict[str, Any]]:
    info_map: dict[str, dict[str, Any]] = {}
    for ticker in sorted({_normalize_ticker(ticker) for ticker in tickers if _normalize_ticker(ticker)}):
        info_map[ticker] = fetch_korean_etf_info_from_naver(ticker)
    return info_map
