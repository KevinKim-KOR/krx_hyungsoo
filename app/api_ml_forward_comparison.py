"""GET /ml/forward-comparison — 06 전향 ML 비교 기록의 PC 읽기 전용 조회(POC6-14).

- 읽기 루트는 서버가 정한 06 연구 폴더 하나(`forward_compare_view.ROOT`) · 클라이언트가 경로 · cohort 를 고르지 못한다.
- `d`(YYYY-MM-DD) 생략 = 가장 최근 유효 주 기록 D · 형식 오류 422 · 유효 D 가 아니면 404.
- 쓰기 · 실행 · 학습 · 모델 열기 · 보고 생성 · SSH · 외부 조회 없음. 연구용 · 운영 미채택(추천 · 매매 아님).
"""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app import forward_compare_view as V

router = APIRouter()


class MlForwardComparisonResponse(BaseModel):
    status: str  # OK | NO_RECORDS | CHECK_REQUIRED | READ_FAILED
    label: str
    message: Optional[str] = None
    cohort: Optional[dict[str, Any]] = None
    dates: Optional[list[dict[str, Any]]] = None
    selected_D: Optional[str] = None
    basis: Optional[dict[str, Any]] = None
    rows: Optional[list[dict[str, Any]]] = None
    report: Optional[dict[str, Any]] = None
    other: Optional[dict[str, Any]] = None


@router.get("/ml/forward-comparison", response_model=MlForwardComparisonResponse)
def get_ml_forward_comparison(
    d: Optional[str] = Query(default=None, description="기준일 D(YYYY-MM-DD)"),
) -> MlForwardComparisonResponse:
    if d is not None:
        try:
            if date.fromisoformat(d).isoformat() != d:
                raise ValueError(d)
        except ValueError:
            raise HTTPException(status_code=422, detail="기준일 형식은 YYYY-MM-DD")
    try:
        body = V.build(V.ROOT, d)
    except V.DateNotFound:
        raise HTTPException(status_code=404, detail="선택한 기준일 기록 없음")
    return MlForwardComparisonResponse(**body)
