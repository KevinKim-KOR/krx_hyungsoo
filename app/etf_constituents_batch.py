"""ETF 구성종목 수집 작업(POC6-31 STEP 1 · PLAN C1 ~ C5 · 판정 §1).

- 작업 = 보유('holdings') 또는 후보 목록('candidates') 한 벌. 대상은 시작 때 확정하고 ETF별 조회는 1회 이내다.
- 같은 종류의 작업이 돌고 있으면 새로 만들지 않고 그 작업을 돌려준다(연타 · 화면 이동 뒤 같은 작업).
  대상 목록이 다르면 `other_list=True` 로 알린다(다른 목록의 작업을 이 목록의 수집처럼 보이지 않게).
- 보유 작업과 후보 작업에 같은 ETF가 겹치면 진행 중인 조회를 공유한다(두 번 부르지 않음). 받은 결과는
  기다린 작업의 목표일로 다시 판정하고, 필요한 확인 기록은 그 작업의 목표일로 남긴다.
- 최대 10개씩 묶고, 묶음마다 기존 시간 예산(30초)을 둔다. 외부 호출 사이 0.5초 간격은 묶음 경계와 두 작업
  사이에도 이어진다(프로세스 안 한 곳에서 마지막 호출 시각을 지킨다). 자동 재시도 · 자동 보충은 없다.
- 재사용: 원천일이 확인된 구성이 목표일 이상이면 다시 부르지 않는다. 그 밖(목표일 미충족 · 실패 · 시간 초과 ·
  저장 잠김 · 원천 기준일 미확인 · 아직 확인 안 함)은 이 작업에서 다시 확인한다.
- 원천 날짜는 달력 날짜(YYYY-MM-DD)로 읽히고 오늘(한국 시각)보다 늦지 않아야 한다. 아니면(날짜 없음 포함)
  저장하지 않는다(마지막 보존 구성 유지 · '원천 기준일 미확인').
- SQLite 잠김(읽기 · 저장)은 그 ETF 결과로만 남기고 다음 ETF로 넘어간다. 잠김으로 못 쓴 확인 기록은 작업 끝에
  한 번 더 쓴다. 그래도 못 쓰면 그 수를 작업 응답(`unlogged_logs`)에 남긴다.

수집기(`fetcher`)는 기존 네이버 수집기를 기본으로 쓴다. 시험은 가짜 수집기 · tmp DB 만 넘긴다.
"""

from __future__ import annotations

import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from app.etf_constituents_fetcher import (
    FetcherFn,
    FetchResult,
    NAVER_STOCK_SOURCE,
    _build_constituent_key,
    default_fetcher,
)
from app.etf_constituents_service import (
    DEFAULT_TOP_K,
    MAX_TICKERS_PER_REQUEST,
    PER_TICKER_DELAY_SECONDS,
    TIME_BUDGET_SECONDS,
)
from app.etf_constituents_status import (
    EXISTING,
    FAILED,
    FETCHED,
    LOCKED,
    LOG_FAILED,
    LOG_LOCKED,
    LOG_NO_SOURCE_DATE,
    LOG_OK,
    LOG_TARGET_WAIT,
    LOG_TIMEOUT,
    NO_SOURCE_DATE,
    RESULT_LABEL,
    RESULT_REASON,
    TARGET_WAIT,
    TIMEOUT,
    UPDATE_FAILED,
    is_locked_error as _is_locked,
    judge,
    read_snapshots,
)
from app.etf_constituents_store import (
    ConstituentRow,
    log_constituent_refresh,
    replace_constituents_snapshot,
)
from app.pc_etf_compare_periods import KST

KIND_HOLDINGS = "holdings"
KIND_CANDIDATES = "candidates"
KINDS = (KIND_HOLDINGS, KIND_CANDIDATES)
CANDIDATES_MAX = (
    30  # 판정 §1 둘째 — 후보는 최대 30개(넘겨받는 목록 상한 LIST_N 과 같음)
)
SHARED_WAIT_SECONDS = 60.0  # 다른 작업이 부르는 중인 같은 ETF 결과를 기다리는 상한
JOB_ERROR_TEXT = "작업 중 오류로 멈췄습니다 — 남은 ETF는 다음 갱신 때 다시 확인합니다"

# 공유받은 실패 결과를 기다린 작업의 목표일로도 남길 때 쓰는 기록 상태
_RESULT_TO_LOG = {
    FAILED: LOG_FAILED,
    TIMEOUT: LOG_TIMEOUT,
    LOCKED: LOG_LOCKED,
    NO_SOURCE_DATE: LOG_NO_SOURCE_DATE,
    TARGET_WAIT: LOG_TARGET_WAIT,
}


def _utc_iso(dt: Optional[datetime] = None) -> str:
    return (dt or datetime.now(timezone.utc)).isoformat()


def _kst_today() -> date:
    return datetime.now(KST).date()


def source_complete(res: FetchResult) -> bool:
    """저장 행이 원천이 준 전체인가(POC6-31 STEP 4 · 검토 지적 backend#0) — 원천 항목 수가 요청 깊이보다 적고 버린 항목이
    없을 때만(수집기는 비중을 읽을 수 없는 항목을 버린다 · 0 으로 채우지 않음). 원천 항목 수를 모르면 False."""
    n = res.source_count
    return n is not None and n < DEFAULT_TOP_K and n == len(res.constituents)


def valid_source_date(src: str, today: date) -> bool:
    """원천 날짜가 `YYYY-MM-DD` 달력 날짜이고 `today`(한국 시각 오늘)보다 늦지 않은가."""
    if len(src) != 10:
        return False
    try:
        d = date.fromisoformat(src)
    except ValueError:
        return False
    return d.isoformat() == src and d <= today


@dataclass
class _Gate:
    """외부 호출 간격 — 프로세스 안 한 곳(묶음 경계 · 두 작업 사이에도 이어짐)."""

    lock: threading.Lock = field(default_factory=threading.Lock)
    last: Optional[float] = None

    def wait(
        self, sleep_fn: Callable[[float], None], mono_fn: Callable[[], float]
    ) -> None:
        with self.lock:
            if self.last is not None:
                gap = PER_TICKER_DELAY_SECONDS - (mono_fn() - self.last)
                if gap > 0:
                    sleep_fn(gap)
            self.last = mono_fn()


@dataclass
class _Flight:
    target: str  # 부르는 작업의 목표일
    done: threading.Event = field(default_factory=threading.Event)
    item: Optional[dict[str, Any]] = None


@dataclass
class Job:
    job_id: str
    kind: str
    target_date: str
    tickers: list[str]
    started_at: str
    state: str = "running"
    finished_at: Optional[str] = None
    items: dict[str, dict[str, Any]] = field(default_factory=dict)
    batch_index: int = 0
    batch_total: int = 0
    calls: int = 0
    reason: Optional[str] = None
    reason_detail: Optional[str] = None  # 예외 이름 등(화면 '자세히' 안)
    # 잠김으로 못 쓴 확인 기록 — 작업 끝에 한 번 더 쓴다(판정 §1 넷째 · 다시 켜도 같은 상태).
    pending_logs: list[dict[str, Any]] = field(default_factory=list)
    log_blocked: bool = (
        False  # 한 번 잠김을 만나면 남은 기록은 끝에 모아 쓴다(ETF마다 5초씩 기다리지 않음)
    )
    unlogged: int = 0

    def snapshot(self) -> dict[str, Any]:
        counts = {k: 0 for k in RESULT_LABEL}
        for it in self.items.values():
            counts[it["result"]] = counts.get(it["result"], 0) + 1
        return {
            "job_id": self.job_id,
            "kind": self.kind,
            "state": self.state,
            "reason": self.reason,
            "reason_detail": self.reason_detail,
            "target_date": self.target_date,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "tickers": list(self.tickers),
            "total": len(self.tickers),
            "done": len(self.items),
            "batch_index": self.batch_index,
            "batch_total": self.batch_total,
            "calls": self.calls,
            "counts": counts,
            "update_failed": sum(counts[k] for k in UPDATE_FAILED),
            # 다른 작업이 부른 결과를 함께 받은 수(이 작업의 '실제 호출'에는 없음)
            "shared": sum(1 for it in self.items.values() if it.get("shared")),
            # 끝내 못 쓴 확인 기록 수(진행 중에는 쓰기 대기 수 포함)
            "unlogged_logs": self.unlogged + len(self.pending_logs),
            "items": [self.items[t] for t in self.tickers if t in self.items],
        }


class Collector:
    """수집 작업 관리(한 프로세스 한 벌 · 시험은 따로 만든다)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, Job] = {}
        self._flights: dict[str, _Flight] = {}
        self._gate = _Gate()

    def current(self, kind: str) -> Optional[dict[str, Any]]:
        with self._lock:
            job = self._jobs.get(kind)
            return job.snapshot() if job else None

    @staticmethod
    def normalize(kind: str, tickers: list[str]) -> list[str]:
        """대상 확정 — 공백 · 중복 제거, 후보는 앞 30개."""
        uniq = list(dict.fromkeys(t.strip() for t in tickers if t and t.strip()))
        return uniq[:CANDIDATES_MAX] if kind == KIND_CANDIDATES else uniq

    def start(
        self,
        kind: str,
        tickers: list[str],
        *,
        target_date: str,
        db_path: Path,
        fetcher: Optional[FetcherFn] = None,
        sleep_fn: Callable[[float], None] = time.sleep,
        mono_fn: Callable[[], float] = time.monotonic,
        today_fn: Callable[[], date] = _kst_today,
        run_async: bool = True,
    ) -> dict[str, Any]:
        """작업 시작. 같은 종류가 돌고 있으면 그 작업을 돌려준다(새로 만들지 않음).

        돌려준 작업의 대상이 요청 목록과 다르면 `other_list=True`.
        """
        if kind not in KINDS:
            raise ValueError(f"unknown kind: {kind}")
        uniq = self.normalize(kind, tickers)
        with self._lock:
            running = self._jobs.get(kind)
            if running is not None and running.state == "running":
                snap = running.snapshot()
                snap["other_list"] = set(running.tickers) != set(uniq)
                return snap
            job = Job(
                job_id=f"{kind}_{uuid.uuid4().hex[:8]}",
                kind=kind,
                target_date=target_date,
                tickers=uniq,
                started_at=_utc_iso(),
                batch_total=(len(uniq) + MAX_TICKERS_PER_REQUEST - 1)
                // MAX_TICKERS_PER_REQUEST,
            )
            self._jobs[kind] = job
        args = (job, db_path, fetcher or default_fetcher(), sleep_fn, mono_fn, today_fn)
        if run_async:
            threading.Thread(target=self._run, args=args, daemon=True).start()
        else:
            self._run(*args)
        with self._lock:
            snap = job.snapshot()
        snap["other_list"] = False
        return snap

    # ---- 실행 ----
    def _run(self, job, db_path, fetch, sleep_fn, mono_fn, today_fn) -> None:
        try:
            for b in range(job.batch_total):
                with self._lock:
                    job.batch_index = b + 1
                lo = b * MAX_TICKERS_PER_REQUEST
                hi = lo + MAX_TICKERS_PER_REQUEST
                batch = job.tickers[lo:hi]
                t0 = mono_fn()
                ctx = (t0, db_path, fetch, sleep_fn, mono_fn, today_fn)
                for tk in batch:
                    item = self._one(job, tk, *ctx)
                    with self._lock:
                        job.items[tk] = item
        except Exception as e:  # noqa: BLE001 — 작업이 끝났음을 늘 남긴다
            with self._lock:
                job.reason = JOB_ERROR_TEXT
                job.reason_detail = type(e).__name__
        finally:
            try:
                self._flush_logs(job, db_path)
            finally:
                with self._lock:
                    job.state = "done"
                    job.finished_at = _utc_iso()

    def _read(self, job, tk, db_path) -> Optional[dict[str, Any]]:
        """저장 상태 읽기. 잠김이면 None(그 ETF는 '저장 잠김')."""
        try:
            return read_snapshots([tk], db_path=db_path)[tk]
        except sqlite3.OperationalError as e:
            if not _is_locked(e):
                raise
            return None

    def _locked_read(self, job, tk, db_path) -> dict[str, Any]:
        self._log(job, tk, job.target_date, LOG_LOCKED, None, "read_locked", db_path)
        return self._item(tk, LOCKED, {}, detail="read_locked")

    def _one(self, job, tk, t0, db_path, fetch, sleep_fn, mono_fn, today_fn):
        snap = self._read(job, tk, db_path)
        if snap is None:
            return self._locked_read(job, tk, db_path)
        if judge(snap, job.target_date)["result"] == EXISTING:
            return self._item(tk, EXISTING, snap)
        while True:
            with self._lock:
                flight = self._flights.get(tk)
                mine = flight is None
                if mine:
                    flight = _Flight(target=job.target_date)
                    self._flights[tk] = flight
            if mine:
                break
            shared = self._shared(job, tk, flight, snap, db_path)
            if shared is not None:
                return shared
            # 다른 작업이 부르지 않고 끝남(그 묶음 시간 초과 · 그 목표일 기준 기존 자료) — 이 작업이 직접 확인한다.
        try:
            item = self._owned(job, tk, t0, db_path, fetch, sleep_fn, mono_fn, today_fn)
            flight.item = item
            return item
        finally:
            with self._lock:
                self._flights.pop(tk, None)
            flight.done.set()

    def _owned(self, job, tk, t0, db_path, fetch, sleep_fn, mono_fn, today_fn):
        # 조회 주인이 된 뒤 다시 읽는다 — 그 사이 다른 작업이 목표일 이상 구성을 저장했으면 부르지 않는다.
        snap = self._read(job, tk, db_path)
        if snap is None:
            return self._locked_read(job, tk, db_path)
        if judge(snap, job.target_date)["result"] == EXISTING:
            return self._item(tk, EXISTING, snap)
        return self._fetch_one(
            job, tk, t0, snap, db_path, fetch, sleep_fn, mono_fn, today_fn
        )

    def _shared(self, job, tk, flight, snap, db_path) -> Optional[dict[str, Any]]:
        """다른 작업이 부르는 중인 같은 ETF — 끝나기를 기다려 이 작업의 목표일로 다시 판정한다.

        None = 다른 작업이 부르지 않고 끝났다(이 작업이 직접 확인한다).
        """
        target = job.target_date
        if not flight.done.wait(SHARED_WAIT_SECONDS):
            detail = "shared_wait_timeout"
            self._log(job, tk, target, LOG_TIMEOUT, None, detail, db_path)
            return self._item(tk, TIMEOUT, snap, detail=detail, shared=True)
        it = flight.item
        if it is None:  # 부른 작업이 오류로 멈춤
            detail = "shared_owner_error"
            self._log(job, tk, target, LOG_FAILED, None, detail, db_path)
            return self._item(tk, FAILED, snap, detail=detail, shared=True)
        res = it["result"]
        if res in (TIMEOUT, EXISTING):
            return None
        out = {**it, "shared": True}
        if res in (FETCHED, TARGET_WAIT):
            src = it["source_asof"]
            mine = FETCHED if src >= target else TARGET_WAIT
            out.update(
                result=mine, label=RESULT_LABEL[mine], reason=RESULT_REASON[mine]
            )
            if mine == TARGET_WAIT:
                self._log(
                    job,
                    tk,
                    target,
                    LOG_TARGET_WAIT,
                    NAVER_STOCK_SOURCE,
                    f"source={src}",
                    db_path,
                )
            return out
        # 받기 실패 · 저장 잠김 · 원천 기준일 미확인 — 목표일이 다르면 이 작업 목표일로도 기록한다.
        if flight.target != target:
            self._log(
                job, tk, target, _RESULT_TO_LOG[res], None, it.get("detail"), db_path
            )
        return out

    def _fetch_one(
        self, job, tk, t0, snap, db_path, fetch, sleep_fn, mono_fn, today_fn
    ):
        target = job.target_date
        if mono_fn() - t0 >= TIME_BUDGET_SECONDS:
            self._log(
                job, tk, target, LOG_TIMEOUT, None, "time_budget_exceeded", db_path
            )
            return self._item(tk, TIMEOUT, snap)
        self._gate.wait(sleep_fn, mono_fn)
        with self._lock:
            job.calls += 1
        checked = _utc_iso()
        try:
            res: FetchResult = fetch(tk, target, DEFAULT_TOP_K)
        except Exception as e:  # noqa: BLE001 — 수집기 예외는 이 ETF 실패로
            res = FetchResult(
                status="unavailable",
                source="unknown",
                constituents=[],
                message=f"fetch_unexpected: {type(e).__name__}",
            )
        if (
            res.status != "ok"
            or not res.constituents
            or res.source != NAVER_STOCK_SOURCE
        ):
            detail = res.message if res.status != "ok" else "source_unclear_or_empty"
            self._log(job, tk, target, LOG_FAILED, res.source, detail, db_path)
            return self._item(tk, FAILED, snap, checked_at=checked, detail=detail)
        src = (res.effective_asof or "").strip()
        if not valid_source_date(src, today_fn()):
            detail = f"invalid_source_date={src}" if src else None
            self._log(job, tk, target, LOG_NO_SOURCE_DATE, res.source, detail, db_path)
            return self._item(
                tk, NO_SOURCE_DATE, snap, checked_at=checked, detail=detail
            )
        rows = [
            ConstituentRow(
                etf_ticker=tk,
                asof=src,
                source=res.source,
                rank=c.rank,
                constituent_ticker=c.constituent_ticker,
                constituent_name=c.constituent_name,
                weight_pct=c.weight_pct,
                etf_name=res.etf_name,
                constituent_key=_build_constituent_key(
                    c.constituent_ticker,
                    c.constituent_reuters_code,
                    c.constituent_isin,
                    c.constituent_name,
                ),
                constituent_isin=c.constituent_isin,
                constituent_reuters_code=c.constituent_reuters_code,
                market_type=c.market_type,
            )
            for c in res.constituents
        ]
        # 검증자 r1 F1 — 같은 날짜 구성을 통째로 바꾸고 원천일 확인 기록을 같은 트랜잭션에(예전 순위 행이 남지 않게 ·
        # 잠김이면 둘 다 안 바뀜). 검증자 r2 F5 — 확인 기록에 그 행들의 내용 지문(읽을 때 같은 내용인지 대조) ·
        # 검증자 r3 F7 — 지문은 같은 트랜잭션에서 저장한 행을 DB 에서 다시 읽어 계산(-0.0 등 표현 차이).
        try:
            replace_constituents_snapshot(
                rows,
                log_status=LOG_OK,
                confirm=True,
                complete=source_complete(res),
                db_path=db_path,
            )
        except sqlite3.OperationalError as e:
            if not _is_locked(e):
                raise
            self._log(job, tk, target, LOG_LOCKED, res.source, None, db_path)
            return self._item(tk, LOCKED, snap, checked_at=checked)
        if src >= target:
            return self._item(
                tk, FETCHED, snap, source_asof=src, rows=len(rows), checked_at=checked
            )
        self._log(
            job, tk, target, LOG_TARGET_WAIT, res.source, f"source={src}", db_path
        )
        return self._item(
            tk, TARGET_WAIT, snap, source_asof=src, rows=len(rows), checked_at=checked
        )

    def _log(self, job, tk, asof, status, source, message, db_path) -> bool:
        """확인 기록 한 줄. 잠김으로 못 쓰면 작업 끝에 다시 쓸 목록에 넣고 False."""
        rec = {
            "etf_ticker": tk,
            "asof": asof,
            "status": status,
            "source": source,
            "message": message,
        }
        with self._lock:
            blocked = job.log_blocked
        if not blocked:
            try:
                log_constituent_refresh(**rec, db_path=db_path)
                return True
            except sqlite3.OperationalError as e:
                if not _is_locked(e):
                    raise
        with self._lock:
            job.log_blocked = True
            job.pending_logs.append(rec)
        return False

    def _flush_logs(self, job, db_path) -> None:
        """잠김으로 못 쓴 확인 기록을 한 번 더 쓴다. 여전히 잠겼으면 남은 수만 센다(더 기다리지 않음)."""
        with self._lock:
            pending, job.pending_logs = job.pending_logs, []
        left = 0
        for i, rec in enumerate(pending):
            try:
                log_constituent_refresh(**rec, db_path=db_path)
            except sqlite3.Error:
                left = len(pending) - i
                break
        with self._lock:
            job.unlogged += left

    @staticmethod
    def _item(
        tk: str,
        result: str,
        snap: dict[str, Any],
        *,
        source_asof: Optional[str] = None,
        rows: Optional[int] = None,
        checked_at: Optional[str] = None,
        detail: Optional[str] = None,
        shared: bool = False,
    ) -> dict[str, Any]:
        conf = snap.get("confirmed")
        latest = snap.get("latest")
        kept = conf or latest
        if source_asof is None and conf is not None and result == EXISTING:
            source_asof = conf["asof"]
        return {
            "ticker": tk,
            "result": result,
            "label": RESULT_LABEL[result],
            "reason": RESULT_REASON[result],
            "source_asof": source_asof,
            "rows": rows if rows is not None else (conf["rows"] if conf else None),
            "kept_asof": (
                None
                if result in (FETCHED, TARGET_WAIT)
                else (kept["asof"] if kept else None)
            ),
            "kept_confirmed": bool(conf) and kept is conf,
            "checked_at": checked_at,
            "detail": detail,
            "shared": shared,
        }


COLLECTOR = Collector()
