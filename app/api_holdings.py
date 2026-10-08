"""GET/PUT /holdings — app/api.py 에서 옮긴 보유 조회 · 입력 정정 저장(POC5-05 개정 2 · 설계 §11-1 Q-D).

- URL · 기존 5필드(ticker · quantity · avg_buy_price · name · account_group) 의미는 그대로.
- 응답에 revision · status(NO_FILE / EMPTY / OK) · 줄 ID(position_id · cycle_id)가 더해졌다.
- PUT 은 '입력 정정 모드' 의 전체 목록 저장이다. 모든 PC 보유 쓰기와 같은 저장 경계
  (holdings_store)를 지나며, 수량 · 평단을 직접 고친 것은 매매가 아니라 입력 정정으로
  기록된다(app/holdings_history.save_full_list). 이력 문서에 revision 없는 요청은 409.
- POC3-08 (A) strict_ticker 검증 · POC2 Step 1 E항(검증 실패 = 422 · run 생성 없음) 유지.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.holdings_edit import current_holdings, save_full_list
from app.holdings_history import HistoryConflict, HistoryInputError
from app.holdings_store import DocumentCorrupt

router = APIRouter(tags=["holdings"])


class HoldingItem(BaseModel):
    ticker: str
    quantity: float
    avg_buy_price: float
    name: Optional[str] = None
    # POC2 Step 2C: 표시/그룹용 라벨. 누락/빈 값은 백엔드에서 "일반" 으로 정규화.
    account_group: Optional[str] = None
    # POC5-05: 보유 줄 · 보유 기간 ID(PC 전용 · OCI payload 에는 들어가지 않음).
    position_id: Optional[str] = None
    cycle_id: Optional[str] = None


class HoldingsPayload(BaseModel):
    holdings: list[HoldingItem]
    # POC5-05: 화면이 읽은 문서 revision · 저장 동작별 UUID(응답 유실 재시도용).
    revision: Optional[int] = None
    request_id: Optional[str] = None


class HoldingsResponse(BaseModel):
    holdings: list[HoldingItem]
    revision: int
    status: str


@router.get("/holdings", response_model=HoldingsResponse)
def get_holdings() -> dict:
    """현재 보유(줄 ID 포함) · revision · 상태. 파일 없으면 빈 목록 + NO_FILE. 쓰기 0."""
    try:
        return current_holdings()
    except (DocumentCorrupt, HistoryConflict) as e:
        # 손상 · 계산 불가는 빈 보유로 바꾸지 않고 알린다.
        raise HTTPException(status_code=500, detail=f"holdings 저장 파일 손상: {e}")


@router.put("/holdings", response_model=HoldingsResponse)
def put_holdings(payload: HoldingsPayload) -> dict:
    """입력 정정 모드 저장. 422 = 입력 오류 · 409 = 오래된 화면 · 충돌 · 500 = 파일 손상."""
    rows = [item.model_dump() for item in payload.holdings]
    try:
        return save_full_list(
            rows, revision=payload.revision, request_id=payload.request_id
        )
    except HistoryInputError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except HistoryConflict as e:
        raise HTTPException(status_code=409, detail=str(e))
    except DocumentCorrupt as e:
        raise HTTPException(status_code=500, detail=f"holdings 저장 파일 손상: {e}")
