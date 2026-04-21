from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from services.price_service import get_exchange_rates
from utils.db_manager import get_db_connection
from utils.portfolio_io import load_portfolio_master


def main() -> None:
    db = get_db_connection()
    if db is None:
        raise RuntimeError("DB 연결 실패")

    rates = get_exchange_rates()
    aud_rate = float(((rates or {}).get("AUD") or {}).get("rate") or 0.0)
    master = load_portfolio_master("aus_account") or {}
    native_cash = float(master.get("cash_balance_native") or 0.0)
    stored_cash = float(master.get("cash_balance") or 0.0)

    print("[호주 스냅샷 현금 감사]")
    print(f"- 현재 AUD/KRW 환율: {aud_rate:,.6f}")
    print(f"- 현재 마스터 cash_balance(KRW): {stored_cash:,.0f}")
    print(f"- 현재 마스터 cash_balance_native(AUD): {native_cash:,.4f}")
    if aud_rate > 0 and native_cash > 0:
        print(f"- 오늘 스냅샷 예상 현금(KRW): {native_cash * aud_rate:,.3f}")
    else:
        print("- 오늘 스냅샷 예상 현금(KRW): 계산 불가")

    print("")
    print("[과거 스냅샷]")
    print("date | stored_cash_krw | total_assets_krw | valuation_krw | holding_count | has_IS | exact_diff")

    for doc in db.daily_snapshots.find({}, {"snapshot_date": 1, "accounts": 1}).sort("snapshot_date", 1):
        snapshot_date = str(doc.get("snapshot_date") or "")
        aus_account = None
        for account in doc.get("accounts") or []:
            if account.get("account_id") == "aus_account":
                aus_account = account
                break
        if not aus_account:
            continue

        holdings = aus_account.get("holdings") or []
        has_is = any(str(holding.get("ticker") or "") == "IS" for holding in holdings)

        exact_diff = "계산불가(native 미저장)"
        print(
            f"{snapshot_date} | "
            f"{float(aus_account.get('cash_balance') or 0.0):,.0f} | "
            f"{float(aus_account.get('total_assets') or 0.0):,.0f} | "
            f"{float(aus_account.get('valuation_krw') or 0.0):,.0f} | "
            f"{len(holdings)} | "
            f"{'Y' if has_is else 'N'} | "
            f"{exact_diff}"
        )


if __name__ == "__main__":
    main()
