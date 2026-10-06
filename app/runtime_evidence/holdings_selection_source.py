"""POC3-OPS-01A — 선정기 입력 조립 (보유 원장 + 가격 이력).

선정 로직(`holdings_selection`)은 순수 함수로 두고, DB·파일 접근은 여기 모은다.
**신규 외부 조회를 하지 않는다** — 현재가는 러너가 이미 수행한 runtime quote 를
그대로 넘겨받는다.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Collection, Optional

from app import trading_day_lag
from app.runtime_evidence.holdings_selection import LOOKBACK_TRADING_DAYS


def load_holding_rows(
    holdings_loader: Callable[[], list[Any]],
) -> list[dict[str, Any]]:
    """보유 원장 → 선정기 입력 dict 목록. 계좌별 행을 그대로 넘긴다.

    같은 ticker 가 여러 계좌에 있으면 선정기가 1건으로 합친다.
    """
    rows: list[dict[str, Any]] = []
    for h in holdings_loader():
        ticker = getattr(h, "ticker", None) or (
            h.get("ticker") if isinstance(h, dict) else None
        )
        if not ticker:
            continue
        name = getattr(h, "name", None) or (
            h.get("name") if isinstance(h, dict) else None
        )
        account = getattr(h, "account_group", None) or (
            h.get("account_group") if isinstance(h, dict) else None
        )
        qty = getattr(h, "quantity", None) or (
            h.get("quantity") if isinstance(h, dict) else None
        )
        buy = getattr(h, "avg_buy_price", None) or (
            h.get("avg_buy_price") if isinstance(h, dict) else None
        )
        rows.append(
            {
                "ticker": ticker,
                "name": name or ticker,
                "account_group": account,
                "quantity": qty,
                "avg_buy_price": buy,
            }
        )
    return rows


def average_buy_prices(rows: list[dict[str, Any]]) -> dict[str, float]:
    """ticker → **수량 가중평균** 매입가.

    같은 종목을 여러 계좌에서 사면 **계좌별 매입가가 다르다**(실측: KODEX 200 이
    84,190 / 88,058 / 114,941, 수량 3 / 15 / 2). 단순 평균을 내면 소량 계좌가
    과대 반영된다. "내가 산 금액 대비" 이므로 **금액합 / 수량합** 이 맞다.

    수량·매입가가 없거나 0 이하인 행은 제외한다. 한 종목의 모든 행이 그렇다면
    그 종목은 결과에 없고, 선정기가 손익 표시만 생략한다.
    """
    agg: dict[str, list[float]] = {}
    for r in rows:
        t = r.get("ticker")
        try:
            qty = float(r.get("quantity") or 0)
            buy = float(r.get("avg_buy_price") or 0)
        except (TypeError, ValueError):
            continue
        if not t or qty <= 0 or buy <= 0:
            continue
        slot = agg.setdefault(t, [0.0, 0.0])
        slot[0] += buy * qty
        slot[1] += qty
    return {t: amt / qty for t, (amt, qty) in agg.items() if qty > 0}


def trading_day_axis(
    today_kst: Optional[str],
    *,
    calendar_dir: Optional[Path] = None,
    stored_dates: Optional[Collection[str]] = None,
) -> list[str]:
    """실행일 **미만** 거래일 축(오름차순) — **거래일 캘린더**로 정한다.

    POC3-02D-OPS-03 확정 계약 10 — 예전에는 `069500` 의 `etf_daily_price` 저장
    날짜를 축으로 썼다. 08:10 배치가 실패해 T-1 행이 없으면 축의 마지막이 T-2 가
    되어 **21거래일 전 종가를 '20거래일' 로** 보고했다(조용한 밀림). 이제 축은
    실행일 기준 캘린더다(`trading_day_lag` · 08:30 · 장중과 같은 함수) — 가격이
    빠지면 그 지표만 fail-closed 된다(`close_on` · 보조값 구간 불완전).

    캘린더가 그해를 덮지 않으면 평일 기본(`trading_day_lag` 규칙 · 5월 1일 · 12월 31일
    제외). 그때 `stored_dates`(보유 종목 가격 이력의 날짜)를 넘기면 T-1 이전 평일 가운데
    저장 자료가 없는 날은 휴장으로 건너뛴다(한국 거래일 계약 2026-09-11 · 축을 비우지
    않고 운영 · 오판은 계약상 허용).
    실행일을 읽을 수 없으면 빈 축 — 기준일이 없어 전 종목이 데이터 확인 대상이다.
    """
    if not today_kst:
        return []
    prev = trading_day_lag.expected_previous_trading_day(
        str(today_kst)[:10], calendar_dir=calendar_dir
    )
    if prev is None:
        return []
    return trading_day_lag.trading_days_ending(
        prev, LOOKBACK_TRADING_DAYS, calendar_dir=calendar_dir, stored=stored_dates
    )


def history_dates(history: dict[str, list[tuple[str, float]]]) -> set[str]:
    """보유 종목 가격 이력에 한 번이라도 나온 날짜(`trading_day_axis` 의 저장 근거)."""
    return {str(d)[:10] for rows in history.values() for d, _ in rows}
