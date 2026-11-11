"""POC6-28 — 「ETF 비교하기 › 보유」 가격 흐름(검증자 r2 F4 정정 · 같은 응답 · 같은 읽기).

보유 종목의 5 · 20저장일 변화 · KODEX 200 대비 · 기존 하락 판정과 그 끝일 행의 저장 상태를 **한 응답 ·
한 DB 읽기**에서 함께 만든다. 다른 시점에 읽은 보유 근거 응답에 이 응답의 저장 상태를 붙이지 않게 한다
(날짜 · 거래량이 같아도 다른 저장 판일 수 있음 · 검증자 r2 F4).

계산은 「확인 근거」 · 보유 근거 PC 사본과 같은 기존 함수를 그대로 쓴다(`app/pc_price_basis.py`):
- 행 조건 = `fetch_recent_price_rows` 와 같다(유효 종가 행 · 최신순 · 21행 · 끝일 제한 없음).
- 비교 판정 순서 · 단기 흐름 값 = `_normalize_item`(기준일 → 이력 길이 → 비교 기간) · `_flow_from_rows`.
- 하락 판정 = `_decline_band`(OCI 보유 알림의 `classify_decline` 경계 · PC 이름).
- KODEX 200 수익률 = 같은 069500 행으로 같은 산식(`_window_return_pct`) — 차이에서 되돌려 만들지 않는다.
새 산식 · 새 경계는 없다. DB 는 호출자의 `mode=ro` 연결로만 읽는다.
"""

from __future__ import annotations

import sqlite3
from typing import Any, Optional

from app.pc_etf_compare_periods import price_state
from app.pc_price_basis import (
    RECENT_ROWS,
    _dates,
    _decline_band,
    _normalize_item,
)
from app.short_term_momentum import _window_return_pct

# (date, close, volume, source, fetched_at) — 최신순
RecentRow = tuple[str, float, Optional[float], str, Optional[str]]


def read_recent_rows(con: sqlite3.Connection, ticker: str) -> list[RecentRow]:
    """`fetch_recent_price_rows` 와 같은 행 조건 + 저장 시각(같은 연결 · 같은 읽기)."""
    return [
        (r[0], float(r[1]), r[2], r[3], r[4])
        for r in con.execute(
            "SELECT date, close, volume, source, fetched_at FROM etf_daily_price "
            "WHERE ticker = ? AND close IS NOT NULL AND close > 0 "
            "ORDER BY date DESC LIMIT ?",
            (ticker, RECENT_ROWS),
        ).fetchall()
    ]


def holding_price_flow(
    mine: list[RecentRow], bench: list[RecentRow]
) -> Optional[dict[str, Any]]:
    """보유 한 종목의 가격 흐름 · 하락 판정 · 끝일 행 저장 상태. 저장 가격이 없으면 None."""
    if not mine:
        return None
    mine4 = [r[:4] for r in mine]
    bench4 = [r[:4] for r in bench]
    item: dict[str, Any] = {"short_term_momentum": {}, "evidence_notes": []}
    comparison = _normalize_item(item, mine4, bench4)
    stm = item["short_term_momentum"]
    dates = _dates(mine4)
    out: dict[str, Any] = {
        "end_date": dates["end"],
        "start_date_5d": dates["start"][5],
        "start_date_20d": dates["start"][20],
        "comparison": comparison,
        "status": stm.get("status"),
        "return_5d_pct": stm.get("return_5d_pct"),
        "return_20d_pct": stm.get("return_20d_pct"),
        "excess_vs_kodex200_20d_pctp": stm.get("excess_vs_kodex200_20d_pctp"),
        "kodex200_return_20d_pct": None,
        "decline_band": _decline_band(stm, comparison),
        "end_price": price_state(mine[0][0], mine[0][4]),
    }
    # 20저장일 KODEX 200 대비가 남아 있으면(양끝 날짜가 KODEX 200 과 같음 · 5일만 다른 window_mismatch 포함)
    # 같은 069500 행으로 KODEX 200 의 20저장일 수익률을 함께 낸다.
    if out["excess_vs_kodex200_20d_pctp"] is not None:
        series = [(r[0], r[1]) for r in reversed(bench4)]
        out["kodex200_return_20d_pct"] = _window_return_pct(series, 20)
    return out
