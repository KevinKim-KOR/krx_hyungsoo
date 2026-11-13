"""POC6-28 — 「ETF 비교하기」 요약 API(PC · 읽기 전용).

- GET /market/etf-compare/summary : 같은 모집단의 상·하위 최대 30 · 묶음 · 네 기준 · 가격 시점 · 국면 · 보유 연결
- GET /market/etf-detail?tickers=… : POC6-29 행 상세 수치(종목 최대 30 · `pc_etf_row_detail`)

계산은 `app/pc_etf_compare_summary.build_summary` 가 한다. 이 파일은 자료 위치를 정하고 읽기 실패를
응답 상태로 바꾼다. 시장 DB 는 `mode=ro` · 외부 호출 · 쓰기 0. 보유는 ticker 만 넘긴다(금액 · 계좌 없음).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Literal, Optional

from fastapi import APIRouter, HTTPException, Query

from app import holdings as holdings_module
from app.holdings import HoldingsValidationError
from app.intraday_config.selector import (
    TOKEN_DICTIONARY_PATH,
    TokenDictionaryError,
    load_token_dictionary,
)
from app.market_briefing.official_csv import resolve_official_csv
from app.market_data_store import DEFAULT_DB_PATH
from app.pc_etf_compare_summary import build_summary
from app.pc_etf_row_detail import MAX_TICKERS, build_etf_detail

MARKET_DB_PATH: Path = DEFAULT_DB_PATH
META_DIR = Path("state/market_meta")
DICTIONARY_PATH: Path = TOKEN_DICTIONARY_PATH

router = APIRouter(tags=["etf-compare"])


def _official() -> tuple[dict[str, dict[str, str]], dict[str, Any]]:
    sel = resolve_official_csv(META_DIR)
    if not sel.ok:
        return {}, {
            "status": "unavailable",
            "name": None,
            "csv_asof": None,
            "rows": None,
        }
    rows = {
        (r.get("단축코드") or "").strip(): r
        for r in sel.records
        if (r.get("단축코드") or "").strip()
    }
    return rows, {
        "status": "ok",
        "name": sel.name,
        "csv_asof": sel.csv_asof,
        "rows": sel.rows,
    }


def _dictionary() -> tuple[Optional[dict[str, list[str]]], dict[str, Any]]:
    try:
        d, sha = load_token_dictionary(DICTIONARY_PATH)
    except TokenDictionaryError:
        return None, {"status": "unavailable", "sha256": None, "sector_count": None}
    return d, {"status": "ok", "sha256": sha, "sector_count": len(d)}


def _held_tickers() -> tuple[Optional[list[str]], str]:
    try:
        loaded = holdings_module.load()
    except (HoldingsValidationError, OSError, ValueError):
        return None, "error"
    if not holdings_module.HOLDINGS_FILE.exists():
        return [], "none"
    return [h.ticker for h in loaded], "ok"


@router.get("/market/etf-compare/summary")
def get_etf_compare_summary(
    basis: Literal["daily", "one_month", "three_month"] = Query("one_month"),
    exclude_inverse: bool = Query(True),
    exclude_leveraged: bool = Query(True),
    exclude_synthetic: bool = Query(True),
    exclude_futures: bool = Query(True),
) -> dict[str, Any]:
    official, official_meta = _official()
    dictionary, dictionary_meta = _dictionary()
    held, holdings_status = _held_tickers()
    return build_summary(
        db_path=MARKET_DB_PATH,
        basis=basis,
        filters={
            "exclude_inverse": exclude_inverse,
            "exclude_leveraged": exclude_leveraged,
            "exclude_synthetic": exclude_synthetic,
            "exclude_futures": exclude_futures,
        },
        official=official,
        official_meta=official_meta,
        dictionary=dictionary,
        dictionary_meta=dictionary_meta,
        held_tickers=held,
        holdings_status=holdings_status,
    )


_TICKER = re.compile(r"^[0-9A-Za-z]{1,12}$")


@router.get("/market/etf-detail")
def get_etf_detail(tickers: str = Query(...)) -> dict[str, Any]:
    """POC6-29 행 상세 수치 — 쉼표로 나눈 종목(중복 제거 뒤 1 ~ 30개 · 그 밖 = 422 · 읽기 전용)."""
    picked: list[str] = []
    for raw in tickers.split(","):
        t = raw.strip()
        if t and t not in picked:
            picked.append(t)
    if (
        not picked
        or len(picked) > MAX_TICKERS
        or not all(_TICKER.match(t) for t in picked)
    ):
        raise HTTPException(
            status_code=422,
            detail=f"tickers 는 종목 코드 1 ~ {MAX_TICKERS}개(쉼표로 구분)입니다.",
        )
    return build_etf_detail(MARKET_DB_PATH, picked)
