"""주별 데이터의 float 필드를 소수점 2자리로 마이그레이션한다.

1. 백업(20260329)에서 원본 버킷 값 복원
2. 소수점 2자리로 round
3. 버킷 합계 100% 보정:
   - 2025-08-01: 배당방어에서 초과분 차감
   - 나머지: 현금에 부족분 추가
"""
from __future__ import annotations

import datetime
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.db_manager import get_db_connection

WEEKLY_COLLECTION = "weekly_fund_data"
BACKUP_COLLECTION = "weekly_fund_data_backup_20260329_195900"

BUCKET_KEYS = [
    "bucket_pct_momentum",
    "bucket_pct_market",
    "bucket_pct_dividend",
    "bucket_pct_alternative",
    "bucket_pct_cash",
]

OTHER_FLOAT_KEYS = [
    "exchange_rate",
]


def migrate():
    db = get_db_connection()
    if db is None:
        print("DB 연결 실패")
        return

    backup_docs = {doc["week_date"]: doc for doc in db[BACKUP_COLLECTION].find()}
    current_docs = list(db[WEEKLY_COLLECTION].find().sort("week_date", 1))

    # 1단계: 백업에서 원본 복원 + 소수점 2자리 round + 100% 보정
    updated = 0
    for doc in current_docs:
        week_date = doc["week_date"]
        set_fields: dict[str, float] = {}

        # 백업이 있으면 원본 버킷 값 기준, 없으면 현재 값 기준
        source = backup_docs.get(week_date, doc)
        raw = {k: float(source.get(k, 0) or 0) for k in BUCKET_KEYS}
        rounded = {k: round(v, 2) for k, v in raw.items()}
        rounded_sum = round(sum(rounded.values()), 2)

        if rounded_sum > 0:
            diff = round(100.0 - rounded_sum, 2)
            if diff != 0:
                if week_date == "2025-08-01":
                    # 배당방어에서 초과분 차감
                    rounded["bucket_pct_dividend"] = round(rounded["bucket_pct_dividend"] + diff, 2)
                else:
                    # 현금에 부족분 추가
                    rounded["bucket_pct_cash"] = round(rounded["bucket_pct_cash"] + diff, 2)

        for k in BUCKET_KEYS:
            cur_val = float(doc.get(k, 0) or 0)
            if cur_val != rounded[k]:
                set_fields[k] = rounded[k]

        # exchange_rate round
        for k in OTHER_FLOAT_KEYS:
            cur_val = float(doc.get(k, 0) or 0)
            new_val = round(float(source.get(k, 0) or 0), 2)
            if cur_val != new_val:
                set_fields[k] = new_val

        if not set_fields:
            continue

        db[WEEKLY_COLLECTION].update_one(
            {"week_date": week_date},
            {"$set": set_fields},
        )
        updated += 1
        final_vals = [rounded.get(k, float(doc.get(k, 0) or 0)) for k in BUCKET_KEYS]
        final_sum = round(sum(final_vals), 2)
        print(f"  {week_date}: 합계={final_sum}%  변경={list(set_fields.keys())}")

    print(f"\n완료: {updated}/{len(current_docs)}건 업데이트")

    # 2단계: 새 백업 생성
    now = datetime.datetime.now(ZoneInfo("Asia/Seoul"))
    backup_name = f"weekly_fund_data_backup_{now.strftime('%Y%m%d_%H%M%S')}"
    all_docs = list(db[WEEKLY_COLLECTION].find())
    for d in all_docs:
        d.pop("_id", None)
    db[backup_name].insert_many(all_docs)
    print(f"\n백업 생성: {backup_name} ({len(all_docs)}건)")


if __name__ == "__main__":
    migrate()
