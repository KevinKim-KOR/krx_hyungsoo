"""Runtime price refresh helper (Low-Frequency Telegram Push Operation v1 A+).

Runner 로부터 분리한 가격 조회 책임. Runner 는 이 함수의 반환값 (성공 quotes +
진단 dict) 을 받아 Fail-Closed 판정만 수행한다.

Fail-Closed 계약 (사용자 A+ 확정):
- 가격 전건 실패 → Runner 가 failed 종료.
- 가격 일부 실패 → Runner 가 failed 종료 (partial 발송 금지).
- Naver 예외 자체 → Runner 가 failed 종료.
- attempted==0 (Market 등 refresh 불필요) → 정상 진행.

이 함수 자체는 정책 판정을 하지 않고 raw 결과만 반환한다.
"""

from __future__ import annotations

from typing import Any, Optional


def refresh_runtime_quotes(
    push_kind: str,
    collect_target_tickers,  # Callable[[str], list[str]] — Fail-Closed: 예외 propagate
) -> tuple[dict[str, Any], dict[str, Any], Optional[str]]:
    """Runtime price refresh 수행.

    반환:
        (market_quotes, diag, error_str)
        market_quotes: {ticker: MarketQuote} — 조회 성공만.
        diag: {"attempted": n, "success": n, "failed": n, "failed_tickers": [...]}.
              refresh 불필요한 push_kind 는 {"attempted":0,"success":0,"failed":0}.
        error_str: 예외 발생 시 "TypeName: msg[:200]" · 성공 시 None.
                   Runner 는 error_str is not None 이면 failed 로 종료.
    """
    market_quotes: dict[str, Any] = {}
    diag: dict[str, Any] = {"attempted": 0, "success": 0, "failed": 0}
    if push_kind not in ("holdings_briefing", "spike_or_falling_alert"):
        return market_quotes, diag, None
    try:
        tickers = collect_target_tickers(push_kind)
    except Exception as e:  # noqa: BLE001
        return market_quotes, diag, f"{type(e).__name__}: {str(e)[:200]}"
    if not tickers:
        return market_quotes, diag, None
    try:
        from app import market_naver

        results = market_naver.fetch_many(tickers)
    except Exception as e:  # noqa: BLE001
        diag["error"] = f"{type(e).__name__}"
        return market_quotes, diag, f"{type(e).__name__}: {str(e)[:200]}"
    for r in results:
        if r.quote is not None:
            market_quotes[r.ticker] = r.quote
    diag = {
        "attempted": len(tickers),
        "success": sum(1 for r in results if r.quote is not None),
        "failed": sum(1 for r in results if r.quote is None),
        "failed_tickers": [r.ticker for r in results if r.quote is None],
    }
    return market_quotes, diag, None
