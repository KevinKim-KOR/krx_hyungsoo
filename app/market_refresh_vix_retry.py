"""POC5-12 — 전체 갱신에서 VIX 만 실패했을 때 'VIX 다시 받기'(설계 §3 · 판정 Q2 · Q3 · §3).

표식 · 결과는 기존 `market_refresh_state` 표의 `vix_retry` 행에 둔다(스키마 · 새 표 없음).

| 상태 | 뜻 | needed |
|---|---|---|
| needed | 가장 최근 전체 갱신에서 다른 단계(ETF 목록 · 가격 · KOSPI · 보유 개별주 · NAV)는 실패하지 않고 VIX 만 실패 | 예 |
| running | VIX 다시 받기 실행 중 | - |
| completed | 다시 받기 성공(VIX 저장 기준일 · 끝난 시각 · 재시도 id) | 아니오 |
| failed | 다시 받기 실패(한국어 사유) · 끝나기 전 서버 재시작 | 예 |
| cleared | 최근 전체 갱신이 VIX 성공이거나 다른 단계도 실패 | 아니오 |

실행 확인 · 시작은 전체 갱신과 같은 잠금(`market_refresh_service._service.lock`)에서 한다. VIX 단계는
POC5-11 `refresh_pc_vix`(20초 · 미국 마감 전 날짜 제외 · 실패 격리)를 서비스 모듈 속성으로 부른다.
전체 갱신 상태 · 마지막 성공 시각 · 건수 · 기록 행은 건드리지 않는다.
"""

from __future__ import annotations

import logging
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from app.market_benchmark_store import latest_benchmark_date
from app.market_data_store import DEFAULT_DB_PATH
from app.market_refresh_state_store import (
    VIX_RETRY_SCOPE,
    MarketRefreshStateRow,
    read_state,
    write_state,
)
from app.pc_vix_refresh import VIX_STEP_FAILED_TEXT

logger = logging.getLogger(__name__)

VIX_RETRY_NEEDED_STATUSES = ("needed", "failed")


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def sync_vix_retry_after_full_refresh(
    db_path: Path,
    *,
    vix_only_failure: bool,
    refresh_id: str,
    finished: datetime,
    vix_msg: Optional[str],
) -> None:
    """전체 갱신 직후 표식을 맞춘다(호출자가 서비스 잠금 보유).

    VIX 만 실패 → needed. 그 밖(VIX 성공 · 다른 단계도 실패)은 예전 표식이 있으면 cleared —
    예전 VIX 단독 실패로 재시도를 열지 않는다. 표식이 없으면 새 행을 만들지 않는다.
    """
    if vix_only_failure:
        write_state(
            MarketRefreshStateRow(
                refresh_id=refresh_id,
                last_attempt_finished_at=_iso(finished),
                last_attempt_status="needed",
                last_error_summary=vix_msg,
            ),
            db_path=db_path,
            scope=VIX_RETRY_SCOPE,
        )
        return
    prior = read_state(db_path=db_path, scope=VIX_RETRY_SCOPE)
    if prior is not None and prior.last_attempt_status != "cleared":
        write_state(
            MarketRefreshStateRow(
                refresh_id=refresh_id,
                last_attempt_finished_at=_iso(finished),
                last_attempt_status="cleared",
            ),
            db_path=db_path,
            scope=VIX_RETRY_SCOPE,
        )


def get_vix_retry_snapshot(db_path: Path = DEFAULT_DB_PATH) -> Optional[dict]:
    """GET /market/refresh/status 의 선택 필드 `vix_retry`. 행이 없으면 None."""
    from app import market_refresh_service as svc

    svc._ensure_loaded(db_path)
    with svc._service.lock:
        row = read_state(db_path=db_path, scope=VIX_RETRY_SCOPE)
    if row is None:
        return None
    return {
        "needed": row.last_attempt_status in VIX_RETRY_NEEDED_STATUSES,
        "status": row.last_attempt_status,
        "refresh_id": row.refresh_id,
        "started_at": row.last_attempt_started_at,
        "finished_at": row.last_attempt_finished_at,
        "error_summary": row.last_error_summary,
        "vix_as_of_date": row.asof,
    }


def _execute_vix_retry_job(*, retry_id: str, db_path: Path, started: datetime) -> None:
    """VIX 단계만 돈다. 결과는 vix_retry 행에만 쓴다."""
    from app import market_refresh_service as svc

    try:
        msg = svc.refresh_pc_vix(db_path=db_path, now_utc=svc._utcnow())
    except Exception:  # noqa: BLE001 — thread 안에서 격리
        logger.exception("PC VIX retry failed")
        msg = VIX_STEP_FAILED_TEXT
    try:
        vix_as_of = latest_benchmark_date("VIX", db_path=db_path)
    except Exception:  # noqa: BLE001
        vix_as_of = None
    with svc._service.lock:
        write_state(
            MarketRefreshStateRow(
                refresh_id=retry_id,
                last_attempt_started_at=_iso(started),
                last_attempt_finished_at=_iso(svc._utcnow()),
                last_attempt_status="completed" if msg is None else "failed",
                last_error_summary=msg,
                asof=vix_as_of,
            ),
            db_path=db_path,
            scope=VIX_RETRY_SCOPE,
        )


def start_vix_retry_job(
    *,
    db_path: Path = DEFAULT_DB_PATH,
    cooldown_hours: Optional[int] = None,
    thread_runner: Optional[Callable[[Callable[[], None]], None]] = None,
):
    """POST /market/refresh?scope=vix — 표식(needed · failed)이 있을 때만 VIX 단계만 돈다.

    전체 갱신 · VIX 다시 받기 실행 중이면 거절(같은 잠금). 대상이 없으면 not_needed(실행 0).
    대기 · 횟수 제한 · 자동 반복 없음.
    """
    from app import market_refresh_service as svc

    hours = svc.DEFAULT_COOLDOWN_HOURS if cooldown_hours is None else cooldown_hours
    svc._ensure_loaded(db_path)
    with svc._service.lock:
        cd = svc._cooldown_remaining_seconds(hours)
        if svc._service.state.status == "running":
            return svc.StartResult(
                status="running",
                refresh_id=svc._service.state.refresh_id,
                message="시장 데이터 갱신이 이미 진행 중입니다.",
                cooldown_remaining_seconds=cd,
            )
        row = read_state(db_path=db_path, scope=VIX_RETRY_SCOPE)
        if row is not None and row.last_attempt_status == "running":
            return svc.StartResult(
                status="vix_retry_running",
                refresh_id=row.refresh_id,
                message="VIX 다시 받기가 진행 중입니다.",
                cooldown_remaining_seconds=cd,
            )
        if row is None or row.last_attempt_status not in VIX_RETRY_NEEDED_STATUSES:
            return svc.StartResult(
                status="not_needed",
                refresh_id=None,
                message="다시 받을 VIX 실패 기록이 없습니다.",
                cooldown_remaining_seconds=cd,
            )
        started = svc._utcnow()
        retry_id = (
            f"vix_retry_{started.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        )
        write_state(
            MarketRefreshStateRow(
                refresh_id=retry_id,
                last_attempt_started_at=_iso(started),
                last_attempt_status="running",
                last_error_summary=row.last_error_summary,
            ),
            db_path=db_path,
            scope=VIX_RETRY_SCOPE,
        )

    def runner() -> None:
        _execute_vix_retry_job(retry_id=retry_id, db_path=db_path, started=started)

    if thread_runner is not None:
        thread_runner(runner)
    else:
        threading.Thread(
            target=runner, name=f"vix-retry-{retry_id}", daemon=True
        ).start()
    return svc.StartResult(
        status="accepted",
        refresh_id=retry_id,
        message="VIX 다시 받기를 시작했습니다.",
        cooldown_remaining_seconds=cd,
    )
