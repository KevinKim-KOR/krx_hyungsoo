from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from fastapi_app.dependencies import require_internal_token
from utils.system_service import (
    BatchAlreadyRunningError,
    SystemAction,
    load_system_data,
    trigger_system_action,
)

router = APIRouter(prefix="/internal/system", tags=["system"])


class SystemActionRequest(BaseModel):
    action: SystemAction


@router.get("")
def get_system_data(_: None = Depends(require_internal_token)) -> dict[str, object]:
    return load_system_data()


@router.post("")
def post_system_action(payload: SystemActionRequest, _: None = Depends(require_internal_token)) -> dict[str, str]:
    try:
        return {"message": trigger_system_action(payload.action)}
    except BatchAlreadyRunningError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
