from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.db_manager import get_db_connection


@dataclass
class MigrationStats:
    stock_meta_updated: int = 0
    portfolio_docs_updated: int = 0
    holdings_updated: int = 0
    weekly_docs_updated: int = 0


def remap_bucket_value(bucket: Any) -> Any:
    """구버전 5버킷 값을 4버킷 체계로 변환한다."""
    if bucket == 2:
        return 1
    if bucket == 3:
        return 2
    if bucket == 4:
        return 3
    if bucket == 5:
        return 4
    return bucket


def migrate_stock_meta(db: Any, stats: MigrationStats) -> None:
    """stock_meta 컬렉션의 bucket 값을 실제로 치환한다."""
    result = db.stock_meta.update_many(
        {"bucket": {"$in": [2, 3, 4, 5]}},
        [
            {
                "$set": {
                    "bucket": {
                        "$switch": {
                            "branches": [
                                {"case": {"$eq": ["$bucket", 2]}, "then": 1},
                                {"case": {"$eq": ["$bucket", 3]}, "then": 2},
                                {"case": {"$eq": ["$bucket", 4]}, "then": 3},
                                {"case": {"$eq": ["$bucket", 5]}, "then": 4},
                            ],
                            "default": "$bucket",
                        }
                    }
                }
            }
        ],
    )
    stats.stock_meta_updated = int(result.modified_count)


def migrate_portfolio_master(db: Any, stats: MigrationStats) -> None:
    """portfolio_master.accounts[].holdings[].bucket 값을 실제로 치환한다."""
    collection = db.portfolio_master
    cursor = collection.find(
        {"accounts.holdings.bucket": {"$in": [2, 3, 4, 5]}},
        {"accounts": 1},
    )

    for doc in cursor:
        accounts = doc.get("accounts") or []
        changed = False
        holdings_updated = 0

        for account in accounts:
            holdings = account.get("holdings") or []
            for holding in holdings:
                old_bucket = holding.get("bucket")
                new_bucket = remap_bucket_value(old_bucket)
                if new_bucket != old_bucket:
                    holding["bucket"] = new_bucket
                    holdings_updated += 1
                    changed = True

        if changed:
            collection.update_one({"_id": doc["_id"]}, {"$set": {"accounts": accounts}})
            stats.portfolio_docs_updated += 1
            stats.holdings_updated += holdings_updated


def migrate_weekly_fund_data(db: Any, stats: MigrationStats) -> None:
    """weekly_fund_data의 버킷 퍼센트를 실제 4버킷 체계로 치환한다."""
    collection = db.weekly_fund_data
    cursor = collection.find(
        {
            "$or": [
                {"bucket_pct_innovation": {"$exists": True}},
                {"bucket_pct_market": {"$exists": True}},
                {"bucket_pct_dividend": {"$exists": True}},
                {"bucket_pct_alternative": {"$exists": True}},
                {"bucket_pct_cash": {"$exists": True}},
            ]
        },
        {
            "bucket_pct_momentum": 1,
            "bucket_pct_innovation": 1,
            "bucket_pct_market": 1,
            "bucket_pct_dividend": 1,
            "bucket_pct_alternative": 1,
            "bucket_pct_cash": 1,
        },
    )

    for doc in cursor:
        momentum = float(doc.get("bucket_pct_momentum", 0.0) or 0.0)
        innovation = float(doc.get("bucket_pct_innovation", 0.0) or 0.0)
        market = float(doc.get("bucket_pct_market", 0.0) or 0.0)
        dividend = float(doc.get("bucket_pct_dividend", 0.0) or 0.0)
        alternative = float(doc.get("bucket_pct_alternative", 0.0) or 0.0)
        cash = float(doc.get("bucket_pct_cash", 0.0) or 0.0)

        collection.update_one(
            {"_id": doc["_id"]},
            {
                "$set": {
                    "bucket_pct_momentum": momentum + innovation,
                    "bucket_pct_market": market,
                    "bucket_pct_dividend": dividend,
                    "bucket_pct_alternative": alternative,
                    "bucket_pct_cash": cash,
                },
                "$unset": {
                    "bucket_pct_innovation": "",
                },
            },
        )
        stats.weekly_docs_updated += 1


def main() -> None:
    db = get_db_connection()
    if db is None:
        raise RuntimeError("MongoDB 연결에 실패했습니다.")

    stats = MigrationStats()
    migrate_stock_meta(db, stats)
    migrate_portfolio_master(db, stats)
    migrate_weekly_fund_data(db, stats)

    print(
        {
            "stock_meta_updated": stats.stock_meta_updated,
            "portfolio_docs_updated": stats.portfolio_docs_updated,
            "holdings_updated": stats.holdings_updated,
            "weekly_docs_updated": stats.weekly_docs_updated,
        }
    )


if __name__ == "__main__":
    main()
