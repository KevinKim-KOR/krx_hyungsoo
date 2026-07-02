"""Naver/FDR 주 소스 + Yahoo/FDR 보조 소스 adapter (2026-06-30 Closeout).

지시문 §4.1 / §4.2 원칙:
- 주 소스: NAVER_FDR — `fdr.DataReader("NAVER:<ticker>", start, end)`.
- 보조 소스: YAHOO_FDR — `fdr.DataReader("YAHOO:<ticker>.KS", start, end)`.
- 호출 식별자에 소스를 명시하여 FDR 의 기본 source inference 에 의존하지 않는다
  (FIX r1 — 지시문 §4.1 "기본 동작에 의존하지 말고 네이버 소스를 명시").
- Yahoo 는 네이버/FDR 실패 또는 빈 응답일 때만 1회 호출. 자동 재시도 없음.
- 새 의존성 도입 금지 — 기존 FinanceDataReader 만 사용.

가격 필드: Close 만 사용. Adj Close 사용 금지. price_basis="SOURCE_CLOSE".
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Callable, Optional

SOURCE_NAVER = "NAVER_FDR"
SOURCE_YAHOO = "YAHOO_FDR"
PRICE_BASIS = "SOURCE_CLOSE"

# FDR 호출 식별자 형식 (지시문 §4.1 / §4.2 — 소스 명시).
NAVER_PREFIX = "NAVER:"
YAHOO_PREFIX = "YAHOO:"
YAHOO_KRX_SUFFIX = ".KS"


def build_naver_symbol(ticker: str) -> str:
    """네이버/FDR 호출용 명시 식별자. 예: '069500' -> 'NAVER:069500'."""
    return f"{NAVER_PREFIX}{ticker}"


def build_yahoo_symbol(ticker: str) -> str:
    """Yahoo/FDR 호출용 명시 식별자. 예: '069500' -> 'YAHOO:069500.KS'."""
    return f"{YAHOO_PREFIX}{ticker}{YAHOO_KRX_SUFFIX}"


# fdr.DataReader(symbol, start, end) 형태의 fetcher — 테스트 stub 주입용.
# symbol 은 build_naver_symbol / build_yahoo_symbol 이 만든 명시 식별자.
PriceFetcher = Callable[[str, date, date], "object"]


@dataclass
class AdapterResult:
    ticker: str
    rows: list[tuple[str, Optional[float]]]  # (YYYY-MM-DD, close)
    source: str  # NAVER_FDR / YAHOO_FDR
    error: Optional[str] = None
    yahoo_attempted: bool = False


def _default_price_fetcher(ticker: str, start: date, end: date):
    import FinanceDataReader as fdr  # lazy import

    return fdr.DataReader(ticker, start, end)


def _df_to_close_rows(df) -> list[tuple[str, Optional[float]]]:
    """FDR DataFrame → (YYYY-MM-DD, close) 리스트. Close 만 사용."""
    out: list[tuple[str, Optional[float]]] = []
    if df is None or len(df) == 0:
        return out
    if "Close" not in df.columns:
        return out
    for idx, raw in df.iterrows():
        try:
            dt = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)[:10]
        except Exception:  # noqa: BLE001
            continue
        close_raw = raw["Close"]
        try:
            if close_raw is None:
                close = None
            else:
                close = float(close_raw)
                if close != close:  # NaN
                    close = None
        except (TypeError, ValueError):
            close = None
        out.append((dt, close))
    return out


def fetch_ticker_prices(
    ticker: str,
    *,
    start: date,
    end: date,
    price_fetcher: Optional[PriceFetcher] = None,
) -> AdapterResult:
    """네이버/FDR 1회 → 빈 응답 또는 실패 시 Yahoo/FDR 1회.

    호출 식별자에 소스를 명시한다 (지시문 §4.1 / §4.2 — FDR 기본
    source inference 에 의존하지 않는다):
      Primary   : fdr.DataReader("NAVER:<ticker>", ...)
      Secondary : fdr.DataReader("YAHOO:<ticker>.KS", ...)

    price_fetcher 는 테스트에서 stub 주입. 미제공 시 실제 FDR 사용.
    """
    fetch = price_fetcher or _default_price_fetcher

    # 1) Primary: NAVER_FDR — 명시 식별자 사용.
    naver_error: Optional[str] = None
    naver_symbol = build_naver_symbol(ticker)
    try:
        df = fetch(naver_symbol, start, end)
        rows = _df_to_close_rows(df)
        if rows:
            return AdapterResult(
                ticker=ticker,
                rows=rows,
                source=SOURCE_NAVER,
                error=None,
                yahoo_attempted=False,
            )
    except Exception as e:  # noqa: BLE001
        naver_error = f"{type(e).__name__}: {e}"[:200]

    # 2) Secondary: YAHOO_FDR — 명시 식별자 + .KS suffix.
    yahoo_symbol = build_yahoo_symbol(ticker)
    try:
        df = fetch(yahoo_symbol, start, end)
        rows = _df_to_close_rows(df)
        if rows:
            return AdapterResult(
                ticker=ticker,
                rows=rows,
                source=SOURCE_YAHOO,
                error=None,
                yahoo_attempted=True,
            )
        # 빈 응답도 실패로 기록
        yahoo_error = "empty_response"
    except Exception as e:  # noqa: BLE001
        yahoo_error = f"{type(e).__name__}: {e}"[:200]

    combined_error = (f"naver:{naver_error or 'empty_response'} | yahoo:{yahoo_error}")[
        :300
    ]
    return AdapterResult(
        ticker=ticker,
        rows=[],
        source=SOURCE_NAVER,
        error=combined_error,
        yahoo_attempted=True,
    )
