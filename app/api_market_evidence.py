"""POC6-32 V2 — `GET /market/evidence` · `GET /market/etf-official`(외부 조회 0).

파일 쓰기(r1 F3): 시장 DB 파일이 없으면 둘 다 만들지 않는다(`/market/evidence` = 빌더가 읽기 없이 '확인 불가' ·
`/market/etf-official` = ETF 목록을 `mode=ro` 로만 읽고 파일이 없으면 열지 않음 · CSV 는 읽기만). DB 가 있으면
`/market/evidence` 의 기존 읽기 함수가 표를 확인한다(시장 표가 모두 있으면 바뀌는 것 없음 · 빠진 시장 표만 그 기존
함수가 만듦 · 공유 저장소라 이 작업에서 바꾸지 않음).

- `/market/evidence` = 공통 시장 근거(`app/market_evidence.build_market_evidence`) — 「오늘의 투자 점검」 일일
  [AI용 시장 정보 복사]가 응답 글(`daily_text`)을 그대로 쓰고, 주간 복사가 같은 근거 줄(`evidence_items`)에 번호를
  붙인다(PLAN §4-1).
- `/market/etf-official?tickers=A,B` = 공식 기준정보(KRX ETF 기본정보 CSV) 조회(`app/etf_official_info` ·
  PLAN §3-1 R1 · §3-2 D2 · D3). 코드는 쉼표로 나누고 앞뒤 공백을 지운 뒤 같은 코드는 한 번만 · 최대 10개 ·
  6자리 코드(숫자 · 영문 대문자)만 받는다(아니면 422). 코드가 정확히 2개일 때만 두 상품의 지수 상태(`pair`)를 더한다.
"""

from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app import market_evidence

router = APIRouter(tags=["market-evidence"])

MAX_TICKERS = 10
_CODE = re.compile(r"[0-9A-Z]{6}")


@router.get("/market/evidence")
def get_market_evidence() -> dict[str, Any]:
    return market_evidence.build_market_evidence()  # 모듈 속성(시험이 바꿔 끼움)


def parse_tickers(raw: str) -> list[str]:
    """'A, B,A' → ['A', 'B'](순서 유지 · 중복 제거) · 비었거나 10개 초과 · 6자리 코드가 아니면 422."""
    codes = list(dict.fromkeys(c.strip() for c in raw.split(",") if c.strip()))
    if not codes:
        raise HTTPException(status_code=422, detail="ETF 코드를 하나 이상 주세요.")
    if len(codes) > MAX_TICKERS:
        raise HTTPException(
            status_code=422, detail=f"ETF 코드는 {MAX_TICKERS}개까지 받습니다."
        )
    bad = [c for c in codes if not _CODE.fullmatch(c)]
    if bad:
        raise HTTPException(
            status_code=422,
            detail=f"6자리 ETF 코드(숫자 · 영문 대문자)가 아닙니다: {', '.join(bad)}",
        )
    return codes


@router.get("/market/etf-official")
def get_etf_official(
    tickers: str = Query(..., description="쉼표로 나눈 ETF 코드(최대 10개)"),
) -> dict[str, Any]:
    codes = parse_tickers(tickers)
    # 공식 기준정보 모듈은 다른 작업 갈래가 함께 만든다 — 부를 때만 읽는다.
    from app.etf_official_info import lookup_official, pair_state

    found = lookup_official(codes)
    out: dict[str, Any] = {"csv": found.get("csv"), "items": found.get("items")}
    if len(codes) == 2:
        items = found.get("items") or {}
        out["pair"] = pair_state(items.get(codes[0]), items.get(codes[1]))
    return out
