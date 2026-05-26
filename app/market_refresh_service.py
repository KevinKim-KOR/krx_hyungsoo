"""Market refresh service — single-flight + 6h cooldown + background job.

지시문 §5.2 / §5.3:
- POST /market/refresh 가 호출하는 백엔드 서비스 (ETF universe + 가격 수집).
- 동시 1건만 실행 (single-flight).
- 마지막 성공 refresh 후 6시간 cooldown.
- 결과는 market_refresh_log + in-memory state 두 곳에 기록.
- JSON artifact 생성하지 않는다.

namespace 주의 (2026-05-18):
- 본 service 가 처리하는 `/market/refresh` 는 ETF universe 전체 수집용.
- holdings naver 시세 갱신용 `/holdings/market/refresh` 와는 서로 다른 endpoint.

설계자 결정:
- in-memory state 는 모듈 수준 dict 1개 + threading.Lock 으로 보호.
- 서버 재시작 시 running 상태 복구는 BACKLOG.
- cooldown 은 in-memory `last_success_at` 기준 (서버 lifetime 안에서만 유효).
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Optional

from app.market_benchmark_store import refresh_kospi_benchmark
from app.market_data_fdr import (
    DEFAULT_LOOKBACK_DAYS,
    PriceFetcher,
    UniverseFetcher,
    refresh_etf_universe,
    refresh_price_history,
)
from app.market_data_store import (
    DEFAULT_DB_PATH,
    list_etf_tickers,
    log_refresh,
)

DEFAULT_COOLDOWN_HOURS = 6


@dataclass
class RefreshState:
    """현재 refresh job 의 in-memory 상태 (서버 lifetime 안에서만 유효)."""

    status: str = "idle"  # idle / running / completed / failed
    refresh_id: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    asof: Optional[str] = None
    universe_count: Optional[int] = None
    price_attempted_count: Optional[int] = None
    price_success_count: Optional[int] = None
    price_fail_count: Optional[int] = None
    runtime_seconds: Optional[float] = None
    error_summary: Optional[str] = None
    cooldown_remaining_seconds: int = 0


@dataclass
class _ServiceState:
    state: RefreshState = field(default_factory=RefreshState)
    lock: threading.Lock = field(default_factory=threading.Lock)
    last_success_at: Optional[datetime] = None


_service = _ServiceState()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_refresh_id() -> str:
    return (
        f"market_refresh_{_utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    )


def _cooldown_remaining_seconds(cooldown_hours: int) -> int:
    if _service.last_success_at is None:
        return 0
    expires_at = _service.last_success_at + timedelta(hours=cooldown_hours)
    remaining = (expires_at - _utcnow()).total_seconds()
    return max(0, int(remaining))


def reset_state_for_testing() -> None:
    """단일 테스트 격리용 — service module state 초기화."""
    with _service.lock:
        _service.state = RefreshState()
        _service.last_success_at = None


def get_state_snapshot(cooldown_hours: int = DEFAULT_COOLDOWN_HOURS) -> RefreshState:
    """현재 RefreshState 의 thread-safe snapshot."""
    with _service.lock:
        snap = RefreshState(**_service.state.__dict__)
    snap.cooldown_remaining_seconds = _cooldown_remaining_seconds(cooldown_hours)
    return snap


def _execute_refresh_job(
    *,
    refresh_id: str,
    db_path: Path,
    universe_fetcher: Optional[UniverseFetcher],
    price_fetcher: Optional[PriceFetcher],
    end_date_for_prices: date,
) -> None:
    """background thread 안에서 실행되는 실제 수집 작업.

    universe → price → state 갱신 → last_success_at 기록.
    예외는 안에서 catch — 절대 thread 가 죽으면 안 된다.
    """
    started = _utcnow()
    with _service.lock:
        _service.state.status = "running"
        _service.state.refresh_id = refresh_id
        _service.state.started_at = _iso(started)
        _service.state.finished_at = None
        _service.state.asof = None
        _service.state.universe_count = None
        _service.state.price_attempted_count = None
        _service.state.price_success_count = None
        _service.state.price_fail_count = None
        _service.state.runtime_seconds = None
        _service.state.error_summary = None

    t0 = time.perf_counter()
    error_summary: Optional[str] = None
    universe_ok = False
    price_attempted = 0
    price_success = 0
    price_fail = 0
    universe_count = 0
    try:
        u_result = refresh_etf_universe(fetcher=universe_fetcher, db_path=db_path)
        universe_ok = u_result.success
        universe_count = u_result.universe_count
        if not universe_ok:
            error_summary = f"universe_fetch_failed: {u_result.error}"
        else:
            tickers = list_etf_tickers(db_path)
            p_result = refresh_price_history(
                tickers,
                end_date=end_date_for_prices,
                lookback_days=DEFAULT_LOOKBACK_DAYS,
                price_fetcher=price_fetcher,
                db_path=db_path,
            )
            price_attempted = p_result.attempted
            price_success = p_result.success
            price_fail = p_result.fail
            if p_result.fail > 0 and p_result.success == 0:
                error_summary = "all_price_fetches_failed"
            elif p_result.fail > 0:
                error_summary = f"price_partial_failure: fail={p_result.fail}"
    except Exception as e:  # noqa: BLE001 — background thread 보호
        error_summary = f"refresh_unexpected: {type(e).__name__}: {e}"

    # KOSPI benchmark — 실패해도 전체 refresh 흐름을 중단시키지 않는다
    # (지시문 §4.4). 별도 log row 로 결과 보존, in-memory state 에는 노출 X.
    try:
        kospi_result = refresh_kospi_benchmark(
            end_date=end_date_for_prices,
            price_fetcher=price_fetcher,
            db_path=db_path,
        )
        kospi_status = kospi_result.get("status", "failed")
        kospi_error = kospi_result.get("error")
        log_refresh(
            run_id=f"kospi-benchmark-{refresh_id}",
            source="FinanceDataReader/KS11",
            asof=end_date_for_prices.isoformat(),
            attempted=1,
            success=1 if kospi_status == "ok" else 0,
            fail=0 if kospi_status == "ok" else 1,
            runtime_seconds=0.0,
            error_summary=kospi_error,
            db_path=db_path,
        )
        # 부분 실패 메시지에 KOSPI 정보 부착 (전체 실패 처리는 하지 않음).
        if kospi_status != "ok" and error_summary is None:
            error_summary = f"kospi_benchmark_unavailable: {kospi_error or 'unknown'}"
    except Exception as e:  # noqa: BLE001 — KOSPI 실패도 thread 안에서 격리
        try:
            log_refresh(
                run_id=f"kospi-benchmark-{refresh_id}",
                source="FinanceDataReader/KS11",
                asof=end_date_for_prices.isoformat(),
                attempted=1,
                success=0,
                fail=1,
                runtime_seconds=0.0,
                error_summary=f"{type(e).__name__}: {e}"[:200],
                db_path=db_path,
            )
        except Exception:  # noqa: BLE001
            pass

    elapsed = time.perf_counter() - t0
    finished = _utcnow()
    success_overall = universe_ok and (price_success > 0 or price_attempted == 0)

    with _service.lock:
        _service.state.status = "completed" if success_overall else "failed"
        _service.state.finished_at = _iso(finished)
        _service.state.asof = end_date_for_prices.isoformat()
        _service.state.universe_count = universe_count
        _service.state.price_attempted_count = price_attempted
        _service.state.price_success_count = price_success
        _service.state.price_fail_count = price_fail
        _service.state.runtime_seconds = round(elapsed, 3)
        _service.state.error_summary = error_summary
        if success_overall:
            _service.last_success_at = finished


@dataclass
class StartResult:
    status: str  # accepted / running / skipped_cooldown / failed_to_start
    refresh_id: Optional[str]
    message: str
    cooldown_remaining_seconds: int = 0


def start_refresh_job(
    *,
    db_path: Path = DEFAULT_DB_PATH,
    cooldown_hours: int = DEFAULT_COOLDOWN_HOURS,
    universe_fetcher: Optional[UniverseFetcher] = None,
    price_fetcher: Optional[PriceFetcher] = None,
    end_date_for_prices: Optional[date] = None,
    thread_runner: Optional[Callable[[Callable[[], None]], None]] = None,
) -> StartResult:
    """POST /market/refresh (ETF universe + 가격 수집) 의 진입점.

    single-flight + cooldown 가드 통과 시 background thread 로 실행.
    thread_runner 인자는 테스트에서 동기 실행으로 강제하는 용도.
    """
    with _service.lock:
        current_status = _service.state.status
        if current_status == "running":
            cd = _cooldown_remaining_seconds(cooldown_hours)
            return StartResult(
                status="running",
                refresh_id=_service.state.refresh_id,
                message="시장 데이터 갱신이 이미 진행 중입니다.",
                cooldown_remaining_seconds=cd,
            )
        cd = _cooldown_remaining_seconds(cooldown_hours)
        if cd > 0:
            return StartResult(
                status="skipped_cooldown",
                refresh_id=_service.state.refresh_id,
                message="최근 시장 데이터가 이미 갱신되었습니다.",
                cooldown_remaining_seconds=cd,
            )
        # job 등록 — status 는 _execute_refresh_job 시작 시 'running' 으로 갱신
        new_id = _new_refresh_id()
        _service.state.status = "running"
        _service.state.refresh_id = new_id
        _service.state.started_at = _iso(_utcnow())
        _service.state.finished_at = None
        _service.state.error_summary = None

    end_for_prices = end_date_for_prices or date.today()

    def runner() -> None:
        _execute_refresh_job(
            refresh_id=new_id,
            db_path=db_path,
            universe_fetcher=universe_fetcher,
            price_fetcher=price_fetcher,
            end_date_for_prices=end_for_prices,
        )

    if thread_runner is not None:
        thread_runner(runner)
    else:
        t = threading.Thread(
            target=runner, name=f"market-refresh-{new_id}", daemon=True
        )
        t.start()

    return StartResult(
        status="accepted",
        refresh_id=new_id,
        message="시장 데이터 갱신을 시작했습니다.",
        cooldown_remaining_seconds=0,
    )
