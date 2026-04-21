"""OHLCV 데이터를 MongoDB에 캐싱하고 관리하기 위한 헬퍼 함수 모음입니다."""

from __future__ import annotations

import io
import re
from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any

import pandas as pd
from bson.binary import Binary
from pymongo.errors import PyMongoError

from utils.db_manager import get_db_connection
from utils.logger import get_app_logger

logger = get_app_logger()

_CLOSE_SERIES_MEMORY_CACHE: dict[tuple[str, str], tuple[datetime | None, pd.Series]] = {}

_COLLECTION_NAME_MAP = {
    "kor": "cache_kor_stocks",
    "us": "cache_us_stocks",
}
_REFRESH_STATUS_COLLECTION = "cache_refresh_status"

_TEMP_SUFFIX_SANITIZE = re.compile(r"[^a-z0-9_-]", re.IGNORECASE)


def _get_close_series_memory_cache(
    collection_name: str,
    ticker: str,
    updated_at: datetime | None,
) -> pd.Series | None:
    cached_entry = _CLOSE_SERIES_MEMORY_CACHE.get((collection_name, ticker))
    if cached_entry is None:
        return None

    cached_updated_at, cached_series = cached_entry
    if cached_updated_at != updated_at:
        return None

    return cached_series.copy()


def _set_close_series_memory_cache(
    collection_name: str,
    ticker: str,
    updated_at: datetime | None,
    close_series: pd.Series,
) -> None:
    _CLOSE_SERIES_MEMORY_CACHE[(collection_name, ticker)] = (updated_at, close_series.copy())


def _resolve_close_column(columns: Iterable[str] | None) -> str | None:
    if columns is None:
        return None

    normalized = [str(column) for column in columns]
    for candidate in ["unadjusted_close", "Close", "close"]:
        if candidate in normalized:
            return candidate
    return None


def _serialize_close_series_payload(close_series: pd.Series, column_name: str) -> Binary | None:
    if close_series is None or close_series.empty:
        return None

    close_df = close_series.to_frame(name=column_name)
    buf = io.BytesIO()
    try:
        close_df.to_parquet(buf, engine="pyarrow", compression="snappy")
    except Exception:
        return None
    return Binary(buf.getvalue())


def _backfill_close_series_payload(collection, ticker: str, close_series: pd.Series, column_name: str) -> None:
    close_payload = _serialize_close_series_payload(close_series, column_name)
    if close_payload is None:
        return

    try:
        collection.update_one(
            {"ticker": ticker},
            {
                "$set": {
                    "close_data": close_payload,
                    "close_column": column_name,
                    "close_row_count": int(len(close_series)),
                }
            },
        )
    except Exception:
        return


def _get_cache_start_date() -> pd.Timestamp | None:
    """config.py에서 CACHE_START_DATE를 로드하여 Timestamp로 반환합니다."""
    try:
        from utils.settings_loader import load_common_settings

        common_settings = load_common_settings()
        raw = common_settings.get("CACHE_START_DATE")
    except Exception:
        return None

    if not raw:
        return None

    try:
        ts = pd.to_datetime(raw).normalize()
        if isinstance(ts, pd.DatetimeIndex):
            ts = ts[0]
        if isinstance(ts, pd.Timestamp):
            if ts.tzinfo is not None:
                ts = ts.tz_localize(None)
            return ts.normalize()
    except Exception:
        return None

    return None


def _resolve_collection_name(account_id: str) -> str:
    token = (account_id or "global").strip().lower() or "global"

    # Static map check (legacy support or specific overrides)
    if token in _COLLECTION_NAME_MAP:
        return _COLLECTION_NAME_MAP[token]

    # Temporary collection handling
    if "_tmp_" in token:
        base, _, suffix = token.partition("_tmp_")
        # Recursively resolve base collection name
        base_collection = _resolve_collection_name(base)
        suffix_clean = _TEMP_SUFFIX_SANITIZE.sub("", suffix)
        if not suffix_clean:
            raise ValueError(f"잘못된 임시 컬렉션 토큰: {account_id}")
        return f"{base_collection}_tmp_{suffix_clean}"

    # Default to generic cache_{token}_stocks pattern for accounts
    return f"cache_{token}_stocks"


def _get_collection(account_id: str):
    db = get_db_connection()
    if db is None:
        return None
    collection_name = _resolve_collection_name(account_id)
    collection = db[collection_name]
    # 보조 인덱스 생성 (존재 시 무시)
    try:
        collection.create_index("ticker", unique=True, name="ticker_unique", background=True)
    except Exception:
        pass
    return collection


def _get_refresh_status_collection():
    db = get_db_connection()
    if db is None:
        return None
    collection = db[_REFRESH_STATUS_COLLECTION]
    try:
        collection.create_index("target_id", unique=True, name="target_id_unique", background=True)
    except Exception:
        pass
    return collection


def get_cache_lookup_keys(account_id: str) -> list[str]:
    """캐시 조회 시도 순서를 반환한다.

    계좌 ID가 전달되면 해당 계좌의 ticker_codes 설정을 기반으로
    실제 캐시 컬렉션 키 목록을 반환한다.
    """
    token = (account_id or "").strip().lower()
    if not token:
        return []

    # 계좌 설정에서 ticker_codes를 읽어 캐시 조회 키로 사용
    try:
        from utils.settings_loader import get_account_settings

        settings = get_account_settings(token)
        ticker_codes = settings.get("ticker_codes")
        if isinstance(ticker_codes, list) and ticker_codes:
            return [str(tc).strip().lower() for tc in ticker_codes if str(tc).strip()]
    except Exception:
        pass

    return [token]


def _deserialize_cached_doc(doc: dict[str, Any], collection=None) -> pd.DataFrame | None:
    """공통 캐시 문서 역직렬화 로직."""
    if not doc:
        return None

    payload = doc.get("data")
    if payload is None:
        return None

    ticker_name = doc.get("ticker", "UNKNOWN")
    df = None
    try:
        buf = io.BytesIO(payload)
        df = pd.read_parquet(buf, engine="pyarrow")
    except Exception as e:
        logger.warning(
            "캐시 역직렬화 실패 (%s). 구버전 캐시이거나 데이터가 손상되었습니다. 재생성합니다. (Error: %s)",
            ticker_name,
            e,
        )
        if collection is not None and ticker_name != "UNKNOWN":
            try:
                collection.delete_one({"ticker": ticker_name})
                logger.info("손상된 캐시 문서 삭제됨: %s (ticker: %s)", collection.name, ticker_name)
            except Exception as e_delete:
                logger.error("손상된 캐시 문서 삭제 실패 (ticker: %s): %s", ticker_name, e_delete)
        return None

    if df is None or df.empty:
        return None
    if not isinstance(df.index, pd.DatetimeIndex):
        try:
            df.index = pd.to_datetime(df.index)
        except Exception:
            return None
    df = df.sort_index()
    df = df[~df.index.duplicated(keep="first")]

    cache_start = _get_cache_start_date()
    if cache_start is not None:
        df = df[df.index >= cache_start]

    if df.empty:
        return None
    return df


def _deserialize_cached_close_series_doc(doc: dict[str, Any], collection=None) -> pd.Series | None:
    """캐시 문서에서 종가 시리즈만 역직렬화한다."""
    if not doc:
        return None

    payload = doc.get("close_data")
    close_column = str(doc.get("close_column") or "").strip() or None
    if payload is None:
        payload = doc.get("data")
    if payload is None:
        return None

    ticker_name = doc.get("ticker", "UNKNOWN")
    columns = doc.get("columns")
    candidate_columns: list[str] = []
    if close_column:
        candidate_columns.append(close_column)
    resolved_column = _resolve_close_column(columns if isinstance(columns, list) else None)
    if resolved_column and resolved_column not in candidate_columns:
        candidate_columns.append(resolved_column)
    if not candidate_columns:
        candidate_columns = ["unadjusted_close", "Close", "close"]

    close_df = None
    last_error = None
    for index, candidate in enumerate(candidate_columns):
        try:
            buf = io.BytesIO(payload)
            if doc.get("close_data") is not None and index == 0:
                close_df = pd.read_parquet(buf, engine="pyarrow")
            else:
                close_df = pd.read_parquet(buf, engine="pyarrow", columns=[candidate])
            if close_df is not None and not close_df.empty and candidate in close_df.columns:
                break
            if doc.get("close_data") is not None and close_df is not None and not close_df.empty:
                break
        except Exception as exc:
            last_error = exc
            close_df = None

    if close_df is None or close_df.empty:
        if collection is not None and last_error is not None and ticker_name != "UNKNOWN":
            logger.warning("종가 시리즈 역직렬화 실패 (%s): %s", ticker_name, last_error)
        return None

    if not isinstance(close_df.index, pd.DatetimeIndex):
        try:
            close_df.index = pd.to_datetime(close_df.index)
        except Exception:
            return None

    close_df = close_df.sort_index()
    close_df = close_df[~close_df.index.duplicated(keep="first")]

    close_series = pd.to_numeric(close_df.iloc[:, 0], errors="coerce").dropna()
    if close_series.empty:
        return None

    cache_start = _get_cache_start_date()
    if cache_start is not None:
        close_series = close_series[close_series.index >= cache_start]

    if close_series.empty:
        return None
    return close_series.astype(float)


def load_cached_frame(account_id: str, ticker: str) -> pd.DataFrame | None:
    """저장된 캐시 DataFrame을 로드하고, CACHE_START_DATE 이전 데이터를 필터링합니다."""
    collection = _get_collection(account_id)
    if collection is None:
        return None

    try:
        doc = collection.find_one({"ticker": (ticker or "").strip().upper()})
    except Exception:
        return None

    return _deserialize_cached_doc(doc, collection)


def load_cached_frame_with_fallback(account_id: str, ticker: str) -> pd.DataFrame | None:
    """계좌 캐시를 조회한다."""
    for cache_key in get_cache_lookup_keys(account_id):
        df = load_cached_frame(cache_key, ticker)
        if df is not None and not df.empty:
            return df
    return None


def load_cached_frames_bulk(account_id: str, tickers: Iterable[str]) -> dict[str, pd.DataFrame]:
    """다수의 티커를 한 번의 질의로 가져와 역직렬화합니다."""
    normalized = []
    for t in tickers:
        norm = (t or "").strip().upper()
        if norm:
            normalized.append(norm)
    if not normalized:
        return {}

    collection = _get_collection(account_id)
    if collection is None:
        return {}

    frames: dict[str, pd.DataFrame] = {}
    try:
        cursor = collection.find({"ticker": {"$in": list(set(normalized))}})
    except Exception:
        return {}

    for doc in cursor:
        ticker = (doc.get("ticker") or "").strip().upper()
        if not ticker:
            continue
        df = _deserialize_cached_doc(doc, collection)  # Pass collection for potential cleanup
        if df is None:
            continue
        frames[ticker] = df

    return frames


def load_cached_close_series_bulk(account_id: str, tickers: Iterable[str]) -> dict[str, pd.Series]:
    """다수의 티커에 대한 종가 시리즈만 한 번에 가져온다."""
    normalized = []
    for t in tickers:
        norm = (t or "").strip().upper()
        if norm:
            normalized.append(norm)
    if not normalized:
        return {}

    collection = _get_collection(account_id)
    if collection is None:
        return {}

    series_map: dict[str, pd.Series] = {}
    collection_name = collection.name

    try:
        metadata_cursor = collection.find(
            {"ticker": {"$in": list(set(normalized))}}, {"_id": 0, "ticker": 1, "updated_at": 1}
        )
    except Exception:
        return {}

    pending_tickers: list[str] = []
    for doc in metadata_cursor:
        ticker = (doc.get("ticker") or "").strip().upper()
        if not ticker:
            continue

        updated_at = doc.get("updated_at") if isinstance(doc.get("updated_at"), datetime) else None
        cached_series = _get_close_series_memory_cache(collection_name, ticker, updated_at)
        if cached_series is not None:
            series_map[ticker] = cached_series
            continue
        pending_tickers.append(ticker)

    if not pending_tickers:
        return series_map

    try:
        cursor = collection.find(
            {"ticker": {"$in": pending_tickers}},
            {"_id": 0, "ticker": 1, "updated_at": 1, "close_data": 1, "close_column": 1},
        )
    except Exception:
        return series_map

    fallback_tickers: list[str] = []
    for doc in cursor:
        ticker = (doc.get("ticker") or "").strip().upper()
        if not ticker:
            continue
        close_series = _deserialize_cached_close_series_doc(doc, collection)
        if close_series is None:
            fallback_tickers.append(ticker)
            continue
        updated_at = doc.get("updated_at") if isinstance(doc.get("updated_at"), datetime) else None
        _set_close_series_memory_cache(collection_name, ticker, updated_at, close_series)
        series_map[ticker] = close_series

    if not fallback_tickers:
        return series_map

    try:
        fallback_cursor = collection.find(
            {"ticker": {"$in": fallback_tickers}},
            {"_id": 0, "ticker": 1, "updated_at": 1, "data": 1, "columns": 1},
        )
    except Exception:
        return series_map

    for doc in fallback_cursor:
        ticker = (doc.get("ticker") or "").strip().upper()
        if not ticker:
            continue
        close_series = _deserialize_cached_close_series_doc(doc, collection)
        if close_series is None:
            continue
        updated_at = doc.get("updated_at") if isinstance(doc.get("updated_at"), datetime) else None
        close_column = (
            _resolve_close_column(doc.get("columns") if isinstance(doc.get("columns"), list) else None) or "Close"
        )
        _backfill_close_series_payload(collection, ticker, close_series, close_column)
        _set_close_series_memory_cache(collection_name, ticker, updated_at, close_series)
        series_map[ticker] = close_series

    return series_map


def load_cached_close_series_bulk_before_or_at(
    account_id: str,
    tickers: Iterable[str],
    completed_at: datetime,
) -> dict[str, pd.Series]:
    """완료 시각 이하로 저장된 종가 시리즈만 조회한다."""
    normalized = []
    for t in tickers:
        norm = (t or "").strip().upper()
        if norm:
            normalized.append(norm)
    if not normalized:
        return {}

    collection = _get_collection(account_id)
    if collection is None:
        return {}

    series_map: dict[str, pd.Series] = {}
    collection_name = collection.name

    try:
        metadata_cursor = collection.find(
            {
                "ticker": {"$in": list(set(normalized))},
                "updated_at": {"$lte": completed_at},
            },
            {"_id": 0, "ticker": 1, "updated_at": 1},
        )
    except Exception:
        return {}

    pending_tickers: list[str] = []
    for doc in metadata_cursor:
        ticker = (doc.get("ticker") or "").strip().upper()
        if not ticker:
            continue

        updated_at = doc.get("updated_at") if isinstance(doc.get("updated_at"), datetime) else None
        cached_series = _get_close_series_memory_cache(collection_name, ticker, updated_at)
        if cached_series is not None:
            series_map[ticker] = cached_series
            continue
        pending_tickers.append(ticker)

    if not pending_tickers:
        return series_map

    try:
        cursor = collection.find(
            {
                "ticker": {"$in": pending_tickers},
                "updated_at": {"$lte": completed_at},
            },
            {"_id": 0, "ticker": 1, "updated_at": 1, "close_data": 1, "close_column": 1},
        )
    except Exception:
        return series_map

    fallback_tickers: list[str] = []
    for doc in cursor:
        ticker = (doc.get("ticker") or "").strip().upper()
        if not ticker:
            continue
        close_series = _deserialize_cached_close_series_doc(doc, collection)
        if close_series is None:
            fallback_tickers.append(ticker)
            continue
        updated_at = doc.get("updated_at") if isinstance(doc.get("updated_at"), datetime) else None
        _set_close_series_memory_cache(collection_name, ticker, updated_at, close_series)
        series_map[ticker] = close_series

    if not fallback_tickers:
        return series_map

    try:
        fallback_cursor = collection.find(
            {
                "ticker": {"$in": fallback_tickers},
                "updated_at": {"$lte": completed_at},
            },
            {"_id": 0, "ticker": 1, "updated_at": 1, "data": 1, "columns": 1},
        )
    except Exception:
        return series_map

    for doc in fallback_cursor:
        ticker = (doc.get("ticker") or "").strip().upper()
        if not ticker:
            continue
        close_series = _deserialize_cached_close_series_doc(doc, collection)
        if close_series is None:
            continue
        updated_at = doc.get("updated_at") if isinstance(doc.get("updated_at"), datetime) else None
        close_column = (
            _resolve_close_column(doc.get("columns") if isinstance(doc.get("columns"), list) else None) or "Close"
        )
        _backfill_close_series_payload(collection, ticker, close_series, close_column)
        _set_close_series_memory_cache(collection_name, ticker, updated_at, close_series)
        series_map[ticker] = close_series

    return series_map


def load_cached_frames_bulk_with_fallback(account_id: str, tickers: Iterable[str]) -> dict[str, pd.DataFrame]:
    """계좌 캐시를 조회한다."""
    normalized = []
    for ticker in tickers:
        norm = (ticker or "").strip().upper()
        if norm:
            normalized.append(norm)
    if not normalized:
        return {}

    frames: dict[str, pd.DataFrame] = {}
    missing = set(normalized)

    for cache_key in get_cache_lookup_keys(account_id):
        if not missing:
            break
        fetched = load_cached_frames_bulk(cache_key, missing)
        if not fetched:
            continue
        frames.update(fetched)
        missing -= set(fetched.keys())

    return frames


def load_cached_close_series_bulk_with_fallback(account_id: str, tickers: Iterable[str]) -> dict[str, pd.Series]:
    """계좌 캐시에서 종가 시리즈만 조회한다."""
    normalized = []
    for ticker in tickers:
        norm = (ticker or "").strip().upper()
        if norm:
            normalized.append(norm)
    if not normalized:
        return {}

    series_map: dict[str, pd.Series] = {}
    missing = set(normalized)

    for cache_key in get_cache_lookup_keys(account_id):
        if not missing:
            break
        fetched = load_cached_close_series_bulk(cache_key, missing)
        if not fetched:
            continue
        series_map.update(fetched)
        missing -= set(fetched.keys())

    return series_map


def load_cached_updated_at_bulk(account_id: str, tickers: Iterable[str]) -> dict[str, datetime]:
    """다수의 티커에 대한 캐시 updated_at 시각을 한 번에 조회합니다."""
    normalized = []
    for t in tickers:
        norm = (t or "").strip().upper()
        if norm:
            normalized.append(norm)
    if not normalized:
        return {}

    collection = _get_collection(account_id)
    if collection is None:
        return {}

    results: dict[str, datetime] = {}
    try:
        cursor = collection.find({"ticker": {"$in": list(set(normalized))}}, {"_id": 0, "ticker": 1, "updated_at": 1})
    except Exception:
        return {}

    for doc in cursor:
        ticker = (doc.get("ticker") or "").strip().upper()
        updated_at = doc.get("updated_at")
        if ticker and isinstance(updated_at, datetime):
            results[ticker] = updated_at

    return results


def load_cached_updated_at_bulk_before_or_at(
    account_id: str,
    tickers: Iterable[str],
    completed_at: datetime,
) -> dict[str, datetime]:
    """완료 시각 이하로 저장된 캐시 updated_at 시각을 조회한다."""
    normalized = []
    for t in tickers:
        norm = (t or "").strip().upper()
        if norm:
            normalized.append(norm)
    if not normalized:
        return {}

    collection = _get_collection(account_id)
    if collection is None:
        return {}

    results: dict[str, datetime] = {}
    try:
        cursor = collection.find(
            {
                "ticker": {"$in": list(set(normalized))},
                "updated_at": {"$lte": completed_at},
            },
            {"_id": 0, "ticker": 1, "updated_at": 1},
        )
    except Exception:
        return {}

    for doc in cursor:
        ticker = (doc.get("ticker") or "").strip().upper()
        updated_at = doc.get("updated_at")
        if ticker and isinstance(updated_at, datetime):
            results[ticker] = updated_at

    return results


def load_cached_updated_at_bulk_with_fallback(account_id: str, tickers: Iterable[str]) -> dict[str, datetime]:
    """계좌 캐시의 updated_at 시각을 조회합니다."""
    normalized = []
    for ticker in tickers:
        norm = (ticker or "").strip().upper()
        if norm:
            normalized.append(norm)
    if not normalized:
        return {}

    updated_map: dict[str, datetime] = {}
    missing = set(normalized)

    for cache_key in get_cache_lookup_keys(account_id):
        if not missing:
            break
        fetched = load_cached_updated_at_bulk(cache_key, missing)
        if not fetched:
            continue
        updated_map.update(fetched)
        missing -= set(fetched.keys())

    return updated_map


def load_cached_updated_at_bulk_before_or_at_with_fallback(
    account_id: str,
    tickers: Iterable[str],
    completed_at: datetime,
) -> dict[str, datetime]:
    """계좌 캐시에서 완료 시각 이하의 updated_at만 조회한다."""
    normalized = []
    for ticker in tickers:
        norm = (ticker or "").strip().upper()
        if norm:
            normalized.append(norm)
    if not normalized:
        return {}

    updated_map: dict[str, datetime] = {}
    missing = set(normalized)

    for cache_key in get_cache_lookup_keys(account_id):
        if not missing:
            break
        fetched = load_cached_updated_at_bulk_before_or_at(cache_key, missing, completed_at)
        if not fetched:
            continue
        updated_map.update(fetched)
        missing -= set(fetched.keys())

    return updated_map


def load_cached_close_series_bulk_before_or_at_with_fallback(
    account_id: str,
    tickers: Iterable[str],
    completed_at: datetime,
) -> dict[str, pd.Series]:
    """계좌 캐시에서 완료 시각 이하의 종가 시리즈만 조회한다."""
    normalized = []
    for ticker in tickers:
        norm = (ticker or "").strip().upper()
        if norm:
            normalized.append(norm)
    if not normalized:
        return {}

    series_map: dict[str, pd.Series] = {}
    missing = set(normalized)

    for cache_key in get_cache_lookup_keys(account_id):
        if not missing:
            break
        fetched = load_cached_close_series_bulk_before_or_at(cache_key, missing, completed_at)
        if not fetched:
            continue
        series_map.update(fetched)
        missing -= set(fetched.keys())

    return series_map


def get_cache_refresh_completed_at(target_id: str) -> datetime | None:
    """지정 대상의 마지막 가격 캐시 완료 시각을 조회한다."""
    target_norm = (target_id or "").strip().lower()
    if not target_norm:
        return None

    collection = _get_refresh_status_collection()
    if collection is None:
        return None

    try:
        doc = collection.find_one({"target_id": target_norm}, {"_id": 0, "completed_at": 1})
    except Exception:
        return None

    completed_at = (doc or {}).get("completed_at")
    return completed_at if isinstance(completed_at, datetime) else None


def set_cache_refresh_completed_at(target_id: str, completed_at: datetime) -> None:
    """지정 대상의 마지막 가격 캐시 완료 시각을 저장한다."""
    target_norm = (target_id or "").strip().lower()
    if not target_norm:
        raise ValueError("target_id가 필요합니다.")

    collection = _get_refresh_status_collection()
    if collection is None:
        raise RuntimeError("캐시 완료 시각 컬렉션을 열 수 없습니다.")

    completed_at_utc = (
        completed_at.replace(tzinfo=None)
        if completed_at.tzinfo is None
        else completed_at.astimezone(timezone.utc).replace(tzinfo=None)
    )

    collection.update_one(
        {"target_id": target_norm},
        {
            "$set": {
                "target_id": target_norm,
                "completed_at": completed_at_utc,
                "updated_at": datetime.utcnow(),
            }
        },
        upsert=True,
    )


def save_cached_frame(account_id: str, ticker: str, df: pd.DataFrame) -> None:
    """캐시 DataFrame을 저장합니다. CACHE_START_DATE 이전 데이터는 제외합니다."""
    if df is None or df.empty:
        raise ValueError("저장할 캐시 데이터가 비어 있습니다.")

    collection = _get_collection(account_id)
    if collection is None:
        raise RuntimeError(f"캐시 컬렉션을 열 수 없습니다: {account_id}")

    df_to_save = df.copy()
    df_to_save.sort_index(inplace=True)
    df_to_save = df_to_save[~df_to_save.index.duplicated(keep="first")]

    # CACHE_START_DATE 이전 데이터 필터링
    cache_start = _get_cache_start_date()
    if cache_start is not None:
        df_to_save = df_to_save[df_to_save.index >= cache_start]

    if df_to_save.empty:
        raise ValueError("CACHE_START_DATE 적용 후 저장할 캐시 데이터가 비어 있습니다.")

    ticker_norm = (ticker or "").strip().upper()

    buf = io.BytesIO()
    try:
        df_to_save.to_parquet(buf, engine="pyarrow", compression="snappy")
    except Exception as exc:
        raise RuntimeError(f"캐시 직렬화 실패 ({ticker_norm})") from exc

    payload = Binary(buf.getvalue())

    try:
        result = collection.update_one(
            {"ticker": ticker_norm},
            {
                "$set": {
                    "ticker": ticker_norm,
                    "data": payload,
                    "updated_at": datetime.utcnow(),
                    "row_count": int(df_to_save.shape[0]),
                    "columns": df_to_save.columns.astype(str).tolist(),
                }
            },
            upsert=True,
        )
    except Exception as exc:
        raise RuntimeError(f"캐시 저장 실패 ({ticker_norm})") from exc

    if not result.acknowledged:
        raise RuntimeError(f"캐시 저장이 확인되지 않았습니다 ({ticker_norm})")

    close_column = _resolve_close_column(df_to_save.columns.astype(str).tolist())
    if close_column is not None:
        close_series = pd.to_numeric(df_to_save[close_column], errors="coerce").dropna().astype(float)
        if not close_series.empty:
            _backfill_close_series_payload(collection, ticker_norm, close_series, close_column)

    saved_doc = collection.find_one({"ticker": ticker_norm}, {"_id": 0, "row_count": 1})
    if not saved_doc:
        raise RuntimeError(f"저장 후 캐시 문서를 찾을 수 없습니다 ({ticker_norm})")

    saved_count = int(saved_doc.get("row_count") or 0)
    expected_count = int(df_to_save.shape[0])
    if saved_count != expected_count:
        raise RuntimeError(
            f"저장된 캐시 행 수가 다릅니다 ({ticker_norm}): expected={expected_count}, actual={saved_count}"
        )


def delete_cached_frame(account_id: str, ticker: str) -> None:
    collection = _get_collection(account_id)
    if collection is None:
        return
    try:
        collection.delete_one({"ticker": (ticker or "").strip().upper()})
    except Exception:
        return


def drop_cache_collection(account_id: str) -> None:
    db = get_db_connection()
    if db is None:
        return
    collection_name = _resolve_collection_name(account_id)
    try:
        db[collection_name].drop()
    except Exception:
        return


def clean_temp_cache_collections(account_id: str, *, max_age_seconds: int | None = None) -> int:
    """남아 있는 임시 캐시 컬렉션을 조건에 맞게 삭제합니다."""
    db = get_db_connection()
    if db is None:
        return 0
    base_name = _COLLECTION_NAME_MAP.get(account_id.strip().lower(), f"cache_{account_id}_stocks")
    removed = 0
    try:
        threshold = None
        if max_age_seconds is not None and max_age_seconds > 0:
            threshold = datetime.utcnow().timestamp() - max_age_seconds

        for coll_name in db.list_collection_names():
            if not coll_name.startswith(f"{base_name}_tmp_"):
                continue
            if threshold is not None:
                parts = coll_name.rsplit("_", 2)
                if len(parts) >= 2:
                    try:
                        ts_val = int(parts[-2])
                        if ts_val >= threshold:
                            continue
                    except ValueError:
                        pass
            db[coll_name].drop()
            removed += 1
    except Exception:
        return removed
    return removed


def swap_cache_collection(account_id: str, temp_token: str) -> None:
    """임시 컬렉션을 메인 캐시 컬렉션으로 원자적으로 교체합니다."""
    db = get_db_connection()
    if db is None:
        raise RuntimeError("MongoDB 연결을 초기화할 수 없습니다.")

    client = db.client
    db_name = db.name
    main_collection_name = _resolve_collection_name(account_id)
    temp_collection_name = _resolve_collection_name(temp_token)

    if temp_collection_name not in db.list_collection_names():
        raise ValueError(f"임시 컬렉션 '{temp_collection_name}'을 찾을 수 없습니다.")

    try:
        client.admin.command(
            {
                "renameCollection": f"{db_name}.{temp_collection_name}",
                "to": f"{db_name}.{main_collection_name}",
                "dropTarget": True,
            }
        )
        # rename 후 새 컬렉션 핸들을 초기화하여 (재)인덱스 보장
        _get_collection(account_id)
    except PyMongoError as exc:
        logger.error("캐시 컬렉션 교체 실패 (%s <- %s): %s", main_collection_name, temp_collection_name, exc)
        raise
    except Exception as exc:
        logger.error("캐시 컬렉션 교체 중 예외 발생: %s", exc)
        raise


def get_cached_date_range(account_id: str, ticker: str) -> tuple[pd.Timestamp, pd.Timestamp] | None:
    df = load_cached_frame(account_id, ticker)
    if df is None or df.empty:
        return None
    return df.index.min(), df.index.max()


def list_available_cache_keys() -> list[str]:
    """캐시된 계정(또는 국가) 키 목록을 반환합니다."""
    db = get_db_connection()
    if db is None:
        return []

    available: list[str] = []
    try:
        existing = set(db.list_collection_names())
    except Exception:
        existing = set()

    # 정적 맵 먼저 체크
    for key, coll in _COLLECTION_NAME_MAP.items():
        if coll in existing:
            available.append(key)

    # 동적 컬렉션 패턴 체크 (cache_{account}_stocks)
    # cache_ 로 시작하고 _stocks 로 끝나는 컬렉션 탐색
    # 단, _tmp_ 가 포함된 건 임시 컬렉션이므로 제외
    for coll_name in existing:
        if coll_name.startswith("cache_") and coll_name.endswith("_stocks"):
            # cache_{account}_stocks
            # account 부분을 추출
            # prefix "cache_" (len 6), suffix "_stocks" (len 7)
            if len(coll_name) > 13:
                inner = coll_name[6:-7]  # extract "account"
                if "_tmp_" in inner:
                    continue
                available.append(inner)

    # 중복 제거 및 정렬
    available = sorted(list(set(available)))

    if not available:
        # DB 연결 실패 또는 없으면 정적 맵 키라도 반환
        available = sorted(_COLLECTION_NAME_MAP.keys())

    return available


def list_cached_tickers(account_id: str) -> list[str]:
    collection = _get_collection(account_id)
    if collection is None:
        return []
    try:
        tickers = collection.distinct("ticker")
    except Exception:
        return []
    return sorted(str(ticker or "").upper() for ticker in tickers if ticker)
