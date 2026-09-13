"""POC3-OPS-02B-2 — 전망(`SP500_SIGN_V1`)과 기초지수 산출.

**순수 계산만 한다.** 외부 I/O·DB 접근은 호출자(`flow`)가 넘긴 값으로 대신한다.

## 전망 — `SP500_SIGN_V1`

`OPS-02B-1` 확정 운영 규칙이다. **직전 미국 거래일의 1일 종가 수익률의 부호**만
쓴다. OLS 는 `RESEARCH_REFERENCE` 이고 운영에 쓰지 않는다.

- `MIXED` **없음.** Nasdaq·반도체가 반대여도 상태를 바꾸거나 가중치를 만들지
  않는다 — 두 지수는 **근거 줄 표시 전용**이다.
- S&P500 이 **정확히 0** 이면 임의 중립 구간을 만들지 않고 **`FLAT`** 이다.
- S&P500 이 stale·unavailable 이면 **`NONE`**.
- **예상 등락률을 만들지 않는다.** 방향 압력까지만이다.

## 기초지수 — `최근 강한 기초지수`

`OPS-02B-1` 검증 계약을 그대로 쓴다. **새 순위 산식을 만들지 않는다.**
가격은 **KRX 무조정 계열에서만** 온다(설계자 §M-1).
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Any, Optional, Sequence

OUTLOOK_UP = "UP"
OUTLOOK_DOWN = "DOWN"
OUTLOOK_FLAT = "FLAT"
OUTLOOK_NONE = "NONE"

MIN_TICKERS_PER_INDEX = 2
MAX_INDEX_CANDIDATES = 2


@dataclass(frozen=True)
class Outlook:
    """방향 압력. **숫자 예측을 담지 않는다.**"""

    state: str
    sp500_return_pct: Optional[float] = None
    sp500_asof: Optional[str] = None
    reason: Optional[str] = None

    @property
    def usable(self) -> bool:
        """전망 문장을 만들 수 있는가. `FLAT` 도 문장이 있다."""
        return self.state in (OUTLOOK_UP, OUTLOOK_DOWN, OUTLOOK_FLAT)

    @property
    def fingerprint_state(self) -> str:
        return self.state


def decide_outlook(
    *,
    sp500_return_pct: Optional[float],
    sp500_asof: Optional[str],
    sp500_fresh: bool,
) -> Outlook:
    """`SP500_SIGN_V1`. **S&P500 하나만** 본다.

    Nasdaq·반도체는 인자로 받지도 않는다 — 받으면 언젠가 섞인다.
    """
    if not sp500_fresh or sp500_return_pct is None:
        return Outlook(
            state=OUTLOOK_NONE,
            sp500_asof=sp500_asof,
            reason="stale_or_unavailable",
        )
    if sp500_return_pct > 0:
        state = OUTLOOK_UP
    elif sp500_return_pct < 0:
        state = OUTLOOK_DOWN
    else:
        state = OUTLOOK_FLAT
    return Outlook(
        state=state, sp500_return_pct=sp500_return_pct, sp500_asof=sp500_asof
    )


@dataclass(frozen=True)
class SupportIndex:
    """근거 줄에 쓰는 보조 지수. **방향 결정에 관여하지 않는다.**"""

    label: str
    return_pct: float
    asof: str


@dataclass(frozen=True)
class IndexCandidate:
    agency: str
    name: str
    ret_5d_pct: float
    ret_20d_pct: float
    ticker_count: int
    # 사용자 요청(2026-09-13) — "추종 ETF 2개" 만으로는 무엇인지 알 수 없다.
    # 공식 CSV `한글종목약명` 을 그대로 쓴다. 축약·번역·테마명 변환 금지.
    products: tuple[str, ...] = ()

    @property
    def identifier(self) -> str:
        """공식 식별자. 축약·번역·테마명 변환을 하지 않는다."""
        return f"{self.agency}|{self.name}"


@dataclass
class IndexLeadership:
    status: str
    candidates: list[IndexCandidate] = field(default_factory=list)
    price_asof: Optional[str] = None
    diagnostics: dict[str, Any] = field(default_factory=dict)

    @property
    def fingerprint_state(self) -> str:
        if self.status != "ok" or not self.candidates:
            return "NONE"
        return "|".join(sorted(c.identifier for c in self.candidates))


def eligible_products(meta_rows: Sequence[dict[str, str]]) -> list[dict[str, str]]:
    """주식형 · 추적배수 일반 · 합성 제외. `02B-1` 검증 계약 그대로."""
    return [
        r
        for r in meta_rows
        if (r.get("기초자산분류") or "").strip() == "주식"
        and (r.get("추적배수") or "").strip() == "일반"
        and "합성" not in (r.get("복제방법") or "")
    ]


def group_by_index(rows: Sequence[dict[str, str]]) -> dict[tuple[str, str], set[str]]:
    """식별키 = `지수산출기관 + 기초지수명` **완전일치**. fuzzy matching 금지."""
    groups: dict[tuple[str, str], set[str]] = {}
    for r in rows:
        key = (
            (r.get("지수산출기관") or "").strip(),
            (r.get("기초지수명") or "").strip(),
        )
        ticker = (r.get("단축코드") or "").strip()
        if key[0] and key[1] and ticker:
            groups.setdefault(key, set()).add(ticker)
    return groups


def product_short_names(rows: Sequence[dict[str, str]]) -> dict[str, str]:
    """`단축코드 → 한글종목약명`. 약명이 비면 그 ticker 는 담지 않는다.

    축약·번역·테마명 변환을 하지 않는다 — 공식 CSV 값 그대로다.
    """
    out: dict[str, str] = {}
    for r in rows:
        t = (r.get("단축코드") or "").strip()
        nm = (r.get("한글종목약명") or "").strip()
        if t and nm:
            out[t] = nm
    return out


def compute_index_leadership(
    *,
    meta_rows: Sequence[dict[str, str]],
    closes: dict[str, dict[str, float]],
    latest: str,
    d5: str,
    d20: str,
) -> IndexLeadership:
    """유효 ticker 로만 그룹 수익률을 낸다.

    설계자 §M-4 — **세 기준 가격이 모두 있어야** 그 ticker 를 `n` 에 포함한다.
    stale·결측 ticker 를 세면 `n≥2` 가 거짓으로 성립한다.

    `코스피 200` 처럼 "정보 가치가 낮아 보이는" 지수를 개발자 판단으로 빼지
    않는다. 목업을 본 뒤 사용자가 판정한다.
    """
    products = eligible_products(meta_rows)
    groups = group_by_index(products)
    short_names = product_short_names(products)
    cl_latest = closes.get(latest) or {}
    cl_5 = closes.get(d5) or {}
    cl_20 = closes.get(d20) or {}

    candidates: list[IndexCandidate] = []
    dropped_insufficient = 0
    for (agency, name), tickers in groups.items():
        r5: list[float] = []
        r20: list[float] = []
        valid_tickers: list[str] = []
        # 종목코드 오름차순 — 표시 순서를 위한 **고정 순서**다. 수익률·인기도 같은
        # 새 순위 산식을 만들지 않는다(설계 §4).
        for t in sorted(tickers):
            a, b, c = cl_latest.get(t), cl_5.get(t), cl_20.get(t)
            if not a or not b or not c or a <= 0 or b <= 0 or c <= 0:
                continue
            valid_tickers.append(t)
            r5.append((a / b - 1.0) * 100.0)
            r20.append((a / c - 1.0) * 100.0)
        valid = len(valid_tickers)
        if valid < MIN_TICKERS_PER_INDEX:
            dropped_insufficient += 1
            continue
        m5, m20 = statistics.median(r5), statistics.median(r20)
        if m5 > 0 and m20 > 0:
            candidates.append(
                IndexCandidate(
                    agency=agency,
                    name=name,
                    ret_5d_pct=round(m5, 1),
                    ret_20d_pct=round(m20, 1),
                    ticker_count=valid,
                    # 수익률 계산에 **실제로 쓰인** ticker 만. 결측·stale 로 빠진
                    # ticker 를 이름으로 되살리지 않는다.
                    products=tuple(
                        short_names[t] for t in valid_tickers if t in short_names
                    ),
                )
            )

    # 동률 순서 (설계 §4): 20일 내림 → 5일 내림 → 공식 식별자 오름.
    candidates.sort(key=lambda c: (-c.ret_20d_pct, -c.ret_5d_pct, c.identifier))
    top = candidates[:MAX_INDEX_CANDIDATES]
    return IndexLeadership(
        status="ok",
        candidates=top,
        price_asof=latest,
        diagnostics={
            "group_count": len(groups),
            "candidate_count": len(candidates),
            "dropped_insufficient_valid_tickers": dropped_insufficient,
            "price_asof": latest,
            "lookback_dates": {"latest": latest, "d5": d5, "d20": d20},
        },
    )


__all__ = [
    "MAX_INDEX_CANDIDATES",
    "MIN_TICKERS_PER_INDEX",
    "OUTLOOK_DOWN",
    "OUTLOOK_FLAT",
    "OUTLOOK_NONE",
    "OUTLOOK_UP",
    "IndexCandidate",
    "IndexLeadership",
    "Outlook",
    "SupportIndex",
    "compute_index_leadership",
    "decide_outlook",
    "eligible_products",
    "group_by_index",
    "product_short_names",
]
