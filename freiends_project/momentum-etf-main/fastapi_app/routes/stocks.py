from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from fastapi_app.dependencies import require_internal_token
from utils.stocks_service import (
    add_active_stock,
    delete_active_stock as delete_active_stock_entry,
    hard_delete_stocks,
    load_active_stocks_table,
    load_deleted_stocks_table,
    refresh_single_stock,
    restore_deleted_stocks,
    update_stock_bucket,
    validate_stock_candidate,
)

router = APIRouter(prefix="/internal/stocks", tags=["stocks"])


class BucketUpdatePayload(BaseModel):
    ticker_type: str
    ticker: str
    bucket_id: int


class StockDeletePayload(BaseModel):
    ticker_type: str
    ticker: str


class DeletedStocksPayload(BaseModel):
    ticker_type: str
    tickers: list[str]


class StockRefreshPayload(BaseModel):
    ticker_type: str
    ticker: str


class StockValidationPayload(BaseModel):
    ticker_type: str
    ticker: str


class StockCreatePayload(BaseModel):
    ticker_type: str
    ticker: str
    bucket_id: int


@router.get("")
def get_active_stocks(
    ticker_type: str | None = Query(default=None),
    _: None = Depends(require_internal_token),
) -> dict[str, object]:
    return load_active_stocks_table(ticker_type)


@router.patch("")
def patch_active_stock(payload: BucketUpdatePayload, _: None = Depends(require_internal_token)) -> dict[str, bool]:
    update_stock_bucket(payload.ticker_type, payload.ticker, payload.bucket_id)
    return {"ok": True}


@router.delete("")
def delete_active_stock(payload: StockDeletePayload, _: None = Depends(require_internal_token)) -> dict[str, bool]:
    delete_active_stock_entry(payload.ticker_type, payload.ticker)
    return {"ok": True}


@router.post("/refresh")
def post_refresh_stock(payload: StockRefreshPayload, _: None = Depends(require_internal_token)) -> dict[str, str]:
    return refresh_single_stock(payload.ticker_type, payload.ticker)


@router.post("/validate")
def post_validate_stock(
    payload: StockValidationPayload, _: None = Depends(require_internal_token)
) -> dict[str, object]:
    return validate_stock_candidate(payload.ticker_type, payload.ticker)


@router.post("")
def post_active_stock(payload: StockCreatePayload, _: None = Depends(require_internal_token)) -> dict[str, object]:
    return add_active_stock(payload.ticker_type, payload.ticker, payload.bucket_id)


@router.get("/deleted")
def get_deleted_stocks(
    ticker_type: str | None = Query(default=None),
    _: None = Depends(require_internal_token),
) -> dict[str, object]:
    return load_deleted_stocks_table(ticker_type)


@router.patch("/deleted")
def patch_deleted_stocks(
    payload: DeletedStocksPayload, _: None = Depends(require_internal_token)
) -> dict[str, int | bool]:
    restored_count = restore_deleted_stocks(payload.ticker_type, payload.tickers)
    return {"ok": True, "restored_count": restored_count}


@router.delete("/deleted")
def delete_deleted_stocks(
    payload: DeletedStocksPayload, _: None = Depends(require_internal_token)
) -> dict[str, int | bool]:
    deleted_count = hard_delete_stocks(payload.ticker_type, payload.tickers)
    return {"ok": True, "deleted_count": deleted_count}
