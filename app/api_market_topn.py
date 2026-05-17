"""PC Market Discovery TOP N 최소 표시 — read-only API.

설계자 결정 (지시문 §3.1):
- state/market/etf_universe_topn_latest.json 파일만 읽는다.
- SQLite 직접 조회 / FDR 호출 / refresh 실행 / TOP N 재계산 모두 금지.
- artifact 없음 / JSON 파싱 실패 / 필수 구조 이상은 정상 응답 (200) 으로 안내.

응답 status:
- "ok"      : artifact 정상
- "missing" : artifact 파일 없음
- "invalid" : artifact 파일은 있으나 JSON 파싱 실패 또는 필수 구조 이상
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.market_topn import DEFAULT_TOPN_PATH

router = APIRouter()


class MarketTopNEntry(BaseModel):
    # 지시문 §3.2 "artifact 에 없는 값은 억지로 만들지 않는다" 준수 —
    # 모든 필드는 Optional. artifact 에 키가 없거나 null 이면 None 그대로 통과.
    # Frontend 가 "-" 또는 "정보 없음" 으로 표시.
    rank: Optional[int] = None
    ticker: Optional[str] = None
    name: Optional[str] = None
    return_pct: Optional[float] = None
    basis_start_date: Optional[str] = None
    basis_end_date: Optional[str] = None


class MarketTopNResponse(BaseModel):
    status: str  # "ok" | "missing" | "invalid"
    error: Optional[str] = None
    asof: Optional[str] = None
    source: Optional[str] = None
    n: Optional[int] = None
    universe_count: Optional[int] = None
    price_success_count: Optional[int] = None
    price_fail_count: Optional[int] = None
    runtime_seconds: Optional[float] = None
    daily_topn: list[MarketTopNEntry] = []
    one_month_topn: list[MarketTopNEntry] = []
    three_month_topn: list[MarketTopNEntry] = []
    topn_caveat: Optional[str] = None
    artifact_path: Optional[str] = None


REQUIRED_KEYS = (
    "asof",
    "source",
    "n",
    "universe_count",
    "daily_topn",
    "one_month_topn",
    "three_month_topn",
)


def _optional_int(raw: dict, key: str) -> Optional[int]:
    """artifact 에 key 가 없거나 None / 형변환 실패 → None (생성 안 함)."""
    if key not in raw or raw[key] is None:
        return None
    try:
        return int(raw[key])
    except (TypeError, ValueError):
        return None


def _optional_float(raw: dict, key: str) -> Optional[float]:
    if key not in raw or raw[key] is None:
        return None
    try:
        return float(raw[key])
    except (TypeError, ValueError):
        return None


def _optional_str(raw: dict, key: str) -> Optional[str]:
    if key not in raw or raw[key] is None:
        return None
    s = str(raw[key])
    return s if s else None


def _entries_from_payload(value: Any) -> list[MarketTopNEntry]:
    """artifact 의 TOP N list 를 그대로 통과시킨다.

    지시문 §3.2: artifact 에 없는 값은 억지로 만들지 않는다.
    필수 필드 (rank / ticker / return_pct) 가 모두 비어 있는 entry 는 의미 없는 row
    이므로 skip — '아무 값도 없는 행'은 표 자체에 포함하지 않는다 (행 생성 자체가
    fallback 이 됨). 일부만 비어 있으면 그대로 None 으로 통과 — frontend 가 "-" 표시.
    """
    if not isinstance(value, list):
        return []
    out: list[MarketTopNEntry] = []
    for raw in value:
        if not isinstance(raw, dict):
            continue
        rank = _optional_int(raw, "rank")
        ticker = _optional_str(raw, "ticker")
        return_pct = _optional_float(raw, "return_pct")
        # 식별자/값이 셋 다 비어 있으면 entry 자체가 무의미 — skip
        if rank is None and not ticker and return_pct is None:
            continue
        out.append(
            MarketTopNEntry(
                rank=rank,
                ticker=ticker,
                name=_optional_str(raw, "name"),
                return_pct=return_pct,
                basis_start_date=_optional_str(raw, "basis_start_date"),
                basis_end_date=_optional_str(raw, "basis_end_date"),
            )
        )
    return out


def read_topn_artifact(path: Path = DEFAULT_TOPN_PATH) -> MarketTopNResponse:
    """artifact 읽고 status 분류. 본 함수는 외부 호출 없음 (파일 read only)."""
    if not path.exists():
        return MarketTopNResponse(
            status="missing",
            artifact_path=str(path),
            error="artifact 파일이 아직 생성되지 않았습니다",
        )

    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError as e:
        return MarketTopNResponse(
            status="invalid",
            artifact_path=str(path),
            error=f"파일 읽기 실패: {type(e).__name__}: {e}",
        )

    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as e:
        return MarketTopNResponse(
            status="invalid",
            artifact_path=str(path),
            error=f"JSON 파싱 실패: {e.msg} (line {e.lineno})",
        )

    if not isinstance(payload, dict):
        return MarketTopNResponse(
            status="invalid",
            artifact_path=str(path),
            error="artifact 최상위 구조가 객체가 아닙니다",
        )

    missing_keys = [k for k in REQUIRED_KEYS if k not in payload]
    if missing_keys:
        return MarketTopNResponse(
            status="invalid",
            artifact_path=str(path),
            error=f"필수 키 누락: {missing_keys}",
        )

    return MarketTopNResponse(
        status="ok",
        artifact_path=str(path),
        asof=payload.get("asof"),
        source=payload.get("source"),
        n=payload.get("n"),
        universe_count=payload.get("universe_count"),
        price_success_count=payload.get("price_success_count"),
        price_fail_count=payload.get("price_fail_count"),
        runtime_seconds=payload.get("runtime_seconds"),
        daily_topn=_entries_from_payload(payload.get("daily_topn")),
        one_month_topn=_entries_from_payload(payload.get("one_month_topn")),
        three_month_topn=_entries_from_payload(payload.get("three_month_topn")),
        topn_caveat=payload.get("topn_caveat"),
    )


@router.get("/market/topn/latest", response_model=MarketTopNResponse)
def get_market_topn_latest() -> MarketTopNResponse:
    """read state/market/etf_universe_topn_latest.json — file only.

    No SQLite query / FDR call / refresh / re-calculation.
    """
    return read_topn_artifact(DEFAULT_TOPN_PATH)
