"""선택 ETF / 시장지수 일별 가격 시계열 read-only API (POC3-02 REMEDIATION-1
+ POC3-01 오늘의 투자 점검 대시보드 KOSPI 시계열 확장).

기존 SQLite 에 저장된 시계열을 그대로 반환한다 — 신규 수집·산식·source 없음.
- ETF ticker (기본): `etf_daily_price` (`fetch_price_history`).
- 시장지수 benchmark (`?benchmark=KOSPI` 등): `market_benchmark_daily_price`
  (`fetch_benchmark_history`). POC3-01 코스피 대표 차트용 (설계자 Q1-a 확정 —
  기존 엔드포인트 확장, 신규 전용 API·market_topn 혼합 금지).

계약 (지시문 §6 + POC3-01):
- 저장된 값만 반환 (조정주가·보간·예측 없음).
- 날짜 오름차순 (fetch_price_history / fetch_benchmark_history 가 date ASC).
- ticker/benchmark 형식 오류 / 저장 데이터 없음(NO_DATA) / 내부 조회 실패
  (UNAVAILABLE) 구분.
- 내부 파일 경로·SQL·stack trace 미노출.
- 신규 DB·테이블·schema·source·cache 없음. 기존 ETF ticker 호출 계약 불변.
"""

from __future__ import annotations

import re
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.market_benchmark_store import fetch_benchmark_history
from app.market_data_store import DEFAULT_DB_PATH as MARKET_DB_PATH
from app.market_data_store import fetch_price_history

router = APIRouter()

# KRX ETF ticker: 6자 영숫자 (예: 069500, 0000D0). 형식 오류와 "정상 형식인데
# 데이터 없음" 을 구분. 실제 etf_daily_price 에 영숫자 ticker 가 다수 존재하므로
# 6자리 숫자만 허용하면 유효 종목을 거부하게 된다.
_TICKER_RE = re.compile(r"^[0-9A-Za-z]{6}$")

# 허용된 시장지수 benchmark (market_benchmark_daily_price.benchmark_id).
# 저장된 지수만 노출 — 임의 benchmark_id 조회를 막는다 (KOSPI 코스피 대표 차트).
_ALLOWED_BENCHMARKS = {"KOSPI"}


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


def _series_response(label: str, rows) -> PriceSeriesResponse:
    """(date, close) rows → PriceSeriesResponse. rows 는 date ASC 저장값 그대로."""
    if not rows:
        return PriceSeriesResponse(
            ticker=label,
            availability="NO_DATA",
            reason="no_stored_data",
        )
    series = [PricePoint(date=d, price=c) for (d, c) in rows]
    return PriceSeriesResponse(
        ticker=label,
        availability="AVAILABLE",
        available_from=series[0].date,
        available_to=series[-1].date,
        series=series,
    )


@router.get("/market/price-series", response_model=PriceSeriesResponse)
def get_price_series(ticker: str = "", benchmark: str = "") -> PriceSeriesResponse:
    """선택 ticker / 시장지수 benchmark 의 저장된 일별 가격 시계열 (read-only).

    - benchmark 파라미터가 있으면 시장지수 시계열 (KOSPI 등) 을 반환한다
      (POC3-01 코스피 대표 차트). 허용 benchmark 만 조회.
    - 없으면 기존대로 선택 ticker 시계열 (frontend lazy · 기존 계약 불변).
    """
    bm = (benchmark or "").strip().upper()
    if bm:
        # 시장지수 benchmark 분기 (POC3-01). 허용 목록 밖은 형식 오류로 구분.
        if bm not in _ALLOWED_BENCHMARKS:
            return PriceSeriesResponse(
                ticker=bm,
                availability="UNAVAILABLE",
                reason="invalid_benchmark",
            )
        try:
            rows = fetch_benchmark_history(bm, db_path=MARKET_DB_PATH)
        except Exception:  # noqa: BLE001 — 내부 오류를 raw 로 노출하지 않는다.
            return PriceSeriesResponse(
                ticker=bm,
                availability="UNAVAILABLE",
                reason="read_failure",
            )
        return _series_response(bm, rows)

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

    return _series_response(tk, rows)
