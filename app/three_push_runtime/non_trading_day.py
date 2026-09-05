"""POC3-OPS-01A — 비거래일 최소 안전계약 (PLAN §9 · 설계자 V1.3 확정).

**신규 휴장일 캘린더를 만들지 않는다. 신규 외부 조회를 하지 않는다.
cron 을 바꾸지 않는다.** 이미 가져오는 quote 의 필드 하나(`price_asof`)만 본다.

근거: `app/market_naver.py` 는 Naver `localTradedAt` 을 **필수**로 요구한다.
없으면 quote 자체를 실패로 처리한다. 따라서 성공한 quote 는 반드시 "그 가격이
언제 체결된 값인지" 를 갖는다. 한국 공휴일에는 KRX 가 열리지 않아 Naver 가 직전
거래일 체결값을 반환한다.

    성공 quote **전부**의 체결일 < 오늘(KST)  →  오늘은 거래일이 아니다

`any` 가 아니라 `all` 이다. 한 종목이라도 오늘 체결값을 가지면 거래일로 본다 —
오탐(발송 억제)보다 과탐(발송)을 택한다.

**조회 실패를 비거래일로 오인하지 않는다.** 완전 수집이 아니면 판정하지 않는다.

**완전성 = 집합 일치 (설계자 확정 2026-09-05)**

    target_set  = 보유 원장에서 추출한 **고유 ticker** 집합
    success_set = 유효한 runtime quote 를 받은 ticker 집합

    complete = target_set 이 비어 있지 않고
               success_set == target_set 이고
               failed_tickers 가 비어 있음

건수 비교가 아니라 **집합 일치**다. 건수만 같고 다른 ticker 가 섞인 경우도
통과시키지 않는다.

경위 — 처음에는 `success == attempted` 였는데 **운영에서 참이 될 수 없었다**.
`collect_target_tickers("holdings_briefing")` 는 보유 **행** 수(32)를 돌려주고
`fetch_many` 는 **고유 ticker** 수(29)만 반환해, 실패 0건이어도 `29 != 32` 라
가드가 항상 죽었다. 그 뒤 `failed == 0 and success > 0` 으로 고쳤으나 이는
개발자 임의 판단이라 승인 대상이 됐고, 설계자가 **집합 일치**로 확정했다.
`attempted`(행 수)는 완전성 분모로 쓰지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class NonTradingDayResult:
    is_non_trading_day: bool
    quote_count: int = 0
    max_price_asof: Optional[str] = None
    today_kst: Optional[str] = None
    reason: str = ""

    def evidence(self) -> dict[str, Any]:
        return {
            "quote_count": self.quote_count,
            "max_price_asof": self.max_price_asof,
            "today_kst": self.today_kst,
        }


def _asof_date(quote: Any) -> Optional[str]:
    """`price_asof` 의 날짜 부분. ISO-8601 + KST (`2026-07-24T15:30:00+09:00`)."""
    raw = getattr(quote, "price_asof", None)
    if not isinstance(raw, str) or len(raw) < 10:
        return None
    return raw[:10]


def detect_non_trading_day(
    market_quotes: dict[str, Any],
    *,
    today_kst: str,
    target_tickers: Any,
    success_tickers: Any,
    failed_tickers: Any,
) -> NonTradingDayResult:
    """비거래일 판정 (설계자 확정 2026-09-05).

    조건 A (완전 수집): `target_set` 비어 있지 않음 · `success_set == target_set`
                        · `failed_tickers` 비어 있음
    조건 B: 성공 quote **전부**의 `price_asof` 날짜 < `today_kst`
    """
    target_set = set(target_tickers or ())
    success_set = set(success_tickers or ())
    failed_set = set(failed_tickers or ())
    if not target_set or success_set != target_set or failed_set:
        # 완전 수집이 아니면 판정하지 않는다. 휴장일인지 장애인지 구분할 수 없다.
        return NonTradingDayResult(
            is_non_trading_day=False,
            quote_count=len(success_set),
            today_kst=today_kst,
            reason="quote_incomplete",
        )

    asof_dates = [_asof_date(q) for q in market_quotes.values()]
    known = [d for d in asof_dates if d]
    if not known or len(known) != len(asof_dates):
        # as-of 없는 quote 는 upstream 에서 실패 처리되지만 방어적으로 판정 보류.
        return NonTradingDayResult(
            is_non_trading_day=False,
            quote_count=len(known),
            today_kst=today_kst,
            reason="asof_missing",
        )

    newest = max(known)
    if newest < today_kst:
        return NonTradingDayResult(
            is_non_trading_day=True,
            quote_count=len(known),
            max_price_asof=newest,
            today_kst=today_kst,
            reason="all_quotes_before_today",
        )
    return NonTradingDayResult(
        is_non_trading_day=False,
        quote_count=len(known),
        max_price_asof=newest,
        today_kst=today_kst,
        reason="traded_today",
    )
