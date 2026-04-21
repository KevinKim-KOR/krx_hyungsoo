from __future__ import annotations

import re
from datetime import datetime
from time import perf_counter
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from config import (
    BUCKET_MAPPING,
    CACHE_START_DATE,
    MARKET_SCHEDULES,
    MIN_TRADING_DAYS,
    TRADING_DAYS_PER_MONTH,
)
from core.strategy.metrics import process_ticker_data
from services.price_service import get_realtime_snapshot, get_realtime_snapshot_meta
from utils.cache_utils import (
    load_cached_close_series_bulk_with_fallback,
    load_cached_updated_at_bulk_with_fallback,
)
from utils.data_loader import get_latest_trading_day, get_trading_days
from utils.logger import get_app_logger
from utils.settings_loader import AccountSettingsError, get_ticker_type_settings
from utils.stock_list_io import get_etfs

ALLOWED_MA_TYPES = ["SMA", "EMA", "WMA", "DEMA", "TEMA", "HMA", "ALMA"]
logger = get_app_logger()
MONTHLY_RETURN_LABEL_COUNT = 13


def _build_ma_rule_score_column(order: int) -> str:
    return f"추세{order}"


def _normalize_ma_rules(ticker_type: str, ma_rules_raw: Any) -> list[dict[str, Any]]:
    if not isinstance(ma_rules_raw, list) or not ma_rules_raw:
        raise AccountSettingsError(f"'{ticker_type}' 설정의 MA_RULES는 1개 이상의 배열이어야 합니다.")
    normalized_rules: list[dict[str, Any]] = []
    seen_orders: set[int] = set()

    for index, raw_rule in enumerate(ma_rules_raw, start=1):
        if not isinstance(raw_rule, dict):
            raise AccountSettingsError(f"'{ticker_type}' 설정의 MA_RULES[{index}]는 객체여야 합니다.")

        order_raw = raw_rule.get("order")
        if order_raw is None:
            raise AccountSettingsError(
                f"'{ticker_type}' 설정의 MA_RULES[{index}]에 필수 항목 'order'가 누락되었습니다."
            )
        try:
            order = int(order_raw)
        except (TypeError, ValueError) as exc:
            raise AccountSettingsError(
                f"'{ticker_type}' 설정의 MA_RULES[{index}] order는 정수여야 합니다: {order_raw}"
            ) from exc
        if order < 1:
            raise AccountSettingsError(f"'{ticker_type}' 설정의 MA_RULES[{index}] order는 1 이상이어야 합니다: {order}")
        if order in seen_orders:
            raise AccountSettingsError(f"'{ticker_type}' 설정의 MA_RULES order가 중복되었습니다: {order}")
        seen_orders.add(order)

        ma_type = str(raw_rule.get("MA_TYPE") or "").strip().upper()
        if not ma_type:
            raise AccountSettingsError(
                f"'{ticker_type}' 설정의 MA_RULES[{index}]에 필수 항목 'MA_TYPE'가 누락되었습니다."
            )
        if ma_type not in ALLOWED_MA_TYPES:
            raise AccountSettingsError(
                f"'{ticker_type}' 설정의 MA_RULES[{index}] MA_TYPE이 유효하지 않습니다: {ma_type}"
            )

        ma_months_raw = raw_rule.get("MA_MONTHS")
        if ma_months_raw is None:
            raise AccountSettingsError(
                f"'{ticker_type}' 설정의 MA_RULES[{index}]에 필수 항목 'MA_MONTHS'가 누락되었습니다."
            )
        try:
            ma_months = int(ma_months_raw)
        except (TypeError, ValueError) as exc:
            raise AccountSettingsError(
                f"'{ticker_type}' 설정의 MA_RULES[{index}] MA_MONTHS는 정수여야 합니다: {ma_months_raw}"
            ) from exc
        if ma_months < 1:
            raise AccountSettingsError(
                f"'{ticker_type}' 설정의 MA_RULES[{index}] MA_MONTHS는 1 이상이어야 합니다: {ma_months}"
            )

        normalized_rules.append(
            {
                "order": order,
                "ma_type": ma_type,
                "ma_months": ma_months,
                "ma_days": int(ma_months) * int(TRADING_DAYS_PER_MONTH),
                "score_column": _build_ma_rule_score_column(order),
            }
        )

    return sorted(normalized_rules, key=lambda item: int(item["order"]))


def get_ticker_type_ma_rules(ticker_type: str) -> list[dict[str, Any]]:
    settings = get_ticker_type_settings(ticker_type)
    ma_rules_raw = settings.get("MA_RULES")
    if ma_rules_raw is None:
        raise AccountSettingsError(f"'{ticker_type}' 설정에 필수 항목 'MA_RULES'가 누락되었습니다.")
    return _normalize_ma_rules(ticker_type, ma_rules_raw)


def build_effective_ma_rules(
    ticker_type: str,
    overrides: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    base_rules = get_ticker_type_ma_rules(ticker_type)
    if not overrides:
        return base_rules

    override_map = {int(rule["order"]): rule for rule in overrides if rule.get("order") is not None}
    raw_rules: list[dict[str, Any]] = []
    for rule in base_rules:
        order = int(rule["order"])
        override = override_map.get(order) or {}
        raw_rules.append(
            {
                "order": order,
                "MA_TYPE": override.get("ma_type", rule["ma_type"]),
                "MA_MONTHS": override.get("ma_months", rule["ma_months"]),
            }
        )
    return _normalize_ma_rules(ticker_type, raw_rules)


def _calculate_rsi(close_series: pd.Series, period: int = 14) -> float | None:
    series = pd.to_numeric(close_series, errors="coerce").dropna()
    if len(series) < period + 1:
        return None

    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    if avg_loss.empty or pd.isna(avg_loss.iloc[-1]):
        return None
    if float(avg_loss.iloc[-1]) == 0.0:
        return 100.0
    rs = float(avg_gain.iloc[-1]) / float(avg_loss.iloc[-1])
    return 100.0 - (100.0 / (1.0 + rs))


def _get_market_timezone(country_code: str) -> ZoneInfo:
    schedule = MARKET_SCHEDULES.get(str(country_code or "").strip().lower())
    timezone_name = str((schedule or {}).get("timezone") or "").strip()
    if not timezone_name:
        return ZoneInfo("Asia/Seoul")
    return ZoneInfo(timezone_name)


def _normalize_market_timestamp(
    value: datetime | pd.Timestamp | None,
    country_code: str,
    *,
    assume_utc: bool,
) -> pd.Timestamp | None:
    if value is None:
        return None

    ts = pd.Timestamp(value)
    if pd.isna(ts):
        return None

    market_tz = _get_market_timezone(country_code)
    if ts.tzinfo is None:
        if assume_utc:
            ts = ts.tz_localize("UTC")
        else:
            ts = ts.tz_localize(market_tz)

    return ts.tz_convert(market_tz).tz_localize(None)


def _build_blocked_rankings_result(
    *,
    latest_trading_day: pd.Timestamp,
    cache_updated_at: pd.Timestamp | None,
    missing_tickers: list[str],
    stale_tickers: list[str],
) -> pd.DataFrame:
    blocked = pd.DataFrame()
    blocked.attrs["cache_blocked"] = True
    blocked.attrs["latest_trading_day"] = latest_trading_day
    blocked.attrs["cache_updated_at"] = cache_updated_at
    blocked.attrs["missing_tickers"] = missing_tickers
    blocked.attrs["stale_tickers"] = stale_tickers
    return blocked


def _get_latest_trading_day_for_reference(country_code: str, reference_date: pd.Timestamp) -> pd.Timestamp:
    reference = pd.Timestamp(reference_date).normalize()
    today_korea = pd.Timestamp.now(tz="Asia/Seoul").tz_localize(None).normalize()
    if reference >= today_korea:
        return get_latest_trading_day(country_code).normalize()

    start_date = (reference - pd.DateOffset(days=10)).strftime("%Y-%m-%d")
    end_date = reference.strftime("%Y-%m-%d")
    trading_days = get_trading_days(start_date, end_date, country_code)
    if trading_days:
        return max(trading_days).normalize()
    return reference


def _slice_close_series_to_date(close_series: pd.Series | None, cutoff_date: pd.Timestamp) -> pd.Series | None:
    if close_series is None or close_series.empty:
        return close_series

    normalized = close_series.copy()
    normalized.index = pd.to_datetime(normalized.index)
    sliced = normalized.loc[normalized.index.normalize() <= pd.Timestamp(cutoff_date).normalize()]
    if sliced.empty:
        return None
    return sliced.sort_index()


def get_rank_months_max() -> int:
    cache_start = pd.to_datetime(CACHE_START_DATE).normalize()
    today = pd.Timestamp.now(tz="Asia/Seoul").tz_localize(None).normalize()
    month_span = ((today.year - cache_start.year) * 12) + (today.month - cache_start.month) + 1
    return max(1, int(month_span))


def _calc_period_return(close_series: pd.Series, days: int) -> float | None:
    series = pd.to_numeric(close_series, errors="coerce").dropna()
    if series.empty:
        return None

    current = float(series.iloc[-1])
    if current <= 0:
        return None

    if len(series) > days:
        previous = float(series.iloc[-(days + 1)])
        if previous > 0:
            return (current / previous - 1.0) * 100.0

    if days == 252 and len(series) >= 240:
        previous = float(series.iloc[0])
        if previous > 0:
            return (current / previous - 1.0) * 100.0

    return None


def get_recent_monthly_return_labels(
    count: int = MONTHLY_RETURN_LABEL_COUNT,
    reference_date: pd.Timestamp | None = None,
) -> list[str]:
    base_month = (reference_date or pd.Timestamp.now(tz="Asia/Seoul").tz_localize(None)).to_period("M")
    return [f"{(base_month - offset).strftime('%Y-%m')}(%)" for offset in range(count)]


def build_recent_monthly_return_metrics(
    close_series: pd.Series | None,
    *,
    reference_date: pd.Timestamp | None = None,
    labels: list[str] | None = None,
) -> dict[str, float | None]:
    return _build_monthly_return_metrics(
        close_series,
        reference_date=reference_date,
        labels=labels,
    )


def _build_monthly_return_metrics(
    close_series: pd.Series | None,
    *,
    reference_date: pd.Timestamp | None = None,
    labels: list[str] | None = None,
) -> dict[str, float | None]:
    labels = labels or get_recent_monthly_return_labels(reference_date=reference_date)
    empty_metrics = {label: None for label in labels}
    if close_series is None:
        return empty_metrics

    series = pd.to_numeric(close_series, errors="coerce").dropna()
    if series.empty:
        return empty_metrics

    normalized = series.copy()
    normalized.index = pd.to_datetime(normalized.index)
    normalized = normalized.sort_index()
    month_end_series = normalized.groupby(normalized.index.to_period("M")).last()
    current_month = (reference_date or pd.Timestamp.now(tz="Asia/Seoul").tz_localize(None)).to_period("M")
    metrics: dict[str, float | None] = {}

    for label in labels:
        match = re.fullmatch(r"(\d{4}-\d{2})\(%\)", label)
        if not match:
            metrics[label] = None
            continue

        month_period = pd.Period(match.group(1), freq="M")
        prev_month_close = month_end_series.get(month_period - 1)
        if prev_month_close is None or pd.isna(prev_month_close):
            metrics[label] = None
            continue

        target_close = normalized.iloc[-1] if month_period == current_month else month_end_series.get(month_period)
        if target_close is None or pd.isna(target_close):
            metrics[label] = None
            continue

        prev_value = float(prev_month_close)
        target_value = float(target_close)
        metrics[label] = None if prev_value <= 0 else ((target_value / prev_value) - 1.0) * 100.0

    return metrics


def _extract_price_metrics_from_close_series(
    close_series: pd.Series | None,
    *,
    reference_date: pd.Timestamp | None = None,
    monthly_labels: list[str] | None = None,
) -> dict[str, Any]:
    monthly_return_metrics = _build_monthly_return_metrics(
        close_series,
        reference_date=reference_date,
        labels=monthly_labels,
    )
    empty_result = {
        "현재가": None,
        "괴리율": None,
        "일간(%)": None,
        "1주(%)": None,
        "2주(%)": None,
        "3주(%)": None,
        "4주(%)": None,
        "1달(%)": None,
        "2달(%)": None,
        "3달(%)": None,
        "4달(%)": None,
        "5달(%)": None,
        "6달(%)": None,
        "7달(%)": None,
        "8달(%)": None,
        "9달(%)": None,
        "10달(%)": None,
        "11달(%)": None,
        "12달(%)": None,
        "고점": None,
        "추세(3달)": [],
        "RSI": None,
        **monthly_return_metrics,
    }
    if close_series is None:
        return empty_result

    series = pd.to_numeric(close_series, errors="coerce").dropna()
    if series.empty:
        return empty_result

    current_price = float(series.iloc[-1])
    daily_pct = None
    if len(series) > 1:
        prev_close = float(series.iloc[-2])
        if prev_close > 0:
            daily_pct = ((current_price / prev_close) - 1.0) * 100.0

    max_price = float(series.max()) if not series.empty else 0.0
    drawdown = None
    if max_price > 0:
        drawdown = (current_price / max_price - 1.0) * 100.0

    return {
        "현재가": current_price,
        "일간(%)": daily_pct,
        "1주(%)": _calc_period_return(series, 5),
        "2주(%)": _calc_period_return(series, 10),
        "3주(%)": _calc_period_return(series, 15),
        "4주(%)": _calc_period_return(series, 20),
        "1달(%)": _calc_period_return(series, 20),
        "2달(%)": _calc_period_return(series, 40),
        "3달(%)": _calc_period_return(series, 60),
        "4달(%)": _calc_period_return(series, 80),
        "5달(%)": _calc_period_return(series, 100),
        "6달(%)": _calc_period_return(series, 126),
        "7달(%)": _calc_period_return(series, 147),
        "8달(%)": _calc_period_return(series, 168),
        "9달(%)": _calc_period_return(series, 189),
        "10달(%)": _calc_period_return(series, 210),
        "11달(%)": _calc_period_return(series, 231),
        "12달(%)": _calc_period_return(series, 252),
        "고점": drawdown,
        "추세(3달)": series.iloc[-60:].astype(float).tolist(),
        "RSI": _calculate_rsi(series),
        **monthly_return_metrics,
    }


def _load_realtime_snapshot(country_code: str, tickers: list[str]) -> dict[str, dict[str, float]]:
    """국가별 실시간 현재가/등락률 스냅샷을 로드합니다."""
    if not tickers:
        return {}

    try:
        return get_realtime_snapshot(country_code, tickers)
    except Exception as exc:
        logger.warning("순위용 실시간 스냅샷 조회 실패: %s", exc)
        return {}


def _apply_realtime_overlay(
    price_metrics: dict[str, Any],
    realtime_entry: dict[str, float] | None,
) -> dict[str, Any]:
    """실시간 현재가/일간 등락률이 있으면 캐시 값을 덮어씁니다."""
    if not isinstance(realtime_entry, dict) or not realtime_entry:
        return price_metrics

    updated = dict(price_metrics)

    now_val = realtime_entry.get("nowVal")
    if now_val is not None:
        try:
            updated["현재가"] = float(now_val)
        except (TypeError, ValueError):
            pass

    change_rate = realtime_entry.get("changeRate")
    if change_rate is not None:
        try:
            updated["일간(%)"] = float(change_rate)
        except (TypeError, ValueError):
            pass

    deviation = realtime_entry.get("deviation")
    if deviation is not None:
        try:
            updated["괴리율"] = float(deviation)
        except (TypeError, ValueError):
            pass

    return updated


def _build_effective_close_series(
    cached_close_series: pd.Series | None,
    realtime_entry: dict[str, float] | None,
) -> pd.Series | None:
    """실시간 가격을 반영한 종가 시리즈를 생성합니다."""
    if cached_close_series is None or cached_close_series.empty:
        return None
    if not isinstance(realtime_entry, dict) or not realtime_entry:
        return cached_close_series

    now_val = realtime_entry.get("nowVal")
    if now_val is None:
        return cached_close_series

    try:
        realtime_price = float(now_val)
    except (TypeError, ValueError):
        return cached_close_series

    adjusted = cached_close_series.copy()
    today = pd.Timestamp.now(tz="Asia/Seoul").tz_localize(None).normalize()
    last_index = pd.Timestamp(adjusted.index[-1])
    if last_index.tzinfo is not None:
        last_index = last_index.tz_localize(None)
    last_index = last_index.normalize()

    if last_index < today:
        adjusted.loc[today] = realtime_price
    else:
        adjusted.iloc[-1] = realtime_price
    return adjusted.sort_index()


def _normalize_ranking_values(
    df: pd.DataFrame,
    country_code: str,
    *,
    monthly_labels: list[str] | None = None,
) -> pd.DataFrame:
    normalized = df.copy()

    price_digits = 2 if str(country_code or "").strip().lower() == "au" else 0
    percent_columns = [
        "괴리율",
        "일간(%)",
        "1주(%)",
        "2주(%)",
        "3주(%)",
        "4주(%)",
        "1달(%)",
        "2달(%)",
        "3달(%)",
        "4달(%)",
        "5달(%)",
        "6달(%)",
        "7달(%)",
        "8달(%)",
        "9달(%)",
        "10달(%)",
        "11달(%)",
        "12달(%)",
        "고점",
        *(monthly_labels or []),
    ]
    one_decimal_columns = ["RSI"]
    score_columns = ["점수"]
    score_columns.extend(
        str(column) for column in normalized.columns if str(column).startswith("추세(") and str(column).endswith(")")
    )

    def _round_if_present(column: str, digits: int) -> None:
        if column not in normalized.columns:
            return
        series = pd.to_numeric(normalized[column], errors="coerce")
        normalized[column] = series.round(digits)

    _round_if_present("현재가", price_digits)
    for column in percent_columns:
        _round_if_present(column, 2)

    for column in one_decimal_columns:
        _round_if_present(column, 1)

    for column in score_columns:
        _round_if_present(column, 1)

    return normalized


def _calculate_signed_percentile_score(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    result = pd.Series(index=series.index, dtype=float)

    positive_mask = numeric > 0
    negative_mask = numeric < 0
    zero_mask = numeric == 0

    if positive_mask.any():
        positive_values = numeric[positive_mask]
        result.loc[positive_mask] = positive_values.rank(method="average", pct=True) * 100.0

    if negative_mask.any():
        negative_values = numeric[negative_mask].abs()
        result.loc[negative_mask] = -(negative_values.rank(method="average", pct=True) * 100.0)

    if zero_mask.any():
        result.loc[zero_mask] = 0.0

    return result


def _build_composite_score(df: pd.DataFrame, ma_rules: list[dict[str, Any]]) -> pd.Series:
    score_columns = [str(rule["score_column"]) for rule in ma_rules]
    if not score_columns:
        return pd.Series(index=df.index, dtype=float)

    normalized_parts = []
    valid_mask = pd.Series(True, index=df.index, dtype=bool)
    for column in score_columns:
        part = _calculate_signed_percentile_score(df[column])
        normalized_parts.append(part)
        valid_mask &= part.notna()

    composite = pd.concat(normalized_parts, axis=1).sum(axis=1, min_count=len(score_columns))
    composite.loc[~valid_mask] = pd.NA
    return composite


def build_ticker_type_rankings(
    ticker_type: str,
    *,
    ma_rules: list[dict[str, Any]] | None = None,
    as_of_date: pd.Timestamp | None = None,
    realtime_snapshot_override: dict[str, dict[str, float]] | None = None,
    status_callback: Any | None = None,
) -> pd.DataFrame:
    if callable(status_callback):
        status_callback("최신 거래일 기준 캐시 상태 확인")
    started_at = perf_counter()
    settings = get_ticker_type_settings(ticker_type)
    country_code = str(settings.get("country_code") or "").strip().lower()

    etfs = get_etfs(ticker_type)
    if not etfs:
        return pd.DataFrame()

    fetch_started_at = perf_counter()
    tickers = [str(item.get("ticker") or "").strip().upper() for item in etfs if str(item.get("ticker") or "").strip()]
    selected_as_of_date = (as_of_date or pd.Timestamp.now(tz="Asia/Seoul").tz_localize(None)).normalize()
    cache_updated_map_raw = load_cached_updated_at_bulk_with_fallback(ticker_type, tickers)
    latest_trading_day = _get_latest_trading_day_for_reference(country_code, selected_as_of_date)
    monthly_labels = get_recent_monthly_return_labels(reference_date=selected_as_of_date)
    missing_tickers = sorted({ticker for ticker in tickers if ticker not in cache_updated_map_raw})
    normalized_cache_updated = {
        ticker: normalized
        for ticker, updated_at in cache_updated_map_raw.items()
        if (normalized := _normalize_market_timestamp(updated_at, country_code, assume_utc=True)) is not None
    }
    stale_tickers = sorted(
        ticker for ticker, updated_at in normalized_cache_updated.items() if updated_at.normalize() < latest_trading_day
    )
    latest_cache_updated_at = max(normalized_cache_updated.values()) if normalized_cache_updated else None

    if missing_tickers or stale_tickers:
        fetch_elapsed = perf_counter() - fetch_started_at
        total_elapsed = perf_counter() - started_at
        logger.warning(
            "[rankings] type=%s blocked latest_trading_day=%s missing=%d stale=%d total=%.3fs fetch=%.3fs",
            ticker_type,
            latest_trading_day.date(),
            len(missing_tickers),
            len(stale_tickers),
            total_elapsed,
            fetch_elapsed,
        )
        return _build_blocked_rankings_result(
            latest_trading_day=latest_trading_day,
            cache_updated_at=latest_cache_updated_at,
            missing_tickers=missing_tickers,
            stale_tickers=stale_tickers,
        )

    if callable(status_callback):
        status_callback("기준 종가 캐시 로드")
    cached_close_series_map = load_cached_close_series_bulk_with_fallback(ticker_type, tickers)
    if callable(status_callback):
        status_callback("실시간 가격 조회")
    today_korea = pd.Timestamp.now(tz="Asia/Seoul").tz_localize(None).normalize()
    realtime_allowed = selected_as_of_date == today_korea
    realtime_snapshot = (
        realtime_snapshot_override
        if realtime_snapshot_override is not None
        else _load_realtime_snapshot(country_code, tickers)
        if realtime_allowed
        else {}
    )
    fetch_elapsed = perf_counter() - fetch_started_at
    realtime_meta = None
    if realtime_allowed and realtime_snapshot_override is None:
        realtime_meta = get_realtime_snapshot_meta(country_code, tickers)

    effective_ma_rules = ma_rules or get_ticker_type_ma_rules(ticker_type)
    rows: list[dict[str, Any]] = []
    effective_close_series_map: dict[str, pd.Series] = {}
    preprocess_elapsed = 0.0
    metric_elapsed = 0.0
    process_elapsed = 0.0

    from utils.portfolio_io import load_all_holding_tickers

    held_tickers = load_all_holding_tickers()

    if callable(status_callback):
        status_callback("순위 계산")

    for etf in etfs:
        ticker = str(etf.get("ticker") or "").strip().upper()
        if not ticker:
            continue

        cached_close_series = cached_close_series_map.get(ticker)
        realtime_entry = realtime_snapshot.get(ticker)
        preprocess_started_at = perf_counter()
        base_close_series = _slice_close_series_to_date(cached_close_series, latest_trading_day)
        effective_close_series = _build_effective_close_series(base_close_series, realtime_entry)
        if effective_close_series is not None and not effective_close_series.empty:
            effective_close_series_map[ticker] = effective_close_series
        preprocess_elapsed += perf_counter() - preprocess_started_at

        metric_started_at = perf_counter()
        price_metrics = _extract_price_metrics_from_close_series(
            effective_close_series,
            reference_date=selected_as_of_date,
            monthly_labels=monthly_labels,
        )
        price_metrics = _apply_realtime_overlay(price_metrics, realtime_entry)
        metric_elapsed += perf_counter() - metric_started_at

        ma_rule_scores = {str(rule["score_column"]): None for rule in effective_ma_rules}

        if effective_close_series is not None and not effective_close_series.empty:
            process_started_at = perf_counter()
            for rule in effective_ma_rules:
                processed = process_ticker_data(
                    ticker,
                    None,
                    ma_days=int(rule["ma_days"]),
                    precomputed_entry={"close": effective_close_series, "open": effective_close_series},
                    ma_type=str(rule["ma_type"]),
                    enable_data_sufficiency_check=False,
                )
                if processed is None:
                    break

                score_series = processed.get("ma_score")
                if not isinstance(score_series, pd.Series) or score_series.empty:
                    break

                score_raw = score_series.iloc[-1]
                if pd.isna(score_raw):
                    break

                rule_score = float(score_raw)
                ma_rule_scores[str(rule["score_column"])] = rule_score

            process_elapsed += perf_counter() - process_started_at
        elif effective_close_series is not None and len(effective_close_series.index) >= MIN_TRADING_DAYS:
            pass

        rows.append(
            {
                "버킷": BUCKET_MAPPING.get(int(etf.get("bucket") or 0), str(etf.get("bucket") or "")),
                "bucket": int(etf.get("bucket") or 0),
                "티커": ticker,
                "종목명": etf.get("name", ""),
                "상장일": etf.get("listing_date", "-"),
                "점수": None,
                "보유": "보유" if ticker in held_tickers else "",
                **ma_rule_scores,
                **price_metrics,
                "거래량": float(etf.get("volume", 0)) if etf.get("volume") is not None else None,
            }
        )

    dataframe_started_at = perf_counter()
    df = pd.DataFrame(rows)
    if df.empty:
        return df

    df["점수"] = _build_composite_score(df, effective_ma_rules)

    realtime_active = bool(realtime_snapshot)
    ranking_computed_at = datetime.now()

    def _to_sortable_score(value: Any) -> float:
        if value is None or pd.isna(value):
            return float("-inf")
        return float(value)

    def _sort_key(row: pd.Series) -> tuple[int, float, str]:
        trend = row.get("점수")
        return (
            1 if trend is None or pd.isna(trend) else 0,
            _to_sortable_score(trend),
            str(row.get("티커", "")),
        )

    sort_values = df.apply(_sort_key, axis=1, result_type="expand")
    sort_values.columns = [
        "_missing_trend",
        "_trend_value",
        "_ticker_sort",
    ]
    df = pd.concat([df, sort_values], axis=1)
    df = df.sort_values(
        by=[
            "_missing_trend",
            "_trend_value",
            "_ticker_sort",
        ],
        ascending=[True, False, True],
        kind="stable",
    ).reset_index(drop=True)

    df = df.drop(
        columns=[
            "_missing_trend",
            "_trend_value",
            "_ticker_sort",
        ]
    )
    df = _normalize_ranking_values(df, country_code, monthly_labels=monthly_labels)
    df.attrs["realtime_active"] = realtime_active
    df.attrs["ranking_computed_at"] = ranking_computed_at
    if realtime_meta:
        df.attrs["realtime_fetched_at"] = realtime_meta.get("fetched_at")
        df.attrs["realtime_expires_at"] = realtime_meta.get("expires_at")
        df.attrs["realtime_is_stale"] = bool(realtime_meta.get("is_stale", False))
        df.attrs["realtime_source"] = realtime_meta.get("source")
    if latest_cache_updated_at is not None:
        df.attrs["cache_updated_at"] = latest_cache_updated_at
    df.attrs["latest_trading_day"] = latest_trading_day
    df.attrs["as_of_date"] = selected_as_of_date
    df.attrs["ma_rules"] = effective_ma_rules
    dataframe_elapsed = perf_counter() - dataframe_started_at
    total_elapsed = perf_counter() - started_at
    logger.info(
        "[rankings] type=%s tickers=%d total=%.3fs fetch=%.3fs preprocess=%.3fs metrics=%.3fs process=%.3fs dataframe=%.3fs",
        ticker_type,
        len(tickers),
        total_elapsed,
        fetch_elapsed,
        preprocess_elapsed,
        metric_elapsed,
        process_elapsed,
        dataframe_elapsed,
    )
    return df


__all__ = [
    "ALLOWED_MA_TYPES",
    "build_recent_monthly_return_metrics",
    "build_effective_ma_rules",
    "build_ticker_type_rankings",
    "get_rank_months_max",
    "get_recent_monthly_return_labels",
    "get_ticker_type_ma_rules",
]
