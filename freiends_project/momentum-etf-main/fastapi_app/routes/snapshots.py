from __future__ import annotations

from fastapi import APIRouter, Depends

from fastapi_app.dependencies import require_internal_token
from utils.snapshot_service import load_snapshot_list

router = APIRouter(prefix="/internal/snapshots", tags=["snapshots"])


@router.get("")
def get_snapshot_list(_: None = Depends(require_internal_token)) -> dict[str, object]:
    return {"snapshots": load_snapshot_list()}
