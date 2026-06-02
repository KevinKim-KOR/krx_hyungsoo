"""NAV / 괴리율 fetcher 인터페이스 + default unavailable fetcher
(POC2 — 2026-06-01).

Market Discovery Evidence Closeout 1차 — 지시문 §7 / §9.

본 STEP 은 NAV/괴리율 source 가 미확정이라 default fetcher 가 항상
unavailable 을 반환한다. 인터페이스만 깔아 두고 별도 진단 STEP 에서 실
source (Naver Stock 계열 ETF 상세 endpoint 등) 채택 시 fetcher 교체.

플래그 (지시문 §7.3):
- 괴리율 절대값 3% 이상 → discount_check_needed
- 괴리율 절대값 5% 이상 → discount_warning
- 플래그는 데이터 품질 확인용. 매수/매도 판단 X.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

DISCOUNT_CHECK_THRESHOLD_PCT = 3.0
DISCOUNT_WARNING_THRESHOLD_PCT = 5.0

UNAVAILABLE_SOURCE = "unavailable"


@dataclass(frozen=True)
class NavFetchResult:
    """NAV / 괴리율 수집 결과.

    status: ok / unavailable / partial
    discount_rate_pct: source 가 직접 제공하면 우선, 없으면 본 모듈이 계산
        (지시문 §7.2). NAV / 시장가격 중 하나라도 없으면 None.
    """

    status: str
    asof: Optional[str] = None
    nav: Optional[float] = None
    market_price: Optional[float] = None
    discount_rate_pct: Optional[float] = None
    source: str = UNAVAILABLE_SOURCE
    message: Optional[str] = None


# Fetcher 시그니처: (ticker) -> NavFetchResult.
NavFetcher = Callable[[str], NavFetchResult]


def unavailable_nav_fetcher(ticker: str) -> NavFetchResult:  # noqa: ARG001
    """default fetcher — 항상 unavailable (지시문 §7.4 마지막 단락).

    실 source 가 채택되기 전까지 이 fetcher 가 사용된다. 외부 호출 0건.
    """
    return NavFetchResult(
        status="unavailable",
        source=UNAVAILABLE_SOURCE,
        message="NAV / discount source not yet adopted (BACKLOG)",
    )


def compute_discount_rate_pct(
    nav: Optional[float], market_price: Optional[float]
) -> Optional[float]:
    """(시장가격 - NAV) / NAV × 100 (지시문 §7.2). 입력 부족 시 None."""
    if nav is None or market_price is None or nav <= 0:
        return None
    return (market_price - nav) / nav * 100.0


def classify_discount_flag(discount_rate_pct: Optional[float]) -> Optional[str]:
    """괴리율 절대값 기준 플래그 (지시문 §7.3)."""
    if discount_rate_pct is None:
        return None
    abs_pct = abs(discount_rate_pct)
    if abs_pct >= DISCOUNT_WARNING_THRESHOLD_PCT:
        return "discount_warning"
    if abs_pct >= DISCOUNT_CHECK_THRESHOLD_PCT:
        return "discount_check_needed"
    return None


def default_nav_fetcher() -> NavFetcher:
    """본 STEP 의 default — unavailable_nav_fetcher.

    별도 진단 STEP 에서 실 source 채택 시 본 함수만 교체.
    """
    return unavailable_nav_fetcher
