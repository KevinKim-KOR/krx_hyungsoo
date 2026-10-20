"""POC6-01 — `GET /market/flow-context`(시장 흐름 · 수급 · 환율 · 유가 · 읽기 전용).

저장된 자료만 읽는다(외부 조회 0 · 표 생성 0 · 쓰기 0). 기간 4종(1 · 3 · 6개월 · 연초 이후)을 한 번에 담아
화면이 기간을 바꿔도 다시 조회하지 않는다. 문장 줄 · AI 전달문은 서버가 만든다(`app/supply_fx_oil_context.py`).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.market_data_store import DEFAULT_DB_PATH
from app.supply_fx_oil_context import build_market_flow_context

router = APIRouter(prefix="/market", tags=["market-flow"])
_DB_PATH: Path = DEFAULT_DB_PATH


class MarketFlowContextResponse(BaseModel):
    generated_at: str
    D: Optional[str]
    has_flows: bool
    series: dict[str, Any]
    periods: dict[str, Any]
    windows: dict[str, Any]
    short_lines: list[dict[str, Any]]
    events: list[dict[str, Any]]
    event_check: dict[str, Any]
    interpretation: dict[str, Any]
    limits: list[str]
    status: list[dict[str, Any]]
    today_lines: list[str]
    ai_text: dict[str, str]


@router.get("/flow-context", response_model=MarketFlowContextResponse)
def get_market_flow_context() -> MarketFlowContextResponse:
    return MarketFlowContextResponse(**build_market_flow_context(db_path=_DB_PATH))
