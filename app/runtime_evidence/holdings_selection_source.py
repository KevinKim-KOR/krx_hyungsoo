"""POC3-OPS-01A — 선정기 입력 조립 (보유 원장 + 가격 이력).

선정 로직(`holdings_selection`)은 순수 함수로 두고, DB·파일 접근은 여기 모은다.
**신규 외부 조회를 하지 않는다** — 현재가는 러너가 이미 수행한 runtime quote 를
그대로 넘겨받는다.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Optional

from app.runtime_evidence.holdings_selection import TRADING_DAY_AXIS_TICKER


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
        rows.append(
            {"ticker": ticker, "name": name or ticker, "account_group": account}
        )
    return rows


def load_price_history(
    tickers: list[str],
    *,
    fetch_history: Callable[..., list[tuple[str, float]]],
    db_path: Optional[Path] = None,
) -> dict[str, list[tuple[str, float]]]:
    """ticker → (date, close) ASC. 분모(20거래일 전 종가)만 쓴다.

    행이 부족한 ticker 도 그대로 넘긴다 — 선정기가
    `DATA_UNAVAILABLE_OR_STALE` 로 판정한다(조용히 빼지 않는다).
    """
    out: dict[str, list[tuple[str, float]]] = {}
    for ticker in tickers:
        rows = (
            fetch_history(ticker, db_path=db_path)
            if db_path is not None
            else fetch_history(ticker)
        )
        out[ticker] = rows or []
    return out


def load_trading_day_axis(
    *,
    fetch_history: Callable[..., list[tuple[str, float]]],
    db_path: Optional[Path] = None,
) -> list[str]:
    """KRX 거래일 축 (오름차순 날짜).

    설계자 확정 2026-09-05 — 기준일을 **거래일 축**에서 고른다. 신규 휴장일
    캘린더를 만들지 않고, walk-forward 가 이미 쓰는 KODEX200 거래일 시퀀스를
    그대로 재사용한다. **신규 외부 조회 0건** (같은 `fetch_history` 를 쓴다).
    """
    rows = (
        fetch_history(TRADING_DAY_AXIS_TICKER, db_path=db_path)
        if db_path is not None
        else fetch_history(TRADING_DAY_AXIS_TICKER)
    )
    return [d for d, _ in (rows or [])]
