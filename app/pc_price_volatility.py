"""POC5-16 — PC 저장 종가의 가격 흔들림(변동성) 근거(PC 근거 응답 사본 전용 · 읽기 전용).

설계 `docs/ai_design/POC5/POC5-16_STORED_PRICE_VOLATILITY_EVIDENCE_DESIGN_V1.md` §2~§4 ·
PLAN V1 §2-1 · 판정 `..._PLAN_DECISION_2026-10-16.md` §3 · §4.

```text
날짜     D = PC 가격 흐름 기준일(price_basis.reference_date) · E = 이 종목의 마지막 유효 가격일
         (기존 거른 읽기 · price_dates.end_date)
순서     E 없음 → unavailable(두 기간 자료 부족) · D 없음 → reference_unavailable · E ≠ D →
         date_mismatch · 통과(E = D)하면 D 이하 원본 최근 41행(비정상 행을 거르지 않음)
창       오래된 순 P0…P40 · 직전 = P0…P20(연결 P0→P1 … P19→P20) · 최근 = P20…P40(연결
         P20→P21 … P39→P40) · 경계 종가 P20 공유 · 행이 모자라면 최근부터 채운다
기간 사유 행 부족 → 비정상 종가 · 허용 밖 출처 → 가격 기준 확인 필요(POC5-06 연결 판정 그대로)
값       단순 수익률(다음 ÷ 직전 − 1) 20개의 모집단 표준편차(분모 20) × 100 · 소수 둘째 자리 ·
         연율화 · 로그 수익률 없음 · 비교는 표시값(반올림한 두 값)으로
```

기존 `ml_feature_primitives.volatility_20d`(표본 분모) · `reentry_review.model`(로그 수익률)은
정의가 달라 쓰지 않는다(그대로 둔다). 같은 종목 여러 계좌는 한 번 읽은 결과를 같이 쓴다.
"""

from __future__ import annotations

import sqlite3
import statistics
from pathlib import Path
from typing import Any, Literal, Optional

from pydantic import BaseModel

from app.market_data_store import DEFAULT_DB_PATH
from app.reentry_review.prices import (
    ALLOWED_SOURCES,
    PriceRow,
    link_break,
    valid_close,
)

WINDOW = 20
RECENT_CLOSES = WINDOW + 1  # 21
ALL_CLOSES = 2 * WINDOW + 1  # 41 · 경계 종가 하나 공유

Reason = Literal["insufficient_history", "invalid_price", "basis_unconfirmed"]


class PriceVolatilityWindow(BaseModel):
    value_pct: float  # 소수 둘째 자리
    start_date: str
    end_date: str


class PriceVolatilityEvidence(BaseModel):
    status: Literal[
        "ok",
        "recent_only",
        "previous_only",
        "unavailable",
        "date_mismatch",
        "reference_unavailable",
    ]
    recent: Optional[PriceVolatilityWindow] = None
    previous: Optional[PriceVolatilityWindow] = None
    # 두 표시값이 다 있을 때만.
    comparison: Optional[Literal["higher", "lower", "same"]] = None
    recent_reason: Optional[Reason] = None
    previous_reason: Optional[Reason] = None
    end_date: Optional[str] = None  # E(마지막 유효 가격일)


def _link_unconfirmed(prev: PriceRow, row: PriceRow) -> bool:
    """POC5-06 연결 판정(`link_break`) 그대로 · 숫자로 읽을 수 없는 저장 change 도 연속성 확인 불가.

    06 판정은 change 를 `float()` 로 읽는다. 손상된 텍스트 change 가 응답 전체를 실패시키지 않게
    PC 쪽에서만 그 기간을 계산하지 않는다(06 동작은 바꾸지 않는다).
    """
    try:
        return link_break(prev, row) is not None
    except (TypeError, ValueError):
        return True


def _window(
    closes: list[PriceRow],
) -> tuple[Optional[PriceVolatilityWindow], Optional[Reason]]:
    """종가 21개(오름차순) 한 기간 → (값, 사유). 첫 종가로 들어오는 창 밖 연결은 보지 않는다."""
    if any(not valid_close(r.close) or r.source not in ALLOWED_SOURCES for r in closes):
        return None, "invalid_price"
    if any(_link_unconfirmed(closes[i - 1], closes[i]) for i in range(1, len(closes))):
        return None, "basis_unconfirmed"
    rets = [
        float(closes[i].close) / float(closes[i - 1].close) - 1.0
        for i in range(1, len(closes))
    ]
    value = round(statistics.pstdev(rets) * 100.0, 2)
    return (
        PriceVolatilityWindow(
            value_pct=value, start_date=closes[0].date, end_date=closes[-1].date
        ),
        None,
    )


def compute_price_volatility(
    rows_asc: list[PriceRow],
    *,
    last_valid_date: Optional[str],
    reference_date: Optional[str],
) -> PriceVolatilityEvidence:
    """판정 순서(모듈 설명 표)대로 한 종목의 근거를 만든다.

    rows_asc = D 이하 원본 최근 행(최대 41 · 오름차순). 날짜 검사를 통과하지 못하면 보지 않는다.
    """
    if last_valid_date is None:
        return PriceVolatilityEvidence(
            status="unavailable",
            recent_reason="insufficient_history",
            previous_reason="insufficient_history",
        )
    if reference_date is None:
        return PriceVolatilityEvidence(
            status="reference_unavailable", end_date=last_valid_date
        )
    if last_valid_date != reference_date:
        return PriceVolatilityEvidence(status="date_mismatch", end_date=last_valid_date)

    rows = rows_asc[-ALL_CLOSES:]
    recent, recent_reason = (
        _window(rows[-RECENT_CLOSES:])
        if len(rows) >= RECENT_CLOSES
        else (None, "insufficient_history")
    )
    previous, previous_reason = (
        _window(rows[:RECENT_CLOSES])
        if len(rows) >= ALL_CLOSES
        else (None, "insufficient_history")
    )
    comparison: Optional[Literal["higher", "lower", "same"]] = None
    if recent and previous:
        status = "ok"
        if recent.value_pct > previous.value_pct:
            comparison = "higher"
        elif recent.value_pct < previous.value_pct:
            comparison = "lower"
        else:
            comparison = "same"
    elif recent:
        status = "recent_only"
    elif previous:
        status = "previous_only"
    else:
        status = "unavailable"
    return PriceVolatilityEvidence(
        status=status,
        recent=recent,
        previous=previous,
        comparison=comparison,
        recent_reason=recent_reason,
        previous_reason=previous_reason,
        end_date=last_valid_date,
    )


def _read_raw_rows(
    con: sqlite3.Connection, ticker: str, reference_date: str
) -> list[PriceRow]:
    """D 이하 원본 최근 41행(오름차순) — null · 0 이하 종가도 거르지 않는다."""
    cur = con.execute(
        "SELECT date, close, source, fetched_at, change FROM etf_daily_price "
        "WHERE ticker = ? AND date <= ? ORDER BY date DESC LIMIT ?",
        (ticker, reference_date, ALL_CLOSES),
    )
    return [PriceRow(*r) for r in reversed(cur.fetchall())]


def build_price_volatility(
    items: list[dict[str, Any]],
    *,
    reference_date: Optional[str],
    db_path: Path = DEFAULT_DB_PATH,
) -> dict[str, PriceVolatilityEvidence]:
    """`apply_pc_price_basis` 결과 종목들 → ticker 별 근거(같은 종목은 한 번만 계산 · 읽기).

    E = 각 종목 `price_dates.end_date`. 날짜 검사를 통과한 종목만 `mode=ro` 로 한 번 읽는다.
    """
    out: dict[str, PriceVolatilityEvidence] = {}
    con: Optional[sqlite3.Connection] = None
    try:
        for item in items:
            ticker = item["ticker"]
            if ticker in out:
                continue
            last_valid = (item.get("price_dates") or {}).get("end_date")
            rows: list[PriceRow] = []
            if (
                last_valid is not None
                and reference_date is not None
                and last_valid == reference_date
            ):
                if con is None:
                    con = sqlite3.connect(
                        f"{Path(db_path).resolve().as_uri()}?mode=ro",
                        uri=True,
                        timeout=5.0,
                    )
                rows = _read_raw_rows(con, ticker, reference_date)
            out[ticker] = compute_price_volatility(
                rows, last_valid_date=last_valid, reference_date=reference_date
            )
    finally:
        if con is not None:
            con.close()
    return out
