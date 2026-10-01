"""POC3-02D-OPS-03 — KRX 창(21거래일) 안 빠진 날 채우기 · 하루 호출 기록(ledger).

PLAN STEP 3-3 · 설계자 RESULT STEP 6(2026-09-30):

```text
범위        목표일(T-1)로 끝나는 21거래일 창 안의 빠진 날만(목표일 자신은 제외)
하루 1회    같은 날짜는 KST 하루에 **한 번만** 부른다 — 08:10 첫 채우기 · 같은 실행의
            backfill_retry · 09:20 --krx-only · 수동 재실행을 모두 합쳐서
기록        이번 실행에서 실제로 부른 날짜(`called`) · 오늘 이미 불러 건너뛴 날짜
            (`skipped_called_today`) · 오늘 날짜별 호출 횟수(`calls_today`)
```

목표일 T-1 시각표 시도(08:10 · 08:15 · 08:20 · 08:24 · 09:20)는 채우기가 아니다 —
ledger 에 넣지 않고 시각표를 그대로 따른다.

ledger 는 KRX 표(`market_data.sqlite`)와 같은 폴더의 `krx_backfill_ledger.json`
(`{"date_kst": "YYYY-MM-DD", "calls": {"YYYY-MM-DD": n}}`)이다. 날짜가 바뀌면 새로
시작한다. 부르기 **전에** 먼저 기록한다 — 조회 도중 멈춰도 그 날짜는 오늘 부른 것으로
남는다. 기록을 못 쓰면 부르지 않는다. 오늘 쓴 ledger 를 읽지 못하면 오늘 무엇을
불렀는지 모르므로 부르지 않는다(지난날 파일이면 새로 시작한다).
"""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from app import trading_day_lag
from app.market_briefing import krx_store
from app.market_briefing import krx_target_checks as checks
from app.market_data_store import DEFAULT_DB_PATH

_KST = timezone(timedelta(hours=9))

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


def read_calls_today(path: Path, today_iso: str) -> Optional[dict[str, int]]:
    """오늘 날짜별 호출 횟수. 다른 날 기록이면 `{}`. 오늘 쓴 파일을 못 읽으면 `None`."""
    if not path.exists():
        return {}
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
        if d.get("date_kst") != today_iso:
            return {}
        return {str(k): int(v) for k, v in (d.get("calls") or {}).items()}
    except (OSError, ValueError, TypeError, AttributeError):
        try:
            mtime = datetime.fromtimestamp(path.stat().st_mtime, _KST)
        except OSError:
            return None
        return None if mtime.date().isoformat() == today_iso else {}


def _write_calls(path: Path, today_iso: str, calls: dict[str, int]) -> None:
    """원자적 저장(임시 파일 → `os.replace`). 실패하면 예외를 올린다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(
        dir=str(path.parent), prefix=path.name + ".", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(
                {"date_kst": today_iso, "calls": calls},
                fh,
                ensure_ascii=False,
                indent=1,
                sort_keys=True,
            )
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


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
) -> dict[str, Any]:
    """창(21거래일) 안 빠진 날을 **오늘 아직 부르지 않은 날만** 1회 받는다.

    조회 오류가 나면 멈춘다(원천 장애 · 시도당 timeout 이 쌓이지 않게). 예외를
    올리지 않는다.
    """
    days = trading_day_lag.trading_days_ending(
        target_iso, krx_store.REQUIRED_TRADING_DAYS, calendar_dir=calendar_dir
    )
    rec: dict[str, Any] = {
        "missing_before": [],
        "called": [],
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
    calls = read_calls_today(ledger_path, today_iso)
    if calls is None:
        rec["stopped"] = STOP_LEDGER_UNREADABLE
        return rec
    for d in missing:
        if calls.get(d, 0) >= 1:
            # 설계자 RESULT STEP 6 — 같은 날짜를 하루에 다시 부르지 않는다.
            rec["skipped_called_today"].append(d)
            continue
        at = _as_kst(now())
        if deadline is not None and at >= deadline:
            rec["stopped"] = STOP_DEADLINE
            break
        calls[d] = 1
        try:
            _write_calls(ledger_path, today_iso, calls)
        except OSError as e:
            calls.pop(d, None)
            rec["stopped"] = f"ledger_error:{type(e).__name__}"
            break
        rec["called"].append(d)
        entry, _rows = checks.attempt_once(
            _bas(d), key=key, fetch=fetch, db_path=db_path, at=at
        )
        if entry["result"] == checks.R_OK:
            rec["filled"].append(d)
            continue
        rec["failed"].append(
            {"date": d, "result": entry["result"], "error_type": entry["error_type"]}
        )
        if entry["result"] == checks.R_FETCH_ERROR:
            rec["stopped"] = STOP_FETCH_ERROR
            break
    rec["calls_today"] = {d: calls[d] for d in days if d in calls}
    return rec


__all__ = [
    "LEDGER_NAME",
    "STOP_DEADLINE",
    "STOP_FETCH_ERROR",
    "STOP_LEDGER_UNREADABLE",
    "fill_missing",
    "ledger_path_for",
    "read_calls_today",
]
