from __future__ import annotations
from datetime import datetime
from typing import Any

from utils.ticker_registry import load_ticker_type_configs as load_account_configs
from utils.db_manager import get_db_connection
from utils.logger import get_app_logger
from utils.normalization import normalize_nullable_number, normalize_text
from utils.stock_list_io import add_stock, hard_remove_stock, invalidate_ticker_type_cache
from utils.stock_meta_updater import fetch_stock_info
from services.price_service import get_realtime_snapshot
from services.stock_cache_service import delete_stock_cache

BUCKETS: dict[int, str] = {
    1: "1. 모멘텀",
    2: "2. 시장지수",
    3: "3. 배당방어",
    4: "4. 대체헷지",
}


def _format_deleted_date(value: Any) -> str:
    if not value:
        return "-"
    if isinstance(value, datetime):
        return value.isoformat()[:10]
    return str(value).strip()[:10] or "-"


def _load_ticker_types_payload() -> list[dict[str, Any]]:
    configs = load_account_configs()
    if not configs:
        raise RuntimeError("종목풀 설정이 없습니다.")
    return [
        {
            "ticker_type": config["ticker_type"],
            "order": config["order"],
            "name": config["name"],
            "icon": config["icon"],
        }
        for config in configs
    ]


def _pick_ticker_type(ticker_types: list[dict[str, Any]], ticker_type: str | None) -> str:
    target = str(ticker_type or "").strip().lower()
    available_ids = [str(t["ticker_type"]).lower() for t in ticker_types]
    
    if target and target in available_ids:
        return target
        
    return available_ids[0] if available_ids else ""


def _normalize_candidate_ticker(ticker: str, country_code: str) -> str:
    text = str(ticker or "").strip().upper()
    if not text:
        raise RuntimeError("티커를 입력하세요.")
    if ":" in text:
        text = text.split(":")[-1].strip().upper()
    if (country_code or "").strip().lower() == "au" and text.endswith(".AX"):
        text = text[:-3]
    return text


def _load_account_config_map() -> dict[str, dict[str, Any]]:
    return {config["ticker_type"]: config for config in load_account_configs()}


def _require_ticker_type_config(ticker_type: str) -> dict[str, Any]:
    type_norm = str(ticker_type or "").strip().lower()
    configs = _load_account_config_map()
    config = configs.get(type_norm)
    if not config:
        raise RuntimeError("종목풀을 찾을 수 없습니다.")
    return config


def _load_stock_meta_doc(ticker_type: str, ticker: str) -> dict[str, Any] | None:
    db = get_db_connection()
    if db is None:
        raise RuntimeError("MongoDB 연결에 실패했습니다.")

    return db.stock_meta.find_one(
        {
            "ticker_type": str(ticker_type or "").strip().lower(),
            "ticker": str(ticker or "").strip().upper(),
        },
        {
            "ticker": 1,
            "name": 1,
            "listing_date": 1,
            "bucket": 1,
            "is_deleted": 1,
        },
    )


def load_active_stocks_table(ticker_type: str | None = None) -> dict[str, Any]:
    ticker_types = _load_ticker_types_payload()
    target_ticker_type = _pick_ticker_type(ticker_types, ticker_type)

    db = get_db_connection()
    if db is None:
        raise RuntimeError("MongoDB 연결에 실패했습니다.")

    docs = list(
        db.stock_meta.find(
            {
                "ticker_type": target_ticker_type,
                "is_deleted": {"$ne": True},
            },
            {
                "ticker": 1,
                "name": 1,
                "bucket": 1,
                "added_date": 1,
                "listing_date": 1,
                "1_week_avg_volume": 1,
                "1_day_earn_rate": 1,
                "1_week_earn_rate": 1,
                "2_week_earn_rate": 1,
                "1_month_earn_rate": 1,
                "3_month_earn_rate": 1,
                "6_month_earn_rate": 1,
                "12_month_earn_rate": 1,
            },
        )
    )

    # 실시간 스냅샷 가져오기
    tickers = [doc.get("ticker", "") for doc in docs if doc.get("ticker")]
    config = _require_ticker_type_config(target_ticker_type)
    country_code = config.get("country_code", "kor")
    realtime_snapshot = {}
    try:
        realtime_snapshot = get_realtime_snapshot(country_code, tickers)
    except Exception:
        pass

    rows = sorted(
        [
            {
                "ticker": normalize_text(doc.get("ticker"), ""),
                "name": normalize_text(doc.get("name"), ""),
                "bucket_id": int(doc.get("bucket") or 1),
                "bucket_name": BUCKETS.get(int(doc.get("bucket") or 1), BUCKETS[1]),
                "added_date": normalize_text(doc.get("added_date"), "-"),
                "listing_date": normalize_text(doc.get("listing_date"), "-"),
                "week_volume": normalize_nullable_number(doc.get("1_week_avg_volume")),
                "return_1d": normalize_nullable_number(
                    realtime_snapshot.get(doc.get("ticker", ""), {}).get("changeRate") 
                ),
                "괴리율": normalize_nullable_number(
                    realtime_snapshot.get(doc.get("ticker", ""), {}).get("deviation")
                ),
                "return_1w": normalize_nullable_number(doc.get("1_week_earn_rate")),
                "return_2w": normalize_nullable_number(doc.get("2_week_earn_rate")),
                "return_1m": normalize_nullable_number(doc.get("1_month_earn_rate")),
                "return_3m": normalize_nullable_number(doc.get("3_month_earn_rate")),
                "return_6m": normalize_nullable_number(doc.get("6_month_earn_rate")),
                "return_12m": normalize_nullable_number(doc.get("12_month_earn_rate")),
            }
            for doc in docs
        ],
        key=lambda row: (
            row["bucket_id"],
            -(row["return_1w"] if row["return_1w"] is not None else float("-inf")),
        ),
    )

    return {
        "ticker_types": ticker_types,
        "rows": rows,
        "ticker_type": target_ticker_type,
    }


def validate_stock_candidate(ticker_type: str, ticker: str) -> dict[str, Any]:
    config = _require_ticker_type_config(ticker_type)
    ticker_type_norm = str(config["ticker_type"]).strip().lower()
    country_code = str(config.get("country_code") or "").strip().lower()
    ticker_norm = _normalize_candidate_ticker(ticker, country_code)

    db = get_db_connection()
    if db is None:
        raise RuntimeError("MongoDB 연결에 실패했습니다.")

    existing = db.stock_meta.find_one(
        {
            "ticker_type": ticker_type_norm,
            "ticker": ticker_norm,
        },
        {
            "name": 1,
            "listing_date": 1,
            "is_deleted": 1,
            "deleted_reason": 1,
            "bucket": 1,
        },
    )

    stock_info = fetch_stock_info(ticker_norm, country_code)
    if not stock_info or not str(stock_info.get("name") or "").strip():
        raise RuntimeError("유효한 티커를 찾지 못했습니다.")

    is_deleted = bool(existing and existing.get("is_deleted") is True)
    is_active = bool(existing and existing.get("is_deleted") is not True)
    deleted_reason = normalize_text(existing.get("deleted_reason"), "") if existing else ""
    listing_date = normalize_text(stock_info.get("listing_date") or (existing or {}).get("listing_date"), "-")
    bucket_id = int((existing or {}).get("bucket") or 1)

    return {
        "ticker": ticker_norm,
        "name": normalize_text(stock_info.get("name"), ""),
        "listing_date": listing_date,
        "status": "active" if is_active else "deleted" if is_deleted else "new",
        "is_deleted": is_deleted,
        "deleted_reason": deleted_reason,
        "bucket_id": bucket_id,
        "ticker_type": ticker_type_norm,
        "country_code": country_code,
    }


def refresh_single_stock(ticker_type: str, ticker: str) -> dict[str, str]:
    """단일 종목의 메타데이터와 가격 캐시를 갱신합니다."""
    logger = get_app_logger()
    type_norm = str(ticker_type or "").strip().lower()
    ticker_norm = str(ticker or "").strip().upper()
    if not type_norm or not ticker_norm:
        raise RuntimeError("계좌와 티커를 지정하세요.")

    config = _require_ticker_type_config(type_norm)
    country_code = str(config.get("country_code") or "kor").strip().lower()

    # 1) 메타데이터 업데이트
    from utils.stock_meta_updater import update_single_ticker_metadata

    try:
        update_single_ticker_metadata(type_norm, ticker_norm)
    except Exception as e:
        logger.error(f"[{type_norm.upper()}/{ticker_norm}] 메타데이터 갱신 실패: {e}")

    # 2) 가격 캐시 업데이트
    from utils.data_loader import fetch_ohlcv

    try:
        from utils.settings_loader import load_common_settings

        settings = load_common_settings() or {}
        start_date = settings.get("CACHE_START_DATE", "2024-01-01")

        fetch_ohlcv(
            ticker_norm,
            country=country_code,
            date_range=[start_date, None],
            update_listing_meta=False,
            force_refresh=True,
            ticker_type=type_norm,
        )
    except Exception as e:
        logger.error(f"[{type_norm.upper()}/{ticker_norm}] 가격 캐시 갱신 실패: {e}")

    return {"ticker": ticker_norm, "ticker_type": type_norm}


def add_active_stock(ticker_type: str, ticker: str, bucket_id: int) -> dict[str, Any]:
    validated = validate_stock_candidate(ticker_type, ticker)
    ticker_type_norm = str(validated["ticker_type"]).strip().lower()
    ticker_norm = str(validated["ticker"]).strip().upper()
    bucket_value = int(bucket_id or 0)
    if bucket_value not in BUCKETS:
        raise RuntimeError("버킷을 선택하세요.")

    created = add_stock(
        ticker_type_norm,
        ticker_norm,
        name=str(validated["name"]),
        listing_date=None if validated["listing_date"] == "-" else validated["listing_date"],
        bucket=bucket_value,
    )
    if not created:
        current = _load_stock_meta_doc(ticker_type_norm, ticker_norm)
        if current and current.get("is_deleted") is not True:
            if validated["status"] == "active":
                raise RuntimeError("이미 등록된 종목입니다.")

            return {
                "ticker": ticker_norm,
                "name": normalize_text(current.get("name"), str(validated["name"])),
                "listing_date": normalize_text(
                    current.get("listing_date"),
                    str(validated["listing_date"]),
                ),
                "bucket_id": int(current.get("bucket") or bucket_value),
                "bucket_name": BUCKETS.get(int(current.get("bucket") or bucket_value), BUCKETS[bucket_value]),
                "status": "active",
            }

        if validated["status"] == "active":
            raise RuntimeError("이미 등록된 종목입니다.")
        raise RuntimeError(f"종목 추가에 실패했습니다: {ticker_norm}")

    try:
        # 추가 성공은 메타/가격 캐시 준비 완료까지 포함한다.
        refresh_single_stock(ticker_type_norm, ticker_norm)
    except Exception as refresh_error:
        db = get_db_connection()
        if db is not None:
            db.stock_meta.delete_one(
                {
                    "ticker_type": ticker_type_norm,
                    "ticker": ticker_norm,
                    "is_deleted": {"$ne": True},
                }
            )
            invalidate_ticker_type_cache(ticker_type_norm)
        raise RuntimeError(f"종목 캐시 갱신에 실패해 추가를 취소했습니다: {refresh_error}") from refresh_error

    return {
        "ticker": ticker_norm,
        "name": str(validated["name"]),
        "listing_date": str(validated["listing_date"]),
        "bucket_id": bucket_value,
        "bucket_name": BUCKETS[bucket_value],
        "status": validated["status"],
    }


def update_stock_bucket(ticker_type: str, ticker: str, bucket_id: int) -> None:
    db = get_db_connection()
    if db is None:
        raise RuntimeError("MongoDB 연결에 실패했습니다.")

    type_norm = str(ticker_type or "").strip().lower()
    result = db.stock_meta.update_one(
        {
            "ticker_type": type_norm,
            "ticker": str(ticker or "").strip().upper(),
            "is_deleted": {"$ne": True},
        },
        {
            "$set": {
                "bucket": int(bucket_id),
                "updated_at": datetime.now(),
            }
        },
    )

    if result.matched_count == 0:
        raise RuntimeError("수정할 종목을 찾을 수 없습니다.")

    # stock_list_io 의 TTL 캐시가 60초간 이전 값을 반환해 버려서 UI 에 반영되지 않는 것을 방지한다.
    invalidate_ticker_type_cache(type_norm)


def delete_active_stock(ticker_type: str, ticker: str) -> None:
    db = get_db_connection()
    if db is None:
        raise RuntimeError("MongoDB 연결에 실패했습니다.")

    type_norm = str(ticker_type or "").strip().lower()
    ticker_norm = str(ticker or "").strip().upper()

    if not hard_remove_stock(type_norm, ticker_norm):
        raise RuntimeError("삭제할 종목을 찾을 수 없습니다.")

    from utils.cache_utils import delete_cached_frame

    try:
        delete_cached_frame(type_norm, ticker_norm)
    except Exception:
        pass

    try:
        delete_stock_cache(type_norm, ticker_norm)
    except Exception:
        pass


def load_deleted_stocks_table(ticker_type: str | None = None) -> dict[str, Any]:
    ticker_types = _load_ticker_types_payload()
    target_ticker_type = _pick_ticker_type(ticker_types, ticker_type)

    db = get_db_connection()
    if db is None:
        raise RuntimeError("MongoDB 연결에 실패했습니다.")

    docs = list(
        db.stock_meta.find(
            {
                "ticker_type": target_ticker_type,
                "is_deleted": True,
            },
            {
                "ticker": 1,
                "name": 1,
                "bucket": 1,
                "added_date": 1,
                "listing_date": 1,
                "1_week_avg_volume": 1,
                "1_day_earn_rate": 1,
                "1_week_earn_rate": 1,
                "2_week_earn_rate": 1,
                "1_month_earn_rate": 1,
                "3_month_earn_rate": 1,
                "6_month_earn_rate": 1,
                "12_month_earn_rate": 1,
                "deleted_at": 1,
                "deleted_reason": 1,
            },
        )
    )

    # 실시간 스냅샷 가져오기
    tickers = [doc.get("ticker", "") for doc in docs if doc.get("ticker")]
    config = _require_ticker_type_config(target_ticker_type)
    country_code = config.get("country_code", "kor")
    realtime_snapshot = {}
    try:
        realtime_snapshot = get_realtime_snapshot(country_code, tickers)
    except Exception:
        pass

    rows = sorted(
        [
            {
                "ticker": normalize_text(doc.get("ticker"), ""),
                "name": normalize_text(doc.get("name"), ""),
                "bucket_id": int(doc.get("bucket") or 1),
                "bucket_name": BUCKETS.get(int(doc.get("bucket") or 1), BUCKETS[1]),
                "added_date": normalize_text(doc.get("added_date"), "-"),
                "listing_date": normalize_text(doc.get("listing_date"), "-"),
                "week_volume": normalize_nullable_number(doc.get("1_week_avg_volume")),
                "return_1d": normalize_nullable_number(
                    realtime_snapshot.get(doc.get("ticker", ""), {}).get("changeRate") 
                ),
                "괴리율": normalize_nullable_number(
                    realtime_snapshot.get(doc.get("ticker", ""), {}).get("deviation")
                ),
                "return_1w": normalize_nullable_number(doc.get("1_week_earn_rate")),
                "return_2w": normalize_nullable_number(doc.get("2_week_earn_rate")),
                "return_1m": normalize_nullable_number(doc.get("1_month_earn_rate")),
                "return_3m": normalize_nullable_number(doc.get("3_month_earn_rate")),
                "return_6m": normalize_nullable_number(doc.get("6_month_earn_rate")),
                "return_12m": normalize_nullable_number(doc.get("12_month_earn_rate")),
                "deleted_date": _format_deleted_date(doc.get("deleted_at")),
                "deleted_reason": normalize_text(doc.get("deleted_reason"), "-"),
            }
            for doc in docs
        ],
        key=lambda row: (row["bucket_id"], row["deleted_date"]),
        reverse=True,
    )

    return {
        "ticker_types": ticker_types,
        "rows": rows,
        "ticker_type": target_ticker_type,
    }


def restore_deleted_stocks(ticker_type: str, tickers: list[str]) -> int:
    type_norm = str(ticker_type or "").strip().lower()
    ticker_list = [str(ticker or "").strip().upper() for ticker in tickers if str(ticker or "").strip()]
    if not type_norm or not ticker_list:
        raise RuntimeError("복구할 종목을 선택하세요.")

    db = get_db_connection()
    if db is None:
        raise RuntimeError("MongoDB 연결에 실패했습니다.")

    now = datetime.now()
    result = db.stock_meta.update_many(
        {
            "ticker_type": type_norm,
            "ticker": {"$in": ticker_list},
            "is_deleted": True,
        },
        {
            "$set": {
                "is_deleted": False,
                "deleted_at": None,
                "deleted_reason": None,
                "added_date": now.date().isoformat(),
                "updated_at": now,
            }
        },
    )
    if result.modified_count > 0:
        invalidate_ticker_type_cache(type_norm)
    return int(result.modified_count)


def hard_delete_stocks(ticker_type: str, tickers: list[str]) -> int:
    type_norm = str(ticker_type or "").strip().lower()
    ticker_list = [str(ticker or "").strip().upper() for ticker in tickers if str(ticker or "").strip()]
    if not type_norm or not ticker_list:
        raise RuntimeError("삭제할 종목을 선택하세요.")

    db = get_db_connection()
    if db is None:
        raise RuntimeError("MongoDB 연결에 실패했습니다.")

    result = db.stock_meta.delete_many(
        {
            "ticker_type": type_norm,
            "ticker": {"$in": ticker_list},
            "is_deleted": True,
        }
    )

    # 캐시 도큐먼트도 함께 제거
    from utils.cache_utils import delete_cached_frame

    for ticker in ticker_list:
        try:
            delete_cached_frame(type_norm, ticker)
        except Exception:
            pass

    if result.deleted_count > 0:
        invalidate_ticker_type_cache(type_norm)
    return int(result.deleted_count)
