"""ETF 구성 행 종류 판정(운영 공통 · POC6-31).

POC6-30 연구 모듈(`app/sector_constituents_comparison.py`)에서 옮겨 온 판정이다(POC6-31 PLAN 판정 Q8 (a)).
연구 모듈은 이 모듈을 가져다 쓴다 — 운영 경로가 연구 모듈을 가져다 쓰지 않게 하려는 방향(DEV_RULES §2.1).

판정 순서(앞에서 걸리면 끝 · POC6-30 PLAN §3 S4 표):
원화현금(ISIN) → 선물 · 옵션(시장 구분 4) → 국내 ETF(ETF 목록에 있는 종목코드) → 채권(시장 구분 3 · 이름에 '채권')
→ 국내 주식(시장 구분 0 · 1 · ISIN KR7 · 6자리 종목코드) → 종류 미확인(시장 구분 2 · ISIN 칸이 12자리 모양이 아님)
→ 해외 ETF(이름이 스스로 ETF) → 종류 미확인(Fund · Trust · SPDR · iShares) → 해외 주식 → 그 밖 종류 미확인.
"""

from __future__ import annotations

import re
from typing import Any, Mapping

CASH_ISIN = "KRD010010001"
# ISIN 칸 모양 — 12자리 · 앞 2자리 영문(검증 숫자는 보지 않음: 원천에 끝자리가 영문인 실제 주식 행이 있다).
# 모양이 아니면(예: 선물 약호 5자리) 주식인지 가를 수 없다.
ISIN_SHAPE = re.compile(r"^[A-Z]{2}[A-Z0-9]{10}$")
ETF_WORD = re.compile(
    r"\bETF\b", re.IGNORECASE
)  # 이름이 스스로 ETF 라고 밝힘 → 해외 ETF
FUND_WORDS = re.compile(
    r"\b(Fund|Trust|SPDR|iShares)\b", re.IGNORECASE
)  # 기업 이름에도 쓰여 종류를 가를 수 없음

CASH, DERIVATIVE, DOMESTIC_ETF = "cash", "derivative", "domestic_etf"
BOND, FOREIGN_ETF = "bond", "foreign_etf"
DOMESTIC_STOCK, FOREIGN_STOCK, UNKNOWN = "domestic_stock", "foreign_stock", "unknown"
STOCK_KINDS = frozenset({DOMESTIC_STOCK, FOREIGN_STOCK})
KIND_LABEL = {
    CASH: "원화현금",
    DERIVATIVE: "선물 · 옵션",
    DOMESTIC_ETF: "국내 ETF",
    BOND: "채권",
    FOREIGN_ETF: "해외 ETF",
    DOMESTIC_STOCK: "국내 주식",
    FOREIGN_STOCK: "해외 주식",
    UNKNOWN: "종류 미확인",
}


def row_kind(row: Mapping[str, Any], etf_tickers: set[str]) -> str:
    """구성 행 하나의 종류. `row` 칸: isin · market_type · ticker · name(없으면 빈 값)."""
    isin = (row.get("isin") or "").strip()
    mt = (row.get("market_type") or "").strip()
    tk = (row.get("ticker") or "").strip()
    name = row.get("name") or ""
    if isin == CASH_ISIN:
        return CASH
    if mt == "4":
        return DERIVATIVE
    if tk and tk in etf_tickers:
        return DOMESTIC_ETF
    if mt == "3" and "채권" in name:
        return BOND
    if (
        mt in ("0", "1")
        and isin.startswith("KR7")
        and ISIN_SHAPE.match(isin)
        and len(tk) == 6
    ):
        return DOMESTIC_STOCK
    if mt == "2" and not ISIN_SHAPE.match(isin):
        return UNKNOWN
    if mt == "2":
        if ETF_WORD.search(name):
            return FOREIGN_ETF
        return UNKNOWN if FUND_WORDS.search(name) else FOREIGN_STOCK
    return UNKNOWN
