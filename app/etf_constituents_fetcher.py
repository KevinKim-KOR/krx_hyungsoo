"""ETF 구성종목 외부 fetcher (POC2 — 2026-05-27).

본 모듈의 책임:
- 단일 ETF 의 (top_k, 구성종목 + 비중) 을 외부 소스에서 가져온다.
- 외부 의존성을 추상화 — 테스트는 dependency injection 으로 stub.

1차 구현 (지시문 §3 우선순위):
- pykrx `stock.get_etf_portfolio_deposit_file(date, ticker)` — KRX 공식 ETF PDF.
- KRX Open API / 다른 공식 경로는 별도 fetcher 추가로 확장 가능.

원칙 (지시문 §3 금지 항목):
- ETF명만 보고 구성종목 추정 X.
- AI 에게 구성종목 묻기 X.
- 비중 임의 생성 X.
- source 불명 데이터를 ok 처리 X.

수집 실패는 명시적 None / 예외로 반환한다 (호출자 service 가 unavailable
status 로 변환).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

PYKRX_SOURCE = "pykrx/get_etf_portfolio_deposit_file"

# fetcher signature: (etf_ticker, asof_yyyymmdd_or_iso, top_k) → FetchResult
FetcherFn = Callable[[str, str, int], "FetchResult"]


@dataclass
class FetchedConstituent:
    rank: int
    constituent_ticker: Optional[str]
    constituent_name: Optional[str]
    weight_pct: Optional[float]


@dataclass
class FetchResult:
    status: str  # "ok" / "unavailable"
    source: str
    constituents: list[FetchedConstituent]
    etf_name: Optional[str] = None
    message: Optional[str] = None


def _asof_to_yyyymmdd(asof: str) -> str:
    """'2026-05-26' → '20260526'. 이미 8자리면 그대로."""
    s = asof.replace("-", "")
    return s[:8]


def _to_optional_float(v) -> Optional[float]:
    try:
        if v is None:
            return None
        f = float(v)
        if f != f:  # NaN
            return None
        return f
    except (TypeError, ValueError):
        return None


def _pykrx_pdf_fetcher(etf_ticker: str, asof: str, top_k: int) -> FetchResult:
    """pykrx 기본 fetcher — KRX PDF. 호출 실패 / 빈 응답 시 unavailable."""
    try:
        from pykrx import (
            stock,
        )  # lazy import — pykrx 미설치 환경에서도 본 모듈 import 안전.
    except Exception as e:  # noqa: BLE001
        return FetchResult(
            status="unavailable",
            source=PYKRX_SOURCE,
            constituents=[],
            message=f"pykrx_import_failed: {type(e).__name__}: {e}",
        )
    yyyymmdd = _asof_to_yyyymmdd(asof)
    try:
        df = stock.get_etf_portfolio_deposit_file(yyyymmdd, etf_ticker)
    except Exception as e:  # noqa: BLE001
        return FetchResult(
            status="unavailable",
            source=PYKRX_SOURCE,
            constituents=[],
            message=f"pykrx_call_failed: {type(e).__name__}: {e}",
        )
    if df is None or len(df) == 0:
        return FetchResult(
            status="unavailable",
            source=PYKRX_SOURCE,
            constituents=[],
            message="no_data",
        )

    # pykrx PDF 컬럼: index=ticker, 비중(%) / 비중 (column 이름은 버전마다 차이).
    weight_col_candidates = ["비중", "비중(%)", "비중 (%)", "Weight"]
    weight_col = None
    for c in weight_col_candidates:
        if c in df.columns:
            weight_col = c
            break
    name_col = None
    for c in ("종목명", "이름", "Name"):
        if c in df.columns:
            name_col = c
            break

    # 비중 내림차순 정렬 후 top_k 추출.
    try:
        if weight_col is not None:
            df_sorted = df.sort_values(weight_col, ascending=False)
        else:
            df_sorted = df
        rows: list[FetchedConstituent] = []
        for rank_idx, (idx, raw) in enumerate(df_sorted.iterrows(), start=1):
            if rank_idx > max(1, top_k):
                break
            ticker = str(idx) if idx is not None else None
            name = None
            if name_col is not None:
                try:
                    name = str(raw[name_col]) if raw[name_col] is not None else None
                except Exception:  # noqa: BLE001
                    name = None
            weight = _to_optional_float(raw[weight_col]) if weight_col else None
            rows.append(
                FetchedConstituent(
                    rank=rank_idx,
                    constituent_ticker=ticker,
                    constituent_name=name,
                    weight_pct=weight,
                )
            )
        if not rows:
            return FetchResult(
                status="unavailable",
                source=PYKRX_SOURCE,
                constituents=[],
                message="parsed_empty",
            )
        return FetchResult(
            status="ok",
            source=PYKRX_SOURCE,
            constituents=rows,
            etf_name=None,
        )
    except Exception as e:  # noqa: BLE001
        return FetchResult(
            status="unavailable",
            source=PYKRX_SOURCE,
            constituents=[],
            message=f"parse_error: {type(e).__name__}: {e}",
        )


def default_fetcher() -> FetcherFn:
    """기본 fetcher 인스턴스 — pykrx PDF. 테스트는 stub 주입."""
    return _pykrx_pdf_fetcher
