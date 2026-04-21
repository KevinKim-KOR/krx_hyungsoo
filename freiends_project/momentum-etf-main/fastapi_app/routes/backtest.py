from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from fastapi_app.dependencies import require_internal_token
from utils.backtest_service import (
    delete_backtest_config,
    list_backtest_configs,
    load_backtest_config,
    run_backtest,
    save_backtest_config,
    validate_backtest_ticker,
)

router = APIRouter(prefix="/internal/backtest", tags=["backtest"])


class BacktestTickerPayload(BaseModel):
    ticker: str
    name: str | None = None
    listing_date: str | None = None


class BacktestGroupPayload(BaseModel):
    group_id: str | None = None
    name: str
    weight: int
    tickers: list[BacktestTickerPayload]


class BacktestSavePayload(BaseModel):
    name: str
    period_months: int
    slippage_pct: float = 0.5
    benchmark: BacktestTickerPayload | None = None
    groups: list[BacktestGroupPayload]
    rebalance_freq: str = "monthly"


class BacktestValidatePayload(BaseModel):
    ticker: str
    country_code: str = "kor"


class BacktestDeletePayload(BaseModel):
    config_id: str


class BacktestRunPayload(BaseModel):
    period_months: int
    slippage_pct: float = 0.5
    benchmark: BacktestTickerPayload | None = None
    groups: list[BacktestGroupPayload]
    country_code: str = "kor"
    rebalance_freq: str = "monthly"


@router.get("")
def get_backtest_configs(
    config_id: str | None = Query(default=None),
    _: None = Depends(require_internal_token),
) -> dict[str, Any]:
    if config_id:
        return load_backtest_config(config_id)
    return list_backtest_configs()


@router.post("")
def post_backtest_config(payload: BacktestSavePayload, _: None = Depends(require_internal_token)) -> dict[str, Any]:
    return save_backtest_config(
        payload.name,
        payload.period_months,
        payload.slippage_pct,
        payload.benchmark.model_dump() if payload.benchmark else None,
        [group.model_dump() for group in payload.groups],
        payload.rebalance_freq,
    )


@router.post("/run")
def post_run_backtest(payload: BacktestRunPayload, _: None = Depends(require_internal_token)) -> dict[str, Any]:
    return run_backtest(
        period_months=payload.period_months,
        slippage_pct=payload.slippage_pct,
        benchmark=payload.benchmark.model_dump() if payload.benchmark else None,
        groups=[group.model_dump() for group in payload.groups],
        country_code=payload.country_code,
        rebalance_freq=payload.rebalance_freq,
    )


@router.post("/validate")
def post_validate_backtest_ticker(
    payload: BacktestValidatePayload, _: None = Depends(require_internal_token)
) -> dict[str, Any]:
    return validate_backtest_ticker(payload.ticker, payload.country_code)


@router.delete("")
def delete_backtest(payload: BacktestDeletePayload, _: None = Depends(require_internal_token)) -> dict[str, Any]:
    return delete_backtest_config(payload.config_id)


@router.post("/delete")
def post_delete_backtest(payload: BacktestDeletePayload, _: None = Depends(require_internal_token)) -> dict[str, Any]:
    return delete_backtest_config(payload.config_id)
