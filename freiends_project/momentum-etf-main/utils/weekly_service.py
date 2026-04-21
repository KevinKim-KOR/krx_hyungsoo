from __future__ import annotations

import datetime
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from services.price_service import get_exchange_rate_series
from utils.account_registry import load_account_configs
from utils.db_manager import get_db_connection
from utils.normalization import to_iso_string
from utils.portfolio_io import load_portfolio_master, load_real_holdings_table

WEEKLY_COLLECTION = "weekly_fund_data"
READ_ONLY_FIELDS = {
    "total_expense",
    "total_principal",
    "total_assets",
    "purchase_amount",
    "valuation_amount",
    "profit_loss",
    "cumulative_profit",
    "weekly_profit",
    "weekly_return_pct",
    "cumulative_return_pct",
    "exchange_rate",
    "bucket_pct_momentum",
    "bucket_pct_market",
    "bucket_pct_dividend",
    "bucket_pct_alternative",
    "bucket_pct_cash",
    "total_stocks",
    "profit_count",
    "loss_count",
}
CORE_VIEW_HIDDEN_KEYS = [
    "withdrawal_personal",
    "withdrawal_mom",
    "nh_principal_interest",
    "deposit_withdrawal",
]
KST = ZoneInfo("Asia/Seoul")
INITIAL_TOTAL_PRINCIPAL_DATE = "2024-01-31"
INITIAL_TOTAL_PRINCIPAL_VALUE = 56_000_000

FIELD_DEFS = [
    {"key": "withdrawal_personal", "label": "개인 인출", "type": "int"},
    {"key": "withdrawal_mom", "label": "엄마", "type": "int"},
    {"key": "nh_principal_interest", "label": "농협원리금", "type": "int"},
    {"key": "total_expense", "label": "지출 합계", "type": "int"},
    {"key": "deposit_withdrawal", "label": "입출금", "type": "int"},
    {"key": "total_principal", "label": "총 원금", "type": "int"},
    {"key": "total_assets", "label": "총 자산", "type": "int"},
    {"key": "purchase_amount", "label": "매입 금액", "type": "int"},
    {"key": "valuation_amount", "label": "평가 금액", "type": "int"},
    {"key": "profit_loss", "label": "평가 손익", "type": "int"},
    {"key": "cumulative_profit", "label": "누적 손익", "type": "int"},
    {"key": "weekly_profit", "label": "금주 손익", "type": "int"},
    {"key": "weekly_return_pct", "label": "주수익률 (%)", "type": "float"},
    {"key": "cumulative_return_pct", "label": "누적 수익률 (%)", "type": "float"},
    {"key": "memo", "label": "비고", "type": "text"},
    {"key": "exchange_rate", "label": "환율", "type": "float"},
    {"key": "bucket_pct_momentum", "label": "1. 모멘텀 (%)", "type": "float"},
    {"key": "bucket_pct_market", "label": "2. 시장지수 (%)", "type": "float"},
    {"key": "bucket_pct_dividend", "label": "3. 배당방어 (%)", "type": "float"},
    {"key": "bucket_pct_alternative", "label": "4. 대체헷지 (%)", "type": "float"},
    {"key": "bucket_pct_cash", "label": "5. 현금 (%)", "type": "float"},
    {"key": "total_stocks", "label": "총 종목 수", "type": "int"},
    {"key": "profit_count", "label": "수익 종목 수", "type": "int"},
    {"key": "loss_count", "label": "손실 종목 수", "type": "int"},
]


def _require_db():
    db = get_db_connection()
    if db is None:
        raise RuntimeError("DB 연결 실패")
    return db


def _get_now_kst() -> datetime.datetime:
    """한국 시간 기준 현재 시각을 반환한다."""
    return datetime.datetime.now(KST)


def _get_active_week_date() -> str:
    """활성 주차 기준일을 YYYY-MM-DD 형식으로 반환한다."""
    now = _get_now_kst()
    this_week_monday = now.date() - datetime.timedelta(days=now.weekday())
    this_week_friday = this_week_monday + datetime.timedelta(days=4)

    # 다음 주 월요일 09:00 전까지는 지난 금요일 행을 유지한다.
    if now.weekday() == 0 and now.time() < datetime.time(hour=9):
        active_friday = this_week_friday - datetime.timedelta(days=7)
    else:
        active_friday = this_week_friday

    return active_friday.strftime("%Y-%m-%d")


def _format_week_date_display(date_str: str) -> str:
    """YYYY-MM-DD → 'YYYY. M. D (요일)' 형식으로 변환."""
    weekday_kr = ["월", "화", "수", "목", "금", "토", "일"]
    dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
    return f"{dt.year}. {dt.month}. {dt.day} ({weekday_kr[dt.weekday()]})"


def _new_empty_doc(week_date: str) -> dict[str, Any]:
    """빈 주별 데이터 문서를 생성한다."""
    now = _get_now_kst()
    return {
        "week_date": week_date,
        "withdrawal_personal": 0,
        "withdrawal_mom": 0,
        "nh_principal_interest": 0,
        "deposit_withdrawal": 0,
        "total_assets": 0,
        "purchase_amount": 0,
        "valuation_amount": 0,
        "memo": "",
        "exchange_rate": 0.0,
        "bucket_pct_momentum": 0.0,
        "bucket_pct_market": 0.0,
        "bucket_pct_dividend": 0.0,
        "bucket_pct_alternative": 0.0,
        "bucket_pct_cash": 0.0,
        "profit_count": 0,
        "loss_count": 0,
        "created_at": now,
        "updated_at": now,
    }


def _normalize_bucket_percentages(source: dict[str, Any]) -> dict[str, float]:
    """구버전 5버킷 데이터를 현재 4버킷 구조로 정규화한다."""
    momentum = _to_float(source.get("bucket_pct_momentum", 0.0))
    innovation = _to_float(source.get("bucket_pct_innovation", 0.0))
    market = _to_float(source.get("bucket_pct_market", 0.0))
    dividend = _to_float(source.get("bucket_pct_dividend", 0.0))
    alternative = _to_float(source.get("bucket_pct_alternative", 0.0))
    cash = _to_float(source.get("bucket_pct_cash", 0.0))
    return {
        "bucket_pct_momentum": momentum + innovation,
        "bucket_pct_market": market,
        "bucket_pct_dividend": dividend,
        "bucket_pct_alternative": alternative,
        "bucket_pct_cash": cash,
    }


def _calculate_total_expense(source: dict[str, Any]) -> int:
    """지출 합계를 계산한다."""
    return (
        _to_int(source.get("withdrawal_personal", 0))
        + _to_int(source.get("withdrawal_mom", 0))
        + _to_int(source.get("nh_principal_interest", 0))
    )


def _calculate_profit_loss(source: dict[str, Any]) -> int:
    """평가 손익을 계산한다."""
    valuation_amount = _to_int(source.get("valuation_amount", 0))
    purchase_amount = _to_int(source.get("purchase_amount", 0))
    return valuation_amount - purchase_amount


def _calculate_total_stocks(source: dict[str, Any]) -> int:
    """총 종목 수를 계산한다."""
    return _to_int(source.get("profit_count", 0)) + _to_int(source.get("loss_count", 0))


def _to_int(value: object) -> int:
    """숫자/빈값을 정수로 정규화한다."""
    return int(float(value or 0))


def _to_float(value: object) -> float:
    """숫자/빈값을 실수로 정규화한다."""
    return float(value or 0.0)


def _get_live_exchange_rate() -> float:
    """현재 시점의 USD/KRW 환율을 반환한다."""
    now = pd.Timestamp(_get_now_kst()).tz_localize(None)
    series = get_exchange_rate_series(now - pd.Timedelta(days=5), now)
    if series.empty:
        return 0.0
    return float(series.iloc[-1])


def _ensure_historical_exchange_rates() -> None:
    """과거 주차의 누락 환율을 일괄 조회해 저장한다."""
    db = _require_db()

    active_week_date = _get_active_week_date()
    target_docs = list(
        db[WEEKLY_COLLECTION]
        .find(
            {
                "week_date": {"$ne": active_week_date},
                "$or": [{"exchange_rate": {"$exists": False}}, {"exchange_rate": 0}, {"exchange_rate": 0.0}],
            },
            {"week_date": 1},
        )
        .sort("week_date", 1)
    )
    if not target_docs:
        return

    start_date = target_docs[0]["week_date"]
    end_date = target_docs[-1]["week_date"]
    rate_series = get_exchange_rate_series(
        pd.Timestamp(start_date) - pd.Timedelta(days=7),
        pd.Timestamp(end_date),
    )
    if rate_series.empty:
        return

    week_dates = [pd.Timestamp(doc["week_date"]) for doc in target_docs]
    aligned_rates = rate_series.reindex(pd.DatetimeIndex(week_dates), method="ffill")
    now = _get_now_kst()

    for doc, rate in zip(target_docs, aligned_rates.tolist(), strict=True):
        if pd.isna(rate):
            continue
        db[WEEKLY_COLLECTION].update_one(
            {"week_date": doc["week_date"]},
            {
                "$set": {
                    "exchange_rate": float(rate),
                    "updated_at": now,
                }
            },
        )


def _apply_derived_fields(source: dict[str, Any]) -> dict[str, Any]:
    """계산 컬럼 값을 반영한 사본을 반환한다."""
    updated = dict(source)
    updated["total_expense"] = _calculate_total_expense(updated)
    updated["profit_loss"] = _calculate_profit_loss(updated)
    updated["total_stocks"] = _calculate_total_stocks(updated)
    return updated


def _apply_running_total_principal(docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """총 원금, 손익, 수익률을 날짜 오름차순 기준으로 계산해 최신순으로 반환한다."""
    docs_by_date = {str(doc["week_date"]): _apply_derived_fields(doc) for doc in docs}
    running_total = INITIAL_TOTAL_PRINCIPAL_VALUE
    running_total_expense = 0
    previous_cumulative_profit = 0

    for week_date in sorted(docs_by_date):
        doc = docs_by_date[week_date]
        if week_date <= INITIAL_TOTAL_PRINCIPAL_DATE:
            doc["total_principal"] = INITIAL_TOTAL_PRINCIPAL_VALUE
        else:
            running_total += _to_int(doc.get("deposit_withdrawal", 0))
            doc["total_principal"] = running_total

        running_total_expense += _to_int(doc.get("total_expense", 0))
        doc["cumulative_profit"] = (
            _to_int(doc.get("total_assets", 0)) - _to_int(doc.get("total_principal", 0)) - running_total_expense
        )
        doc["weekly_profit"] = _to_int(doc.get("cumulative_profit", 0)) - previous_cumulative_profit
        total_principal = _to_int(doc.get("total_principal", 0))
        if total_principal == 0:
            doc["weekly_return_pct"] = 0.0
            doc["cumulative_return_pct"] = 0.0
        else:
            doc["weekly_return_pct"] = round((_to_int(doc.get("weekly_profit", 0)) / total_principal) * 100, 2)
            doc["cumulative_return_pct"] = round((_to_int(doc.get("cumulative_profit", 0)) / total_principal) * 100, 2)
        previous_cumulative_profit = _to_int(doc.get("cumulative_profit", 0))

    return [
        docs_by_date[str(doc["week_date"])] for doc in sorted(docs, key=lambda item: item["week_date"], reverse=True)
    ]


def _ensure_active_week_row() -> str:
    """활성 주차 데이터가 없으면 빈 행을 생성한다 (upsert로 중복 방지)."""
    db = _require_db()
    active_week_date = _get_active_week_date()
    db[WEEKLY_COLLECTION].update_one(
        {"week_date": active_week_date},
        {"$setOnInsert": _new_empty_doc(active_week_date)},
        upsert=True,
    )
    return active_week_date


def _doc_to_api_row(doc: dict[str, Any]) -> dict[str, Any]:
    """MongoDB 문서를 Node UI용 행 스키마로 변환한다."""
    computed_doc = _apply_derived_fields(doc)
    exchange_rate = _to_float(computed_doc.get("exchange_rate", 0.0))
    bucket_percentages = _normalize_bucket_percentages(computed_doc)

    return {
        "week_date": str(computed_doc["week_date"]),
        "week_date_display": _format_week_date_display(str(computed_doc["week_date"])),
        "withdrawal_personal": _to_int(computed_doc.get("withdrawal_personal", 0)),
        "withdrawal_mom": _to_int(computed_doc.get("withdrawal_mom", 0)),
        "nh_principal_interest": _to_int(computed_doc.get("nh_principal_interest", 0)),
        "total_expense": _to_int(computed_doc.get("total_expense", 0)),
        "deposit_withdrawal": _to_int(computed_doc.get("deposit_withdrawal", 0)),
        "total_principal": _to_int(computed_doc.get("total_principal", 0)),
        "total_assets": _to_int(computed_doc.get("total_assets", 0)),
        "purchase_amount": _to_int(computed_doc.get("purchase_amount", 0)),
        "valuation_amount": _to_int(computed_doc.get("valuation_amount", 0)),
        "profit_loss": _to_int(computed_doc.get("profit_loss", 0)),
        "cumulative_profit": _to_int(computed_doc.get("cumulative_profit", 0)),
        "weekly_profit": _to_int(computed_doc.get("weekly_profit", 0)),
        "weekly_return_pct": round(float(computed_doc.get("weekly_return_pct", 0.0) or 0.0), 2),
        "cumulative_return_pct": round(float(computed_doc.get("cumulative_return_pct", 0.0) or 0.0), 2),
        "memo": str(computed_doc.get("memo", "") or ""),
        "exchange_rate": round(exchange_rate, 2),
        "exchange_rate_change_pct": 0.0,
        **{k: round(v, 2) for k, v in bucket_percentages.items()},
        "total_stocks": _to_int(computed_doc.get("total_stocks", 0)),
        "profit_count": _to_int(computed_doc.get("profit_count", 0)),
        "loss_count": _to_int(computed_doc.get("loss_count", 0)),
        "updated_at": to_iso_string(computed_doc.get("updated_at")),
    }


def _build_api_rows(docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Node UI와 동일한 응답 행 리스트를 생성한다."""
    rows = [_doc_to_api_row(doc) for doc in docs]
    for idx, row in enumerate(rows):
        current_rate = float(row.get("exchange_rate", 0.0) or 0.0)
        older_rate = float(rows[idx + 1].get("exchange_rate", 0.0) or 0.0) if idx + 1 < len(rows) else 0.0
        if older_rate > 0:
            row["exchange_rate_change_pct"] = round(((current_rate / older_rate) - 1.0) * 100, 2)
        else:
            row["exchange_rate_change_pct"] = 0.0
    return rows


def _load_weekly_docs() -> list[dict[str, Any]]:
    """MongoDB에서 주별 데이터 원본 문서 리스트를 최신순으로 반환한다."""
    db = _require_db()
    docs = list(db[WEEKLY_COLLECTION].find().sort("week_date", -1))
    return _apply_running_total_principal(docs)


def _aggregate_live_summary_into_active_week() -> str:
    """기존 Python 주별 집계 규칙으로 활성 주차 1행을 갱신한다."""
    db = _require_db()

    active_week_date = _get_active_week_date()
    total_assets = 0.0
    total_purchase = 0.0
    total_valuation = 0.0
    total_cash = 0.0
    total_profit_count = 0
    total_loss_count = 0
    live_exchange_rate = _get_live_exchange_rate()
    bucket_totals = {
        "1. 모멘텀": 0.0,
        "2. 시장지수": 0.0,
        "3. 배당방어": 0.0,
        "4. 대체헷지": 0.0,
    }
    all_missing_tickers: list[str] = []

    for account in load_account_configs():
        if not account.get("settings", {}).get("show_hold", True):
            continue

        account_id = account["account_id"]
        master_data = load_portfolio_master(account_id)
        cash_balance = float(master_data.get("cash_balance", 0.0) if master_data else 0.0)
        total_cash += cash_balance

        holdings_df = load_real_holdings_table(account_id)
        if holdings_df is None or holdings_df.empty:
            account_purchase = 0.0
            account_valuation = 0.0
        else:
            missing = holdings_df.attrs.get("missing_price_tickers") or []
            if missing:
                all_missing_tickers.extend(missing)

            account_purchase = float(holdings_df["매입금액(KRW)"].sum())
            account_valuation = float(holdings_df["평가금액(KRW)"].sum())
            total_profit_count += int((holdings_df["평가손익(KRW)"] >= 0).sum())
            total_loss_count += int((holdings_df["평가손익(KRW)"] < 0).sum())
            for bucket_name in bucket_totals:
                bucket_totals[bucket_name] += float(
                    holdings_df.loc[holdings_df["버킷"] == bucket_name, "평가금액(KRW)"].sum()
                )

        total_assets += account_valuation + cash_balance
        total_purchase += account_purchase
        total_valuation += account_valuation

    if all_missing_tickers:
        joined = ", ".join(all_missing_tickers)
        raise RuntimeError(
            f"가격 캐시가 없는 종목이 있어 집계를 중단합니다: {joined}. "
            "종목 관리에서 해당 종목의 메타/캐시 새로고침을 실행하세요."
        )

    if total_assets > 0:
        bucket_raw = {
            "bucket_pct_momentum": (bucket_totals["1. 모멘텀"] / total_assets) * 100,
            "bucket_pct_market": (bucket_totals["2. 시장지수"] / total_assets) * 100,
            "bucket_pct_dividend": (bucket_totals["3. 배당방어"] / total_assets) * 100,
            "bucket_pct_alternative": (bucket_totals["4. 대체헷지"] / total_assets) * 100,
            "bucket_pct_cash": (total_cash / total_assets) * 100,
        }
        bucket_rounded = {k: round(v, 2) for k, v in bucket_raw.items()}
        diff = round(round(sum(bucket_raw.values()), 2) - sum(bucket_rounded.values()), 2)
        if diff != 0:
            largest = max(bucket_rounded, key=lambda k: bucket_rounded[k])
            bucket_rounded[largest] = round(bucket_rounded[largest] + diff, 2)
    else:
        bucket_rounded = {
            "bucket_pct_momentum": 0.0,
            "bucket_pct_market": 0.0,
            "bucket_pct_dividend": 0.0,
            "bucket_pct_alternative": 0.0,
            "bucket_pct_cash": 0.0,
        }

    db[WEEKLY_COLLECTION].update_one(
        {"week_date": active_week_date},
        {
            "$set": {
                "total_assets": int(round(total_assets)),
                "purchase_amount": int(round(total_purchase)),
                "valuation_amount": int(round(total_valuation)),
                "exchange_rate": round(float(live_exchange_rate), 2),
                **bucket_rounded,
                "profit_count": total_profit_count,
                "loss_count": total_loss_count,
                "updated_at": _get_now_kst(),
            },
            "$unset": {
                "bucket_pct_innovation": "",
            },
        },
        upsert=False,
    )
    return active_week_date


def load_weekly_table_data() -> dict[str, Any]:
    """주별 화면용 테이블 데이터를 반환한다."""
    active_week_date = _ensure_active_week_row()
    weekly_docs = _load_weekly_docs()
    return {
        "active_week_date": active_week_date,
        "rows": _build_api_rows(weekly_docs),
        "editable_fields": FIELD_DEFS,
        "read_only_keys": list(READ_ONLY_FIELDS),
        "core_hidden_keys": list(CORE_VIEW_HIDDEN_KEYS),
    }


def aggregate_active_week_data() -> dict[str, str]:
    """활성 주차 데이터를 집계해 저장한다."""
    _ensure_active_week_row()
    _ensure_historical_exchange_rates()
    active_week_date = _aggregate_live_summary_into_active_week()
    return {"week_date": active_week_date}


def update_weekly_row(week_date: str, payload: dict[str, Any]) -> dict[str, str]:
    """주별 수정 가능 필드를 저장한다."""
    target_week_date = str(week_date or "").strip()
    if not target_week_date:
        raise RuntimeError("수정할 주차를 찾을 수 없습니다.")

    update_doc: dict[str, Any] = {}
    for field in FIELD_DEFS:
        key = field["key"]
        if key in READ_ONLY_FIELDS or key not in payload:
            continue

        raw_value = payload[key]
        if field["type"] == "text":
            update_doc[key] = str(raw_value or "").strip()
            continue

        try:
            numeric_value = float(raw_value or 0)
        except (TypeError, ValueError) as exc:
            raise RuntimeError(f"{field['label']} 값이 올바르지 않습니다.") from exc

        if field["type"] == "int":
            update_doc[key] = int(numeric_value)
        else:
            update_doc[key] = round(numeric_value, 4)

    update_doc["updated_at"] = _get_now_kst()

    db = _require_db()
    result = db[WEEKLY_COLLECTION].update_one(
        {"week_date": target_week_date},
        {"$set": update_doc},
    )
    if result.matched_count == 0:
        raise RuntimeError("수정할 주별 데이터를 찾지 못했습니다.")

    return {"week_date": target_week_date}
