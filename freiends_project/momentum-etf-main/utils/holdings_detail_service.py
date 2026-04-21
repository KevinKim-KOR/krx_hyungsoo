"""계좌 상세 — 전체 계좌의 보유 종목을 한 테이블로 반환한다."""

from __future__ import annotations

import math
from typing import Any

from config import BUCKET_MAPPING
from services.price_service import get_exchange_rates
from utils.account_stocks_io import get_account_targets, save_account_targets
from utils.account_registry import load_account_configs
from utils.assets_service import load_cash_accounts
from utils.logger import get_app_logger
from utils.portfolio_io import load_portfolio_master, load_real_holdings_table, save_portfolio_master

logger = get_app_logger()


def _normalize_target_ticker(ticker: str) -> str:
    return str(ticker or "").replace("ASX:", "").strip().upper()


def _assign_sort_order(holdings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """보유 종목 배열에 순서를 다시 부여한다."""
    normalized_holdings: list[dict[str, Any]] = []
    for index, holding in enumerate(holdings):
        next_holding = dict(holding)
        next_holding["sort_order"] = index
        normalized_holdings.append(next_holding)
    return normalized_holdings


def _compute_account_total_assets_native(
    rows: list[dict[str, Any]],
    cash_info: dict[str, Any] | None,
    account_currency: str,
    rates: dict[str, Any],
) -> float:
    total_valuation_krw = sum(float(row.get("valuation_krw") or 0.0) for row in rows)
    currency = str(account_currency or "KRW").strip().upper() or "KRW"
    cash_info = cash_info or {}

    if currency == "KRW":
        return total_valuation_krw + float(cash_info.get("cash_balance_krw") or 0.0)

    if currency == "AUD":
        aud_rate = float(((rates or {}).get("AUD") or {}).get("rate") or 0.0)
        if aud_rate <= 0:
            raise RuntimeError("AUD 환율을 가져오지 못했습니다.")
        cash_native = cash_info.get("cash_balance_native")
        if cash_native in (None, ""):
            cash_native = float(cash_info.get("cash_balance_krw") or 0.0) / aud_rate
        return (total_valuation_krw / aud_rate) + float(cash_native or 0.0)

    return total_valuation_krw


def _compute_target_quantity(target_amount: float, current_price: float, currency: str) -> float | int | None:
    if current_price <= 0:
        return None
    quantity = target_amount / current_price
    currency_code = str(currency or "KRW").strip().upper()
    if currency_code == "AUD":
        return round(quantity, 4)
    return max(math.floor(quantity), 0)


def _apply_target_metrics(
    rows: list[dict[str, Any]],
    account_id: str,
    cash_info: dict[str, Any] | None,
    account_currency: str,
    rates: dict[str, Any],
) -> list[dict[str, Any]]:
    if not account_id:
        return rows

    target_items = get_account_targets(account_id)
    if not rows:
        return rows

    target_map = {
        _normalize_target_ticker(str(item.get("ticker") or "")): float(item.get("ratio") or 0.0)
        for item in target_items
    }
    account_total_assets = _compute_account_total_assets_native(rows, cash_info, account_currency, rates)

    enriched_rows: list[dict[str, Any]] = []
    for row in rows:
        target_ratio = target_map.get(_normalize_target_ticker(str(row.get("ticker") or "")))
        next_row = dict(row)
        next_row["target_ratio"] = target_ratio
        if target_ratio is None:
            next_row["target_amount"] = None
            next_row["target_quantity"] = None
        else:
            target_amount = round(account_total_assets * (target_ratio / 100.0), 2)
            next_row["target_amount"] = target_amount
            next_row["target_quantity"] = _compute_target_quantity(
                target_amount,
                float(next_row.get("current_price_num") or 0.0),
                account_currency,
            )
        enriched_rows.append(next_row)
    return enriched_rows


def _save_target_ratio(account_id: str, ticker: str, target_ratio: float | None) -> None:
    normalized_account_id = str(account_id or "").strip().lower()
    normalized_ticker = _normalize_target_ticker(ticker)
    if not normalized_account_id or not normalized_ticker:
        raise RuntimeError("계좌 ID와 종목코드가 필요합니다.")

    targets = get_account_targets(normalized_account_id)
    remaining_items: list[dict[str, Any]] = []
    found = False

    for item in targets:
        item_ticker = _normalize_target_ticker(str(item.get("ticker") or ""))
        if item_ticker == normalized_ticker:
            found = True
            if target_ratio is not None and target_ratio > 0:
                next_item = dict(item)
                next_item["ticker"] = normalized_ticker
                next_item["ratio"] = target_ratio
                remaining_items.append(next_item)
            continue
        remaining_items.append(dict(item))

    if not found and target_ratio is not None and target_ratio > 0:
        remaining_items.append({"ticker": normalized_ticker, "ratio": target_ratio})

    save_account_targets(normalized_account_id, remaining_items)


def load_all_holdings_detail(account_id: str | None = None) -> dict[str, Any]:
    """모든 계좌 또는 특정 계좌의 보유 종목을 반환한다."""
    all_accounts = load_account_configs()
    rates = get_exchange_rates()
    cash_data = load_cash_accounts()
    cash_accounts = cash_data.get("accounts", [])
    cash_map = {
        str(account.get("account_id") or ""): account
        for account in cash_accounts
        if isinstance(account, dict)
    }

    target_id = str(account_id or "").strip()
    if target_id.upper() == "TOTAL":
        target_id = ""

    # target_id가 비어있으면 모든 계좌를 순회하며 데이터를 수집함
    all_rows: list[dict[str, Any]] = []
    account_summaries: list[dict[str, Any]] = []
    selected_account_currency = "KRW"
    selected_cash_info: dict[str, Any] | None = None

    for account in all_accounts:
        curr_account_id = str(account["account_id"])

        # 필터링: account_id가 있으면 해당 계좌만, 없으면 전체
        if target_id and curr_account_id != target_id:
            continue

        account_name = str(account.get("name") or curr_account_id)

        try:
            df = load_real_holdings_table(
                curr_account_id,
                preloaded_exchange_rates=rates,
            )
        except Exception as exc:
            logger.warning("holdings 로드 실패 (%s): %s", curr_account_id, exc)
            continue

        if df is None or df.empty:
            continue

        settings = account.get("settings") or {}
        country_code = str(settings.get("country_code") or "").strip().lower()
        currency = str(settings.get("currency") or "KRW").strip().upper()
        cash_info = cash_map.get(curr_account_id)
        if curr_account_id == target_id:
            selected_account_currency = currency
            selected_cash_info = cash_info

        account_rows: list[dict[str, Any]] = []

        for _, row in df.iterrows():
            ticker_raw = str(row.get("티커") or "").strip()
            row_currency = str(row.get("환종") or currency).strip().upper()

            # 종목코드 포맷: 호주는 ASX:TICKER
            if country_code == "au" and ticker_raw != "IS":
                display_ticker = f"ASX:{ticker_raw}"
            else:
                display_ticker = ticker_raw

            bucket_id = int(row.get("bucket_id") or 0)
            bucket_name = BUCKET_MAPPING.get(bucket_id, f"{bucket_id}. Bucket")

            avg_price = float(row.get("평균 매입가") or 0)
            current_price = float(row.get("현재가") or 0)
            # NaN/None 방어 로직 추가
            def safe_int(val):
                import pandas as pd
                if pd.isna(val) or val is None:
                    return 0
                try:
                    return int(float(val))
                except (ValueError, TypeError):
                    return 0

            quantity = safe_int(row.get("수량"))
            buy_amount = safe_int(row.get("매입금액(KRW)"))
            val_amount = safe_int(row.get("평가금액(KRW)"))
            pnl = safe_int(row.get("평가손익(KRW)"))
            ret_pct = float(row.get("수익률(%)") or 0)

            # 현지 통화 가격 포맷
            price_prefix = ""
            if row_currency == "AUD":
                price_prefix = "A$"
            elif row_currency == "USD":
                price_prefix = "$"

            account_rows.append(
                {
                    "account_id": curr_account_id,
                    "account_name": account_name,
                    "currency": row_currency,
                    "bucket": bucket_name,
                    "bucket_id": bucket_id,
                    "ticker": display_ticker,
                    "name": str(row.get("종목명") or ""),
                    "quantity": quantity,
                    "average_buy_price": f"{price_prefix}{avg_price:,.4f}" if price_prefix else f"{avg_price:,.0f}원",
                    "current_price": f"{price_prefix}{current_price:,.2f}"
                    if price_prefix
                    else f"{current_price:,.0f}원",
                    "current_price_num": current_price,
                    "days_held": str(row.get("보유일", "-")),
                    "pnl_krw": pnl,
                    "pnl_krw_num": pnl,
                    "return_pct": round(ret_pct, 2),
                    "weight_pct": float(row.get("weight_pct") or 0),
                    "daily_change_pct": float(row.get("일간(%)") or 0) if row.get("일간(%)") is not None else None,
                    "buy_amount_krw": buy_amount,
                    "valuation_krw": val_amount,
                    "memo": str(row.get("memo") or "").strip(),
                    "sort_order": safe_int(row.get("sort_order")),
                }
            )

        account_rows = _apply_target_metrics(
            account_rows,
            account_id=curr_account_id,
            cash_info=cash_info,
            account_currency=currency,
            rates=rates,
        )
        all_rows.extend(account_rows)

        valuation_krw = sum(float(row.get("valuation_krw") or 0.0) for row in account_rows)
        cash_balance_krw = float((cash_info or {}).get("cash_balance_krw") or 0.0)
        # 호주 계좌: cash_balance_krw가 0이고 cash_balance_native가 있으면 환율 적용하여 KRW 환산
        if cash_balance_krw == 0.0 and currency == "AUD":
            cash_native = float((cash_info or {}).get("cash_balance_native") or 0.0)
            if cash_native > 0:
                aud_rate = float(((rates or {}).get("AUD") or {}).get("rate") or 0.0)
                if aud_rate > 0:
                    cash_balance_krw = round(cash_native * aud_rate, 2)
        cash_target_ratio = float((cash_info or {}).get("cash_target_ratio") or 0.0)
        target_ratio_total = sum(float(row.get("target_ratio") or 0.0) for row in account_rows) + cash_target_ratio
        account_summaries.append(
            {
                "account_id": curr_account_id,
                "order": int(account["order"]),
                "name": account_name,
                "account_url": str(settings.get("URL") or "").strip() or None,
                "icon": str(account.get("icon") or ""),
                "currency": currency,
                "total_principal": float((cash_info or {}).get("total_principal") or 0.0),
                "cash_balance_krw": cash_balance_krw,
                "cash_balance_native": (cash_info or {}).get("cash_balance_native"),
                "cash_currency": str((cash_info or {}).get("cash_currency") or currency).strip().upper(),
                "cash_target_ratio": cash_target_ratio,
                "intl_shares_value": (cash_info or {}).get("intl_shares_value"),
                "intl_shares_change": (cash_info or {}).get("intl_shares_change"),
                "updated_at": (cash_info or {}).get("updated_at"),
                "valuation_krw": valuation_krw,
                "total_assets_krw": valuation_krw + cash_balance_krw,
                "holdings_count": len([r for r in account_rows if str(r.get("ticker") or "") != "IS"]),
                "target_ratio_total": target_ratio_total,
            }
        )

    if target_id:
        account_summaries = [row for row in account_summaries if str(row.get("account_id") or "") == target_id]

    return {
        "accounts": [
            *[
                {
                    "account_id": a["account_id"],
                    "name": a["name"],
                    "icon": a["icon"],
                }
                for a in all_accounts
            ]
        ],
        "account_id": target_id,
        "cash": selected_cash_info,
        "rows": all_rows,
        "account_summaries": sorted(account_summaries, key=lambda row: int(row.get("order") or 0)),
    }


def delete_holding(account_id: str, ticker: str) -> dict[str, str]:
    """계좌에서 특정 종목을 삭제한다."""
    account_id = str(account_id or "").strip()
    ticker = str(ticker or "").strip()
    if not account_id or not ticker:
        raise RuntimeError("계좌 ID와 종목코드가 필요합니다.")

    # ASX: 접두어 제거
    raw_ticker = ticker.replace("ASX:", "")

    master = load_portfolio_master(account_id)
    if not master:
        raise RuntimeError("계좌 데이터를 찾을 수 없습니다.")

    holdings = master.get("holdings", [])
    new_holdings = [h for h in holdings if str(h.get("ticker", "")).strip() != raw_ticker]

    if len(new_holdings) == len(holdings):
        raise RuntimeError(f"종목 {ticker}을 찾을 수 없습니다.")

    save_portfolio_master(account_id, _assign_sort_order(new_holdings))
    _save_target_ratio(account_id, raw_ticker, None)
    
    # 변경 사항을 스냅샷에 즉시 동기화
    try:
        from utils.snapshot_service import update_today_snapshot_all_accounts
        update_today_snapshot_all_accounts()
    except Exception as e:
        from utils.logger import get_app_logger
        get_app_logger().warning(f"Failed to update snapshot after deletion: {e}")

    return {"deleted": ticker}


def update_holding(
    account_id: str,
    ticker: str,
    quantity: int | None = None,
    average_buy_price: float | None = None,
    memo: str | None = None,
    target_ratio: float | None = None,
) -> dict[str, str]:
    """계좌의 특정 종목 수량/매입단가를 수정한다."""
    account_id = str(account_id or "").strip()
    ticker = str(ticker or "").strip()
    if not account_id or not ticker:
        raise RuntimeError("계좌 ID와 종목코드가 필요합니다.")

    raw_ticker = ticker.replace("ASX:", "")

    master = load_portfolio_master(account_id)
    if not master:
        raise RuntimeError("계좌 데이터를 찾을 수 없습니다.")

    holdings = master.get("holdings", [])
    found = False
    for h in holdings:
        if str(h.get("ticker", "")).strip() == raw_ticker:
            if quantity is not None:
                h["quantity"] = int(quantity)
            if average_buy_price is not None:
                h["average_buy_price"] = float(average_buy_price)
            if memo is not None:
                h["memo"] = str(memo).strip()
            found = True
            break

    if not found:
        raise RuntimeError(f"종목 {ticker}을 찾을 수 없습니다.")

    save_portfolio_master(account_id, _assign_sort_order(holdings))
    if target_ratio is not None:
        _save_target_ratio(account_id, raw_ticker, float(target_ratio))
    
    # 변경 사항을 스냅샷에 즉시 동기화
    try:
        from utils.snapshot_service import update_today_snapshot_all_accounts
        update_today_snapshot_all_accounts()
    except Exception as e:
        from utils.logger import get_app_logger
        get_app_logger().warning(f"Failed to update snapshot after update: {e}")

    return {"updated": ticker}


def add_holding(
    account_id: str,
    ticker: str,
    quantity: int,
    average_buy_price: float,
    memo: str | None = None,
    target_ratio: float | None = None,
) -> dict[str, Any]:
    """계좌에 새로운 종목을 추가한다."""
    account_id = str(account_id or "").strip()
    ticker = str(ticker or "").strip()

    if not account_id or not ticker:
        raise RuntimeError("계좌 ID와 종목코드가 필요합니다.")

    # 1. 티커 검증 및 상세 메타데이터 가져오기 (종목명, 버킷 등)
    res = validate_ticker_for_account(account_id, ticker)
    raw_ticker = res["ticker"]

    # 2. 계좌 설정에서 통화 정보 가져오기
    from utils.settings_loader import get_account_settings
    try:
        settings = get_account_settings(account_id)
        currency = settings.get("currency", "KRW")
    except Exception:
        currency = "KRW"

    master = load_portfolio_master(account_id)
    if not master:
        raise RuntimeError("계좌 데이터를 찾을 수 없습니다.")

    holdings = master.get("holdings", [])

    # 중복 확인
    for h in holdings:
        if str(h.get("ticker", "")).strip() == raw_ticker:
            raise RuntimeError(f"종목 {ticker}은 이미 등록되어 있습니다.")

    # 3. 정석적인 구조로 새로운 종목 구성
    from datetime import datetime
    next_sort_order = max((int(h.get("sort_order") or 0) for h in holdings), default=-1) + 1
    new_holding = {
        "ticker": raw_ticker,
        "name": res["name"],
        "quantity": int(quantity),
        "average_buy_price": float(average_buy_price),
        "currency": currency,
        "first_buy_date": datetime.now().strftime("%Y-%m-%d"),
        "memo": str(memo or "").strip(),
        "sort_order": next_sort_order,
    }

    holdings.append(new_holding)
    save_portfolio_master(account_id, _assign_sort_order(holdings))
    if target_ratio is not None:
        _save_target_ratio(account_id, raw_ticker, float(target_ratio))

    # 변경 사항을 스냅샷에 즉시 동기화
    try:
        from utils.snapshot_service import update_today_snapshot_all_accounts
        update_today_snapshot_all_accounts()
    except Exception as e:
        from utils.logger import get_app_logger
        get_app_logger().warning(f"Failed to update snapshot after addition: {e}")

    return {"added": ticker, "name": res["name"]}


def reorder_holdings(account_id: str, ordered_tickers: list[str]) -> dict[str, Any]:
    """계좌 보유 종목의 사용자 지정 순서를 저장한다."""
    normalized_account_id = str(account_id or "").strip()
    if not normalized_account_id:
        raise RuntimeError("계좌 ID가 필요합니다.")

    normalized_tickers = [_normalize_target_ticker(ticker) for ticker in ordered_tickers]
    normalized_tickers = [ticker for ticker in normalized_tickers if ticker]
    if not normalized_tickers:
        raise RuntimeError("정렬할 종목코드가 필요합니다.")

    master = load_portfolio_master(normalized_account_id)
    if not master:
        raise RuntimeError("계좌 데이터를 찾을 수 없습니다.")

    holdings = [dict(holding) for holding in (master.get("holdings") or [])]
    if not holdings:
        raise RuntimeError("정렬할 종목이 없습니다.")

    holding_map = {
        _normalize_target_ticker(str(holding.get("ticker") or "")): holding
        for holding in holdings
    }
    missing_tickers = [ticker for ticker in normalized_tickers if ticker not in holding_map]
    if missing_tickers:
        joined = ", ".join(missing_tickers)
        raise RuntimeError(f"순서를 저장할 종목을 찾을 수 없습니다: {joined}")

    ordered_holdings: list[dict[str, Any]] = []
    seen: set[str] = set()
    for ticker in normalized_tickers:
        if ticker in seen:
            continue
        ordered_holdings.append(holding_map[ticker])
        seen.add(ticker)

    for holding in holdings:
        ticker = _normalize_target_ticker(str(holding.get("ticker") or ""))
        if ticker not in seen:
            ordered_holdings.append(holding)

    save_portfolio_master(normalized_account_id, _assign_sort_order(ordered_holdings))

    try:
        from utils.snapshot_service import update_today_snapshot_all_accounts

        update_today_snapshot_all_accounts()
    except Exception as e:
        from utils.logger import get_app_logger

        get_app_logger().warning(f"Failed to update snapshot after reorder: {e}")

    return {"reordered": len(ordered_holdings)}


def validate_ticker_for_account(account_id: str, ticker: str) -> dict[str, Any]:
    """계좌에 추가할 수 있는 유효한 티커인지 검증한다."""
    account_id = str(account_id or "").strip()
    ticker = str(ticker or "").strip().upper()

    if not account_id or not ticker:
        raise RuntimeError("계좌 ID와 종목코드가 필요합니다.")

    # ASX: 접두어 제거
    raw_ticker = ticker.replace("ASX:", "").strip().upper()
    if not raw_ticker:
        raise RuntimeError("유효한 티커를 입력하세요.")

    from utils.settings_loader import get_account_settings
    from utils.stocks_service import validate_stock_candidate

    # 1. 계좌 설정 로드 (zaccounts/ 하위의 실제 설정 파일 읽기)
    try:
        settings = get_account_settings(account_id)
        # account_settings["settings"]가 아닌 top-level에 있는 경우가 많음
        inner_settings = settings.get("settings") or settings
    except Exception as e:
        raise RuntimeError(f"계좌 설정을 찾을 수 없습니다: {account_id} ({e})")

    # 2. 계좌의 ticker_types 목록 추출 (실제 필드명인 'ticker_codes' 사용)
    ticker_types = settings.get("ticker_codes") or []
    
    if isinstance(ticker_types, str):
        ticker_types = [ticker_types]

    if not ticker_types:
        available_keys = list(settings.keys())
        raise RuntimeError(f"계좌 설정({account_id})에서 'ticker_codes'를 찾을 수 없습니다. (Keys: {available_keys})")

    # 3. 기존 "종목 추가" 모달과 동일한 검증 엔진 사용
    last_error = None
    validated_res = None
    
    for tt in ticker_types:
        try:
            # StocksManager가 사용하는 동일한 함수 호출
            validated_res = validate_stock_candidate(tt, ticker)
            break # 성공하면 루프 중단
        except Exception as e:
            last_error = str(e)
            continue

    if not validated_res:
        raise RuntimeError(last_error or f"등록되지 않은 종목입니다: {ticker}")

    return {
        "ticker": validated_res["ticker"],
        "name": validated_res["name"],
        "bucket_id": validated_res.get("bucket_id") or 1,
        "status": "success"
    }
