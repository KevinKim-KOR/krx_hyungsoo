"""FinanceDataReader wrapper — B 방향 PC 작업 ETF 데이터 소스.

본 모듈은 FDR 호출의 단일 진입점이다. 테스트는 본 모듈의 함수를
monkeypatch 로 stub 처리한다.

원칙:
- universe listing 은 fdr.StockListing("ETF/KR") 1회로 끝낸다.
- 가격 시계열은 ticker 별 fdr.DataReader 호출 — etf_master 에는 영향 없음.
- 외부 의존이라 호출 실패는 candidate 단위로 격리.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Callable, Optional, Sequence

from app.market_data_store import (
    DEFAULT_DB_PATH,
    EtfDailyPriceRow,
    EtfMasterRow,
    log_refresh,
    normalize_ticker_list,
    upsert_daily_prices,
    upsert_etf_master,
)

FDR_SOURCE = "FinanceDataReader"
DEFAULT_LOOKBACK_DAYS = 120  # 3개월 수익률 + 거래일/휴장일 여유

UniverseFetcher = Callable[[], "object"]  # returns pandas DataFrame
PriceFetcher = Callable[[str, date, date], "object"]


@dataclass
class UniverseRefreshResult:
    run_id: str
    universe_count: int
    runtime_seconds: float
    success: bool
    error: Optional[str] = None


@dataclass
class PriceRefreshResult:
    run_id: str
    attempted: int  # 요청 대상 종목 수(기존 의미 · 시작 안 한 종목 포함)
    success: int
    fail: int  # attempted - success(기존 의미 · 시작 안 한 종목 포함)
    runtime_seconds: float
    failure_examples: list[dict] = field(default_factory=list)
    # POC5-17 — 연속 시간 초과로 멈췄을 때만 채운다(인자를 준 호출만 · 기본 0 / False).
    not_started: int = 0  # 멈춘 뒤 조회하지 않은 종목 수(시도 · 시간 초과로 세지 않음)
    stopped_on_timeouts: bool = False


def _is_request_timeout(exc: BaseException) -> bool:
    """실제 요청 시간 초과만 참 — 예외 종류로만 판단한다(메시지 문자열로 판단하지 않는다).

    `requests` Timeout 계열 · 내장 TimeoutError · 본문을 받는 중의 읽기 시간 초과(`requests` 가
    `ConnectionError(urllib3 ReadTimeoutError)` 로 올린다 · requests 2.34 · urllib3 2.7 실측).
    """
    if isinstance(exc, TimeoutError):
        return True
    try:
        import requests
        import urllib3
    except ImportError:  # pragma: no cover - FDR 의존성으로 늘 설치됨
        return False
    if isinstance(exc, requests.exceptions.Timeout):
        return True
    return (
        isinstance(exc, requests.exceptions.ConnectionError)
        and bool(exc.args)
        and isinstance(exc.args[0], urllib3.exceptions.TimeoutError)
    )


def _default_universe_fetcher():
    import FinanceDataReader as fdr  # lazy import

    return fdr.StockListing("ETF/KR")


def _default_price_fetcher(ticker: str, start: date, end: date):
    import FinanceDataReader as fdr  # lazy import

    return fdr.DataReader(ticker, start, end)


def _to_optional_float(val) -> Optional[float]:
    try:
        if val is None:
            return None
        f = float(val)
        if f != f:  # NaN
            return None
        return f
    except (TypeError, ValueError):
        return None


def _to_optional_int(val) -> Optional[int]:
    try:
        if val is None:
            return None
        f = float(val)
        if f != f:
            return None
        return int(f)
    except (TypeError, ValueError):
        return None


def refresh_etf_universe(
    *,
    fetcher: UniverseFetcher = None,
    db_path: Path = DEFAULT_DB_PATH,
) -> UniverseRefreshResult:
    """fdr.StockListing("ETF/KR") 1회 호출 결과를 etf_master 에 upsert.

    AC-4: 본 함수는 ticker 별 추가 호출을 절대 하지 않는다.
    """
    fetch = fetcher or _default_universe_fetcher
    run_id = f"fdr-universe-{uuid.uuid4().hex[:12]}"
    t0 = time.perf_counter()
    try:
        df = fetch()
    except Exception as e:  # noqa: BLE001
        elapsed = time.perf_counter() - t0
        log_refresh(
            run_id=run_id,
            source=f"{FDR_SOURCE}/universe",
            asof=date.today().isoformat(),
            attempted=0,
            success=0,
            fail=1,
            runtime_seconds=elapsed,
            error_summary=f"fetch_error: {type(e).__name__}: {e}",
            db_path=db_path,
        )
        return UniverseRefreshResult(
            run_id=run_id,
            universe_count=0,
            runtime_seconds=elapsed,
            success=False,
            error=f"{type(e).__name__}: {e}",
        )

    if df is None or len(df) == 0:
        elapsed = time.perf_counter() - t0
        log_refresh(
            run_id=run_id,
            source=f"{FDR_SOURCE}/universe",
            asof=date.today().isoformat(),
            attempted=0,
            success=0,
            fail=1,
            runtime_seconds=elapsed,
            error_summary="empty_universe",
            db_path=db_path,
        )
        return UniverseRefreshResult(
            run_id=run_id,
            universe_count=0,
            runtime_seconds=elapsed,
            success=False,
            error="empty_universe",
        )

    df = df.copy()
    df["Symbol"] = df["Symbol"].astype(str).str.zfill(6)

    rows: list[EtfMasterRow] = []
    for _idx, raw in df.iterrows():
        rows.append(
            EtfMasterRow(
                ticker=str(raw["Symbol"]),
                name=(
                    str(raw["Name"])
                    if "Name" in raw and raw["Name"] is not None
                    else None
                ),
                category=(
                    str(raw["Category"])
                    if "Category" in raw and raw["Category"] is not None
                    else None
                ),
                price=(
                    _to_optional_float(raw.get("Price"))
                    if hasattr(raw, "get")
                    else _to_optional_float(raw["Price"] if "Price" in raw else None)
                ),
                volume=_to_optional_int(raw["Volume"]) if "Volume" in raw else None,
                market_cap=(
                    _to_optional_float(raw["MarCap"]) if "MarCap" in raw else None
                ),
            )
        )

    written = upsert_etf_master(rows, source=FDR_SOURCE, db_path=db_path)
    elapsed = time.perf_counter() - t0

    log_refresh(
        run_id=run_id,
        source=f"{FDR_SOURCE}/universe",
        asof=date.today().isoformat(),
        attempted=len(rows),
        success=written,
        fail=0,
        runtime_seconds=elapsed,
        error_summary=None,
        db_path=db_path,
    )

    return UniverseRefreshResult(
        run_id=run_id,
        universe_count=written,
        runtime_seconds=elapsed,
        success=True,
    )


def _dataframe_to_price_rows(ticker: str, df) -> list[EtfDailyPriceRow]:
    """fdr.DataReader DataFrame → EtfDailyPriceRow 리스트."""
    rows: list[EtfDailyPriceRow] = []
    if df is None or len(df) == 0:
        return rows
    if "Close" not in df.columns:
        return rows
    for idx, raw in df.iterrows():
        try:
            dt = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)[:10]
        except Exception:  # noqa: BLE001
            continue
        rows.append(
            EtfDailyPriceRow(
                ticker=ticker,
                date=dt,
                open=(
                    _to_optional_float(raw.get("Open"))
                    if hasattr(raw, "get")
                    else _to_optional_float(raw["Open"] if "Open" in raw else None)
                ),
                high=_to_optional_float(raw["High"]) if "High" in raw else None,
                low=_to_optional_float(raw["Low"]) if "Low" in raw else None,
                close=_to_optional_float(raw["Close"]),
                volume=_to_optional_int(raw["Volume"]) if "Volume" in raw else None,
                change=_to_optional_float(raw["Change"]) if "Change" in raw else None,
            )
        )
    return rows


def refresh_price_history(
    tickers: Sequence[str],
    *,
    end_date: date,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    price_fetcher: PriceFetcher = None,
    db_path: Path = DEFAULT_DB_PATH,
    stop_after_consecutive_timeouts: Optional[int] = None,
    on_stop: Optional[Callable[[int], None]] = None,
) -> PriceRefreshResult:
    """ticker 별 가격 시계열을 fetch → etf_daily_price 에 upsert. 실패는 격리.

    POC5-17 — `stop_after_consecutive_timeouts` 를 주면(PC 버튼 갱신만) 종목 조회 결과가 그 수만큼
    연속으로 실제 시간 초과일 때 남은 종목은 조회하지 않는다. 시간 초과 아닌 결과(성공 · 빈 자료 ·
    다른 예외 · 저장 실패)가 끼면 연속 수를 0으로 되돌린다. 주지 않으면 기존 동작 그대로(OCI 배치).
    `on_stop(조회하지 않은 수)` 는 멈추는 순간 · 가격 기록을 쓰기 전에 부른다(기록이 실패해도
    호출자가 중단을 안다 · 검증자 r1).
    """
    fetch = price_fetcher or _default_price_fetcher
    run_id = f"fdr-prices-{uuid.uuid4().hex[:12]}"
    normalized = normalize_ticker_list(tickers)
    start_date = end_date - timedelta(days=lookback_days)

    t0 = time.perf_counter()
    success = 0
    failures: list[dict] = []
    consecutive_timeouts = 0
    not_started = 0
    for i, tk in enumerate(normalized):
        if (
            stop_after_consecutive_timeouts is not None
            and consecutive_timeouts >= stop_after_consecutive_timeouts
        ):
            not_started = len(normalized) - i
            if on_stop is not None:
                on_stop(not_started)
            break
        try:
            df = fetch(tk, start_date, end_date)
        except Exception as e:  # noqa: BLE001
            consecutive_timeouts = (
                consecutive_timeouts + 1 if _is_request_timeout(e) else 0
            )
            if len(failures) < 10:
                failures.append(
                    {"ticker": tk, "error": f"{type(e).__name__}: {e}"[:160]}
                )
            continue
        consecutive_timeouts = 0
        rows = _dataframe_to_price_rows(tk, df)
        if not rows:
            if len(failures) < 10:
                failures.append({"ticker": tk, "error": "no_data"})
            continue
        try:
            upsert_daily_prices(rows, source=FDR_SOURCE, db_path=db_path)
            success += 1
        except Exception as e:  # noqa: BLE001
            if len(failures) < 10:
                failures.append(
                    {"ticker": tk, "error": f"store: {type(e).__name__}: {e}"[:160]}
                )

    elapsed = time.perf_counter() - t0
    fail = len(normalized) - success
    error_summary = None
    if failures:
        error_summary = "; ".join(
            f"{f['ticker']}:{f['error'][:48]}" for f in failures[:5]
        )
    if not_started:
        # 기존 기록 의미(attempted = 대상 · fail = 대상 - 성공)는 그대로 · 조회하지 않은 수를 사유에 따로 적는다.
        error_summary = (
            f"stopped_after_consecutive_timeouts={stop_after_consecutive_timeouts} "
            f"queried={len(normalized) - not_started} not_started={not_started}; "
            + (error_summary or "")
        )

    log_refresh(
        run_id=run_id,
        source=f"{FDR_SOURCE}/prices",
        asof=end_date.isoformat(),
        attempted=len(normalized),
        success=success,
        fail=fail,
        runtime_seconds=elapsed,
        error_summary=error_summary,
        db_path=db_path,
    )

    return PriceRefreshResult(
        run_id=run_id,
        attempted=len(normalized),
        success=success,
        fail=fail,
        runtime_seconds=elapsed,
        failure_examples=failures[:5],
        not_started=not_started,
        stopped_on_timeouts=bool(not_started),
    )
