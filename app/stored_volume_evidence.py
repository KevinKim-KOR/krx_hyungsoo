"""POC5-09 — 저장 거래량 확인 근거 (설계서 §3 · PLAN §2-1 · §7).

PC 시장 DB `etf_daily_price` 에 이미 저장된 거래량(주)만 읽어, 기준일 거래량을
바로 앞 20개 저장일 평균과 비교한 관찰값을 만든다. 새 수집 · 저장 · 외부 호출 없음.

정의(설계서 §3 · 판정 §9-2):
- 기준일 D = 그 종목의 최신 저장 가격 날짜(가격 흐름과 같은 행 조건). 거래량이
  없어도 더 오래된 날로 대신하지 않는다.
- 비교 창 = D 를 뺀 바로 앞 20개 저장 가격 날짜(달력 20일 아님). 창 밖 날로 메우지
  않는다.
- 유효 거래량 = 값 있음 · 유한수 · 0 이상(0 은 유효).
- 평균 = 창 20개가 모두 유효할 때만 산술 평균. 배수 = D 거래량 ÷ 평균.
- 배수 사유 우선순위: 기준일 거래량 없음 → 평균 자료 부족 → 평균 0 → 계산.

기존 `ml_feature_primitives.volume_ratio_20d` 는 기준일을 창에 넣고 0 을 빼므로
정의가 달라 쓰지 않는다(ML 특징값용 그대로).
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Literal, Optional, Union

from pydantic import BaseModel

from app.market_data_store import DEFAULT_DB_PATH, fetch_recent_price_rows

VOLUME_WINDOW = 20
# 기준일 1행 + 비교 창 20행.
VOLUME_ROWS_NEEDED = VOLUME_WINDOW + 1

RecentPriceRow = tuple[str, float, Optional[float], str]


class StoredVolumeEvidence(BaseModel):
    ticker: str
    # no_price_data = 저장 가격 행이 하나도 없음(나머지 칸은 비어 있음).
    status: Literal["ok", "no_price_data"]
    asof_date: Optional[str] = None
    source: Optional[str] = None
    # 저장값 그대로(보통 정수 · 주). 유효하지 않으면 null.
    volume: Optional[Union[int, float]] = None
    window_size: int = VOLUME_WINDOW
    window_start_date: Optional[str] = None
    window_end_date: Optional[str] = None
    window_date_count: int = 0
    valid_count: int = 0
    avg_prev20: Optional[float] = None
    avg_status: Literal["ok", "insufficient"] = "insufficient"
    ratio: Optional[float] = None
    ratio_status: Literal["ok", "volume_missing", "avg_insufficient", "avg_zero"] = (
        "volume_missing"
    )


def _valid_volume(v: object) -> bool:
    if v is None or isinstance(v, bool) or not isinstance(v, (int, float)):
        return False
    if isinstance(v, float) and not math.isfinite(v):
        return False
    return v >= 0


def compute_stored_volume_evidence(
    ticker: str, rows_desc: list[RecentPriceRow]
) -> StoredVolumeEvidence:
    """최신순 저장 가격 행 `(date, close, volume, source)` → 거래량 관찰값.

    rows_desc 는 `fetch_recent_price_rows(limit=VOLUME_ROWS_NEEDED)` 결과(또는 그
    앞부분 이상)여야 한다. 21번째 이후 행은 보지 않는다.
    """
    if not rows_desc:
        return StoredVolumeEvidence(ticker=ticker, status="no_price_data")

    d_date, _d_close, d_volume, d_source = rows_desc[0]
    window = rows_desc[1:VOLUME_ROWS_NEEDED]
    volume = d_volume if _valid_volume(d_volume) else None
    valid = [float(r[2]) for r in window if _valid_volume(r[2])]

    avg: Optional[float] = None
    if len(valid) == VOLUME_WINDOW:
        avg = math.fsum(valid) / VOLUME_WINDOW

    ratio: Optional[float] = None
    if volume is None:
        ratio_status = "volume_missing"
    elif avg is None:
        ratio_status = "avg_insufficient"
    elif avg == 0:
        ratio_status = "avg_zero"
    else:
        ratio_status = "ok"
        ratio = volume / avg

    return StoredVolumeEvidence(
        ticker=ticker,
        status="ok",
        asof_date=d_date,
        source=d_source,
        volume=volume,
        window_start_date=(window[-1][0] if window else None),
        window_end_date=(window[0][0] if window else None),
        window_date_count=len(window),
        valid_count=len(valid),
        avg_prev20=avg,
        avg_status=("ok" if avg is not None else "insufficient"),
        ratio=ratio,
        ratio_status=ratio_status,
    )


# POC5-19 — 「확인 근거」 종목 상세의 최근 저장일 거래량 흐름(PC 근거 응답 사본의 선택 필드).
# 거래량 칸과 같은 읽기 행(종가가 유효한 저장 행 · 최신순)의 앞 TREND_POINTS 개 = 기준일 포함.
TREND_POINTS = 20


class VolumeTrendPoint(BaseModel):
    date: str
    # 유효하지 않은 거래량(null · 숫자 아님 · 음수 · 무한대)은 null — 0 으로 채우지 않는다(저장된 0 은 0).
    volume: Optional[Union[int, float]] = None


class VolumeTrendEvidence(BaseModel):
    asof_date: Optional[str] = None
    points: list[VolumeTrendPoint] = []  # 오래된 순 · 최대 TREND_POINTS
    missing_count: int = 0


def compute_volume_trend(rows_desc: list[RecentPriceRow]) -> VolumeTrendEvidence:
    """최신순 저장 가격 행 `(date, close, volume, source)` → 기준일 포함 최근 최대 20개 저장일 거래량.

    행을 건너뛰지 않는다(거래량이 비어 있어도 그 날짜 자리를 유지 · 더 오래된 행으로 채우지 않음).
    """
    window = rows_desc[:TREND_POINTS]
    points = [
        VolumeTrendPoint(date=r[0], volume=(r[2] if _valid_volume(r[2]) else None))
        for r in reversed(window)
    ]
    return VolumeTrendEvidence(
        asof_date=(window[0][0] if window else None),
        points=points,
        missing_count=sum(1 for p in points if p.volume is None),
    )


def build_stored_volume_evidence(
    ticker: str, *, db_path: Path = DEFAULT_DB_PATH
) -> StoredVolumeEvidence:
    """한 종목의 저장 거래량 관찰값 — 읽기 1회(최근 21행 · 출처 포함)."""
    rows = fetch_recent_price_rows(ticker, limit=VOLUME_ROWS_NEEDED, db_path=db_path)
    return compute_stored_volume_evidence(ticker, rows)
