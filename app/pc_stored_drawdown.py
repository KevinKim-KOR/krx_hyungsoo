"""POC5-25 — PC 저장 종가의 '20저장일 종가 고점 대비'(PC 시장 목록 응답 전용 · 읽기 전용).

설계 `docs/ai_design/POC5/POC5-25_STORED_PRICE_DRAWDOWN_EVIDENCE_DESIGN_V1.md` §2 · §3 ·
PLAN V1 §2 · 판정 `..._PLAN_DECISION_2026-10-19.md` §2 · §3.

```text
기준일   D = 그 종목의 실제 PC 저장 가격 기준일 = POC5-21 `price_end_date`(마지막 유효 종가 행 ·
         `fetch_price_history` 거른 읽기 · POC5-16 E 와 같은 정의). 시장 최신일 · 스냅샷 날짜로 대신 안 함.
창       D 를 포함한 D 이하 원본 저장 행 20개(거르지 않음 · 20개 변화 구간용 21행 아님 · 달력 · 거래일 아님)
판정     D 없음 · 창 마지막 행 ≠ D → end_date_unknown · 20행 미만 → insufficient_history ·
         창 안 비정상 종가 · 허용 밖 출처 → invalid_price(PLAN §2 · POC5-06 BAD_CLOSE ·
         SOURCE_NOT_ALLOWED 와 같은 묶음) ·
         가격 기준 연결(POC5-06 link_break) 확인 불가 → basis_unconfirmed
         (비정상 행을 빼고 더 오래된 행으로 채우지 않는다)
값       H = 20개 종가 최대(장중 고가 아님) · 고점일 = H 와 같은 가장 최근 날짜 ·
         (D 종가 ÷ H − 1) × 100 · 단위 % · 소수 4자리 · 고점과 같으면 0
```

옛 ML `drawdown_20d`(폐기된 점수 스냅샷 · 비율 · 날짜 없음 · 거른 행의 양수 종가만 최대)와 섞지 않는다 —
그 필드 · 연구 정의는 그대로 두고 이 객체만 화면 · 정렬이 쓴다.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Literal, Optional

from pydantic import BaseModel

from app.market_data_store import DEFAULT_DB_PATH

# POC5-16 연결 판정 그대로(숫자로 읽을 수 없는 change 도 확인 불가 · 06 동작 무변경).
from app.pc_price_volatility import _link_unconfirmed
from app.reentry_review.prices import ALLOWED_SOURCES, PriceRow, valid_close

WINDOW = 20

Reason = Literal[
    "end_date_unknown", "insufficient_history", "invalid_price", "basis_unconfirmed"
]


class StoredDrawdown(BaseModel):
    status: Literal["ok", "unavailable"]
    reason: Optional[Reason] = None
    value_pct: Optional[float] = None  # 소수 4자리 · ok 일 때만
    end_date: Optional[str] = None  # D
    start_date: Optional[str] = None  # 창 첫 행(읽은 행이 있을 때)
    close: Optional[float] = None  # D 종가 · ok 일 때만
    peak_close: Optional[float] = None
    peak_date: Optional[str] = None
    rows: int = 0  # 창에 읽힌 원본 행 수(최대 20)


def compute_stored_drawdown(
    rows_asc: list[PriceRow], *, end_date: Optional[str]
) -> StoredDrawdown:
    """D 이하 원본 행(오름차순 · 최대 20 을 넘으면 최근 20만) → 근거 하나(판정 순서는 모듈 설명 표)."""
    if end_date is None:
        return StoredDrawdown(status="unavailable", reason="end_date_unknown")
    rows = rows_asc[-WINDOW:]
    base: dict[str, Any] = {
        "end_date": end_date,
        "rows": len(rows),
        "start_date": rows[0].date if rows else None,
    }
    if rows and rows[-1].date != end_date:
        # D 는 마지막 유효 종가 행이라 늘 창 끝이다 — 아니면(그 사이 행이 바뀜 등) 계산하지 않는다.
        return StoredDrawdown(status="unavailable", reason="end_date_unknown", **base)
    if len(rows) < WINDOW:
        return StoredDrawdown(
            status="unavailable", reason="insufficient_history", **base
        )
    if any(not valid_close(r.close) or r.source not in ALLOWED_SOURCES for r in rows):
        return StoredDrawdown(status="unavailable", reason="invalid_price", **base)
    if any(_link_unconfirmed(rows[i - 1], rows[i]) for i in range(1, len(rows))):
        return StoredDrawdown(status="unavailable", reason="basis_unconfirmed", **base)
    closes = [float(r.close) for r in rows]
    peak = max(closes)
    peak_date = max(r.date for r, c in zip(rows, closes) if c == peak)
    return StoredDrawdown(
        status="ok",
        value_pct=round((closes[-1] / peak - 1.0) * 100.0, 4),
        close=closes[-1],
        peak_close=peak,
        peak_date=peak_date,
        **base,
    )


def candidate_end_date(candidate: dict[str, Any]) -> Optional[str]:
    """POC5-21 실제 끝 행 날짜 — 기간마다 같은 '그 종목 마지막 유효 종가 행'(있는 첫 값)."""
    for r in (candidate.get("returns") or {}).values():
        if isinstance(r, dict) and r.get("price_end_date"):
            return r["price_end_date"]
    return None


def _read_window(con: sqlite3.Connection, ticker: str, end_date: str) -> list[PriceRow]:
    """D 이하 원본 최근 20행(오름차순) — null · 0 이하 종가 · 출처도 거르지 않는다."""
    cur = con.execute(
        "SELECT date, close, source, fetched_at, change FROM etf_daily_price "
        "WHERE ticker = ? AND date <= ? ORDER BY date DESC LIMIT ?",
        (ticker, end_date, WINDOW),
    )
    return [PriceRow(*r) for r in reversed(cur.fetchall())]


def build_stored_drawdown(
    candidates: list[dict[str, Any]], *, db_path: Path = DEFAULT_DB_PATH
) -> dict[str, StoredDrawdown]:
    """PC 화면 API 의 후보(POC5-21 실제 끝 행 날짜가 붙은 기간 dict) → ticker 별 근거(같은 종목은 한 번 · mode=ro 연결 하나)."""
    out: dict[str, StoredDrawdown] = {}
    con: Optional[sqlite3.Connection] = None
    try:
        for cand in candidates:
            ticker = cand.get("ticker")
            if not ticker or ticker in out:
                continue
            end = candidate_end_date(cand)
            rows: list[PriceRow] = []
            if end is not None:
                if con is None:
                    con = sqlite3.connect(
                        f"{Path(db_path).resolve().as_uri()}?mode=ro",
                        uri=True,
                        timeout=5.0,
                    )
                rows = _read_window(con, ticker, end)
            out[ticker] = compute_stored_drawdown(rows, end_date=end)
    finally:
        if con is not None:
            con.close()
    return out
