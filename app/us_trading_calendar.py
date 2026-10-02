"""POC3-02D-OPS-03 — 미국(NYSE) 완료 세션 · 거래일 달력 준비 상태.

확정 계약 11(설계자 판정 STEP 9) — S&P500 정상 = **가장 최근 완료 미국 세션**. 달력
날짜가 아니라 세션으로 본다. 정본은 NYSE 공식 휴장일 공지다.

## 휴장일 파일

`state/market_meta/nyse_holidays_YYYY.csv` — 연도별 versioned CSV. 머리 주석(`#`)에
출처 URL · 받은 시각 · sha256 을 둔다. 열은 `date,kind,name,close_et` 이고 `kind` 는
`holiday`(휴장) · `early_close`(조기 폐장 · `close_et` 뉴욕 시각). 새 의존성 0 —
시간대는 표준 라이브러리 `zoneinfo` 다.

| 상황 | 세션 판정 |
|---|---|
| 그해 파일 있음 | 평일에서 휴장일을 뺀다 · 조기 폐장일은 그 시각에 마감 |
| 그해 파일 없음 · 손상 | **평일 fallback** — 휴장일도 세션으로 본다 |

평일 fallback 은 보수적이다. 휴장 다음 날 기대 세션이 휴장일로 잡혀 전망이 빠질 뿐,
오래된 값을 최신으로 보지 않는다. 손상 파일은 그해를 덮지 않는다(한 줄이라도 틀리면
그 파일 전체를 쓰지 않는다).

## 기대 세션

실행 시각을 뉴욕 시각으로 바꿔 **그날 세션이 마감(16:00 · 조기 폐장일은 그 시각)
뒤면 그날**, 아니면 전날부터 거슬러 첫 세션. 08:30 KST 는 늘 전날 뉴욕 장 마감 뒤다
(서머타임 19:30 · 표준시 18:30).

## 달력 준비 상태(readiness)

한국(`krx_trading_days_YYYY.csv`) · 미국(`nyse_holidays_YYYY.csv`) 올해 · 다음 해
파일이 있는가(확정 계약 11 — 사람의 기억에 맡기지 않고 기록한다).

| 조건 | 상태 |
|---|---|
| 올해 파일 없음 | `warn` (언제든) |
| 다음 해 파일 없음 · 12월 | `warn` |
| 다음 해 파일 없음 · 11월 | `due` — 11-30 까지 점검(안내) |
| 그 밖 | `ok` |
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

from app.market_briefing.calendar import CALENDAR_DIR, parse_date

NYSE_GLOB = "nyse_holidays_*.csv"
_NYSE_NAME = re.compile(r"^nyse_holidays_(\d{4})\.csv$")
NY_TZ = "America/New_York"
REGULAR_CLOSE = time(16, 0)
KIND_HOLIDAY = "holiday"
KIND_EARLY_CLOSE = "early_close"
HEADER = ("date", "kind", "name", "close_et")

DECIDED_BY_FILE = "nyse_file"
DECIDED_BY_WEEKDAY = "weekday_fallback"

_KST = timezone(timedelta(hours=9))
# 거슬러 올라가는 달력일 상한. 연휴가 길어도 넉넉하다.
_WALK_LIMIT_DAYS = 30


@dataclass(frozen=True)
class NyseYear:
    """한 해 휴장 · 조기 폐장. 파일 하나에서 온다."""

    year: int
    holidays: frozenset[str]
    early_closes: tuple[tuple[str, time], ...]
    source_path: str


@dataclass(frozen=True)
class NyseCalendar:
    """읽은 연도들. 없는 해는 평일 fallback."""

    years: dict[int, NyseYear] = field(default_factory=dict)

    def covers(self, year: int) -> bool:
        return year in self.years

    def is_session(self, d: date) -> bool:
        if d.weekday() >= 5:
            return False
        y = self.years.get(d.year)
        return y is None or d.isoformat() not in y.holidays

    def close_time(self, d: date) -> time:
        y = self.years.get(d.year)
        if y is not None:
            for iso, t in y.early_closes:
                if iso == d.isoformat():
                    return t
        return REGULAR_CLOSE

    def decided_by(self, d: date) -> str:
        return DECIDED_BY_FILE if self.covers(d.year) else DECIDED_BY_WEEKDAY


def _parse_close(text: str) -> Optional[time]:
    try:
        hh, mm = text.strip().split(":")
        return time(int(hh), int(mm))
    except (ValueError, TypeError):
        return None


def parse_year_file(path: Path) -> Optional[NyseYear]:
    """파일 하나를 읽는다. 이름 · 머리 · 어느 한 줄이라도 틀리면 `None`."""
    m = _NYSE_NAME.match(path.name)
    if not m:
        return None
    year = int(m.group(1))
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    lines = [ln for ln in text.splitlines() if ln.strip() and not ln.startswith("#")]
    try:
        rows = list(csv.reader(lines))
    except csv.Error:
        return None
    if not rows or tuple(c.strip() for c in rows[0]) != HEADER:
        return None
    holidays: set[str] = set()
    early: list[tuple[str, time]] = []
    for r in rows[1:]:
        if len(r) != len(HEADER):
            return None
        d = parse_date(r[0].strip())
        kind = r[1].strip()
        if d is None or d.year != year or d.weekday() >= 5:
            return None
        if kind == KIND_HOLIDAY:
            holidays.add(d.isoformat())
        elif kind == KIND_EARLY_CLOSE:
            t = _parse_close(r[3])
            if t is None:
                return None
            early.append((d.isoformat(), t))
        else:
            return None
    if not holidays:
        # 휴장일이 하나도 없는 해는 없다 — 빈 파일은 그해를 덮지 않는다.
        return None
    return NyseYear(
        year=year,
        holidays=frozenset(holidays),
        early_closes=tuple(sorted(early)),
        source_path=str(path),
    )


def load_nyse_calendar(directory: Optional[Path] = None) -> NyseCalendar:
    """폴더의 연도 파일을 모두 읽는다. **예외를 올리지 않는다**(없으면 빈 달력)."""
    base = directory or CALENDAR_DIR
    years: dict[int, NyseYear] = {}
    try:
        paths = sorted(base.glob(NYSE_GLOB)) if base.exists() else []
    except OSError:
        paths = []
    for p in paths:
        y = parse_year_file(p)
        if y is not None:
            years[y.year] = y
    return NyseCalendar(years=years)


def _ny_zone():
    """뉴욕 시간대. 시스템에 시간대 자료가 없으면 `None`(호출부가 stale 로 본다)."""
    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo(NY_TZ)
    except Exception:  # noqa: BLE001 - ImportError · ZoneInfoNotFoundError
        return None


def expected_completed_session(
    now: datetime,
    *,
    calendar_dir: Optional[Path] = None,
    cal: Optional[NyseCalendar] = None,
) -> Optional[str]:
    """`now` 시점에 **가장 최근 완료된** NYSE 세션(뉴욕 날짜 `YYYY-MM-DD`).

    시각대가 없는 `now` 는 KST 로 본다. 시간대 자료가 없으면 `None`.
    """
    tz = _ny_zone()
    if tz is None:
        return None
    if now.tzinfo is None:
        now = now.replace(tzinfo=_KST)
    cal = cal or load_nyse_calendar(calendar_dir)
    et = now.astimezone(tz)
    d = et.date()
    if cal.is_session(d) and et.time() >= cal.close_time(d):
        return d.isoformat()
    for i in range(1, _WALK_LIMIT_DAYS + 1):
        prev = d - timedelta(days=i)
        if cal.is_session(prev):
            return prev.isoformat()
    return None


def previous_session(
    session: str,
    *,
    calendar_dir: Optional[Path] = None,
    cal: Optional[NyseCalendar] = None,
) -> Optional[str]:
    """`session` 바로 앞 NYSE 세션. 읽을 수 없는 날짜면 `None`."""
    d = parse_date(session)
    if d is None:
        return None
    cal = cal or load_nyse_calendar(calendar_dir)
    for i in range(1, _WALK_LIMIT_DAYS + 1):
        prev = d - timedelta(days=i)
        if cal.is_session(prev):
            return prev.isoformat()
    return None


def session_check(
    last_session: Optional[str],
    prev_session: Optional[str],
    *,
    now: datetime,
    calendar_dir: Optional[Path] = None,
) -> dict[str, Any]:
    """S&P500 저장 계열의 마지막 두 세션을 기대 세션과 대조한다.

    `fresh` 조건 — 마지막 세션 == 기대 세션 **그리고** 그 앞 행 == 바로 앞 세션.
    1일 수익률이 두 세션을 건너뛰면 '직전 미국 거래일' 문장이 틀린다(확정 계약 5 와
    같은 이유 — 행 위치가 아니라 세션 날짜로 본다).
    """
    cal = load_nyse_calendar(calendar_dir)
    expected = expected_completed_session(now, cal=cal)
    out: dict[str, Any] = {
        "expected_session": expected,
        "last_session": last_session,
        "prev_session": prev_session,
        "expected_previous_session": None,
        "decided_by": None,
        "fresh": False,
        "reason": None,
    }
    if expected is None:
        out["reason"] = "expected_session_unknown"
        return out
    out["decided_by"] = cal.decided_by(date.fromisoformat(expected))
    if last_session != expected:
        out["reason"] = "last_session_not_expected"
        return out
    want_prev = previous_session(expected, cal=cal)
    out["expected_previous_session"] = want_prev
    if prev_session is None or prev_session != want_prev:
        out["reason"] = "previous_session_mismatch"
        return out
    out["fresh"] = True
    out["reason"] = "ok"
    return out


# ── 거래일 달력 준비 상태 (확정 계약 11 · 미국만) ─────────────────────────────
# 한국 거래일은 연도 파일이 보조자료다 — 없으면 평일 기본으로 운영하고 경고하지 않는다
# (2026-09-11 사용자 확정 · 설계자 2026-10-02 복원 · `app.market_briefing.calendar`).

READY_OK = "ok"
READY_DUE = "due"
READY_WARN = "warn"
READY_UNKNOWN = "unknown"
CHECK_FROM_MONTH = 11
WARN_FROM_MONTH = 12
MARKETS = ("NYSE",)
_FILE_PREFIX = {"KRX": "krx_trading_days_", "NYSE": "nyse_holidays_"}


def calendar_file_name(market: str, year: int) -> str:
    return f"{_FILE_PREFIX[market]}{year}.csv"


def calendar_readiness(
    today: date, present: Callable[[str, int], bool], *, basis: str
) -> dict[str, Any]:
    """올해 · 다음 해 달력 파일 준비 상태. `present(market, year)` 로 있는지 묻는다."""
    cur, nxt = today.year, today.year + 1
    missing_current = [m for m in MARKETS if not present(m, cur)]
    missing_next = [m for m in MARKETS if not present(m, nxt)]
    if missing_current:
        state = READY_WARN
    elif missing_next and today.month >= WARN_FROM_MONTH:
        state = READY_WARN
    elif missing_next and today.month >= CHECK_FROM_MONTH:
        state = READY_DUE
    else:
        state = READY_OK
    return {
        "checked_date": today.isoformat(),
        "state": state,
        "basis": basis,
        "current_year": cur,
        "next_year": nxt,
        "missing_current": missing_current,
        "missing_next": missing_next,
    }


def calendar_readiness_for_names(today: date, names: Iterable[str]) -> dict[str, Any]:
    """파일 **이름 목록**만으로(PC 가 OCI 폴더 목록을 읽을 때)."""
    have = set(names)
    return calendar_readiness(
        today,
        lambda m, y: calendar_file_name(m, y) in have,
        basis="file_name",
    )


def calendar_readiness_for_dir(
    today: date, directory: Optional[Path] = None
) -> dict[str, Any]:
    """폴더의 파일을 **읽어서**(배치 · 미국만). 손상 파일은 없는 것으로 본다. 예외를
    올리지 않는다."""
    nyse = load_nyse_calendar(directory or CALENDAR_DIR)
    return calendar_readiness(
        today, lambda _market, year: nyse.covers(year), basis="file_content"
    )


__all__ = [
    "CHECK_FROM_MONTH",
    "DECIDED_BY_FILE",
    "DECIDED_BY_WEEKDAY",
    "KIND_EARLY_CLOSE",
    "KIND_HOLIDAY",
    "MARKETS",
    "NYSE_GLOB",
    "NY_TZ",
    "NyseCalendar",
    "NyseYear",
    "READY_DUE",
    "READY_OK",
    "READY_UNKNOWN",
    "READY_WARN",
    "REGULAR_CLOSE",
    "WARN_FROM_MONTH",
    "calendar_file_name",
    "calendar_readiness",
    "calendar_readiness_for_dir",
    "calendar_readiness_for_names",
    "expected_completed_session",
    "load_nyse_calendar",
    "parse_year_file",
    "previous_session",
    "session_check",
]
