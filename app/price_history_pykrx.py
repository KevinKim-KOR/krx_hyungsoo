"""POC2 Step 6 — pykrx 가격 히스토리 단일 호출 모듈.

설계자 결정 (Step 6 §6):
- pykrx 호출 코드는 본 모듈에만 둔다 — 다른 어디에서도 import 금지.
- ticker 별 1개월 (lookback_days=30) 가격 변화 계산에 필요한 base/latest close 를 추출.
- pykrx 예외는 통제된 결과 (PriceHistoryFailure) 로 변환 — 호출자가 candidate 단위로 격리.
- DB / 캐시 / history 도입 금지. 본 모듈은 호출 시점에 외부 fetch 만 수행.
- pykrx import 는 함수 호출 시점에 lazy import — 모듈 import 만으로는 외부 호출 미발생.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional, Union

DEFAULT_FETCH_WINDOW_DAYS = 45
DEFAULT_LOOKBACK_DAYS = 30


@dataclass
class PriceHistoryBasis:
    """pykrx 1개월 수익률 계산용 기준 데이터 — 성공 결과."""

    base_date: str  # 'YYYY-MM-DD'
    base_close: float
    latest_date: str  # 'YYYY-MM-DD'
    latest_close: float


@dataclass
class PriceHistoryFailure:
    """pykrx 조회/추출 실패 — candidate 단위 격리용."""

    reason: str  # 'no_data' | 'fetch_error' | 'no_base_close' | 'asof_invalid'
    detail: Optional[str] = None


PriceHistoryResult = Union[PriceHistoryBasis, PriceHistoryFailure]


def _parse_asof(asof: str) -> date:
    """'YYYY-MM-DD' → date. 형식 오류는 ValueError 로 통일."""
    return datetime.strptime(asof, "%Y-%m-%d").date()


def _fetch_pykrx_ohlcv(ticker: str, fromdate: date, todate: date):
    """pykrx 호출 wrapper — 단일 진입점. 테스트에서는 본 함수를 monkeypatch.

    예외는 호출자가 catch — fetch_error 분기에서 detail 포함.
    """
    from pykrx import stock  # lazy import

    from_str = fromdate.strftime("%Y%m%d")
    to_str = todate.strftime("%Y%m%d")
    return stock.get_market_ohlcv(from_str, to_str, ticker)


def fetch_one_month_basis(
    ticker: str,
    asof: str,
    fetch_window_days: int = DEFAULT_FETCH_WINDOW_DAYS,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
) -> PriceHistoryResult:
    """asof 기준 1개월 수익률 계산용 base/latest close 를 pykrx 에서 추출.

    절차:
    1. asof 검증 + fromdate = asof - fetch_window_days 일.
    2. pykrx OHLCV 조회 (fromdate ~ asof).
    3. 데이터프레임 비어 있거나 '종가' 컬럼 없으면 실패.
    4. latest_date / latest_close = 마지막 거래일의 종가.
    5. base_target = asof - lookback_days. 그 날짜 또는 이후의 첫 거래일을 base 로.
    6. base_idx == last_idx (단일 거래일만 존재) → no_base_close.

    반환: 성공 시 PriceHistoryBasis, 실패 시 PriceHistoryFailure.
    """
    try:
        asof_date = _parse_asof(asof)
    except (TypeError, ValueError) as e:
        return PriceHistoryFailure(reason="asof_invalid", detail=str(e))

    fromdate = asof_date - timedelta(days=fetch_window_days)
    todate = asof_date

    try:
        df = _fetch_pykrx_ohlcv(ticker, fromdate, todate)
    except Exception as e:  # noqa: BLE001 — 외부 의존 광범위 예외 격리
        return PriceHistoryFailure(reason="fetch_error", detail=f"pykrx: {e}")

    if df is None or len(df) == 0:
        return PriceHistoryFailure(reason="no_data")
    if "종가" not in df.columns:
        return PriceHistoryFailure(reason="fetch_error", detail="no '종가' column")

    df = df.sort_index()

    last_idx = df.index[-1]
    try:
        latest_close = float(df.loc[last_idx, "종가"])
    except (TypeError, ValueError) as e:
        return PriceHistoryFailure(reason="fetch_error", detail=f"latest cast: {e}")

    if not (latest_close > 0):
        return PriceHistoryFailure(reason="no_data", detail="latest_close <= 0")

    latest_date_str = last_idx.strftime("%Y-%m-%d")

    base_target = asof_date - timedelta(days=lookback_days)
    base_idx = None
    for idx in df.index:
        if idx.date() >= base_target:
            base_idx = idx
            break
    if base_idx is None or base_idx == last_idx:
        return PriceHistoryFailure(
            reason="no_base_close",
            detail=f"no trading day on or after {base_target.isoformat()}",
        )

    try:
        base_close = float(df.loc[base_idx, "종가"])
    except (TypeError, ValueError) as e:
        return PriceHistoryFailure(reason="fetch_error", detail=f"base cast: {e}")

    if not (base_close > 0):
        return PriceHistoryFailure(reason="no_base_close", detail="base_close <= 0")

    return PriceHistoryBasis(
        base_date=base_idx.strftime("%Y-%m-%d"),
        base_close=base_close,
        latest_date=latest_date_str,
        latest_close=latest_close,
    )


def compute_one_month_return_pct(basis: PriceHistoryBasis) -> float:
    """one_month_return_pct = (latest_close / base_close - 1) * 100."""
    return (basis.latest_close / basis.base_close - 1.0) * 100.0
