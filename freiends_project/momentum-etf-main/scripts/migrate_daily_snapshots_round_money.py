"""daily_snapshots의 KRW 금액 필드를 정수 반올림으로 마이그레이션한다."""

from __future__ import annotations

import datetime
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.db_manager import get_db_connection

SNAPSHOT_COLLECTION = "daily_snapshots"
SNAPSHOT_MONEY_FIELDS = (
    "total_assets",
    "total_principal",
    "cash_balance",
    "valuation_krw",
    "purchase_amount",
)


def _round_money(value: object) -> int:
    try:
        return int(round(float(value or 0)))
    except (TypeError, ValueError):
        return 0


def _needs_round_migration(value: object, rounded: int) -> bool:
    if isinstance(value, bool):
        return True
    return value != rounded or not isinstance(value, int)


def _build_backup_collection_name() -> str:
    now = datetime.datetime.now(ZoneInfo("Asia/Seoul"))
    return f"{SNAPSHOT_COLLECTION}_backup_{now.strftime('%Y%m%d_%H%M%S')}"


def migrate() -> None:
    db = get_db_connection()
    if db is None:
        print("DB 연결 실패")
        return

    source_docs = list(db[SNAPSHOT_COLLECTION].find().sort("snapshot_date", 1))
    if not source_docs:
        print("대상 스냅샷이 없습니다.")
        return

    backup_name = _build_backup_collection_name()
    backup_docs = []
    for doc in source_docs:
        copied = dict(doc)
        copied.pop("_id", None)
        backup_docs.append(copied)
    db[backup_name].insert_many(backup_docs)
    print(f"백업 생성: {backup_name} ({len(backup_docs)}건)")

    updated = 0
    for doc in source_docs:
        set_fields: dict[str, object] = {}

        for field in SNAPSHOT_MONEY_FIELDS:
            if field in doc:
                rounded = _round_money(doc.get(field))
                if _needs_round_migration(doc.get(field), rounded):
                    set_fields[field] = rounded

        current_accounts = doc.get("accounts") or []
        next_accounts: list[dict[str, object]] = []
        accounts_changed = False
        for account in current_accounts:
            if not isinstance(account, dict):
                next_accounts.append(account)
                continue

            next_account = dict(account)
            account_changed = False
            for field in SNAPSHOT_MONEY_FIELDS:
                if field in next_account:
                    rounded = _round_money(next_account.get(field))
                    if _needs_round_migration(next_account.get(field), rounded):
                        next_account[field] = rounded
                        account_changed = True
            if account_changed:
                accounts_changed = True
            next_accounts.append(next_account)

        if accounts_changed:
            set_fields["accounts"] = next_accounts

        if not set_fields:
            continue

        db[SNAPSHOT_COLLECTION].update_one({"_id": doc["_id"]}, {"$set": set_fields})
        updated += 1
        print(f"  {doc.get('snapshot_date')}: 변경={sorted(set_fields.keys())}")

    print(f"완료: {updated}/{len(source_docs)}건 업데이트")


if __name__ == "__main__":
    migrate()
