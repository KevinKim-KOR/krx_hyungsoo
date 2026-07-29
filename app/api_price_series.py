"""선택 ETF 일별 가격 시계열 read-only API (POC3-02 REMEDIATION-1).

기존 SQLite (etf_daily_price) 에 저장된 선택 ticker 의 일별 가격을 그대로 반환한다.
`app.market_data_store.fetch_price_history` 재사용 — 신규 수집·산식·source 없음.

계약 (지시문 §6):
- 저장된 값만 반환 (조정주가·보간·예측 없음).
- 날짜 오름차순 (fetch_price_history 가 date ASC).
- ticker 형식 오류 / 저장 데이터 없음(NO_DATA) / 내부 조회 실패(UNAVAILABLE) 구분.
- 내부 파일 경로·SQL·stack trace 미노출.
- 신규 DB·테이블·schema·source·cache 없음.
"""

from __future__ import annotations

import re
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.market_data_store import DEFAULT_DB_PATH as MARKET_DB_PATH
from app.market_data_store import fetch_price_history

router = APIRouter()

# KRX ETF ticker: 6자 영숫자 (예: 069500, 0000D0). 형식 오류와 "정상 형식인데
# 데이터 없음" 을 구분. 실제 etf_daily_price 에 영숫자 ticker 가 다수 존재하므로
# 6자리 숫자만 허용하면 유효 종목을 거부하게 된다.
_TICKER_RE = re.compile(r"^[0-9A-Za-z]{6}$")


class PricePoint(BaseModel):
    date: str  # SQLite 저장 거래 기준일 (YYYY-MM-DD)
    price: float  # 기존 저장 종가 (close)


class PriceSeriesResponse(BaseModel):
    ticker: str
    # AVAILABLE: 저장 데이터 있음 / NO_DATA: 정상 형식이나 저장 데이터 없음 /
    # UNAVAILABLE: ticker 형식 오류 또는 내부 조회 실패.
    availability: str
    reason: Optional[str] = None
    available_from: Optional[str] = None  # 실제 반환 데이터 최초 기준일
    available_to: Optional[str] = None  # 실제 반환 데이터 최종 기준일
    series: list[PricePoint] = []


@router.get("/market/price-series", response_model=PriceSeriesResponse)
def get_price_series(ticker: str = "") -> PriceSeriesResponse:
    """선택 ticker 의 저장된 일별 가격 시계열 (read-only).

    사용자가 표에서 선택한 한 ticker 만 조회한다 (frontend lazy).
    """
    tk = (ticker or "").strip()

    # ticker 형식 오류 → UNAVAILABLE (데이터 없음과 구분).
    if not tk or not _TICKER_RE.match(tk):
        return PriceSeriesResponse(
            ticker=tk,
            availability="UNAVAILABLE",
            reason="invalid_ticker",
        )

    # 내부 조회 실패(DB 손상 등) → UNAVAILABLE (raw 예외 미노출).
    try:
        rows = fetch_price_history(tk, db_path=MARKET_DB_PATH)
    except Exception:  # noqa: BLE001 — 내부 오류를 raw 로 노출하지 않는다.
        return PriceSeriesResponse(
            ticker=tk,
            availability="UNAVAILABLE",
            reason="read_failure",
        )

    # 정상 형식이나 저장 데이터 없음 → NO_DATA (빈 정상 차트 아님).
    if not rows:
        return PriceSeriesResponse(
            ticker=tk,
            availability="NO_DATA",
            reason="no_stored_data",
        )

    # rows 는 (date, close) date ASC. 저장값 그대로 (재계산 없음).
    series = [PricePoint(date=d, price=c) for (d, c) in rows]
    return PriceSeriesResponse(
        ticker=tk,
        availability="AVAILABLE",
        available_from=series[0].date,
        available_to=series[-1].date,
        series=series,
    )
