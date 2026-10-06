"""POC3-02D-OPS-03 — KRX 창(21거래일) 안 빠진 날 채우기 · 하루 호출 기록(ledger).

PLAN STEP 3-3 · 설계자 RESULT STEP 6(2026-09-30):

```text
범위        목표일(T-1)로 끝나는 21거래일 창 안의 빠진 날만(목표일 자신은 제외)
하루 1회    같은 날짜는 KST 하루에 **한 번만** 부른다 — 08:10 첫 채우기 · 같은 실행의
            backfill_retry · 09:20 --krx-only · 수동 재실행을 모두 합쳐서
보강 1회    단 첫 호출이 **일시 오류**(HTTP 5xx · 429 · timeout · 연결 오류 ·
            `RemoteProtocolError` · `krx_target_checks.is_transient_fetch_error`)로 끝난 날짜는 09:20 보강
            (`reinforcement=True` · **09:20 회차 창에 시작한 `run_krx_only` 만** ·
            `in_reinforcement_window`)이 **한 번 더** 부른다 — 날짜별
            하루 최대 = 최초 1회 + 보강 1회(POC3-02D-OPS-04 Q6 b). 보강 실행은 새
            보강 대상을 만들지 않는다. 영구 실패는 같은 날 다시 부르지 않는다
기록        이번 실행에서 실제로 부른 날짜(`called`) · 그 가운데 보강(`retried`) · 오늘
            이미 불러 건너뛴 날짜(`skipped_called_today`) · 오늘 날짜별 호출 횟수
            (`calls_today`)
```

목표일 T-1 시각표 시도(08:10 · 08:15 · 08:20 · 08:24 · 09:20)는 채우기가 아니다 —
ledger 에 넣지 않고 시각표를 그대로 따른다.

ledger 는 KRX 표(`market_data.sqlite`)와 같은 폴더의 `krx_backfill_ledger.json`
(`{"date_kst": "YYYY-MM-DD", "calls": {"YYYY-MM-DD": n}, "retryable": [...]}` ·
`retryable` 은 비었으면 쓰지 않는다)이다. 날짜가 바뀌면 새로 시작한다. 부르기 **전에** 먼저 기록한다 — 조회 도중 멈춰도 그 날짜는 오늘 부른 것으로
남는다. 기록을 못 쓰면 부르지 않는다. 오늘 쓴 ledger 를 읽지 못하면 오늘 무엇을
불렀는지 모르므로 부르지 않는다(지난날 파일이면 새로 시작한다).
"""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from app import trading_day_lag
from app.market_briefing import krx_store
from app.market_briefing import krx_target_checks as checks
from app.market_data_store import DEFAULT_DB_PATH

_KST = timezone(timedelta(hours=9))

# POC3-02D-OPS-04 항목 5(PLAN §2-5) — 보강은 09:20 정기 회차만. cron 09:20 줄과 수동
# `--krx-only` 는 같은 명령이라 시작 시각으로 가른다: 이 창 밖(08:40 · 10:05 등)의 수동
# 실행은 보강하지 않는다. T-1 을 이미 받은 날은 보강 기회도 남는다 — 못 받은 날 목표일을
# 조회한 수동 실행은 하루 1회 가드(OPS-03 확정 계약 7)로 09:20 회차를 막는다(알려진 한계).
REINFORCEMENT_WINDOW = (time(9, 20), time(9, 30))

LEDGER_NAME = "krx_backfill_ledger.json"

STOP_DEADLINE = "deadline"
STOP_FETCH_ERROR = "fetch_error"
STOP_LEDGER_UNREADABLE = "ledger_unreadable"


def _as_kst(dt: datetime) -> datetime:
    return dt.replace(tzinfo=_KST) if dt.tzinfo is None else dt.astimezone(_KST)


def ledger_path_for(db_path: Optional[Path]) -> Path:
    """KRX 표와 같은 폴더(운영 = `state/market/krx_backfill_ledger.json`)."""
    return Path(db_path or DEFAULT_DB_PATH).parent / LEDGER_NAME


def _bas(iso: str) -> str:
    return iso.replace("-", "")


def read_ledger_today(
    path: Path, today_iso: str
) -> Optional[tuple[dict[str, int], set[str]]]:
    """오늘 `(날짜별 호출 횟수, 보강 대상 날짜)`. 다른 날 기록이면 빈 값.

    오늘 쓴 파일을 못 읽으면 `None`(오늘 무엇을 불렀는지 모른다). `retryable` 이 없는
    옛 형식 · 깨진 `retryable` 은 보강 대상 없음으로 읽는다(보수적).
    """
    if not path.exists():
        return {}, set()
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
        if d.get("date_kst") != today_iso:
            return {}, set()
        calls = {str(k): int(v) for k, v in (d.get("calls") or {}).items()}
    except (OSError, ValueError, TypeError, AttributeError):
        try:
            mtime = datetime.fromtimestamp(path.stat().st_mtime, _KST)
        except OSError:
            return None
        return None if mtime.date().isoformat() == today_iso else ({}, set())
    raw = d.get("retryable")
    retryable = (
        {str(x) for x in raw if isinstance(x, str)} if isinstance(raw, list) else set()
    )
    return calls, retryable


def _write_calls(
    path: Path,
    today_iso: str,
    calls: dict[str, int],
    retryable: Optional[set[str]] = None,
) -> None:
    """원자적 저장(임시 파일 → `os.replace`). 실패하면 예외를 올린다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {"date_kst": today_iso, "calls": calls}
    if retryable:
        payload["retryable"] = sorted(retryable)
    fd, tmp = tempfile.mkstemp(
        dir=str(path.parent), prefix=path.name + ".", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=1, sort_keys=True)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def write_ledger(
    path: Path,
    today_iso: str,
    calls: dict[str, int],
    retryable: Optional[set[str]] = None,
) -> None:
    """ledger 저장(원자적). 다른 ledger 파일(예: 개별주 · POC3-02D-OPS-04)도 같은 규칙으로 쓴다."""
    _write_calls(path, today_iso, calls, retryable)


def in_reinforcement_window(now: datetime) -> bool:
    """`now`(KST 로 바꿔 본다)가 09:20 회차 창(09:20:00 이상 09:30:00 미만)인가."""
    t = _as_kst(now).time()
    start, end = REINFORCEMENT_WINDOW
    return start <= t < end


def call_allowed(
    day: str, calls: dict[str, int], retryable: set[str], *, reinforcement: bool
) -> bool:
    """오늘 `day` 를 부를 수 있는가 — 처음이거나, 09:20 보강의 일시 오류 날짜 1회."""
    n = calls.get(day, 0)
    if n == 0:
        return True
    return n == 1 and reinforcement and day in retryable


def fill_missing(
    target_iso: str,
    *,
    today: date,
    key: str,
    fetch: Callable[[str, str], list[dict[str, Any]]],
    db_path: Optional[Path],
    calendar_dir: Optional[Path],
    now: Callable[[], datetime],
    deadline: Optional[datetime],
    ledger_path: Path,
    reinforcement: bool = False,
) -> dict[str, Any]:
    """창(21거래일) 안 빠진 날을 **오늘 아직 부르지 않은 날만** 1회 받는다.

    `reinforcement=True`(09:20 회차 창에 시작한 `run_krx_only` 만)이면 첫 호출이 일시 오류였던 날짜를
    한 번 더 부른다. 조회 오류가 나면 멈춘다(원천 장애 · 시도당 timeout 이 쌓이지
    않게). 예외를 올리지 않는다.
    """
    days = trading_day_lag.trading_days_ending(
        target_iso, krx_store.REQUIRED_TRADING_DAYS, calendar_dir=calendar_dir
    )
    rec: dict[str, Any] = {
        "missing_before": [],
        "called": [],
        "retried": [],
        "skipped_called_today": [],
        "filled": [],
        "failed": [],
        "stopped": None,
    }
    try:
        stored = set(krx_store.stored_trading_days(db_path=db_path))
    except sqlite3.Error as e:
        rec["stopped"] = f"store_error:{type(e).__name__}"
        return rec
    missing = [d for d in days if d != target_iso and d not in stored]
    rec["missing_before"] = missing
    if not missing:
        return rec
    today_iso = today.isoformat()
    got = read_ledger_today(ledger_path, today_iso)
    if got is None:
        rec["stopped"] = STOP_LEDGER_UNREADABLE
        return rec
    calls, retryable = got
    for d in missing:
        if not call_allowed(d, calls, retryable, reinforcement=reinforcement):
            # 설계자 RESULT STEP 6 — 같은 날짜를 하루에 다시 부르지 않는다
            # (09:20 보강의 일시 오류 날짜 1회만 예외 · OPS-04 Q6 b).
            rec["skipped_called_today"].append(d)
            continue
        at = _as_kst(now())
        if deadline is not None and at >= deadline:
            rec["stopped"] = STOP_DEADLINE
            break
        prev = calls.get(d, 0)
        calls[d] = prev + 1
        retryable.discard(d)  # 보강 기회는 부르기 전에 쓴다
        try:
            _write_calls(ledger_path, today_iso, calls, retryable)
        except OSError as e:
            # 앞 기록으로 되돌린다(지우면 첫 호출 기록까지 사라져 하루 3회가 열린다).
            if prev:
                calls[d] = prev
                retryable.add(d)
            else:
                calls.pop(d, None)
            rec["stopped"] = f"ledger_error:{type(e).__name__}"
            break
        rec["called"].append(d)
        if prev:
            rec["retried"].append(d)
        entry, _rows = checks.attempt_once(
            _bas(d), key=key, fetch=fetch, db_path=db_path, at=at
        )
        if entry["result"] == checks.R_OK:
            rec["filled"].append(d)
            continue
        transient = entry.get("transient") is True
        rec["failed"].append(
            {
                "date": d,
                "result": entry["result"],
                "error_type": entry["error_type"],
                "http": entry.get("http"),
                "transient": transient,
            }
        )
        if transient and not reinforcement and not prev:
            # 08:10 등 첫 호출의 일시 오류 — 09:20 보강 대상으로 남긴다. 못 쓰면 보강
            # 없음 쪽으로 둔다(예외를 올리지 않는다).
            retryable.add(d)
            try:
                _write_calls(ledger_path, today_iso, calls, retryable)
            except OSError as e:
                retryable.discard(d)
                rec["retryable_write_error"] = type(e).__name__
        if entry["result"] == checks.R_FETCH_ERROR:
            rec["stopped"] = STOP_FETCH_ERROR
            break
    rec["calls_today"] = {d: calls[d] for d in days if d in calls}
    return rec


__all__ = [
    "LEDGER_NAME",
    "STOP_DEADLINE",
    "STOP_FETCH_ERROR",
    "REINFORCEMENT_WINDOW",
    "STOP_LEDGER_UNREADABLE",
    "call_allowed",
    "fill_missing",
    "in_reinforcement_window",
    "ledger_path_for",
    "read_ledger_today",
    "write_ledger",
]
