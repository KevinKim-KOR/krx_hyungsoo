"""계좌별 목표 포트폴리오(종목 및 비율)를 관리하는 유틸리티."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pymongo import UpdateOne

from utils.db_manager import get_db_connection
from utils.logger import get_app_logger

logger = get_app_logger()

_COLLECTION_NAME = "account_targets"
_INDEX_ENSURED = False


def _get_collection():
    """account_targets 컬렉션 핸들을 반환하고, 최초 호출 시 인덱스를 보장한다."""
    global _INDEX_ENSURED
    db = get_db_connection()
    if db is None:
        return None
    coll = db[_COLLECTION_NAME]
    if not _INDEX_ENSURED:
        try:
            coll.create_index(
                [("account_id", 1), ("ticker", 1)],
                unique=True,
                name="account_ticker_target_unique",
                background=True,
            )
            _INDEX_ENSURED = True
        except Exception as e:
            logger.warning("account_targets 인덱스 생성 실패: %s", e)
    return coll


def get_account_targets(account_id: str) -> list[dict[str, Any]]:
    """해당 계좌의 목표 포트폴리오를 반환합니다."""
    account_norm = (account_id or "").strip().lower()
    if not account_norm:
        return []

    coll = _get_collection()
    if coll is None:
        return []

    try:
        docs = list(coll.find({"account_id": account_norm}, {"_id": 0}))
        results = []
        for doc in docs:
            doc.pop("created_at", None)
            doc.pop("updated_at", None)
            results.append(doc)
        return results
    except Exception as exc:
        logger.error("account_targets 조회 실패 (account=%s): %s", account_norm, exc)
        return []


def save_account_targets(account_id: str, items: list[dict[str, Any]]) -> None:
    """해당 계좌의 목표 포트폴리오를 저장합니다. 전달되지 않은 티커는 Hard delete 처리됩니다."""
    account_norm = (account_id or "").strip().lower()
    if not account_norm:
        raise ValueError("account_id가 필요합니다.")

    coll = _get_collection()
    if coll is None:
        raise RuntimeError("MongoDB 연결 실패 — account_targets 컬렉션에 쓸 수 없습니다.")

    now = datetime.now(timezone.utc)
    new_tickers = set()
    operations = []

    for item in items:
        ticker = str(item.get("ticker", "")).strip().upper()
        if not ticker:
            continue
        new_tickers.add(ticker)

        doc = dict(item)
        doc["account_id"] = account_norm
        doc["ticker"] = ticker
        ratio = doc.get("ratio", 0)
        try:
            doc["ratio"] = float(ratio)
        except (ValueError, TypeError):
            doc["ratio"] = 0.0

        doc["updated_at"] = now

        operations.append(
            UpdateOne(
                {"account_id": account_norm, "ticker": ticker},
                {"$set": doc, "$setOnInsert": {"created_at": now}},
                upsert=True,
            )
        )

    if operations:
        try:
            coll.bulk_write(operations, ordered=False)
        except Exception as exc:
            logger.error("account_targets bulk_write 실패 (account=%s): %s", account_norm, exc)
            raise

    # 목록에 없는 종목 Hard delete (사용자 요청: 마스터에서 관리되므로 매핑은 바로 삭제)
    try:
        coll.delete_many(
            {"account_id": account_norm, "ticker": {"$nin": list(new_tickers)}}
        )
    except Exception as exc:
        logger.warning("account_targets 잔여 종목 hard delete 실패 (account=%s): %s", account_norm, exc)

    logger.info("%d개 종목이 %s 계좌의 목표 포트폴리오에 저장되었습니다.", len(new_tickers), account_norm)
