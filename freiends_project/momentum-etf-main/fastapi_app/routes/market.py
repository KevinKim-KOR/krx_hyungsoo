from __future__ import annotations

from fastapi import APIRouter, Depends

from fastapi_app.dependencies import require_internal_token
from utils.market_service import load_market_data

router = APIRouter(prefix="/internal/market", tags=["market"])


@router.get("")
def get_market_data(_: None = Depends(require_internal_token)) -> dict[str, object]:
    return load_market_data()


@router.get("/fx")
def get_fx_data(_: None = Depends(require_internal_token)) -> dict[str, object]:
    from services.price_service import get_exchange_rates

    return get_exchange_rates()


@router.get("/vkospi")
def get_vkospi_data(_: None = Depends(require_internal_token)) -> dict[str, object]:
    from services.vkospi_service import get_vkospi

    data = get_vkospi()
    if not data:
        return {"error": "VKOSPI 데이터를 가져올 수 없습니다."}
    return data


@router.get("/fear-greed")
def get_fear_greed_data(_: None = Depends(require_internal_token)) -> dict[str, object]:
    from services.fear_greed_service import get_fear_greed_summary

    data = get_fear_greed_summary()
    if not data:
        return {"error": "CNN 공포탐욕지수 데이터를 가져올 수 없습니다."}
    return data
