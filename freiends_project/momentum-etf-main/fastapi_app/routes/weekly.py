from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, model_validator

from fastapi_app.dependencies import require_internal_token
from utils.weekly_service import aggregate_active_week_data, load_weekly_table_data, update_weekly_row

router = APIRouter(prefix="/internal/weekly", tags=["weekly"])


class WeeklyRowUpdatePayload(BaseModel):
    """주별 데이터 수정 페이로드. week_date 필수, 나머지는 FIELD_DEFS 기반 동적 필드."""

    model_config = {"extra": "allow"}

    week_date: str

    @model_validator(mode="after")
    def strip_week_date(self) -> WeeklyRowUpdatePayload:
        self.week_date = self.week_date.strip()
        if not self.week_date:
            raise ValueError("week_date는 필수입니다.")
        return self


@router.get("")
def get_weekly_data(_: None = Depends(require_internal_token)) -> dict[str, Any]:
    return load_weekly_table_data()


@router.post("")
def post_weekly_aggregate(_: None = Depends(require_internal_token)) -> dict[str, str]:
    return aggregate_active_week_data()


@router.patch("")
def patch_weekly_row(payload: WeeklyRowUpdatePayload, _: None = Depends(require_internal_token)) -> dict[str, str]:
    return update_weekly_row(payload.week_date, payload.model_dump())
