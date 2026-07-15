"""NAV row 해석 + 사용자용 문장 생성 (지시문 §5.3).

Cleanup / FIX r7 Round 2 에서 `app/runtime_evidence_composer.py` 로부터 분리.
NAV fact 는 nav_discount_snapshot 에 귀속. holdings_snapshot 성공 근거로 합산 X.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Optional

from app.runtime_evidence.constants import fmt_pct


def build_nav_facts(
    holdings: list,
    nav_fn: Callable[..., Any],
    market_db_path: Path,
) -> tuple[list[str], int, Optional[str], int]:
    """NAV evidence 문장 리스트 + 카운터.

    반환:
      notes: 사용자용 문장 리스트.
      fact_count: NAV contentful fact 수.
      asof_latest: NAV 최신 as-of.
      matched_count: NAV row 매칭 성공 holding 수.

    조건 (§5.3):
    - NAV row.asof 필수 (실제 as-of 존재).
    - NAV 값 (nav / market_price / discount_rate_pct) 중 최소 하나 필수.
    """
    notes: list[str] = []
    fact_count = 0
    matched_count = 0
    asof_latest: Optional[str] = None

    for h in holdings:
        row = nav_fn(etf_ticker=h.ticker, db_path=market_db_path)
        if row is None:
            continue
        if not row.asof:
            continue
        has_nav_or_price = (row.nav is not None) or (row.market_price is not None)
        if not has_nav_or_price and row.discount_rate_pct is None:
            continue
        matched_count += 1
        if asof_latest is None or row.asof > asof_latest:
            asof_latest = row.asof
        parts: list[str] = []
        if row.market_price is not None and row.nav is not None:
            parts.append(f"시장가 {row.market_price:,.0f} / NAV {row.nav:,.0f}")
        elif row.nav is not None:
            parts.append(f"NAV {row.nav:,.0f}")
        elif row.market_price is not None:
            parts.append(f"시장가 {row.market_price:,.0f}")
        disc = fmt_pct(row.discount_rate_pct)
        if disc:
            parts.append(f"괴리율 {disc}")
        if parts:
            notes.append(
                f"{h.display_name()} NAV ({row.asof} 기준): " + " · ".join(parts) + "."
            )
            fact_count += 1

    return notes, fact_count, asof_latest, matched_count
