from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, Query

from fastapi_app.dependencies import require_internal_token
from utils.holdings_detail_service import (
    add_holding,
    delete_holding,
    load_all_holdings_detail,
    reorder_holdings,
    update_holding,
    validate_ticker_for_account,
)

router = APIRouter(prefix="/internal/holdings", tags=["holdings"])


@router.get("")
def get_all_holdings(
    account: str | None = Query(default=None),
    _: None = Depends(require_internal_token),
) -> dict[str, Any]:
    return load_all_holdings_detail(account_id=account)


@router.delete("")
def delete_one_holding(
    account: str = Query(...),
    ticker: str = Query(...),
    _: None = Depends(require_internal_token),
) -> dict[str, Any]:
    return delete_holding(account_id=account, ticker=ticker)


@router.patch("")
def patch_one_holding(
    body: dict[str, Any] = Body(...),
    _: None = Depends(require_internal_token),
) -> dict[str, Any]:
    return update_holding(
        account_id=body.get("account_id", ""),
        ticker=body.get("ticker", ""),
        quantity=body.get("quantity"),
        average_buy_price=body.get("average_buy_price"),
        memo=body.get("memo"),
        target_ratio=body.get("target_ratio"),
    )


@router.patch("/order")
def patch_holdings_order(
    body: dict[str, Any] = Body(...),
    _: None = Depends(require_internal_token),
) -> dict[str, Any]:
    return reorder_holdings(
        account_id=body.get("account_id", ""),
        ordered_tickers=body.get("ordered_tickers", []),
    )


@router.post("")
def post_one_holding(
    body: dict[str, Any] = Body(...),
    _: None = Depends(require_internal_token),
) -> dict[str, Any]:
    return add_holding(
        account_id=body.get("account_id", ""),
        ticker=body.get("ticker", ""),
        quantity=body.get("quantity", 0),
        average_buy_price=body.get("average_buy_price", 0),
        memo=body.get("memo"),
        target_ratio=body.get("target_ratio"),
    )


@router.post("/validate")
def validate_ticker(
    body: dict[str, Any] = Body(...),
    _: None = Depends(require_internal_token),
) -> dict[str, Any]:
    return validate_ticker_for_account(
        account_id=body.get("account_id", ""),
        ticker=body.get("ticker", ""),
    )
