"""보유 ETF 구성종목 — [최신 자료 갱신] 단계와 상태 읽기(POC6-31 STEP 2 · PLAN C9 ~ C13).

- 대상: 단계 시작 때 한 번 읽은 보유 → 종목 코드 중복 제거 → ETF 목록(`etf_master`)에 있는 것만.
  한도 = 그때의 보유 ETF 수(판정 Q22 · 고정 숫자 아님).
- 수집은 `etf_constituents_batch.COLLECTOR` 의 보유 작업으로 한다(같은 작업 한 번 · 겹친 요청 공유 · 간격 이어짐).
- 상태 읽기는 저장 자료(구성 표 · 수집 기록)만 읽는다 — 서버를 다시 켜도 같은 상태 · 읽기만으로 수집이 시작되지 않는다.
- 할 일 개수(판정 Q16) = 보유 ETF 를 종목 단위로 센 '다시 확인 필요' 수(직접 보유 주식 · 계좌 행 · 시장 후보 상태 뺌).
"""

from __future__ import annotations

import sqlite3
import time
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from app import etf_constituents_store
from app import holdings as holdings_module
from app.collect_target_date import collect_target_date
from app.etf_constituents_batch import COLLECTOR, KIND_HOLDINGS, Collector
from app.etf_constituents_status import (
    HOLDINGS_ACTION,
    RESULT_LABEL,
    not_checked_reason,
    stored_status,
)
from app.holdings import HoldingsValidationError

__all__ = ["not_checked_reason"]  # 예전 위치에서 부르던 이름(상태 모듈로 옮김)

REASON_EMPTY = "보유 종목이 없습니다"
REASON_INVALID = "보유 파일을 읽지 못했습니다"
REASON_NO_ETF_LIST = "ETF 목록을 읽지 못했습니다 — 시장 자료 갱신 뒤 다시 누르세요"
REASON_NO_TARGET = "수집 목표일을 정하지 못했습니다(달력)"
STEP_ERROR_TEXT = "보유 구성종목을 받는 중 오류가 났습니다."
POLL_SECONDS = 0.5


def _db() -> Path:
    # 부를 때 모듈 속성으로 찾는다(시험이 tmp 경로로 바꿔 끼운다).
    return Path(etf_constituents_store.DEFAULT_DB_PATH)


def _etf_tickers(db_path: Path) -> set[str]:
    p = Path(db_path)
    if not p.exists():
        return set()
    with closing(sqlite3.connect(f"file:{p}?mode=ro", uri=True)) as con:
        try:
            return {r[0] for r in con.execute("SELECT ticker FROM etf_master")}
        except sqlite3.OperationalError:
            return set()


def holdings_etf_targets(
    *, db_path: Path
) -> tuple[list[tuple[str, Optional[str]]], Optional[str]]:
    """[(ETF 코드, 보유 이름)] · 건너뛸 사유(없으면 None)."""
    try:
        loaded = holdings_module.load()
    except (HoldingsValidationError, OSError, ValueError):
        return [], REASON_INVALID
    if not loaded:
        return [], REASON_EMPTY
    etfs = _etf_tickers(db_path)
    if not etfs:
        return [], REASON_NO_ETF_LIST
    seen: dict[str, Optional[str]] = {}
    for h in loaded:
        if h.ticker in etfs and h.ticker not in seen:
            seen[h.ticker] = h.name
    return list(seen.items()), None


def _summary(snap: dict[str, Any], names: dict[str, Optional[str]]) -> dict[str, Any]:
    items = [{**it, "name": names.get(it["ticker"])} for it in snap.get("items", [])]
    return {
        "status": "running" if snap.get("state") == "running" else "done",
        "reason": snap.get("reason"),
        "reason_detail": snap.get("reason_detail"),
        "job_id": snap.get("job_id"),
        "target_date": snap.get("target_date"),
        "total": snap.get("total"),
        "done": snap.get("done"),
        "batch_index": snap.get("batch_index"),
        "batch_total": snap.get("batch_total"),
        "calls": snap.get("calls"),
        "counts": snap.get("counts"),
        "update_failed": snap.get("update_failed"),
        "shared": snap.get("shared", 0),
        "unlogged_logs": snap.get("unlogged_logs", 0),
        "items": items,
    }


def plan_step(
    *,
    now: Optional[datetime] = None,
    db_path: Optional[Path] = None,
    calendar_dir: Optional[Path] = None,
) -> dict[str, Any]:
    """대상 · 한도 · 목표일을 **[최신 자료 갱신]을 누른 시점에** 한 번 읽어 고정한다(검증자 r1 F3 · 설계 §3 · 판정 Q22).

    {targets: [(ETF 코드, 보유 이름)], reason, target_date, db_path} — 단계는 이것만 쓴다(도중에 보유를 바꿔도 대상 ·
    호출 한도가 바뀌지 않음).
    """
    db = Path(db_path or _db())
    targets, reason = holdings_etf_targets(db_path=db)
    target = collect_target_date(
        now or datetime.now(timezone.utc), calendar_dir=calendar_dir
    )
    if reason is None and target is None:
        reason = REASON_NO_TARGET
    return {"targets": targets, "reason": reason, "target_date": target, "db_path": db}


def constituents_step(
    *,
    plan: Optional[dict[str, Any]] = None,
    now: Optional[datetime] = None,
    db_path: Optional[Path] = None,
    calendar_dir: Optional[Path] = None,
    collector: Optional[Collector] = None,
    fetcher=None,
    on_progress: Optional[Callable[[dict[str, Any]], None]] = None,
    wait_fn: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """[최신 자료 갱신]의 '보유 구성종목' 단계 — 끝날 때까지 기다리며 진행을 `on_progress` 로 알린다.

    `plan` = 작업 시작 때 `plan_step` 으로 고정한 대상(묶음 작업은 늘 넘긴다). 없으면 지금 읽는다(단독 호출).
    """
    p = plan or plan_step(now=now, db_path=db_path, calendar_dir=calendar_dir)
    db = Path(p["db_path"])
    col = collector or COLLECTOR
    targets, reason, target = p["targets"], p["reason"], p["target_date"]
    if reason is not None:
        return {
            "status": "skipped",
            "reason": reason,
            "target_date": target,
            "items": [],
        }
    names = dict(targets)
    snap = col.start(
        KIND_HOLDINGS,
        [t for t, _ in targets],
        target_date=target,
        db_path=db,
        fetcher=fetcher,
    )
    while snap.get("state") == "running":
        if on_progress is not None:
            on_progress(_summary(snap, names))
        wait_fn(POLL_SECONDS)
        snap = col.current(KIND_HOLDINGS) or snap
    return _summary(snap, names)


def holdings_constituents_status(
    *,
    now: Optional[datetime] = None,
    db_path: Optional[Path] = None,
    calendar_dir: Optional[Path] = None,
    collector: Optional[Collector] = None,
) -> dict[str, Any]:
    """보유 ETF 별 구성 상태(저장 자료만 · 읽기 전용). 화면 진입 · [요약 다시 읽기] · 할 일 개수가 읽는다."""
    db = Path(db_path or _db())
    col = collector or COLLECTOR
    targets, reason = holdings_etf_targets(db_path=db)
    target = collect_target_date(
        now or datetime.now(timezone.utc), calendar_dir=calendar_dir
    )
    running = col.current(KIND_HOLDINGS)
    base: dict[str, Any] = {
        "status": "ok",
        "reason": None,
        "target_date": target,
        "running": bool(running and running.get("state") == "running"),
        "total": 0,
        "needs_check": 0,
        "counts": {k: 0 for k in RESULT_LABEL},
        "items": [],
    }
    if reason is None and target is None:
        reason = REASON_NO_TARGET
    if reason is not None:
        base.update(status="skipped", reason=reason)
        return base
    names = dict(targets)
    base.update(
        stored_status(
            [t for t, _ in targets],
            target_date=target,
            db_path=db,
            action=HOLDINGS_ACTION,
            names=names,
        )
    )
    return base
