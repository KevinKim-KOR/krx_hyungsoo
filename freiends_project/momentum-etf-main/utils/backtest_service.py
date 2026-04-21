from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

import pandas as pd

from utils.account_registry import load_account_configs
from utils.cache_utils import list_available_cache_keys, load_cached_close_series_bulk_with_fallback
from utils.data_loader import get_latest_trading_day, get_trading_days
from utils.db_manager import get_db_connection
from utils.stocks_service import validate_stock_candidate

def _get_weekly_rebalance_dates(
    evaluation_days: list[pd.Timestamp],
    country_code: str = "kor",
) -> set[pd.Timestamp]:
    rebalance_dates: set[pd.Timestamp] = set()
    if not evaluation_days:
        return rebalance_dates

    current_week: int | None = None
    last_day_of_week: pd.Timestamp | None = None

    for day in evaluation_days:
        week_key = day.isocalendar()[1]
        year_key = day.isocalendar()[0]
        combined = year_key * 100 + week_key

        if combined != current_week:
            if last_day_of_week is not None:
                rebalance_dates.add(last_day_of_week)
            current_week = combined

        last_day_of_week = day

    if last_day_of_week is not None:
        rebalance_dates.add(last_day_of_week)

    return rebalance_dates


def _get_monthly_rebalance_dates(
    evaluation_days: list[pd.Timestamp],
) -> set[pd.Timestamp]:
    rebalance_dates: set[pd.Timestamp] = set()
    if not evaluation_days:
        return rebalance_dates

    current_month: str | None = None
    last_day_of_month: pd.Timestamp | None = None

    for day in evaluation_days:
        month_key = f"{day.year}-{day.month}"
        if month_key != current_month:
            if last_day_of_month is not None:
                rebalance_dates.add(last_day_of_month)
            current_month = month_key
        last_day_of_month = day

    if last_day_of_month is not None:
        rebalance_dates.add(last_day_of_month)

    return rebalance_dates


def _get_ticker_type_for_country(country_code: str) -> str:
    """국가 코드를 백테스트용 기본 종목풀로 변환합니다."""
    cc = str(country_code or "").strip().lower()
    if cc == "au":
        return "aus"
    # 한국의 경우 기본적으로 kor_kr 타입을 사용
    return "kor_kr"


def _get_collection():
    db = get_db_connection()
    if db is None:
        raise RuntimeError("MongoDB 연결에 실패했습니다.")
    return db.backtest_configs


def validate_backtest_ticker(ticker: str, country_code: str = "kor") -> dict[str, Any]:
    ticker_type = _get_ticker_type_for_country(country_code)
    validated = validate_stock_candidate(ticker_type, ticker)
    return {
        "ticker": str(validated["ticker"]),
        "name": str(validated["name"]),
        "listing_date": str(validated["listing_date"]),
        "status": str(validated["status"]),
        "is_deleted": bool(validated["is_deleted"]),
        "deleted_reason": str(validated["deleted_reason"]),
    }


def _normalize_ticker_items(items: list[dict[str, Any]]) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in items:
        ticker = str(item.get("ticker") or "").strip().upper()
        if not ticker:
            continue
        if ticker in seen:
            continue
        seen.add(ticker)
        normalized.append(
            {
                "ticker": ticker,
                "name": str(item.get("name") or "").strip(),
                "listing_date": str(item.get("listing_date") or "").strip(),
            }
        )
    return normalized


def _normalize_optional_ticker(item: dict[str, Any] | None) -> dict[str, str] | None:
    if not item:
        return None
    ticker = str(item.get("ticker") or "").strip().upper()
    if not ticker:
        return None
    return {
        "ticker": ticker,
        "name": str(item.get("name") or "").strip(),
        "listing_date": str(item.get("listing_date") or "").strip(),
    }


def _normalize_groups(groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized_groups: list[dict[str, Any]] = []
    for index, group in enumerate(groups, start=1):
        name = str(group.get("name") or "").strip() or f"그룹{index}"
        weight = int(group.get("weight") or 0)
        tickers = _normalize_ticker_items(list(group.get("tickers") or []))
        normalized_groups.append(
            {
                "group_id": str(group.get("group_id") or f"group-{index}"),
                "name": name,
                "weight": weight,
                "tickers": tickers,
            }
        )
    return normalized_groups


def _normalize_slippage_pct(slippage_pct: float | int | str | None) -> float:
    try:
        value = round(float(slippage_pct), 1)
    except (TypeError, ValueError) as exc:
        raise ValueError("슬리피지는 숫자로 입력하세요.") from exc
    if value < 0 or value > 100:
        raise ValueError("슬리피지는 0% 이상 100% 이하로 입력하세요.")
    return value


def _build_config_signature(
    name: str,
    period_months: int,
    slippage_pct: float,
    benchmark: dict[str, Any] | None,
    groups: list[dict[str, Any]],
    rebalance_freq: str = "monthly",
) -> dict[str, Any]:
    return {
        "name": name,
        "period_months": period_months,
        "slippage_pct": slippage_pct,
        "benchmark": _normalize_optional_ticker(benchmark),
        "rebalance_freq": str(rebalance_freq or "monthly").strip().lower(),
        "groups": [
            {
                "name": str(group.get("name") or "").strip(),
                "weight": int(group.get("weight") or 0),
                "tickers": [
                    {
                        "ticker": str(item.get("ticker") or "").strip().upper(),
                        "name": str(item.get("name") or "").strip(),
                        "listing_date": str(item.get("listing_date") or "").strip(),
                    }
                    for item in list(group.get("tickers") or [])
                ],
            }
            for group in groups
        ],
    }


def save_backtest_config(
    name: str,
    period_months: int,
    slippage_pct: float,
    benchmark: dict[str, Any] | None,
    groups: list[dict[str, Any]],
    rebalance_freq: str = "monthly",
) -> dict[str, Any]:
    title = str(name or "").strip()
    if not title:
        raise ValueError("백테스트 제목을 입력하세요.")

    period_value = int(period_months or 0)
    if period_value < 1 or period_value > 24:
        raise ValueError("기간은 최근 1달에서 24달 사이여야 합니다.")
    slippage_value = _normalize_slippage_pct(slippage_pct)

    normalized_groups = _normalize_groups(groups)
    if not normalized_groups:
        raise ValueError("최소 1개 그룹이 필요합니다.")

    normalized_benchmark = _normalize_optional_ticker(benchmark)
    target_signature = _build_config_signature(
        title,
        period_value,
        slippage_value,
        normalized_benchmark,
        normalized_groups,
        rebalance_freq,
    )
    existing_docs = list(
        _get_collection().find(
            {},
            {
                "_id": 0,
                "config_id": 1,
                "name": 1,
                "period_months": 1,
                "slippage_pct": 1,
                "rebalance_freq": 1,
                "groups": 1,
                "created_at": 1,
                "updated_at": 1,
            },
        )
    )
    for existing_doc in existing_docs:
        existing_signature = _build_config_signature(
            str(existing_doc.get("name") or ""),
            int(existing_doc.get("period_months") or 0),
            _normalize_slippage_pct(existing_doc.get("slippage_pct") or 0.5),
            existing_doc.get("benchmark") if isinstance(existing_doc.get("benchmark"), dict) else None,
            _normalize_groups(list(existing_doc.get("groups") or [])),
            existing_doc.get("rebalance_freq") or "monthly",
        )
        if existing_signature == target_signature:
            return {
                "config_id": str(existing_doc.get("config_id") or ""),
                "name": title,
                "saved_at": (existing_doc.get("updated_at") or existing_doc.get("created_at") or "").isoformat()
                if isinstance(existing_doc.get("updated_at") or existing_doc.get("created_at"), datetime)
                else str(existing_doc.get("updated_at") or existing_doc.get("created_at") or ""),
                "duplicated": True,
            }

    now = datetime.now()
    config_id = f"bt_{uuid4().hex}"
    document = {
        "config_id": config_id,
        "name": title,
        "period_months": period_value,
        "slippage_pct": slippage_value,
        "benchmark": normalized_benchmark,
        "rebalance_freq": str(rebalance_freq or "monthly").strip().lower(),
        "groups": normalized_groups,
        "created_at": now,
        "updated_at": now,
    }

    _get_collection().insert_one(document)
    return {
        "config_id": config_id,
        "name": title,
        "saved_at": now.isoformat(),
        "duplicated": False,
    }


def list_backtest_configs() -> dict[str, list[dict[str, Any]]]:
    docs = list(
        _get_collection()
        .find(
            {},
            {
                "_id": 0,
                "config_id": 1,
                "name": 1,
                "period_months": 1,
                "slippage_pct": 1,
                "benchmark": 1,
                "rebalance_freq": 1,
                "created_at": 1,
                "updated_at": 1,
            },
        )
        .sort("updated_at", -1)
    )
    items = []
    for doc in docs:
        saved_at = doc.get("updated_at") or doc.get("created_at")
        items.append(
            {
                "config_id": str(doc.get("config_id") or ""),
                "name": str(doc.get("name") or ""),
                "period_months": int(doc.get("period_months") or 0),
                "slippage_pct": _normalize_slippage_pct(doc.get("slippage_pct") or 0.5),
                "benchmark": _normalize_optional_ticker(
                    doc.get("benchmark") if isinstance(doc.get("benchmark"), dict) else None
                ),
                "rebalance_freq": str(doc.get("rebalance_freq") or "monthly"),
                "saved_at": saved_at.isoformat() if isinstance(saved_at, datetime) else str(saved_at or ""),
            }
        )
    return {"items": items}


def load_backtest_config(config_id: str) -> dict[str, Any]:
    config_id_value = str(config_id or "").strip()
    if not config_id_value:
        raise ValueError("불러올 백테스트를 선택하세요.")

    doc = _get_collection().find_one({"config_id": config_id_value}, {"_id": 0})
    if not doc:
        raise RuntimeError("저장된 백테스트를 찾을 수 없습니다.")

    saved_at = doc.get("updated_at") or doc.get("created_at")
    return {
        "config_id": str(doc.get("config_id") or ""),
        "name": str(doc.get("name") or ""),
        "period_months": int(doc.get("period_months") or 12),
        "slippage_pct": _normalize_slippage_pct(doc.get("slippage_pct") or 0.5),
        "benchmark": _normalize_optional_ticker(
            doc.get("benchmark") if isinstance(doc.get("benchmark"), dict) else None
        ),
        "rebalance_freq": str(doc.get("rebalance_freq") or "monthly"),
        "groups": _normalize_groups(list(doc.get("groups") or [])),
        "saved_at": saved_at.isoformat() if isinstance(saved_at, datetime) else str(saved_at or ""),
    }


def delete_backtest_config(config_id: str) -> dict[str, str]:
    config_id_value = str(config_id or "").strip()
    if not config_id_value:
        raise ValueError("삭제할 백테스트를 선택하세요.")

    result = _get_collection().delete_one({"config_id": config_id_value})
    if result.deleted_count == 0:
        raise RuntimeError("삭제할 백테스트를 찾을 수 없습니다.")

    return {"config_id": config_id_value}


def _resolve_backtest_window(
    period_months: int, country_code: str = "kor"
) -> tuple[pd.Timestamp, pd.Timestamp, list[pd.Timestamp], pd.Timestamp]:
    today = pd.Timestamp(datetime.now()).normalize()
    latest_trading_day = get_latest_trading_day(country_code).normalize()
    start_reference = (today - pd.DateOffset(months=period_months)).normalize()
    trading_days = get_trading_days(
        start_reference.strftime("%Y-%m-%d"),
        latest_trading_day.strftime("%Y-%m-%d"),
        country_code,
    )
    evaluation_days = [
        pd.Timestamp(day).normalize() for day in trading_days if pd.Timestamp(day).normalize() > start_reference
    ]
    if not evaluation_days:
        raise RuntimeError("백테스트 구간의 거래일을 찾지 못했습니다.")
    return start_reference, latest_trading_day, evaluation_days, evaluation_days[0]


def _build_target_weights(groups: list[dict[str, Any]], trade_date: pd.Timestamp) -> dict[str, float]:
    target_weights: dict[str, float] = {}
    for group in groups:
        group_weight = max(float(group.get("weight") or 0), 0.0) / 100.0
        valid_items = []
        for item in list(group.get("tickers") or []):
            ticker = str(item.get("ticker") or "").strip().upper()
            if not ticker:
                continue
            listing_date_text = str(item.get("listing_date") or "").strip()
            if listing_date_text:
                try:
                    listing_date = pd.Timestamp(listing_date_text).normalize()
                except Exception:
                    listing_date = None
            else:
                listing_date = None
            valid_items.append({"ticker": ticker, "listing_date": listing_date})

        active_items = [
            item for item in valid_items if item["listing_date"] is None or item["listing_date"] <= trade_date
        ]
        if not active_items or group_weight <= 0:
            continue

        ticker_weight = group_weight / len(active_items)
        for item in active_items:
            ticker = str(item["ticker"])
            target_weights[ticker] = target_weights.get(ticker, 0.0) + ticker_weight
    return target_weights


def _build_price_matrix(
    groups: list[dict[str, Any]],
    evaluation_days: list[pd.Timestamp],
    benchmark: dict[str, Any] | None = None,
    country_code: str = "kor",
) -> tuple[dict[str, pd.Series], list[str]]:
    tickers = sorted(
        {
            str(item.get("ticker") or "").strip().upper()
            for group in groups
            for item in list(group.get("tickers") or [])
            if str(item.get("ticker") or "").strip()
        }
    )
    if benchmark and str(benchmark.get("ticker") or "").strip():
        tickers = sorted(set([*tickers, str(benchmark.get("ticker") or "").strip().upper()]))
    best_series_map: dict[str, pd.Series] = {}

    for cache_key in list_available_cache_keys():
        fetched = load_cached_close_series_bulk_with_fallback(cache_key, tickers)
        if not fetched:
            continue
        for ticker, series in fetched.items():
            current_best = best_series_map.get(ticker)
            if current_best is None:
                best_series_map[ticker] = series
                continue

            current_best_end = pd.Timestamp(current_best.index.max()).normalize()
            candidate_end = pd.Timestamp(series.index.max()).normalize()
            if candidate_end > current_best_end:
                best_series_map[ticker] = series
                continue
            if candidate_end == current_best_end and len(series) > len(current_best):
                best_series_map[ticker] = series

    # 실시간 스냅샷으로 캐시에 없는 최신 가격 보충
    try:
        from services.price_service import get_realtime_snapshot

        realtime = get_realtime_snapshot(country_code, tickers)
        today = pd.Timestamp(datetime.now()).normalize()
        for ticker, entry in realtime.items():
            now_val = entry.get("nowVal")
            if now_val is None or float(now_val) <= 0:
                continue
            series = best_series_map.get(ticker)
            if series is None:
                continue
            series = series.copy()
            series.index = pd.to_datetime(series.index).normalize()
            if today not in series.index:
                series.loc[today] = float(now_val)
                best_series_map[ticker] = series.sort_index()
    except Exception:
        pass

    close_series_map = best_series_map
    missing_cache = sorted([ticker for ticker in tickers if ticker not in close_series_map])
    if missing_cache:
        return {}, missing_cache

    aligned: dict[str, pd.Series] = {}
    evaluation_index = pd.DatetimeIndex(evaluation_days)
    missing_price_tickers: list[str] = []
    benchmark_items = [benchmark] if benchmark else []
    for item in [item for group in groups for item in list(group.get("tickers") or [])] + benchmark_items:
        ticker = str(item.get("ticker") or "").strip().upper()
        if not ticker or ticker in aligned:
            continue
        source_series = close_series_map[ticker].sort_index()
        source_series.index = pd.to_datetime(source_series.index).normalize()
        reindexed = pd.to_numeric(source_series, errors="coerce").reindex(evaluation_index).ffill()

        listing_date_text = str(item.get("listing_date") or "").strip()
        listing_date = None
        if listing_date_text:
            try:
                listing_date = pd.Timestamp(listing_date_text).normalize()
            except Exception:
                listing_date = None
        if listing_date is None and not source_series.empty:
            listing_date = pd.Timestamp(source_series.index.min()).normalize()

        active_slice = reindexed[evaluation_index >= listing_date] if listing_date is not None else reindexed
        if active_slice.isna().any():
            missing_price_tickers.append(ticker)
            continue
        aligned[ticker] = reindexed.astype(float)

    if missing_price_tickers:
        return {}, sorted(list(set(missing_price_tickers)))
    return aligned, []


def _format_missing_tickers(groups: list[dict[str, Any]], tickers: list[str]) -> str:
    label_map = {
        str(item.get("ticker") or "").strip().upper(): str(item.get("name") or "").strip()
        for group in groups
        for item in list(group.get("tickers") or [])
        if str(item.get("ticker") or "").strip()
    }
    return ", ".join(f"{label_map.get(ticker) or ticker}({ticker})" for ticker in tickers)


def run_backtest(
    *,
    period_months: int,
    slippage_pct: float,
    benchmark: dict[str, Any] | None,
    groups: list[dict[str, Any]],
    country_code: str = "kor",
    rebalance_freq: str = "monthly",
) -> dict[str, Any]:
    period_value = int(period_months or 0)
    if period_value < 1 or period_value > 24:
        raise ValueError("기간은 최근 1달에서 24달 사이여야 합니다.")
    slippage_value = _normalize_slippage_pct(slippage_pct)

    normalized_groups = _normalize_groups(groups)
    normalized_benchmark = _normalize_optional_ticker(benchmark)
    if not normalized_groups:
        raise ValueError("최소 1개 그룹이 필요합니다.")

    total_weight = sum(max(float(group.get("weight") or 0), 0.0) for group in normalized_groups)
    if abs(total_weight - 100.0) > 0.001:
        raise ValueError("그룹 비중 합계는 100%여야 합니다.")

    _, latest_trading_day, evaluation_days, initial_buy_date = _resolve_backtest_window(period_value, country_code)
    price_matrix, missing_tickers = _build_price_matrix(
        normalized_groups, evaluation_days, normalized_benchmark, country_code
    )
    if missing_tickers:
        raise RuntimeError(
            f"일부 티커의 가격 캐시가 없습니다: {_format_missing_tickers(normalized_groups, missing_tickers)}"
        )

    if rebalance_freq not in ("daily", "weekly", "monthly"):
        raise ValueError("리밸런싱 주기는 daily, weekly, monthly 중 하나여야 합니다.")

    if rebalance_freq == "daily":
        rebalance_dates = set(evaluation_days)
    elif rebalance_freq == "weekly":
        rebalance_dates = _get_weekly_rebalance_dates(evaluation_days, country_code)
    else:
        rebalance_dates = _get_monthly_rebalance_dates(evaluation_days)
        
    rebalance_dates.add(initial_buy_date)

    slippage_rate = slippage_value / 100.0
    cash = 1.0
    position_values = {ticker: 0.0 for ticker in price_matrix}
    previous_prices: dict[str, float] = {}
    equity_curve: list[dict[str, Any]] = []

    for day in evaluation_days:
        day_prices = {ticker: float(series.loc[day]) for ticker, series in price_matrix.items()}

        if previous_prices:
            for ticker, current_value in list(position_values.items()):
                if current_value <= 0:
                    continue
                previous_price = previous_prices.get(ticker)
                current_price = day_prices.get(ticker)
                if previous_price is None or previous_price <= 0 or current_price is None or current_price <= 0:
                    raise RuntimeError(f"백테스트 가격 계산에 실패했습니다: {ticker} {day.strftime('%Y-%m-%d')}")
                position_values[ticker] = current_value * (current_price / previous_price)

        is_trade_day = day in rebalance_dates
        if is_trade_day:
            total_equity = cash + sum(position_values.values())
            target_weights = _build_target_weights(normalized_groups, day)
            target_cash_weight = max(0.0, 1.0 - sum(target_weights.values()))
            target_position_values = {ticker: total_equity * weight for ticker, weight in target_weights.items()}
            traded_notional = 0.0
            for ticker in set(position_values) | set(target_position_values):
                traded_notional += abs(target_position_values.get(ticker, 0.0) - position_values.get(ticker, 0.0))
            cost = traded_notional * slippage_rate
            net_equity = max(total_equity - cost, 0.0)
            position_values = {ticker: net_equity * weight for ticker, weight in target_weights.items()}
            cash = net_equity * target_cash_weight

        total_equity = cash + sum(position_values.values())
        equity_curve.append(
            {
                "date": day.strftime("%Y-%m-%d"),
                "equity": total_equity,
            }
        )
        previous_prices = day_prices

    if not equity_curve:
        raise RuntimeError("백테스트 결과를 계산하지 못했습니다.")

    equity_series = pd.Series(
        [float(item["equity"]) for item in equity_curve],
        index=pd.to_datetime([str(item["date"]) for item in equity_curve]),
        dtype=float,
    )
    running_max = equity_series.cummax()
    drawdown_series = equity_series / running_max - 1.0
    start_equity = float(equity_series.iloc[0])
    end_equity = float(equity_series.iloc[-1])
    cumulative_return_pct = ((end_equity / start_equity) - 1.0) * 100.0 if start_equity > 0 else 0.0
    total_days = max((equity_series.index[-1] - equity_series.index[0]).days, 1)
    cagr_pct = ((end_equity / start_equity) ** (365.25 / total_days) - 1.0) * 100.0 if start_equity > 0 else 0.0
    mdd_pct = float(drawdown_series.min() * 100.0)

    benchmark_result = None
    if normalized_benchmark is not None:
        benchmark_ticker = str(normalized_benchmark.get("ticker") or "").strip().upper()
        benchmark_series = price_matrix.get(benchmark_ticker)
        if benchmark_series is None:
            raise RuntimeError(
                f"벤치마크 종목의 가격 캐시가 없습니다: {_format_missing_tickers([], [benchmark_ticker])}"
            )
        benchmark_prices = benchmark_series.sort_index()
        benchmark_active = benchmark_prices[benchmark_prices.index >= equity_series.index[0]]
        if benchmark_active.empty:
            raise RuntimeError("벤치마크 종목의 거래 데이터를 찾을 수 없습니다.")
        benchmark_equity = benchmark_active / float(benchmark_active.iloc[0])
        benchmark_running_max = benchmark_equity.cummax()
        benchmark_drawdown = benchmark_equity / benchmark_running_max - 1.0
        benchmark_start = float(benchmark_equity.iloc[0])
        benchmark_end = float(benchmark_equity.iloc[-1])
        benchmark_total_days = max((benchmark_equity.index[-1] - benchmark_equity.index[0]).days, 1)
        benchmark_result = {
            "ticker": benchmark_ticker,
            "name": str(normalized_benchmark.get("name") or benchmark_ticker),
            "cumulative_return_pct": round(((benchmark_end / benchmark_start) - 1.0) * 100.0, 2),
            "cagr_pct": round(((benchmark_end / benchmark_start) ** (365.25 / benchmark_total_days) - 1.0) * 100.0, 2),
            "mdd_pct": round(float(benchmark_drawdown.min() * 100.0), 2),
        }

    return {
        "initial_buy_date": initial_buy_date.strftime("%Y-%m-%d"),
        "latest_trading_day": latest_trading_day.strftime("%Y-%m-%d"),
        "cumulative_return_pct": round(cumulative_return_pct, 2),
        "cagr_pct": round(cagr_pct, 2),
        "mdd_pct": round(mdd_pct, 2),
        "benchmark": benchmark_result,
        "equity_curve": [
            {
                "date": str(date),
                "equity": round(float(value), 6),
            }
            for date, value in zip(equity_series.index.strftime("%Y-%m-%d"), equity_series.tolist(), strict=True)
        ],
    }
