from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from fastapi_app.dependencies import require_internal_token
from utils.assets_service import load_cash_accounts, save_cash_accounts

router = APIRouter(prefix="/internal/cash", tags=["cash"])


class CashSavePayload(BaseModel):
    accounts: list[dict[str, Any]]


@router.get("")
def get_cash_accounts(_: None = Depends(require_internal_token)) -> dict[str, Any]:
    return load_cash_accounts()


@router.post("")
def post_cash_accounts(payload: CashSavePayload, _: None = Depends(require_internal_token)) -> dict[str, str]:
    return save_cash_accounts(payload.accounts)
