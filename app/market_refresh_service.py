"""Market refresh service — single-flight + 6h cooldown + background job.

지시문 §5.2 / §5.3:
- POST /market/refresh 가 호출하는 백엔드 서비스 (ETF universe + 가격 수집).
- 동시 1건만 실행 (single-flight).
- 마지막 성공 refresh 후 6시간 cooldown.
- 결과는 market_refresh_log + market_refresh_state 두 곳에 기록.
- JSON artifact 생성하지 않는다.

namespace 주의 (2026-05-18):
- 본 service 가 처리하는 `/market/refresh` 는 ETF universe 전체 수집용.
- holdings naver 시세 갱신용 `/holdings/market/refresh` 와는 서로 다른 endpoint.

D-2 (2026-06-30): 상태 SSOT 를 SQLite (market_refresh_state) 로 전환.
- in-memory state 는 SQLite 와 동기화된 보조 캐시.
- 모든 상태 변경 시 SQLite 영속화.
- 모듈 초기화/첫 호출 시 SQLite 에서 복구 + running → failed 정규화.
- 6h cooldown 도 SQLite last_success_at 기반.
"""

from __future__ import annotations

import logging

import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Optional

from app.etf_nav_service import refresh_nav_universe
from app.pc_vix_refresh import VIX_STEP_FAILED_TEXT, refresh_pc_vix
from app.holdings_equity_refresh import (
    HOLDINGS_EQUITY_STEP_FAILED_TEXT,
    refresh_holdings_equity_prices,
)
from app.market_benchmark_store import (
    KOSPI_SOURCE,
    KospiFetcher,
    refresh_kospi_benchmark,
)
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
from app.market_refresh_state_store import (
    VIX_RETRY_SCOPE,
    MarketRefreshStateRow,
    clear_state,
    normalize_running_to_failed,
    read_state,
    write_state,
)
from app.market_refresh_vix_retry import sync_vix_retry_after_full_refresh
from app.three_push_runtime.market_data_batch import fdr_request_timeout

DEFAULT_COOLDOWN_HOURS = 6
# POC5-17 — ETF 가격 조회가 이만큼 연속으로 시간 초과면 남은 종목은 조회하지 않고 실패로 끝낸다.
PRICE_TIMEOUT_STOP_STREAK = 5
PRICE_TIMEOUT_STOP_TEXT = (
    "가격 조회가 연속으로 시간 초과되어 남은 {n}종목은 받지 않았습니다. "
    "앞서 받은 자료는 보존했습니다. 갱신 작업 종료 후 다시 실행할 수 있습니다."
)

# NAV refresh summary artifact 경로 (지시문 §5.5).
NAV_REFRESH_SUMMARY_PATH = Path("state/market/nav_discount_refresh_latest.json")


logger = logging.getLogger(__name__)


def _write_nav_refresh_summary(summary) -> None:  # noqa: ANN001 — runtime dataclass
    """NAV universe refresh 결과를 JSON artifact 로 저장. 실패 시 무시 (격리)."""
    import json
    from dataclasses import asdict

    try:
        NAV_REFRESH_SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = asdict(summary)
        with NAV_REFRESH_SUMMARY_PATH.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2, default=str)
    except Exception:  # noqa: BLE001 — artifact 실패도 thread 안에서 격리
        pass


@dataclass
class RefreshState:
    """현재 refresh job 의 상태. SSOT 는 SQLite, 본 dataclass 는 동기화된 캐시."""

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
    last_success_asof_date: Optional[str] = None
    # SQLite hydrate 가 db_path 별로 1회씩만 수행되도록.
    loaded_for_db: Optional[str] = None


_service = _ServiceState()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_iso(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        # 기존 _iso 포맷: 'YYYY-MM-DDTHH:MM:SSZ'
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _new_refresh_id() -> str:
    return (
        f"market_refresh_{_utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    )


def _row_to_state(row: MarketRefreshStateRow) -> RefreshState:
    """SQLite 행 → RefreshState 변환.

    running 정규화는 호출 전에 normalize_running_to_failed 로 이미 처리됐다고 가정.
    상태 행이 없거나 idle 인 경우 호출자가 별도 처리.
    """
    status = row.last_attempt_status or "idle"
    return RefreshState(
        status=status,
        refresh_id=row.refresh_id,
        started_at=row.last_attempt_started_at,
        finished_at=row.last_attempt_finished_at,
        asof=row.asof,
        universe_count=row.universe_count,
        price_attempted_count=row.price_attempted_count,
        price_success_count=row.price_success_count,
        price_fail_count=row.price_fail_count,
        runtime_seconds=row.runtime_seconds,
        error_summary=row.last_error_summary,
    )


def _hydrate_from_sqlite(db_path: Path) -> None:
    """SQLite → in-memory 복구. 호출 전에 _service.lock 보유 필수.

    - running 상태가 남아 있으면 failed 로 정규화 (detail 필드 보존).
    - last_success_at / last_success_asof_date 도 in-memory 미러에 반영.
    """
    normalize_running_to_failed(db_path=db_path)
    # POC5-12 — 끝나기 전에 서버가 다시 켜진 'VIX 다시 받기'는 실패(다시 누를 수 있음)로 둔다.
    normalize_running_to_failed(
        db_path=db_path, summary=VIX_STEP_FAILED_TEXT, scope=VIX_RETRY_SCOPE
    )
    row = read_state(db_path=db_path)
    if row is None:
        _service.state = RefreshState()
        _service.last_success_at = None
        _service.last_success_asof_date = None
    else:
        _service.state = _row_to_state(row)
        _service.last_success_at = _parse_iso(row.last_success_at)
        _service.last_success_asof_date = row.last_success_asof_date
    _service.loaded_for_db = str(db_path.resolve())


def _ensure_loaded(db_path: Path) -> None:
    """첫 호출 또는 db_path 변경 시 SQLite 에서 in-memory 복구. lock 자체 획득."""
    key = str(db_path.resolve())
    with _service.lock:
        if _service.loaded_for_db == key:
            return
        _hydrate_from_sqlite(db_path)


def _persist_current_state(db_path: Path) -> None:
    """현재 in-memory state 를 SQLite 에 영속화. 호출 전에 _service.lock 보유 필수.

    last_success_asof_date / last_success_at 보존 규칙:
    - in-memory mirror 에 값이 있으면 그것을 우선.
    - mirror 가 None 이고 SQLite 에 이전 성공 기록이 있으면 그것을 유지.
    실패·중단·running 진입이 마지막 정상 성공 기록을 덮어쓰면 안 된다.
    """
    s = _service.state
    last_success_iso = (
        _iso(_service.last_success_at) if _service.last_success_at else None
    )
    last_success_asof = _service.last_success_asof_date
    if last_success_iso is None or last_success_asof is None:
        prior = read_state(db_path=db_path)
        if prior is not None:
            if last_success_iso is None:
                last_success_iso = prior.last_success_at
            if last_success_asof is None:
                last_success_asof = prior.last_success_asof_date
    row = MarketRefreshStateRow(
        refresh_id=s.refresh_id,
        last_success_asof_date=last_success_asof,
        last_success_at=last_success_iso,
        last_attempt_started_at=s.started_at,
        last_attempt_finished_at=s.finished_at,
        last_attempt_status=s.status,
        last_error_summary=s.error_summary,
        asof=s.asof,
        universe_count=s.universe_count,
        price_attempted_count=s.price_attempted_count,
        price_success_count=s.price_success_count,
        price_fail_count=s.price_fail_count,
        runtime_seconds=s.runtime_seconds,
    )
    write_state(row, db_path=db_path)
    # in-memory mirror 도 SQLite 와 동기화된 값으로 갱신
    # (다음 cooldown 계산 등에서 일관성 유지).
    if _service.last_success_at is None and last_success_iso is not None:
        _service.last_success_at = _parse_iso(last_success_iso)
    if _service.last_success_asof_date is None and last_success_asof is not None:
        _service.last_success_asof_date = last_success_asof


def _cooldown_remaining_seconds(cooldown_hours: int) -> int:
    if _service.last_success_at is None:
        return 0
    expires_at = _service.last_success_at + timedelta(hours=cooldown_hours)
    remaining = (expires_at - _utcnow()).total_seconds()
    return max(0, int(remaining))


def reset_state_for_testing(db_path: Path = DEFAULT_DB_PATH) -> None:
    """단일 테스트 격리용 — service module state + SQLite 단일 행 초기화."""
    with _service.lock:
        _service.state = RefreshState()
        _service.last_success_at = None
        _service.last_success_asof_date = None
        _service.loaded_for_db = str(db_path.resolve())
    clear_state(db_path=db_path)
    clear_state(db_path=db_path, scope=VIX_RETRY_SCOPE)


def get_state_snapshot(
    cooldown_hours: int = DEFAULT_COOLDOWN_HOURS,
    db_path: Path = DEFAULT_DB_PATH,
) -> RefreshState:
    """현재 RefreshState 의 thread-safe snapshot.

    첫 호출 시 SQLite 에서 in-memory 복구 + running 정규화.
    """
    _ensure_loaded(db_path)
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
    kospi_fetcher: Optional[KospiFetcher] = None,
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
        _persist_current_state(db_path)

    t0 = time.perf_counter()
    error_summary: Optional[str] = None
    universe_ok = False
    price_attempted = 0
    price_success = 0
    price_fail = 0
    stop_box: list[int] = []  # POC5-17 — 중단 때 조회하지 않은 수(가격 기록 전에 받음)
    universe_count = 0
    try:
        # POC5-17 — FDR 조회 요청 대기 상한(기존 함수 · 20초 · 연결 · 읽기마다 · 작업 전체 종료 보장 아님).
        with fdr_request_timeout():
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
                    stop_after_consecutive_timeouts=PRICE_TIMEOUT_STOP_STREAK,
                    on_stop=stop_box.append,
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
    # POC5-17 — 연속 시간 초과 중단은 그 뒤 가격 기록이 실패해도 failed(검증자 r1) · 예외 사유는 뒤에 붙인다.
    price_stopped = bool(stop_box)
    if price_stopped:
        unexpected = (error_summary or "").startswith("refresh_unexpected")
        stop_text = PRICE_TIMEOUT_STOP_TEXT.format(n=stop_box[0])
        error_summary = f"{stop_text} · {error_summary}" if unexpected else stop_text

    # POC5-10 — 보유 개별주 가격(ETF 단계 뒤 · KOSPI 단계 앞). 'KOSPI 행이 마지막 기록'인 기존
    # '마지막 refresh'(`latest_refresh_log()` · 화면 · 연결 ID)를 바꾸지 않으려는 순서다. 실패해도
    # 전체 갱신 상태(완료 · 실패)는 ETF 결과대로 두고, 한국어 문구만 error_summary 끝에 붙인다.
    try:
        with fdr_request_timeout():  # POC5-17 — 같은 FDR 가격 조회 · 같은 요청 대기 상한
            holdings_equity_msg = refresh_holdings_equity_prices(
                refresh_id=refresh_id,
                end_date=end_date_for_prices,
                db_path=db_path,
                price_fetcher=price_fetcher,
            )
    except Exception:  # noqa: BLE001 — 로그 기록 실패까지 thread 안에서 격리
        logger.exception("holdings equity price step failed")
        holdings_equity_msg = HOLDINGS_EQUITY_STEP_FAILED_TEXT

    # KOSPI benchmark — 실패해도 전체 refresh 흐름을 중단시키지 않는다
    # (지시문 §4.4). 별도 log row 로 결과 보존, in-memory state 에는 노출 X.
    # POC3-02D-OPS-03 확정 계약 9 — 자료원 KRX `idx/kospi_dd_trd`(OCI 08:10 배치와 같은
    # 함수). log source 는 화면 상태가 읽는 `KOSPI_SOURCE` 와 같아야 한다.
    kospi_ok = (
        False  # POC5-12 — 예외 경로는 error_summary 를 남기지 않으므로 따로 둔다.
    )
    try:
        kospi_result = refresh_kospi_benchmark(
            end_date=end_date_for_prices,
            fetcher=kospi_fetcher,
            db_path=db_path,
        )
        kospi_status = kospi_result.get("status", "failed")
        kospi_error = kospi_result.get("error")
        kospi_ok = kospi_status == "ok"
        log_refresh(
            run_id=f"kospi-benchmark-{refresh_id}",
            source=KOSPI_SOURCE,
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
                source=KOSPI_SOURCE,
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

    # POC5-11 — VIX(시장 불안 지표 · KOSPI 뒤 · NAV 앞). OCI 08:10 배치와 같은 수집 함수 ·
    # 조회 대기 20초 · 미국 마감 전 날짜 제외(`app/pc_vix_refresh.py`). 실패해도 다른 단계 결과 ·
    # 최종 판정은 그대로이고 한국어 문구만 완료 사유 끝에 붙인다. 기록 행 없음(로그만).
    try:
        vix_msg = refresh_pc_vix(db_path=db_path, now_utc=_utcnow())
    except Exception:  # noqa: BLE001 — VIX 실패도 thread 안에서 격리
        logger.exception("PC VIX step failed")
        vix_msg = VIX_STEP_FAILED_TEXT

    # NAV / 괴리율 수집 (2026-06-08 Naver Universe Integration — 지시문 §5.4).
    # Naver `etfItemList.nhn` 1회 호출로 전체 ETF universe NAV / 시장가격 / 괴리율
    # 일괄 upsert. per-ticker N회 호출 패턴은 폐기. 실패는 전체 refresh 흐름
    # 중단 X (지시문 §5.4 / §9 제약). summary artifact 도 함께 생성.
    # POC5-12 — 'VIX 만 실패' 판단에 NAV 실제 결과를 쓴다(예외 없음 · status == "ok" 일 때만 성공).
    # NAV 수집 방식 · 전체 갱신 completed/failed 판정은 그대로다.
    nav_ok = False
    try:
        nav_summary = refresh_nav_universe(
            asof=end_date_for_prices.isoformat(),
            db_path=db_path,
        )
        nav_ok = getattr(nav_summary, "status", None) == "ok"
        _write_nav_refresh_summary(nav_summary)
    except Exception:  # noqa: BLE001 — NAV 실패도 thread 안에서 격리
        pass

    elapsed = time.perf_counter() - t0
    finished = _utcnow()
    success_overall = universe_ok and (price_success > 0 or price_attempted == 0)
    # POC5-17 — 연속 시간 초과로 멈춘 회차는 뒤 단계가 성공해도 failed(성공 시각 · 대기 시작 안 함).
    success_overall = success_overall and not price_stopped
    # POC5-12 — 다른 단계(ETF 목록 · 가격 · KOSPI 사유 · 보유 개별주 · NAV)가 실제로 실패하지 않았고
    # VIX 만 실패했는지(이 갱신의 결과로만 판단 · 문구 · 현재 VIX 날짜로 추측하지 않음).
    vix_only_failure = (
        success_overall
        and error_summary is None
        and holdings_equity_msg is None
        and kospi_ok
        and nav_ok
        and vix_msg is not None
    )
    # POC5-10 — 보유 개별주 단계 문구는 기존(ETF · KOSPI) 요약 뒤에 붙인다(그 판정은 그대로).
    # POC5-11 — VIX 문구는 그 뒤.
    error_summary = (
        " · ".join(x for x in (error_summary, holdings_equity_msg, vix_msg) if x)
        or None
    )

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
            _service.last_success_asof_date = end_date_for_prices.isoformat()
        # 성공/실패 모두 SQLite 영속화. 실패 경로는 last_success_* 를
        # 건드리지 않으므로 마지막 정상 성공 기록은 그대로 유지된다.
        _persist_current_state(db_path)
        # POC5-12 — 'VIX 다시 받기' 표식은 가장 최근 전체 갱신 결과에 맞춘다.
        sync_vix_retry_after_full_refresh(
            db_path,
            vix_only_failure=vix_only_failure,
            refresh_id=refresh_id,
            finished=finished,
            vix_msg=vix_msg,
        )

    # 시장 데이터 갱신 **성공 후** 장중 설정 재계산 (설계자 §10-3(2)).
    # 별도 cron 을 만들지 않는 대신 여기에 건다. lock 밖에서 돌린다 —
    # 산출이 refresh 상태 lock 을 잡고 있을 이유가 없다.
    if success_overall:
        _regenerate_intraday_config(db_path)


def _regenerate_intraday_config(db_path: Path) -> None:
    """장중 설정 후보 재산출. **refresh thread 를 절대 죽이지 않는다.**

    `generate()` 자체가 예외를 올리지 않지만 import 실패까지 막는다. 재계산이
    안 되는 것보다 시세 갱신이 실패로 뒤집히는 게 나쁘다.
    """
    try:
        from app.intraday_config import generator

        out = generator.generate(db_path=db_path)
        logger.info("장중 설정 재산출: %s", out.get("status"))
    except Exception as e:  # noqa: BLE001
        logger.warning("장중 설정 재산출 실패(무시): %s", e)


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
    kospi_fetcher: Optional[KospiFetcher] = None,
) -> StartResult:
    """POST /market/refresh (ETF universe + 가격 수집) 의 진입점.

    single-flight + cooldown 가드 통과 시 background thread 로 실행.
    thread_runner 인자는 테스트에서 동기 실행으로 강제하는 용도.
    """
    _ensure_loaded(db_path)
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
        # POC5-12 — 'VIX 다시 받기'가 도는 중이면 전체 갱신도 시작하지 않는다(같은 잠금).
        # 상태값을 따로 둔다 — 화면이 이것을 전체 갱신 진행으로 읽고 '갱신 완료'로 보이지 않게.
        vix_row = read_state(db_path=db_path, scope=VIX_RETRY_SCOPE)
        if vix_row is not None and vix_row.last_attempt_status == "running":
            return StartResult(
                status="vix_retry_running",
                refresh_id=vix_row.refresh_id,
                message="VIX 다시 받기가 진행 중입니다.",
                cooldown_remaining_seconds=_cooldown_remaining_seconds(cooldown_hours),
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
        _persist_current_state(db_path)

    end_for_prices = end_date_for_prices or date.today()

    def runner() -> None:
        _execute_refresh_job(
            refresh_id=new_id,
            db_path=db_path,
            universe_fetcher=universe_fetcher,
            price_fetcher=price_fetcher,
            end_date_for_prices=end_for_prices,
            kospi_fetcher=kospi_fetcher,
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
