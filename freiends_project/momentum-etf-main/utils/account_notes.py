"""계좌별 메모를 MongoDB에 저장하는 유틸리티."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from utils.db_manager import get_db_connection
from utils.logger import get_app_logger

logger = get_app_logger()

_COLLECTION_NAME = "account_notes"
_INDEX_ENSURED = False


def _get_collection():
    """account_notes 컬렉션 핸들을 반환하고 최초 호출 시 인덱스를 보장한다."""
    global _INDEX_ENSURED
    db = get_db_connection()
    if db is None:
        return None

    coll = db[_COLLECTION_NAME]
    if not _INDEX_ENSURED:
        try:
            coll.create_index([("account_id", 1)], unique=True, name="account_note_unique", background=True)
            _INDEX_ENSURED = True
        except Exception:
            pass
    return coll


def load_account_note(account_id: str) -> dict[str, Any] | None:
    """계좌 메모 최신본을 반환한다."""
    account_norm = (account_id or "").strip().lower()
    if not account_norm:
        raise ValueError("account_id가 필요합니다.")

    coll = _get_collection()
    if coll is None:
        raise RuntimeError("MongoDB 연결 실패 — account_notes 컬렉션을 읽을 수 없습니다.")

    doc = coll.find_one({"account_id": account_norm}, {"_id": 0})
    if not doc:
        return None
    return {
        "account_id": account_norm,
        "content": str(doc.get("content") or ""),
        "updated_at": doc.get("updated_at"),
    }


def save_account_note(account_id: str, content: str) -> datetime:
    """계좌 메모를 저장하고 갱신 시각을 반환한다."""
    account_norm = (account_id or "").strip().lower()
    if not account_norm:
        raise ValueError("account_id가 필요합니다.")

    coll = _get_collection()
    if coll is None:
        raise RuntimeError("MongoDB 연결 실패 — account_notes 컬렉션에 쓸 수 없습니다.")

    updated_at = datetime.now(timezone.utc)
    payload = {
        "account_id": account_norm,
        "content": str(content or ""),
        "updated_at": updated_at,
    }
    result = coll.update_one({"account_id": account_norm}, {"$set": payload}, upsert=True)
    if not result.acknowledged:
        raise RuntimeError(f"계좌 메모 저장이 확인되지 않았습니다: {account_norm}")

    logger.info("계좌 메모 저장 완료: %s", account_norm)
    return updated_at


__all__ = [
    "load_account_note",
    "save_account_note",
]
