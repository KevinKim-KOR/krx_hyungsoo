from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import pandas as pd
import requests
import yfinance as yf
from pykrx import stock

from utils.data_loader import get_trading_days
from utils.logger import get_app_logger

logger = get_app_logger()

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
NAVER_ETF_COMPONENT_URL = "https://stock.naver.com/api/domestic/detail/{ticker}/ETFComponent"
_NAVER_ETF_COMPONENT_CACHE: dict[str, dict[str, Any]] = {}
_NAVER_ETF_COMPONENT_TTL_SECONDS = 300
_FOREIGN_PRICE_CACHE: dict[str, dict[str, Any]] = {}
_FOREIGN_PRICE_TTL_SECONDS = 300
_YAHOO_SYMBOL_RESOLUTION_CACHE: dict[str, dict[str, Any]] = {}
_YAHOO_SYMBOL_RESOLUTION_TTL_SECONDS = 3600


def _normalize_ticker(ticker: str) -> str:
    return str(ticker or "").strip().upper().replace("ASX:", "")


def _normalize_date(value: str | None) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None


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


def _to_int(value: Any) -> int | None:
    parsed = _to_float(value)
    if parsed is None:
        return None
    return int(parsed)


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


# Yahoo Finance 에서 쓰는 주요 거래소 접미사 화이트리스트.
# reuters_code 가 이 중 하나로 끝나면 그대로 Yahoo 심볼로 사용한다.
# 참고: https://help.yahoo.com/kb/SLN2310.html
_YAHOO_EXCHANGE_SUFFIXES: frozenset[str] = frozenset(
    {
        # 아시아/태평양
        "T",     # 도쿄 (TSE)
        "HK",    # 홍콩
        "SS",    # 상하이
        "SZ",    # 선전
        "BJ",    # 베이징
        "KS",    # 한국 KOSPI
        "KQ",    # 한국 KOSDAQ
        "TW",    # 타이완
        "TWO",   # 타이완 OTC
        "SI",    # 싱가포르
        "BK",    # 방콕
        "JK",    # 자카르타
        "KL",    # 쿠알라룸푸르
        "HO",    # 호치민
        "AX",    # 호주 ASX
        "NZ",    # 뉴질랜드
        # 유럽
        "L",     # 런던
        "IL",    # 런던 IOB
        "PA",    # 파리
        "DE",    # XETRA
        "F",     # 프랑크푸르트
        "BE",    # 베를린
        "DU",    # 뒤셀도르프
        "HM",    # 함부르크
        "MU",    # 뮌헨
        "SG",    # 슈투트가르트
        "AS",    # 암스테르담
        "BR",    # 브뤼셀
        "LS",    # 리스본
        "MC",    # 마드리드
        "MI",    # 밀라노
        "SW",    # 스위스
        "VX",    # 스위스(VX)
        "ST",    # 스톡홀름
        "HE",    # 헬싱키
        "OL",    # 오슬로
        "CO",    # 코펜하겐
        "IC",    # 아이슬란드
        "IR",    # 아일랜드
        "VI",    # 빈
        "PR",    # 프라하
        "WA",    # 바르샤바
        "BD",    # 부다페스트
        "AT",    # 아테네
        "IS",    # 이스탄불
        "TA",    # 텔아비브
        # 아메리카
        "TO",    # 토론토 TSX
        "V",     # 토론토 TSX Venture
        "CN",    # 캐나다 CSE
        "NE",    # 캐나다 NEO
        "SA",    # 브라질 B3
        "MX",    # 멕시코
        "BA",    # 부에노스아이레스
        "SN",    # 산티아고
        # 중동/아프리카
        "SR",    # 사우디
        "QA",    # 카타르
        "JO",    # 요하네스버그
        "CA",    # 카이로
    }
)


def extract_yahoo_symbol_from_reuters_code(value: str | None) -> str | None:
    normalized = str(value or "").strip().upper()
    if not normalized:
        return None
    base, dot, suffix = normalized.partition(".")
    base = base.strip()
    suffix = suffix.strip()
    if not base:
        return None
    if not dot:
        return base
    if suffix in _YAHOO_EXCHANGE_SUFFIXES:
        return f"{base}.{suffix}"
    return base


def extract_yahoo_symbol_from_isin(value: str | None) -> str | None:
    normalized = str(value or "").strip().upper()
    if not normalized:
        return None
    if normalized.startswith("AU") and len(normalized) == 12:
        asx_code = normalized[8:11].strip().upper()
        if len(asx_code) == 3 and asx_code.isalpha():
            return f"{asx_code}.AX"
    return None


def extract_yahoo_symbol_from_component_code(
    component_item_code: str | None,
    raw_code: str | None,
) -> str | None:
    normalized_code = str(component_item_code or "").strip().upper()
    normalized_raw = str(raw_code or "").strip().upper()
    if not normalized_code:
        return None

    if len(normalized_code) == 6 and normalized_code.isdigit() and normalized_raw.startswith("CNE"):
        if normalized_code.startswith("6"):
            return f"{normalized_code}.SS"
        if normalized_code.startswith(("0", "3")):
            return f"{normalized_code}.SZ"
        if normalized_code.startswith(("4", "8")):
            return f"{normalized_code}.BJ"
    # 일본: ISIN 이 JP 로 시작하고 component code 가 4자리 TSE 종목코드인 경우
    if len(normalized_code) == 4 and normalized_code.isdigit() and normalized_raw.startswith("JP"):
        return f"{normalized_code}.T"
    return None


def _get_preferred_exchanges_from_isin(isin_code: str | None) -> list[str]:
    normalized = str(isin_code or "").strip().upper()
    if normalized.startswith("AU"):
        return ["ASX"]
    if normalized.startswith("FR"):
        return ["PAR"]
    return []


def _extract_yahoo_symbol_from_search_result(item: dict[str, Any]) -> str | None:
    symbol = str(item.get("symbol") or "").strip().upper()
    if not symbol:
        return None
    return symbol


def resolve_yahoo_symbol_from_isin_or_name(
    raw_code: str | None,
    raw_name: str | None,
) -> str | None:
    queries = [str(raw_code or "").strip().upper(), str(raw_name or "").strip()]
    queries = [query for query in queries if query]
    if not queries:
        return None

    preferred_exchanges = _get_preferred_exchanges_from_isin(raw_code)
    now = datetime.now()
    cache_key = f"{str(raw_code or '').strip().upper()}::{str(raw_name or '').strip().upper()}"
    cached_entry = _YAHOO_SYMBOL_RESOLUTION_CACHE.get(cache_key)
    if _is_cache_alive(cached_entry, now):
        return cached_entry.get("data")

    resolved_symbol: str | None = None
    for query in queries:
        try:
            search = yf.Search(query, max_results=10, news_count=0, lists_count=0, recommended=0)
        except Exception as exc:
            logger.info("Yahoo 심볼 검색 실패(%s): %s", query, exc)
            continue

        quotes = list(search.quotes or [])
        if not quotes:
            continue

        if preferred_exchanges:
            for exchange in preferred_exchanges:
                preferred_match = next(
                    (
                        item
                        for item in quotes
                        if str(item.get("exchange") or "").strip().upper() == exchange
                        and _extract_yahoo_symbol_from_search_result(item)
                    ),
                    None,
                )
                if preferred_match:
                    resolved_symbol = _extract_yahoo_symbol_from_search_result(preferred_match)
                    break
        if resolved_symbol:
            break

        first_match = next((item for item in quotes if _extract_yahoo_symbol_from_search_result(item)), None)
        if first_match:
            resolved_symbol = _extract_yahoo_symbol_from_search_result(first_match)
            break

    _YAHOO_SYMBOL_RESOLUTION_CACHE[cache_key] = {
        "data": resolved_symbol,
        "expires_at": now + timedelta(seconds=_YAHOO_SYMBOL_RESOLUTION_TTL_SECONDS),
    }
    return resolved_symbol


def extract_display_ticker_from_symbol(value: str | None) -> str | None:
    normalized = str(value or "").strip().upper()
    if not normalized:
        return None
    if "." in normalized:
        base, _, suffix = normalized.partition(".")
        if base.isalpha() and suffix.isalpha():
            return base
    if normalized.endswith(".AX"):
        return normalized[:-3]
    if normalized.endswith(".HK"):
        return normalized
    return normalized


def _normalize_reference_date(value: str | None) -> str | None:
    normalized = str(value or "").strip()
    if not normalized:
        return None
    return normalized.replace("-", "")


def _normalize_contracts(value: Any) -> int | float | None:
    parsed = _to_float(value)
    if parsed is None:
        return None
    if float(parsed).is_integer():
        return int(parsed)
    return round(parsed, 2)


def fetch_korean_etf_holdings_from_naver(ticker: str) -> dict[str, Any]:
    normalized_ticker = _normalize_ticker(ticker)
    if not normalized_ticker:
        raise ValueError("ETF 티커가 필요합니다.")

    cache_key = f"naver-holdings:{normalized_ticker}"
    now = datetime.now()
    cached_entry = _NAVER_ETF_COMPONENT_CACHE.get(cache_key)
    if _is_cache_alive(cached_entry, now):
        return dict(cached_entry["data"])

    session = _create_naver_session()
    response = session.get(NAVER_ETF_COMPONENT_URL.format(ticker=normalized_ticker), timeout=15)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        raise RuntimeError(f"네이버 ETFComponent 응답 형식이 올바르지 않습니다: {normalized_ticker}")
    if not payload:
        raise RuntimeError(f"네이버 ETFComponent 응답이 비어 있습니다: {normalized_ticker}")

    holdings: list[dict[str, Any]] = []
    as_of_date: str | None = None

    for item in payload:
        raw_code = str(item.get("componentIsinCode") or item.get("componentItemCode") or "").strip().upper()
        raw_name = str(item.get("componentName") or "").strip()

        component_item_code = str(item.get("componentItemCode") or "").strip().upper() or None
        component_reuters_code = str(item.get("componentReutersCode") or "").strip().upper() or None
        yahoo_symbol = (
            extract_yahoo_symbol_from_reuters_code(component_reuters_code)
            or extract_yahoo_symbol_from_component_code(component_item_code, raw_code)
            or extract_yahoo_symbol_from_isin(raw_code)
            or resolve_yahoo_symbol_from_isin_or_name(raw_code, raw_name)
        )
        display_ticker = component_item_code or extract_display_ticker_from_symbol(yahoo_symbol) or raw_code
        reference_date = _normalize_reference_date(item.get("referenceDate"))
        if reference_date:
            as_of_date = reference_date

        holdings.append(
            {
                "ticker": display_ticker,
                "name": raw_name,
                "raw_code": raw_code,
                "raw_name": raw_name,
                "reuters_code": component_reuters_code,
                "yahoo_symbol": yahoo_symbol,
                "contracts": _normalize_contracts(item.get("cuUnitQuantity")),
                "amount": _to_int(item.get("evalAmount")),
                "weight": _to_float(item.get("weight")),
                "market_type": str(item.get("componentMarketType") or "").strip() or None,
            }
        )

    if not holdings:
        raise RuntimeError(f"네이버 ETFComponent에서 저장 가능한 구성종목이 없습니다: {normalized_ticker}")
    if not as_of_date:
        raise RuntimeError(f"네이버 ETFComponent 기준일(referenceDate)을 찾지 못했습니다: {normalized_ticker}")

    holdings.sort(key=lambda row: (row.get("weight") is None, -(row.get("weight") or 0)))
    document = {
        "ticker": normalized_ticker,
        "country_code": "kor",
        "source": "naver_etf_component",
        "as_of_date": as_of_date,
        "holdings_count": len(holdings),
        "holdings": holdings,
        "fetched_at": now.isoformat(),
    }
    _NAVER_ETF_COMPONENT_CACHE[cache_key] = {
        "data": dict(document),
        "expires_at": now + timedelta(seconds=_NAVER_ETF_COMPONENT_TTL_SECONDS),
    }
    return document


def fetch_korean_stock_price_snapshot(tickers: list[str], as_of_date: str) -> dict[str, dict[str, Any]]:
    normalized_date = _normalize_date(as_of_date)
    if not normalized_date:
        raise ValueError("현재가 조회 기준일(as_of_date)이 필요합니다.")

    normalized_tickers = [_normalize_ticker(ticker) for ticker in tickers if _normalize_ticker(ticker)]
    if not normalized_tickers:
        return {}

    target_date = pd.Timestamp(normalized_date)
    search_start_date = (target_date - pd.Timedelta(days=10)).strftime("%Y-%m-%d")
    search_end_date = target_date.strftime("%Y-%m-%d")
    try:
        trading_days = get_trading_days(
            search_start_date,
            search_end_date,
            "kor",
        )
    except Exception as exc:
        logger.exception(
            "한국 거래일 조회 실패: as_of_date=%s, search_start=%s, search_end=%s, tickers=%s",
            normalized_date,
            search_start_date,
            search_end_date,
            normalized_tickers,
        )
        raise RuntimeError(
            "한국 거래일 조회에 실패했습니다: "
            f"as_of_date={normalized_date}, search_start={search_start_date}, "
            f"search_end={search_end_date}, original_error={exc}"
        ) from exc

    normalized_trading_days = [pd.Timestamp(day).strftime("%Y%m%d") for day in trading_days]
    if normalized_date not in normalized_trading_days:
        logger.error(
            "한국 거래일 불일치: as_of_date=%s, search_start=%s, search_end=%s, trading_days=%s, tickers=%s",
            normalized_date,
            search_start_date,
            search_end_date,
            normalized_trading_days,
            normalized_tickers,
        )
        raise RuntimeError(
            "한국 거래일 목록에 기준일이 없습니다: "
            f"as_of_date={normalized_date}, search_start={search_start_date}, "
            f"search_end={search_end_date}, trading_days={normalized_trading_days}"
        )

    target_index = normalized_trading_days.index(normalized_date)
    if target_index == 0:
        logger.error(
            "전일 거래일 계산 실패: as_of_date=%s, trading_days=%s, tickers=%s",
            normalized_date,
            normalized_trading_days,
            normalized_tickers,
        )
        raise RuntimeError(
            "전일 거래일을 계산할 수 없습니다: "
            f"as_of_date={normalized_date}, trading_days={normalized_trading_days}"
        )
    previous_date = normalized_trading_days[target_index - 1]

    result: dict[str, dict[str, Any]] = {}
    for ticker in normalized_tickers:
        if not ticker.isdigit() or len(ticker) != 6:
            continue
        df = stock.get_market_ohlcv_by_date(previous_date, normalized_date, ticker)
        if df is None or df.empty:
            continue
        working_df = df.copy().sort_index()
        if len(working_df) < 2:
            continue

        previous_close = _to_int(working_df.iloc[-2].get("종가"))
        current_price = _to_int(working_df.iloc[-1].get("종가"))
        if previous_close is None or current_price is None or previous_close == 0:
            continue

        change_pct = round(((current_price / previous_close) - 1.0) * 100.0, 2)
        result[ticker] = {
            "current_price": current_price,
            "previous_close": previous_close,
            "change_pct": change_pct,
            "price_currency": "KRW",
        }

    return result


def _fetch_single_foreign_stock_price_snapshot(symbol: str) -> dict[str, Any] | None:
    try:
        ticker = yf.Ticker(symbol)
        history = ticker.history(period="5d", auto_adjust=False)
    except Exception as exc:
        logger.info("해외 구성종목 가격 조회 실패(%s): %s", symbol, exc)
        return None
    if history is None or history.empty:
        return None

    working_df = history.copy().sort_index()
    working_df = working_df[pd.to_numeric(working_df.get("Close"), errors="coerce").notna()]
    if len(working_df) < 2:
        return None

    previous_close = _to_float(working_df.iloc[-2].get("Close"))
    current_price = _to_float(working_df.iloc[-1].get("Close"))
    if previous_close is None or current_price is None or previous_close == 0:
        return None

    as_of_date = pd.Timestamp(working_df.index[-1]).strftime("%Y%m%d")
    metadata = getattr(ticker, "history_metadata", None)
    price_currency = None
    if isinstance(metadata, dict):
        price_currency = str(metadata.get("currency") or "").strip().upper() or None

    return {
        "current_price": round(current_price, 2),
        "previous_close": round(previous_close, 2),
        "change_pct": round(((current_price / previous_close) - 1.0) * 100.0, 2),
        "price_currency": price_currency,
        "as_of_date": as_of_date,
    }


def fetch_foreign_stock_price_snapshot(symbols: list[str]) -> tuple[dict[str, dict[str, Any]], str | None]:
    normalized_symbols = sorted({str(symbol or "").strip().upper() for symbol in symbols if str(symbol or "").strip()})
    if not normalized_symbols:
        return {}, None

    now = datetime.now()
    result: dict[str, dict[str, Any]] = {}
    as_of_dates: set[str] = set()
    for symbol in normalized_symbols:
        cache_key = f"foreign:{symbol}"
        cached_entry = _FOREIGN_PRICE_CACHE.get(cache_key)
        snapshot: dict[str, Any] | None
        if _is_cache_alive(cached_entry, now):
            snapshot = dict(cached_entry["data"])
        else:
            snapshot = _fetch_single_foreign_stock_price_snapshot(symbol)
            if snapshot is None:
                continue
            _FOREIGN_PRICE_CACHE[cache_key] = {
                "data": dict(snapshot),
                "expires_at": now + timedelta(seconds=_FOREIGN_PRICE_TTL_SECONDS),
            }

        result[symbol] = snapshot
        as_of_date = str(snapshot.get("as_of_date") or "").strip()
        if as_of_date:
            as_of_dates.add(as_of_date)

    if not as_of_dates:
        return result, None
    return result, max(as_of_dates)
