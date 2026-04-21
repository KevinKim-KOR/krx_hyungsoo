from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from config import MARKET_SCHEDULES
from utils.data_loader import (
    fetch_au_quoteapi_snapshot,
    fetch_naver_etf_inav_snapshot,
    fetch_naver_stock_realtime_snapshot,
    get_latest_trading_day,
)
from utils.data_loader import (
    get_exchange_rate_series as load_exchange_rate_series,
)
from utils.logger import get_app_logger

logger = get_app_logger()

_PRICE_SERVICE_CACHE: dict[str, dict[str, Any]] = {}

_KOR_ACTIVE_TTL_SECONDS = 30
_AU_ACTIVE_TTL_SECONDS = 60
_IDLE_TTL_SECONDS = 3600
_FX_TTL_SECONDS = 3600


def get_realtime_snapshot(country_code: str, tickers: Sequence[str]) -> dict[str, dict[str, float]]:
    """국가별 실시간 스냅샷을 반환한다."""

    country = _normalize_country_code(country_code)
    normalized_tickers = _normalize_tickers(tickers)
    if not normalized_tickers:
        return {}

    cache_key = _build_realtime_cache_key(country, normalized_tickers)
    cached_entry = _PRICE_SERVICE_CACHE.get(cache_key)
    now = datetime.now()

    if _is_cache_alive(cached_entry, now):
        return _filter_snapshot_data(cached_entry["data"], normalized_tickers)

    try:
        fetched_data, source = _fetch_realtime_snapshot(country, normalized_tickers)
    except Exception as exc:
        stale_data = _reuse_stale_cache(cache_key, normalized_tickers, exc)
        if stale_data is not None:
            return stale_data
        raise

    ttl_seconds = _get_realtime_ttl_seconds(country)
    _store_cache_entry(
        cache_key=cache_key,
        data=fetched_data,
        source=source,
        ttl_seconds=ttl_seconds,
        is_stale=False,
    )
    return _filter_snapshot_data(fetched_data, normalized_tickers)


def get_exchange_rates() -> dict[str, Any]:
    """USD/KRW, AUD/KRW 환율을 반환한다."""

    cache_key = "fx:usd_aud"
    cached_entry = _PRICE_SERVICE_CACHE.get(cache_key)
    now = datetime.now()

    if _is_cache_alive(cached_entry, now):
        return dict(cached_entry["data"])

    try:
        rates = _fetch_exchange_rates()
    except Exception as exc:
        stale_rates = _reuse_stale_exchange_rates(cache_key, exc)
        if stale_rates is not None:
            return stale_rates
        raise

    _store_cache_entry(
        cache_key=cache_key,
        data=rates,
        source="yfinance",
        ttl_seconds=_FX_TTL_SECONDS,
        is_stale=False,
    )
    return dict(rates)


def get_exchange_rate_series(
    start_date: str | Any,
    end_date: str | Any,
    symbol: str = "KRW=X",
    *,
    allow_partial: bool = False,
) -> Any:
    """환율 시계열을 반환한다."""

    return load_exchange_rate_series(
        start_date=start_date,
        end_date=end_date,
        symbol=symbol,
        allow_partial=allow_partial,
    )


def clear_price_service_cache() -> None:
    """가격 서비스 메모리 캐시를 초기화한다."""

    _PRICE_SERVICE_CACHE.clear()


def get_realtime_cache_meta(cache_key: str) -> dict[str, Any] | None:
    """캐시 메타데이터를 반환한다."""

    entry = _PRICE_SERVICE_CACHE.get(str(cache_key or "").strip())
    if not entry:
        return None
    return {
        "fetched_at": entry.get("fetched_at"),
        "expires_at": entry.get("expires_at"),
        "is_stale": entry.get("is_stale", False),
        "source": entry.get("source"),
        "size": len(entry.get("data", {})),
    }


def get_realtime_snapshot_meta(country_code: str, tickers: Sequence[str]) -> dict[str, Any] | None:
    """국가별 실시간 스냅샷 캐시 메타데이터를 반환한다."""

    country = _normalize_country_code(country_code)
    normalized_tickers = _normalize_tickers(tickers)
    if not normalized_tickers:
        return None
    cache_key = _build_realtime_cache_key(country, normalized_tickers)
    return get_realtime_cache_meta(cache_key)


def _normalize_country_code(country_code: str) -> str:
    country = str(country_code or "").strip().lower()
    if not country:
        raise ValueError("country_code는 필수입니다.")
    if country not in MARKET_SCHEDULES:
        raise ValueError(f"지원하지 않는 country_code입니다: {country}")
    return country


def _normalize_tickers(tickers: Sequence[str]) -> tuple[str, ...]:
    normalized = sorted({str(ticker or "").strip().upper() for ticker in tickers if str(ticker or "").strip()})
    return tuple(normalized)


def _build_realtime_cache_key(country: str, tickers: Sequence[str]) -> str:
    joined = ",".join(tickers)
    return f"realtime:{country}:{joined}"


def _is_cache_alive(cache_entry: dict[str, Any] | None, now: datetime) -> bool:
    if not cache_entry:
        return False
    expires_at = cache_entry.get("expires_at")
    if not isinstance(expires_at, datetime):
        return False
    return now < expires_at


def _filter_snapshot_data(
    data: dict[str, dict[str, float]],
    tickers: Sequence[str],
) -> dict[str, dict[str, float]]:
    ticker_set = set(tickers)
    return {ticker: value for ticker, value in data.items() if ticker in ticker_set}


def _fetch_realtime_snapshot(country: str, tickers: Sequence[str]) -> tuple[dict[str, dict[str, float]], str]:
    if country == "kor":
        etf_snapshot = fetch_naver_etf_inav_snapshot(tickers)
        missing_tickers = [ticker for ticker in tickers if ticker not in etf_snapshot]
        if not missing_tickers:
            return etf_snapshot, "naver_etf"

        stock_snapshot = fetch_naver_stock_realtime_snapshot(missing_tickers)
        merged_snapshot = dict(etf_snapshot)
        merged_snapshot.update(stock_snapshot)
        return merged_snapshot, "mixed"

    if country == "au":
        return fetch_au_quoteapi_snapshot(tickers), "au_quoteapi"

    raise ValueError(f"지원하지 않는 country_code입니다: {country}")


def _reuse_stale_cache(
    cache_key: str,
    tickers: Sequence[str],
    exc: Exception,
) -> dict[str, dict[str, float]] | None:
    cached_entry = _PRICE_SERVICE_CACHE.get(cache_key)
    if not cached_entry or "data" not in cached_entry:
        return None

    cached_entry["is_stale"] = True
    logger.warning("실시간 가격 조회 실패로 stale 캐시를 재사용합니다. key=%s error=%s", cache_key, exc)
    return _filter_snapshot_data(cached_entry["data"], tickers)


def _reuse_stale_exchange_rates(cache_key: str, exc: Exception) -> dict[str, Any] | None:
    cached_entry = _PRICE_SERVICE_CACHE.get(cache_key)
    if not cached_entry or "data" not in cached_entry:
        return None

    cached_entry["is_stale"] = True
    logger.warning("환율 조회 실패로 stale 캐시를 재사용합니다. key=%s error=%s", cache_key, exc)
    return dict(cached_entry["data"])


def _store_cache_entry(
    *,
    cache_key: str,
    data: dict[str, Any],
    source: str,
    ttl_seconds: int,
    is_stale: bool,
) -> None:
    fetched_at = datetime.now()
    _PRICE_SERVICE_CACHE[cache_key] = {
        "data": dict(data),
        "fetched_at": fetched_at,
        "expires_at": fetched_at + timedelta(seconds=ttl_seconds),
        "is_stale": is_stale,
        "source": source,
    }


def _get_realtime_ttl_seconds(country: str) -> int:
    if _is_market_active(country):
        if country == "kor":
            return _KOR_ACTIVE_TTL_SECONDS
        if country == "au":
            return _AU_ACTIVE_TTL_SECONDS
    return _IDLE_TTL_SECONDS


def _is_market_active(country: str) -> bool:
    schedule = MARKET_SCHEDULES.get(country)
    if not schedule:
        raise ValueError(f"시장 스케줄이 없습니다: {country}")

    timezone_name = str(schedule.get("timezone") or "").strip()
    if not timezone_name:
        raise ValueError(f"시장 타임존이 없습니다: {country}")

    now_local = datetime.now(ZoneInfo(timezone_name))
    latest_trading_day = get_latest_trading_day(country).normalize()
    if latest_trading_day.date() != now_local.date():
        return False

    open_time = schedule.get("open")
    close_time = schedule.get("close")
    open_offset_minutes = int(schedule.get("open_offset_minutes") or 0)
    close_offset_minutes = int(schedule.get("close_offset_minutes") or 0)
    if open_time is None or close_time is None:
        raise ValueError(f"시장 시간이 없습니다: {country}")

    market_open_dt = datetime.combine(now_local.date(), open_time, tzinfo=now_local.tzinfo) - timedelta(
        minutes=open_offset_minutes
    )
    market_close_dt = datetime.combine(now_local.date(), close_time, tzinfo=now_local.tzinfo) + timedelta(
        minutes=close_offset_minutes
    )
    return market_open_dt <= now_local <= market_close_dt


def _fetch_exchange_rates() -> dict[str, Any]:
    import yfinance as yf

    mapping = {
        "USD": "KRW=X",
        "AUD": "AUDKRW=X",
    }
    rates: dict[str, Any] = {}
    missing_currencies: list[str] = []

    for currency, symbol in mapping.items():
        try:
            ticker = yf.Ticker(symbol)
            current_rate = float(ticker.fast_info.last_price)
            previous_close = float(ticker.fast_info.previous_close)
        except Exception as exc:
            logger.warning("%s 환율 조회 실패: %s", currency, exc)
            missing_currencies.append(currency)
            continue

        change_pct = 0.0
        if previous_close > 0:
            change_pct = ((current_rate - previous_close) / previous_close) * 100.0

        rates[currency] = {
            "rate": current_rate,
            "change_pct": change_pct,
        }

    if missing_currencies:
        joined = ", ".join(missing_currencies)
        raise RuntimeError(f"환율 데이터를 조회하지 못했습니다: {joined}")

    rates["updated_at"] = datetime.now()
    return rates


__all__ = [
    "clear_price_service_cache",
    "get_exchange_rate_series",
    "get_exchange_rates",
    "get_realtime_cache_meta",
    "get_realtime_snapshot",
]
