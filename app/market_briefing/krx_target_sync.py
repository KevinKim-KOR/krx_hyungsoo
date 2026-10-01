"""POC3-02D-OPS-03 — KRX 목표일(T-1) 수집 · 시도 시각표 · 적재 판정 · 대표 커버리지 기록.

설계자 PLAN 판정(2026-09-29 · 확정 계약 1 · 2 · 3 · 5 · 7) · 설계자 RESULT STEP 2 · 6
(2026-09-30). KRX 는 전일 자료를 **익영업일 08:00** 에 공개한다(공식 FAQ) — 07:20
역탐색은 늘 T-2 였다.

| KRX 단계 시작(KST) | 시도 |
|---|---|
| 08:00 전 | **건너뛰고 기록** — 표 · 정합성 JSON 을 건드리지 않는다 |
| 08:00 ~ 08:27 | 08:10(단계 시작 즉시) · 08:15 · 08:20 · 08:24 중 남은 시각 · 최대 4회 · 08:27 뒤 새 시도 없음 |
| 08:27 뒤 | **1회**(수동 재실행 · 09:20 보강) |

목표일은 **거래일 캘린더로만** 정한다(`trading_day_lag.expected_previous_trading_day`).
0행 · 가격 빈 응답은 휴장이 아니라 '공개 전' 이다. 옛 역탐색
(`krx_sync.resolve_basis_date`)은 T-1 이 없으면 같은 호출 안에서 T-2 를 돌려주므로
쓰지 않는다.

**적재 성공 조건**(`krx_target_checks`) — ① 기준일 ③ 행 수 95% ④ 관계식 · 중복 · 0행 ·
결측 ⑤ read-back. **② 대표 ETF 커버리지는 적재 성공 조건이 아니다**(설계자 RESULT
STEP 2) — 적재가 성공하면 따로 판정해 `representatives` · `representatives_refresh_due`
로 기록만 한다. 장중 설정을 못 읽거나 대표가 상장폐지돼도 KRX 전체 적재와 08:30
기초지수는 그대로다. 정합성 JSON 의 `refresh_due`(CSV 갱신 안내)는 건드리지 않는다.

**성공한 T-1 은 덮어쓰지 않는다(확정 계약 2)** — T-1 이 표에 있고 정합성 JSON 이 T-1
판정이면 조회하지 않는다. 실패 · T-2 응답은 표에 쓰지 않고, T-1 판정이 든 정합성
JSON 을 '판정 못 함' 으로 덮지 않는다.

**곁 작업(`side_task`)** — 같은 시각표로 도는 독립 작업(설계자 RESULT STEP 3 · 08:10
배치의 KOSPI 재시도 · `market_benchmark_kospi_retry`). ETF 시도 사이(다음 ETF 시각을
기다리는 동안)와 ETF 단계가 끝난 뒤(판정 · 정합성 JSON 을 쓴 뒤)에만 부른다. 같은
시각이면 ETF 가 먼저다. ETF 가 성공 · 실패 · 건너뜀으로 끝나도 곁 작업의 남은 시각은
계속 돈다. 곁 작업의 예외는 삼킨다(ETF 결과를 바꾸지 않는다).

**빠진 거래일 채우기**(`krx_backfill` · PLAN STEP 3-3 · 설계자 RESULT STEP 6) — 매 실행
창(21거래일) 안 빠진 날을 채우되 **같은 날짜는 KST 하루 1회**(모든 실행 합산 ·
ledger). 목표일 조회가 원천에 닿은(`fetch_error` 아님) 첫 시도 뒤에 채운다 — 원천
불통 중에는 부르지 않는다. 첫 채우기가 원천 오류 · 마감으로 멈췄으면 T-1 성공 뒤 한
번 더(`backfill_retry` · 오늘 아직 안 부른 날만). 이미 받은 날(09:20)도 채운다.
"""

from __future__ import annotations

import sqlite3
import time as _time
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Optional, Sequence

from app import trading_day_lag
from app.intraday_config.representatives import COVERAGE_OK
from app.market_briefing import krx_backfill, krx_store, krx_sync, meta_gate
from app.market_briefing import krx_target_checks as checks

_KST = timezone(timedelta(hours=9))

STAGE_OPEN = time(8, 0)
ATTEMPT_SLOTS = (time(8, 10), time(8, 15), time(8, 20), time(8, 24))
STAGE_DEADLINE = time(8, 27)
# 단계 시작 직후(이 간격 미만)의 슬롯은 시작 시도에 합친다 — 1초 간격 연속 시도 방지.
MIN_SLOT_GAP = timedelta(seconds=60)
# 확정 계약 4 — 행 수 95%. 판정은 `krx_target_checks.check_response` 가 한다.
MIN_ROW_RATIO = checks.MIN_ROW_RATIO

MODE_SCHEDULED = "scheduled"
MODE_SINGLE = "single_attempt"
MODE_SKIPPED_BEFORE_OPEN = "skipped_before_open"
MODE_ALREADY_LOADED = "already_loaded"

STATUS_OK = krx_sync.STATUS_OK
STATUS_NO_API_KEY = krx_sync.STATUS_NO_API_KEY
STATUS_SKIPPED_BEFORE_OPEN = "skipped_before_open"
STATUS_TARGET_NOT_OBTAINED = "target_not_obtained"
STATUS_NO_TARGET_DATE = "target_date_unknown"

# 곁 작업 반복 상한 — 시각표(4개)의 몇 배. 이른 깨어남에도 남은 시각을 놓치지 않는다.
_SIDE_LOOP_LIMIT = 4 * len(ATTEMPT_SLOTS)

# 테스트가 가짜 시계 · sleep 을 넘기지 않아도 대체할 수 있게 모듈 이름으로 둔다.
_sleep = _time.sleep


def _now_kst() -> datetime:
    return datetime.now(_KST)


def _as_kst(dt: datetime) -> datetime:
    return dt.replace(tzinfo=_KST) if dt.tzinfo is None else dt.astimezone(_KST)


def _at(day: date, t: time) -> datetime:
    return datetime.combine(day, t, tzinfo=_KST)


def _bas(iso: str) -> str:
    return iso.replace("-", "")


def attempt_plan(
    start: datetime, *, max_attempts: Optional[int] = None
) -> tuple[str, list[datetime]]:
    """단계 시작 시각 → `(mode, 시도 시각들)`. 순수 함수(확정 계약 1)."""
    start = _as_kst(start)
    day = start.date()
    if start < _at(day, STAGE_OPEN):
        return MODE_SKIPPED_BEFORE_OPEN, []
    if start >= _at(day, STAGE_DEADLINE):
        mode, plan = MODE_SINGLE, [start]
    else:
        slots = [_at(day, s) for s in ATTEMPT_SLOTS]
        if start < slots[0]:
            plan = slots
        else:
            # 지금 시각이 속한 슬롯은 즉시 · 남은 슬롯은 그 시각에.
            plan = [start] + [s for s in slots if s - start >= MIN_SLOT_GAP]
        mode = MODE_SCHEDULED
    if max_attempts is not None:
        plan = plan[: max(0, max_attempts)]
        if len(plan) == 1:
            mode = MODE_SINGLE
    return mode, plan


def _stored_rows(iso: str, db_path: Optional[Path]) -> int:
    """이미 저장된 행 수. 저장소를 못 읽으면 0 — 시도로 넘어가 `store_error` 로 남는다."""
    try:
        return krx_store.row_count_on(iso, db_path=db_path)
    except sqlite3.Error:
        return 0


def _judged_for(previous: Optional[meta_gate.ConsistencyResult], iso: str) -> bool:
    """정합성 JSON 이 `iso` 날짜의 **실제 판정**인가(판정 못 한 날은 기준일이 비어 있다)."""
    if previous is None or not previous.evaluated_at_kst:
        return False
    return (previous.evaluated_api_basis_date or "") in (iso, _bas(iso))


def _refresh_from(previous: Optional[meta_gate.ConsistencyResult]) -> dict[str, Any]:
    if previous is None:
        return {}
    return {
        "consistency_status": previous.status,
        "refresh_due": previous.refresh_due,
        "refresh_due_reason": previous.refresh_due_reason,
        "refresh_due_cycle_id": previous.refresh_due_cycle_id,
        "csv_name": previous.csv_name,
    }


def sync_krx_target(
    *,
    today: date,
    consistency_path: Path,
    meta_dir: Optional[Path] = None,
    official_csv_path: Optional[Path] = None,
    db_path: Optional[Path] = None,
    env_path: Optional[Path] = None,
    calendar_dir: Optional[Path] = None,
    fetcher: Optional[Callable[[str, str], list[dict[str, Any]]]] = None,
    required_tickers: Optional[Sequence[str]] = None,
    runtime_db_path: Optional[Path] = None,
    max_attempts: Optional[int] = None,
    clock: Optional[Callable[[], datetime]] = None,
    sleep: Optional[Callable[[float], None]] = None,
    logger: Any = None,
    backfill_ledger_path: Optional[Path] = None,
    side_task: Any = None,
) -> dict[str, Any]:
    """08:10 배치 · 09:20 보강의 KRX 단계. **예외를 올리지 않는다.**

    조회 · 검사 · 저장 오류는 시도 기록(`fetch_error` · `store_error` 등)으로 남긴다.
    호출 인자 오류(`meta_dir` · `official_csv_path` 둘 다 · 둘 다 없음)만
    `TypeError` 로 올린다(`krx_sync.sync_krx_daily` 와 같다). 배치는 그래도 한 번 더
    감싼다(`_krx_stage`).

    `required_tickers` — 대표 커버리지 판정용 대표 목록(없으면 활성 장중 설정).
    적재 성공 여부에는 쓰지 않는다(설계자 RESULT STEP 2).
    `backfill_ledger_path` — 채우기 하루 호출 기록. 없으면 KRX 표와 같은 폴더.
    `side_task` — 같은 시각표의 곁 작업(`run_due(now)` · `next_slot()`). 08:10 배치의
    KOSPI 재시도만 넘긴다(설계자 RESULT STEP 3). 09:20 보강은 넘기지 않는다.
    """
    if (meta_dir is None) == (official_csv_path is None):
        raise TypeError("meta_dir 과 official_csv_path 중 하나만 넘긴다")
    now = clock or _now_kst
    pause = sleep or _sleep
    kw = dict(
        today=today,
        consistency_path=consistency_path,
        meta_dir=meta_dir,
        official_csv_path=official_csv_path,
        db_path=db_path,
        env_path=env_path,
        calendar_dir=calendar_dir,
        fetcher=fetcher,
        required_tickers=required_tickers,
        runtime_db_path=runtime_db_path,
        max_attempts=max_attempts,
        logger=logger,
        backfill_ledger_path=backfill_ledger_path,
    )
    try:
        out = _sync_target(now=now, pause=pause, side=side_task, **kw)
    except Exception:
        # ETF 단계 예외(배치가 다시 감싼다)도 곁 작업의 남은 시각을 막지 않는다.
        _drain_side(side_task, now, pause)
        raise
    # 판정 · 정합성 JSON 을 쓴 뒤에 곁 작업의 남은 시각을 돈다(ETF 를 늦추지 않는다).
    _drain_side(side_task, now, pause)
    return out


def _sync_target(
    *,
    today: date,
    consistency_path: Path,
    meta_dir: Optional[Path],
    official_csv_path: Optional[Path],
    db_path: Optional[Path],
    env_path: Optional[Path],
    calendar_dir: Optional[Path],
    fetcher: Optional[Callable[[str, str], list[dict[str, Any]]]],
    required_tickers: Optional[Sequence[str]],
    runtime_db_path: Optional[Path],
    max_attempts: Optional[int],
    logger: Any,
    backfill_ledger_path: Optional[Path],
    now: Callable[[], datetime],
    pause: Callable[[float], None],
    side: Any,
) -> dict[str, Any]:
    """`sync_krx_target` 본체(목표일 시각표 · 판정). 곁 작업은 ETF 시도 사이에만 부른다."""
    start = _as_kst(now())
    out: dict[str, Any] = {
        "status": None,
        "mode": None,
        "target_date": None,
        "basis_date": None,
        "rows_written": 0,
        "stage_started_at": start.isoformat(timespec="seconds"),
        "attempts": [],
    }

    target = trading_day_lag.expected_previous_trading_day(
        today.isoformat(), calendar_dir=calendar_dir
    )
    out["target_date"] = target
    if target is None:
        out["status"] = STATUS_NO_TARGET_DATE
        return out
    target_bas = _bas(target)

    mode, plan = attempt_plan(start, max_attempts=max_attempts)
    out["mode"] = mode
    if mode == MODE_SKIPPED_BEFORE_OPEN or not plan:
        # 공개(08:00) 전 — 헛재시도 없이 기록만. 표 · 정합성 JSON 을 건드리지 않는다.
        out["status"] = STATUS_SKIPPED_BEFORE_OPEN
        _log(logger, "KRX 단계 건너뜀: 공개 전 시작(%s)", out["stage_started_at"])
        return out

    deadline = _at(start.date(), STAGE_DEADLINE) if mode == MODE_SCHEDULED else None
    # 네트워크 경계는 `krx_sync._default_fetcher` 하나다(테스트 가드가 여기에 걸린다).
    fetch = fetcher or krx_sync._default_fetcher
    key = krx_sync.read_api_key(env_path)
    fill = dict(
        today=today,
        key=key,
        fetch=fetch,
        db_path=db_path,
        calendar_dir=calendar_dir,
        now=now,
        ledger_path=backfill_ledger_path or krx_backfill.ledger_path_for(db_path),
    )
    reps = dict(
        db_path=db_path,
        required_tickers=required_tickers,
        runtime_db_path=runtime_db_path,
    )
    previous = meta_gate.load_consistency(consistency_path)
    if _stored_rows(target, db_path) and _judged_for(previous, target):
        # 확정 계약 2 — 이미 성공한 T-1. 다시 조회 · 저장 · 판정하지 않는다.
        out.update(
            status=STATUS_OK,
            mode=MODE_ALREADY_LOADED,
            basis_date=target_bas,
            already_loaded=True,
            **_refresh_from(previous),
        )
        if key:
            # PLAN STEP 3-3 — 창 안 빈 날은 매 실행 채운다(없으면 조회 0 · T-1 재조회 아님).
            # 설계자 RESULT STEP 6 — 오늘 이미 부른 날짜는 다시 부르지 않는다(ledger).
            out["backfill"] = krx_backfill.fill_missing(
                target, deadline=deadline, **fill
            )
        _record_representatives(out, target, logger=logger, **reps)
        return out

    if not key:
        out["status"] = STATUS_NO_API_KEY
        out.update(
            _record_failure(consistency_path, previous, target, STATUS_NO_API_KEY)
        )
        return out

    success_rows: Optional[list[dict[str, Any]]] = None
    for i, when in enumerate(plan):
        # 첫 ETF 시도 앞에서는 곁 작업을 부르지 않는다(ETF 가 먼저다 · 설계자 RESULT STEP 3).
        _wait_for(when, now, pause, side if i > 0 else None)
        at = _as_kst(now())
        if deadline is not None and i > 0 and at >= deadline:
            out["deadline_reached"] = True
            break
        entry, rows = checks.attempt_once(
            target_bas, key=key, fetch=fetch, db_path=db_path, at=at
        )
        out["attempts"].append(entry)
        _log(
            logger,
            "KRX 목표일 시도: target=%s result=%s rows=%s priced=%s http=%s err=%s",
            target_bas,
            entry["result"],
            entry["rows"],
            entry["priced_rows"],
            entry["http"],
            entry["error_type"],
        )
        if "backfill" not in out:
            if entry["result"] != checks.R_FETCH_ERROR:
                # 빠진 거래일 채우기 — 원천에 닿은 첫 시도 뒤 한 번(성공이면 판정 전에
                # 창을 채운다). 목표일 조회가 원천 불통(`fetch_error`)이면 부르지 않고
                # 다음 시도로 미룬다 — 불통 중에 부르면 ledger 가 그 날짜를 오늘 부른
                # 것으로 남겨 원천이 돌아와도 오늘 다시 부르지 못한다(설계자 RESULT STEP 6).
                out["backfill"] = krx_backfill.fill_missing(
                    target, deadline=deadline, **fill
                )
        elif rows is not None and out["backfill"].get("stopped"):
            # 원천 오류 · 마감으로 멈춰 못 부른 날이 남았으면 T-1 을 받은 뒤 한 번 더
            # (08:10 일시 장애로 창이 비지 않게). 이미 부른 날은 ledger 가 건너뛴다
            # (설계자 RESULT STEP 6 — 같은 날짜 하루 1회).
            out["backfill_retry"] = krx_backfill.fill_missing(
                target, deadline=deadline, **fill
            )
        if rows is not None:
            success_rows = rows
            out["rows_written"] = entry.get("rows_written", 0)
            break

    if success_rows is None:
        last = out["attempts"][-1]["result"] if out["attempts"] else "no_attempt"
        out["status"] = STATUS_TARGET_NOT_OBTAINED
        out.update(_record_failure(consistency_path, previous, target, last))
        _log(logger, "KRX 목표일 미확보: target=%s last=%s", target_bas, last)
        return out

    window_fn = _window_fn(target, calendar_dir=calendar_dir, db_path=db_path, out=out)
    judged = krx_sync.judge_and_save_consistency(
        success_rows,
        bas_dd=target_bas,
        window_fn=window_fn,
        consistency_path=consistency_path,
        previous=previous,
        meta_dir=meta_dir,
        official_csv_path=official_csv_path,
        db_path=db_path,
        logger=logger,
    )
    out.update(
        status=STATUS_OK,
        basis_date=target_bas,
        api_ticker_count=judged["api_ticker_count"],
        consistency_status=judged["consistency_status"],
        join_coverage=judged["join_coverage"],
        **judged["refresh"],
    )
    _record_representatives(out, target, logger=logger, **reps)
    return out


def _pause_until(when: datetime, now: Callable[[], datetime], pause) -> None:
    wait = (when - _as_kst(now())).total_seconds()
    if wait > 0:
        pause(wait)


def _run_side(side: Any, now: Callable[[], datetime]) -> Optional[datetime]:
    """곁 작업의 도래 시각을 돌리고 다음 시각을 돌려준다. 예외는 삼킨다(`None`)."""
    if side is None:
        return None
    try:
        side.run_due(_as_kst(now()))
        nxt = side.next_slot()
    except Exception:  # noqa: BLE001 - 곁 작업 오류가 ETF 단계를 멈추지 않는다
        return None
    return _as_kst(nxt) if nxt is not None else None


def _wait_for(when: datetime, now: Callable[[], datetime], pause, side: Any) -> None:
    """`when` 까지 기다린다. 그 사이 곁 작업 시각이 오면 그것부터 돈다.

    같은 시각이면 기다림을 끝내고 ETF 시도로 간다 — 곁 작업은 다음 기다림 앞에서 돈다.
    """
    for _ in range(_SIDE_LOOP_LIMIT):
        nxt = _run_side(side, now)
        if nxt is None or nxt >= when:
            break
        _pause_until(nxt, now, pause)
    _pause_until(when, now, pause)


def _drain_side(side: Any, now: Callable[[], datetime], pause) -> None:
    """ETF 단계가 끝난 뒤 곁 작업의 남은 시각을 차례로 돈다(마감은 곁 작업이 정한다)."""
    for _ in range(_SIDE_LOOP_LIMIT):
        nxt = _run_side(side, now)
        if nxt is None:
            return
        _pause_until(nxt, now, pause)


def _record_representatives(
    out: dict[str, Any], target: str, *, logger: Any = None, **kw: Any
) -> None:
    """적재 뒤 대표 커버리지(설계자 RESULT STEP 2). 적재 결과 · 정합성 JSON 은 그대로다.

    `representatives_refresh_due` 는 장중 설정(대표) 갱신 필요 표시다 — 공식 CSV 갱신
    안내가 읽는 `refresh_due` 와 섞지 않는다.
    """
    rep = checks.evaluate_representatives(target, **kw)
    out["representatives"] = rep
    out["representatives_refresh_due"] = rep.get("representatives_refresh_due")
    if rep.get("status") != COVERAGE_OK:
        _log(
            logger,
            "KRX 대표 커버리지: status=%s missing=%s — 적재는 성공 · 장중 신규 진입 생략",
            rep.get("status"),
            rep.get("missing"),
        )


def _window_fn(
    target: str,
    *,
    calendar_dir: Optional[Path],
    db_path: Optional[Path],
    out: dict[str, Any],
) -> Callable[[], Optional[krx_store.PriceWindow]]:
    """판정 창 = 거래일 날짜 창(확정 계약 5). 창 상태는 `out["window"]` 에 남긴다."""

    def _fn() -> Optional[krx_store.PriceWindow]:
        window = krx_store.resolve_calendar_window(
            target, calendar_dir=calendar_dir, db_path=db_path
        )
        out["window"] = window.to_dict()
        return window.price_window()

    return _fn


def _record_failure(
    consistency_path: Path,
    previous: Optional[meta_gate.ConsistencyResult],
    target: str,
    reason: str,
) -> dict[str, Any]:
    """목표일을 못 받은 날. T-1 판정이 든 JSON 은 **덮지 않는다**(확정 계약 2)."""
    if _judged_for(previous, target):
        return {"consistency_kept": True, **_refresh_from(previous)}
    result = meta_gate.ConsistencyResult(
        status=meta_gate.STATUS_API_FETCH_FAILED,
        error=f"{STATUS_TARGET_NOT_OBTAINED}:{reason}",
    )
    return krx_sync._save_not_evaluated(result, consistency_path, previous)


def _log(logger: Any, msg: str, *args: Any) -> None:
    if logger is not None:
        logger.info(msg, *args)


__all__ = [
    "ATTEMPT_SLOTS",
    "MIN_ROW_RATIO",
    "MODE_ALREADY_LOADED",
    "MODE_SCHEDULED",
    "MODE_SINGLE",
    "MODE_SKIPPED_BEFORE_OPEN",
    "STAGE_DEADLINE",
    "STAGE_OPEN",
    "STATUS_NO_API_KEY",
    "STATUS_NO_TARGET_DATE",
    "STATUS_OK",
    "STATUS_SKIPPED_BEFORE_OPEN",
    "STATUS_TARGET_NOT_OBTAINED",
    "attempt_plan",
    "sync_krx_target",
]
