"""POC6-29 — 보유 현재가 갱신(네이버) 한 번에 하나(PLAN §3-6 · 판정 Q7).

`POST /holdings/market/refresh`(「보유 현황」 [시세 갱신 (Naver)])의 본문을 그대로 옮기고 서버 잠금을 더한다.
연타 · 다른 탭 · 「보유 현황」 · [최신 자료 갱신] 묶음 작업이 겹쳐도 네이버 조회는 한 번만 돈다 — 도는 중에
들어온 호출은 그 실행이 끝날 때까지 기다렸다가 **같은 결과**를 받는다(새로 조회하지 않음).

동작은 기존 endpoint 와 같다: 보유 파일 손상 = 500 · 보유 없음 = 422(`HoldingsRefreshRejected`) · 종목별 실패는
격리 · 성공한 시세만 캐시(`market_cache.upsert_many`)에 반영. 외부 호출은 네이버 `fetch_many` 하나(호출 시점에
모듈 속성으로 찾는다 — 기존 시험의 바꿔 끼우기 그대로).
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Callable, Optional

from app import holdings as holdings_module
from app import market_cache, market_naver
from app.holdings import HoldingsValidationError
from app.market_cache import MarketQuote

FetchMany = Callable[[list[str]], list[market_naver.FetchResult]]

EMPTY_DETAIL = "holdings 가 비어 있습니다. 먼저 보유 종목을 입력 후 저장해 주세요."


@dataclass(frozen=True)
class QuoteRefreshResult:
    ok_count: int
    fail_count: int
    quotes: list[MarketQuote]
    failures: list[dict[str, str]]


class HoldingsRefreshRejected(Exception):
    """기존 endpoint 의 HTTP 거절(보유 파일 손상 500 · 보유 없음 422)과 같은 값."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class _Flight:
    def __init__(self) -> None:
        self.done = threading.Event()
        self.result: Optional[QuoteRefreshResult] = None
        self.error: Optional[BaseException] = None


_lock = threading.Lock()
_inflight: Optional[_Flight] = None


def _run(fetch_many: Optional[FetchMany]) -> QuoteRefreshResult:
    try:
        loaded = holdings_module.load()
    except HoldingsValidationError as e:
        raise HoldingsRefreshRejected(500, f"holdings 저장 파일 손상: {e}")
    if not loaded:
        raise HoldingsRefreshRejected(422, EMPTY_DETAIL)

    tickers = [h.ticker for h in loaded]
    results = (fetch_many or market_naver.fetch_many)(tickers)

    successes = [r for r in results if r.quote is not None]
    failures = [r for r in results if r.quote is None]
    if successes:
        market_cache.upsert_many([r.quote for r in successes])  # type: ignore[misc]
    return QuoteRefreshResult(
        ok_count=len(successes),
        fail_count=len(failures),
        quotes=[r.quote for r in successes if r.quote is not None],
        failures=[
            {"ticker": r.ticker, "reason": r.reason or "unknown"} for r in failures
        ],
    )


def refresh_holdings_quotes_shared(
    fetch_many: Optional[FetchMany] = None,
) -> tuple[QuoteRefreshResult, bool]:
    """(결과, 다른 호출이 이미 돌리던 실행에 붙었는지). 붙은 호출은 그 실행의 결과 · 거절을 그대로 받는다."""
    global _inflight
    with _lock:
        flight = _inflight
        joined = flight is not None
        if flight is None:
            flight = _inflight = _Flight()
    if joined:
        flight.done.wait()
        err = flight.error
        if isinstance(err, HoldingsRefreshRejected):
            raise HoldingsRefreshRejected(err.status_code, err.detail)
        if err is not None:
            raise RuntimeError("보유 현재가 갱신이 실패했습니다.") from err
        assert flight.result is not None
        return flight.result, True
    try:
        flight.result = _run(fetch_many)
        return flight.result, False
    except (
        BaseException
    ) as e:  # noqa: BLE001 — 기다리는 호출에 같은 실패를 넘긴 뒤 다시 던진다
        flight.error = e
        raise
    finally:
        with _lock:
            _inflight = None
        flight.done.set()


def refresh_holdings_quotes(
    fetch_many: Optional[FetchMany] = None,
) -> QuoteRefreshResult:
    return refresh_holdings_quotes_shared(fetch_many)[0]
