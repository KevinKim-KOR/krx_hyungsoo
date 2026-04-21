from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from fastapi_app.dependencies import require_internal_token
from utils.note_service import load_note_page_data, save_note_page_data

router = APIRouter(prefix="/internal/note", tags=["note"])


class NoteSavePayload(BaseModel):
    account_id: str
    content: str


@router.get("")
def get_note_data(
    account_id: str | None = Query(default=None),
    _: None = Depends(require_internal_token),
) -> dict[str, Any]:
    return load_note_page_data(account_id)


@router.patch("")
def patch_note_data(payload: NoteSavePayload, _: None = Depends(require_internal_token)) -> dict[str, str]:
    return save_note_page_data(payload.account_id, payload.content)
