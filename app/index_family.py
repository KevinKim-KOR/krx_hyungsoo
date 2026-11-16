"""ETF 지수 계열(POC6-31 PLAN 판정 §2 첫째 · Q9).

- 공식 기초지수명(KRX 기준정보 CSV `기초지수명`)이 같으면 한 계열이다.
- 이름이 다른 지수는 **같은 기초지수임이 확인된 사례만** 한 계열로 묶는다. 지금 확인된 사례는
  POC6-30 PLAN 판정 Q2
  (`docs/ai_design/POC6/POC6_30_SECTOR_SUMMARY_CONSTITUENTS_PLAN_DECISION_2026-11-14.md`)가
  확인한 Dow Jones U.S. Dividend 100 계열(가격지수형 1 + 커버드콜 3)뿐이다 — 공식 지수명 4개 그대로 적는다.
  새 사례는 설계자 판정으로만 더한다(이름 규칙으로 자동 합치지 않음).
- 공식 지수명이 없으면 계열 미확인(None).
"""

from __future__ import annotations

from typing import Optional

DJ_DIVIDEND_100 = "Dow Jones U.S. Dividend 100 계열"

# 공식 기초지수명 → 계열 이름(판정으로 확인된 같은 기초지수 · 이름 문자열 그대로).
CONFIRMED_SAME_INDEX: dict[str, str] = {
    "Dow Jones U.S. Dividend 100 Price Return Index": DJ_DIVIDEND_100,
    "Dow Jones U.S. Dividend 100 10% Premium Covered Call Index(Total Return)": DJ_DIVIDEND_100,
    "DowJones U.S. Dividend 100 7% Premium Covered Call 지수 (TR)": DJ_DIVIDEND_100,
    "DowJones U.S. Dividend 100 3% Premium Covered Call 지수 (TR)": DJ_DIVIDEND_100,
}


def family_of(index_name: Optional[str]) -> Optional[str]:
    """지수 계열 이름. 확인된 같은 기초지수 → 그 계열 · 아니면 공식 지수명 · 없으면 None."""
    name = (index_name or "").strip()
    if not name:
        return None
    return CONFIRMED_SAME_INDEX.get(name, name)
