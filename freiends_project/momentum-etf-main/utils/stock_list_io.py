"""계좌 종목 메타데이터를 MongoDB stock_meta 컬렉션에서 읽고 쓰는 유틸리티."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
from time import monotonic
from typing import Any

from utils.db_manager import get_db_connection
from utils.logger import get_app_logger

logger = get_app_logger()

# ---------------------------------------------------------------------------
# 컬렉션 / 인덱스
# ---------------------------------------------------------------------------
_COLLECTION_NAME = "stock_meta"
_INDEX_ENSURED = False
_LEGACY_INDEX_DROPPED = False


def _get_collection():
    """stock_meta 컬렉션 핸들을 반환하고, 최초 호출 시 인덱스를 보장한다."""
    global _INDEX_ENSURED, _LEGACY_INDEX_DROPPED
    db = get_db_connection()
    if db is None:
        return None
    coll = db[_COLLECTION_NAME]
    if not _LEGACY_INDEX_DROPPED:
        try:
            index_info = coll.index_information()
            legacy_index = index_info.get("account_ticker_unique")
            legacy_keys = legacy_index.get("key") if isinstance(legacy_index, dict) else None
            if legacy_keys == [("account_id", 1), ("ticker", 1)]:
                coll.drop_index("account_ticker_unique")
            _LEGACY_INDEX_DROPPED = True
        except Exception:
            pass
    if not _INDEX_ENSURED:
        try:
            coll.create_index(
                [("ticker_type", 1), ("ticker", 1)],
                unique=True,
                name="ticker_type_ticker_unique",
                background=True,
            )
            _INDEX_ENSURED = True
        except Exception:
            pass
    return coll


def ensure_stock_meta_readable() -> None:
    """stock_meta 컬렉션을 읽을 수 없으면 즉시 예외를 발생시킨다."""
    coll = _get_collection()
    if coll is None:
        raise RuntimeError("MongoDB 연결 실패 — stock_meta 컬렉션을 읽을 수 없습니다.")


# ---------------------------------------------------------------------------
# 인메모리 캐시 (기존 호환)
# ---------------------------------------------------------------------------
_TICKER_TYPE_STOCKS_CACHE: dict[str, tuple[float, list[dict]]] = {}
_LISTING_CACHE: dict[tuple[str, str], str | None] = {}
_CACHE_TTL_SECONDS = 60.0


def _invalidate_cache(ticker_type: str | None = None) -> None:
    """캐시를 무효화한다. ticker_type가 None이면 전체 캐시를 초기화한다."""
    if ticker_type is None:
        _TICKER_TYPE_STOCKS_CACHE.clear()
        _LISTING_CACHE.clear()
    else:
        norm = (ticker_type or "").strip().lower()
        _TICKER_TYPE_STOCKS_CACHE.pop(norm, None)
        # listing 캐시에서 해당 계좌 관련 항목 제거는 비용이 크므로 전체 초기화
        _LISTING_CACHE.clear()


# 외부 모듈(예: stocks_service)에서 stock_meta 를 직접 갱신한 뒤 호출할 수 있도록
# 공개 alias 를 제공한다.
def invalidate_ticker_type_cache(ticker_type: str | None = None) -> None:
    _invalidate_cache(ticker_type)


# ---------------------------------------------------------------------------
# 내부 로드 (캐시 적용)
# ---------------------------------------------------------------------------


def _load_ticker_type_stocks_raw(ticker_type: str) -> list[dict]:
    """DB에서 해당 종목풀의 활성(is_deleted!=True) 종목 메타데이터를 로드한다 (TTL 캐시 적용)."""
    type_norm = (ticker_type or "").strip().lower()
    cached = _TICKER_TYPE_STOCKS_CACHE.get(type_norm)
    if cached is not None:
        cached_at, cached_docs = cached
        if monotonic() - cached_at < _CACHE_TTL_SECONDS:
            return cached_docs

    coll = _get_collection()
    if coll is None:
        logger.error("MongoDB 연결 실패 — stock_meta 컬렉션을 읽을 수 없습니다.")
        _TICKER_TYPE_STOCKS_CACHE[type_norm] = (monotonic(), [])
        return []

    try:
        # Soft Delete: is_deleted가 True가 아닌 것만 조회
        query = {
            "ticker_type": type_norm,
            "is_deleted": {"$ne": True},
        }
        docs = list(coll.find(query, {"_id": 0}))
        # ticker_type 필드는 내부 관리용이므로 반환 데이터에서 제거
        for doc in docs:
            doc.pop("ticker_type", None)
            doc.pop("created_at", None)
            doc.pop("updated_at", None)
            doc.pop("is_deleted", None)
            doc.pop("deleted_at", None)
        _TICKER_TYPE_STOCKS_CACHE[type_norm] = (monotonic(), docs)
        return docs
    except Exception as exc:
        logger.error("stock_meta 컬렉션 조회 실패 (type=%s): %s", type_norm, exc)
        _TICKER_TYPE_STOCKS_CACHE[type_norm] = (monotonic(), [])
        return []


# ---------------------------------------------------------------------------
# 공개 API — 읽기
# ---------------------------------------------------------------------------

from utils.settings_loader import get_ticker_type_settings, list_available_ticker_types  # noqa: E402


def get_etfs(ticker_type: str, include_extra_tickers: Iterable[str] | None = None) -> list[dict[str, str]]:
    """
    MongoDB stock_meta 컬렉션에서 활성 종목 목록을 반환합니다.
    플랫 리스트 형태: [{ticker, name, listing_date, ...}, ...]
    """
    type_norm = (ticker_type or "").strip().lower()
    if not type_norm:
        raise ValueError("ticker_type must be provided")

    all_etfs: list[dict[str, Any]] = []
    seen_tickers: set[str] = set()

    data = _load_ticker_type_stocks_raw(type_norm)
    if not data:
        return []

    for item in data:
        if not isinstance(item, dict) or not item.get("ticker"):
            continue

        ticker = str(item["ticker"]).strip()
        if not ticker or ticker in seen_tickers:
            continue

        seen_tickers.add(ticker)

        new_item = dict(item)
        new_item["ticker"] = ticker
        new_item["type"] = "etf"
        all_etfs.append(new_item)

    return all_etfs


def get_etfs_by_country(country: str) -> list[dict[str, Any]]:
    """
    (Legacy Helper) 해당 country_code를 가진 모든 계좌의 종목을 합산하여 반환합니다.
    이름 해석 등 계좌 컨텍스트가 없는 경우에 사용합니다.
    """
    country_norm = (country or "").strip().lower()
    types = list_available_ticker_types()

    unique_tickers: dict[str, dict] = {}
    for t_type in types:
        try:
            settings = get_ticker_type_settings(t_type)
            if settings.get("country_code", "").lower() == country_norm:
                etfs = get_etfs(t_type)
                for etf in etfs:
                    tkr = etf.get("ticker")
                    if tkr and tkr not in unique_tickers:
                        unique_tickers[tkr] = etf
        except Exception:
            pass

    return list(unique_tickers.values())


def get_all_etfs_including_deleted(ticker_type: str) -> list[dict[str, Any]]:
    """해당 계좌의 전체 ETF 항목(삭제된 종목 포함)을 DB에서 직접 조회하여 반환합니다."""
    type_norm = (ticker_type or "").strip().lower()
    if not type_norm:
        return []

    coll = _get_collection()
    if coll is None:
        return []

    try:
        # 조건 없이 (ticker_type 일치하는) 모든 도큐먼트 조회
        docs = list(coll.find({"ticker_type": type_norm}, {"_id": 0}))
        results: list[dict[str, Any]] = []
        for doc in docs:
            doc.pop("ticker_type", None)
            doc.pop("created_at", None)
            doc.pop("updated_at", None)
            doc.setdefault("type", "etf")
            results.append(doc)
        return results
    except Exception as exc:
        logger.error("전체 종목 조회(삭제포함) 실패 (type=%s): %s", type_norm, exc)
        return []


def get_all_etfs(ticker_type: str) -> list[dict[str, Any]]:
    """해당 계좌의 전체 ETF 항목(활성 상태만)을 반환합니다."""

    raw_data = _load_ticker_type_stocks_raw(ticker_type)
    if not raw_data:
        return []

    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw_data:
        if not isinstance(item, dict):
            continue
        ticker = str(item.get("ticker") or "").strip()
        if not ticker or ticker in seen:
            continue
        seen.add(ticker)
        entry = dict(item)
        entry["ticker"] = ticker
        entry.setdefault("type", "etf")
        results.append(entry)
    return results


# ---------------------------------------------------------------------------
# 공개 API — 쓰기
# ---------------------------------------------------------------------------


def save_etfs(ticker_type: str, data: list[dict]) -> None:
    """
    종목 메타데이터를 MongoDB stock_meta 컬렉션에 저장합니다 (upsert).
    Soft Delete 방식: 기존에 있지만 새 데이터에 없는 종목은 is_deleted=True 처리합니다.
    """
    type_norm = (ticker_type or "").strip().lower()
    if not type_norm:
        raise ValueError("ticker_type required")

    coll = _get_collection()
    if coll is None:
        raise RuntimeError("MongoDB 연결 실패 — stock_meta 컬렉션에 쓸 수 없습니다.")

    now = datetime.now(timezone.utc)
    new_tickers: set[str] = set()

    from pymongo import UpdateOne

    operations = []
    for item in data:
        if not isinstance(item, dict):
            continue
        ticker = str(item.get("ticker") or "").strip()
        if not ticker:
            continue
        ticker = ticker.upper()
        new_tickers.add(ticker)

        doc = dict(item)
        doc.pop("type", None)
        doc["ticker_type"] = type_norm
        doc["ticker"] = ticker
        doc["updated_at"] = now
        doc["is_deleted"] = False  # 활성 상태로 설정
        doc["deleted_at"] = None

        operations.append(
            UpdateOne(
                {"ticker_type": type_norm, "ticker": ticker},
                {"$set": doc, "$setOnInsert": {"created_at": now}},
                upsert=True,
            )
        )

    if operations:
        try:
            coll.bulk_write(operations, ordered=False)
        except Exception as exc:
            logger.error("stock_meta bulk_write 실패 (type=%s): %s", type_norm, exc)
            raise

    # DB에는 있지만 새 데이터에는 없는 종목 → Soft Delete
    try:
        coll.update_many(
            {"ticker_type": type_norm, "ticker": {"$nin": list(new_tickers)}},
            {
                "$set": {
                    "is_deleted": True,
                    "deleted_at": now,
                    "updated_at": now,
                }
            },
        )
    except Exception as exc:
        logger.warning("stock_meta 잔여 종목 soft delete 실패 (type=%s): %s", type_norm, exc)

    logger.info("%d개 종목 정보가 stock_meta 컬렉션에 저장되었습니다. (type=%s)", len(new_tickers), type_norm)
    _invalidate_cache(type_norm)


def add_stock(ticker_type: str, ticker: str, name: str = "", **extra_fields: Any) -> bool:
    """
    단일 종목을 stock_meta 컬렉션에 추가한다.
    이미 존재하면(삭제된 경우 포함) 활성 상태로 복구한다.
    """
    type_norm = (ticker_type or "").strip().lower()
    ticker_norm = str(ticker or "").strip().upper()
    if not type_norm or not ticker_norm:
        return False

    coll = _get_collection()
    if coll is None:
        return False

    now = datetime.now(timezone.utc)

    # 1. 먼저 존재 여부 확인 (삭제된 것 포함)
    existing = coll.find_one({"ticker_type": type_norm, "ticker": ticker_norm})

    if existing:
        if not existing.get("is_deleted"):
            # 이미 활성 상태로 존재하면 False 반환 (또는 업데이트? 현재는 기각)
            logger.info("이미 존재하는 종목입니다: %s (type=%s)", ticker_norm, type_norm)
            return False

        # 삭제된 상태라면 복구
        try:
            update_doc = {
                "is_deleted": False,
                "deleted_at": None,
                "deleted_reason": None,
                "added_date": now.strftime("%Y-%m-%d"),
                "updated_at": now,
            }
            if name:
                update_doc["name"] = name
            update_doc.update(extra_fields)

            coll.update_one({"_id": existing["_id"]}, {"$set": update_doc})
            _invalidate_cache(type_norm)
            logger.info("삭제된 종목 복구: %s (type=%s)", ticker_norm, type_norm)
            return True
        except Exception as exc:
            logger.warning("종목 복구 실패 %s: %s", ticker_norm, exc)
            return False

    # 2. 없으면 신규 삽입
    doc: dict[str, Any] = {
        "ticker_type": type_norm,
        "ticker": ticker_norm,
        "name": name or "",
        "created_at": now,
        "updated_at": now,
        "added_date": now.strftime("%Y-%m-%d"),
        "is_deleted": False,
        "deleted_at": None,
        "bucket": 1,
    }
    doc.update(extra_fields)

    try:
        coll.insert_one(doc)
        _invalidate_cache(type_norm)
        logger.info("종목 추가: %s (type=%s)", ticker_norm, type_norm)
        return True
    except Exception as exc:
        logger.warning("종목 추가 실패 %s (type=%s): %s", ticker_norm, type_norm, exc)
        return False


def update_stock(ticker_type: str, ticker: str, **update_fields: Any) -> bool:
    """종목 정보를 업데이트한다."""
    type_norm = (ticker_type or "").strip().lower()
    ticker_norm = str(ticker or "").strip()
    if not type_norm or not ticker_norm:
        return False

    coll = _get_collection()
    if coll is None:
        return False

    update_fields["updated_at"] = datetime.now(timezone.utc)

    try:
        result = coll.update_one({"ticker_type": type_norm, "ticker": ticker_norm}, {"$set": update_fields})
        if result.modified_count > 0:
            _invalidate_cache(type_norm)
            return True
        return False
    except Exception as exc:
        logger.warning("종목 업데이트 실패 %s (type=%s): %s", ticker_norm, type_norm, exc)
        return False


def bulk_update_stocks(ticker_type: str, updates: list[dict[str, Any]]) -> int:
    """
    여러 종목의 정보를 한 번에 업데이트한다.
    updates format: [{"ticker": "005930", "bucket": 1}, ...]
    returns: 성공적으로 업데이트된 종목 수
    """
    if not updates:
        return 0

    type_norm = (ticker_type or "").strip().lower()
    coll = _get_collection()
    if coll is None:
        return 0

    from pymongo import UpdateOne

    now = datetime.now(timezone.utc)
    operations = []
    for item in updates:
        ticker = item.get("ticker")
        if not ticker:
            continue

        fields = dict(item)
        fields.pop("ticker", None)
        fields["updated_at"] = now

        operations.append(
            UpdateOne(
                {"ticker_type": type_norm, "ticker": ticker},
                {"$set": fields},
            )
        )

    if not operations:
        return 0

    try:
        result = coll.bulk_write(operations, ordered=False)
        if result.modified_count > 0 or result.upserted_count > 0:
            _invalidate_cache(type_norm)
        return result.modified_count + result.upserted_count
    except Exception as exc:
        logger.error("bulk_update_stocks 실패 (type=%s): %s", type_norm, exc)
        return 0


def remove_stock(ticker_type: str, ticker: str, reason: str = "") -> bool:
    """단일 종목을 Soft Delete 처리한다."""
    type_norm = (ticker_type or "").strip().lower()
    ticker_norm = str(ticker or "").strip()
    if not type_norm or not ticker_norm:
        return False

    coll = _get_collection()
    if coll is None:
        return False

    now = datetime.now(timezone.utc)
    update_fields: dict[str, Any] = {
        "is_deleted": True,
        "deleted_at": now,
        "updated_at": now,
    }
    if reason:
        update_fields["deleted_reason"] = reason.strip()

    try:
        result = coll.update_one(
            {"ticker_type": type_norm, "ticker": ticker_norm},
            {"$set": update_fields},
        )
        if result.modified_count > 0:
            _invalidate_cache(type_norm)
            logger.info("종목 삭제(Soft): %s (type=%s, reason=%s)", ticker_norm, type_norm, reason)
            return True
        return False
    except Exception as exc:
        logger.warning("종목 삭제 실패 %s (type=%s): %s", ticker_norm, type_norm, exc)
        return False


def hard_remove_stock(ticker_type: str, ticker: str) -> bool:
    """단일 종목을 MongoDB에서 완전히 삭제(Hard Delete)한다."""
    type_norm = (ticker_type or "").strip().lower()
    ticker_norm = str(ticker or "").strip()
    if not type_norm or not ticker_norm:
        return False

    coll = _get_collection()
    if coll is None:
        return False

    try:
        result = coll.delete_one({"ticker_type": type_norm, "ticker": ticker_norm})
        if result.deleted_count > 0:
            _invalidate_cache(type_norm)
            logger.info("종목 완전 삭제(Hard): %s (type=%s)", ticker_norm, type_norm)
            return True
        return False
    except Exception as exc:
        logger.warning("종목 완전 삭제 실패 %s (type=%s): %s", ticker_norm, type_norm, exc)
        return False


def get_deleted_etfs(ticker_type: str) -> list[dict[str, Any]]:
    """해당 계좌의 Soft Delete된 종목 목록을 반환한다."""
    type_norm = (ticker_type or "").strip().lower()
    if not type_norm:
        return []

    coll = _get_collection()
    if coll is None:
        return []

    try:
        docs = list(
            coll.find(
                {"ticker_type": type_norm, "is_deleted": True},
                {"_id": 0},
            )
        )
        results: list[dict[str, Any]] = []
        for doc in docs:
            doc.pop("ticker_type", None)
            doc.pop("created_at", None)
            doc.pop("updated_at", None)
            results.append(doc)
        return results
    except Exception as exc:
        logger.warning("삭제 종목 조회 실패 (type=%s): %s", type_norm, exc)
        return []


# ---------------------------------------------------------------------------
# 공개 API — listing_date 관련
# ---------------------------------------------------------------------------


def check_stock_status(ticker_type: str, ticker: str) -> str | None:
    """
    종목의 상태를 확인한다.
    Returns:
        "ACTIVE": 이미 활성 상태로 존재함
        "DELETED": 삭제된 상태로 존재함 (복구 가능)
        None: 존재하지 않음 (신규)
    """
    type_norm = (ticker_type or "").strip().lower()
    ticker_norm = str(ticker or "").strip()
    if not type_norm or not ticker_norm:
        return None

    coll = _get_collection()
    if coll is None:
        return None

    existing = coll.find_one({"ticker_type": type_norm, "ticker": ticker_norm})
    if existing:
        if existing.get("is_deleted"):
            return "DELETED"
        return "ACTIVE"
    return None


def get_listing_date(country: str, ticker: str) -> str | None:
    """country_code 기준으로 listing_date를 조회한다."""
    country_norm = (country or "").strip().lower()
    ticker_norm = str(ticker or "").strip()
    cache_key = (country_norm, ticker_norm)
    if cache_key in _LISTING_CACHE:
        return _LISTING_CACHE[cache_key]

    types = list_available_ticker_types()
    for t_type in types:
        try:
            settings = get_ticker_type_settings(t_type)
            if settings.get("country_code", "").lower() == country_norm:
                data = _load_ticker_type_stocks_raw(t_type)
                for item in data:
                    if not isinstance(item, dict):
                        continue
                    item_ticker = str(item.get("ticker") or "").strip()
                    if item_ticker == ticker_norm:
                        listing_date = item.get("listing_date")
                        if listing_date:
                            _LISTING_CACHE[cache_key] = listing_date
                            return listing_date
        except Exception:
            continue

    _LISTING_CACHE[cache_key] = None
    return None


def set_listing_date(country: str, ticker: str, listing_date: str) -> None:
    """해당 country_code를 공유하는 모든 계좌에서 티커의 listing_date를 설정한다."""
    country_norm = (country or "").strip().lower()
    ticker_norm = str(ticker or "").strip()
    if not ticker_norm:
        return

    coll = _get_collection()
    if coll is None:
        return

    types = list_available_ticker_types()
    updated_any = False

    for t_type in types:
        try:
            settings = get_ticker_type_settings(t_type)
            if settings.get("country_code", "").lower() != country_norm:
                continue

            type_norm = t_type.strip().lower()
            result = coll.update_one(
                {"ticker_type": type_norm, "ticker": ticker_norm},
                {"$set": {"listing_date": listing_date, "updated_at": datetime.now(timezone.utc)}},
            )
            if result.modified_count > 0 or result.matched_count > 0:
                updated_any = True
                _invalidate_cache(type_norm)
        except Exception:
            continue

    if updated_any:
        _LISTING_CACHE[(country_norm, ticker_norm)] = listing_date
