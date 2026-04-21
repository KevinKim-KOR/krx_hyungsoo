from __future__ import annotations

from fastapi import APIRouter, Depends

from fastapi_app.dependencies import require_internal_token
from utils.dashboard_service import load_dashboard_data

router = APIRouter(prefix="/internal/dashboard", tags=["dashboard"])


@router.get("")
def get_dashboard_data(_: None = Depends(require_internal_token)) -> dict[str, object]:
    return load_dashboard_data()
