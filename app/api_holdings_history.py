"""POC5-05 개정 2 — 매매 이력 로컬 API(PC). 설계 §5 · §8 · PLAN §2-4.

- GET  /holdings/trade-history              : position 별 보유 기간 · 기록 · 계산값(쓰기 0)
- PUT  /holdings/trade-history              : 통합 매매 명령(매수 · 매도 · 전량매도 · 새 보유 ·
                                              잔고 등록 · 정정 · 취소) → {record, holdings, revision}
- GET  /holdings/trade-history/market-flow  : 사용자가 누를 때만 · PC 시세 DB 읽기 전용 요약
- GET  /holdings/trade-history/reentry-review    : POC5-06 재진입 검토 창(내 거래 · 저장된 근거) ·
                                                  학습 · 외부 조회 · 쓰기 0
- POST /holdings/trade-history/reentry-review/ml : POC5-06 ML 연구 1회(선택 ETF · 고정 Ridge) →
                                                  PC 연구 산출물(state/ml/research/poc5_06/)

오류 detail 은 문자열이다(화면이 그대로 보여 준다): 422 입력 오류 · 409 충돌 · 404 없음 ·
500 파일 손상 · 시세 DB 조회 실패.
"""

from __future__ import annotations

import sqlite3
from typing import Optional

from fastapi import APIRouter, Body, HTTPException, Query

from app import holdings_history as history_module
from app import holdings_history_view as view_module
from app.holdings_history import HistoryConflict, HistoryInputError
from app.holdings_store import DocumentCorrupt

router = APIRouter(prefix="/holdings", tags=["holdings-trade-history"])


@router.get("/trade-history")
def get_trade_history(
    position_id: Optional[str] = Query(default=None, max_length=64),
) -> dict:
    try:
        return view_module.history(position_id)
    except (DocumentCorrupt, HistoryConflict) as e:
        raise HTTPException(
            status_code=500, detail=f"보유 · 이력 파일을 읽을 수 없습니다: {e}"
        )


@router.put("/trade-history")
def put_trade_history(payload: dict = Body(...)) -> dict:
    try:
        return history_module.apply_command(payload)
    except HistoryInputError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except HistoryConflict as e:
        raise HTTPException(status_code=409, detail=str(e))
    except DocumentCorrupt as e:
        raise HTTPException(
            status_code=500, detail=f"보유 · 이력 파일을 읽을 수 없습니다: {e}"
        )


@router.get("/trade-history/market-flow")
def get_market_flow(
    position_id: str = Query(..., max_length=64),
    cycle_id: str = Query(..., max_length=64),
) -> dict:
    from app import holdings_market_flow as flow

    try:
        ticker, cycle = view_module.market_flow_input(position_id, cycle_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except (DocumentCorrupt, HistoryConflict) as e:
        raise HTTPException(
            status_code=500, detail=f"보유 · 이력 파일을 읽을 수 없습니다: {e}"
        )
    try:
        return flow.build_market_flow(ticker=ticker, cycle=cycle)
    except (flow.MarketFlowReadError, sqlite3.Error) as e:
        raise HTTPException(status_code=500, detail=f"시세 DB 조회 실패: {e}")


_REVIEW_GONE = "보유가 바뀌었거나 없는 보유 기간입니다 — History 를 다시 여세요."


@router.get("/trade-history/reentry-review")
def get_reentry_review(
    position_id: str = Query(..., max_length=64),
    cycle_id: str = Query(..., max_length=64),
) -> dict:
    from app.reentry_review import review

    try:
        return review.build_review(position_id, cycle_id)
    except LookupError:
        raise HTTPException(status_code=404, detail=_REVIEW_GONE)
    except (DocumentCorrupt, HistoryConflict) as e:
        raise HTTPException(
            status_code=500, detail=f"보유 · 이력 파일을 읽을 수 없습니다: {e}"
        )
    except review.ReviewReadError as e:
        raise HTTPException(status_code=500, detail=f"시세 DB 조회 실패: {e}")


@router.post("/trade-history/reentry-review/ml")
def post_reentry_ml(payload: dict = Body(...)) -> dict:
    from app.reentry_review import review

    ids = [payload.get("position_id"), payload.get("cycle_id")]
    if not all(isinstance(v, str) and 0 < len(v) <= 64 for v in ids):
        raise HTTPException(
            status_code=422, detail="position_id · cycle_id 는 64자 이하 문자열입니다."
        )
    try:
        return review.run_ml(ids[0], ids[1])
    except LookupError:
        raise HTTPException(status_code=404, detail=_REVIEW_GONE)
    except (DocumentCorrupt, HistoryConflict) as e:
        raise HTTPException(
            status_code=500, detail=f"보유 · 이력 파일을 읽을 수 없습니다: {e}"
        )
    except review.ReviewReadError as e:
        raise HTTPException(status_code=500, detail=f"시세 DB 조회 실패: {e}")
    except review.ArtifactSaveError as e:
        raise HTTPException(status_code=500, detail=f"{e} — 결과를 보이지 않습니다.")
