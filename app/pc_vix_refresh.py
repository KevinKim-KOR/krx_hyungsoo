"""POC5-11 — PC 수동 갱신('최신 시장 데이터 갱신')의 VIX(시장 불안 지표) 단계.

PC 갱신(`app/market_refresh_service.py`)은 KOSPI 단계 뒤 · NAV 단계 앞에서 이 함수를 부른다.
수집은 OCI 08:10 배치와 같은 `app.market_benchmark_batch.refresh_vix` 를 재사용한다.

- 조회 대기 상한(설계자 판정 Q2 (b)): 기존 `fdr_request_timeout()`(20초)으로 감싼다. 이 블록 안의
  `requests` 호출(FDR Yahoo `^VIX` 조회 1회)에 timeout 이 없으면 20초를 넣는다 — 연결 대기 20초 ·
  응답 바이트 사이 무응답 20초를 각각 끊는다. 조회 1회 전체 시간 · DNS 조회 · 전체 갱신 시간의 상한은
  아니다. 블록을 빠져나오면(정상 · 예외 · timeout) 원래 함수로 되돌린다.
- 미확정 자료 제외(판정 §3): Yahoo 조회 끝은 PC 의 로컬 자정이라, 한국 시각 새벽(미국 장중)에 갱신하면
  진행 중인 미국 세션 값이 들어온다. 조회 시작 = 끝이면 FDR 이 끝을 하루 늘려 한국 저녁(미국 장 시작 뒤)에도
  들어온다. 저장은 '마지막 저장일 다음 날부터'만 받으므로 그 값은 다시 고쳐지지 않는다. 그래서 PC 호출만
  미국 동부 시각 기준 마감이 지난 마지막 날짜(`max_date`)까지 저장한다 — 두 경우 모두 막는다. 갱신 시간대는
  막지 않고(마감 전이면 전날까지만 저장), 남은 범위가 주말뿐이면 조회하지 않는다(요일만 · 거래일 달력 없음 ·
  미국 평일 휴장은 남음).
- 실패(판정 Q3 (a)): 한국어 문구 하나를 돌려준다. 기술 사유(status · exit_code · error · as_of_date)는
  서버 로그에만 남긴다. 새 기록 행 · 상태 파일 없음. error 가 없어도 status 가 ok 가 아니면 실패다.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from app.market_benchmark_batch import refresh_vix
from app.three_push_runtime.market_data_batch import fdr_request_timeout

logger = logging.getLogger(__name__)

VIX_STEP_FAILED_TEXT = "시장 불안 지표(VIX)를 갱신하지 못했습니다"

# VIX 지수 장 마감 16:15(미국 동부) + 여유 15분. 이 시각이 지나면 그날 값을 확정으로 본다.
US_SESSION_SETTLED_ET = time(16, 30)
_US_EASTERN = ZoneInfo("America/New_York")


def last_settled_us_date(now_utc: datetime) -> date:
    """미국 동부 시각으로 마감이 지난 마지막 날짜(주말 · 휴장 구분 없음 — 그날 행이 없을 뿐)."""
    now_et = now_utc.astimezone(_US_EASTERN)
    if now_et.time() >= US_SESSION_SETTLED_ET:
        return now_et.date()
    return now_et.date() - timedelta(days=1)


def refresh_pc_vix(*, db_path: Path, now_utc: datetime) -> Optional[str]:
    """VIX 를 받아 저장한다. 성공이면 None, 실패면 한국어 문구(완료 사유 끝에 붙일 것)."""
    max_date = last_settled_us_date(now_utc)
    with fdr_request_timeout():
        result = refresh_vix(db_path=db_path, max_date=max_date)
    status = result.get("status")
    if status == "ok":
        logger.info(
            "PC VIX refresh ok: as_of_date=%s exit_code=%s settled_through=%s",
            result.get("as_of_date"),
            result.get("exit_code"),
            max_date,
        )
        return None
    logger.warning(
        "PC VIX refresh failed: status=%s exit_code=%s error=%s as_of_date=%s settled_through=%s",
        status,
        result.get("exit_code"),
        result.get("error"),
        result.get("as_of_date"),
        max_date,
    )
    return VIX_STEP_FAILED_TEXT
