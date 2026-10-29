"""POC6-13 — 자동 실행 창 · 일정 시각 · 호출 사유 추정 · 상한(순수 함수 · 설계 §3 · PLAN §3-2).

```text
자동 창      10:00 이상 ~ 15:20 미만 KST 에만 06 예측 · 보관을 새로 시작한다(실제 마감은 06 의 close_cutoff_at)
일정         10:05 · 12:05 · 14:35 · 15:25(15:25 = 상태 점검만) + 로그인 1회
상한         하루(KST) 자동 예측 4회 · 자동 보관 4회 · 같은 종류 시도 사이 15분 · 예측 20분 · 보관 10분
사유         일정 시각 + 2분 안 = SCHEDULED, 그 밖 = CATCH_UP — 시각으로 한 **추정**(깨어남 이벤트 확인 아님)
```
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Optional

KST = timezone(timedelta(hours=9))
WINDOW_OPEN = time(10, 0)
WINDOW_CLOSE = time(15, 20)
SLOTS = (time(10, 5), time(12, 5), time(14, 35), time(15, 25))
SCHEDULE_TOLERANCE = timedelta(minutes=2)
MAX_PREDICT = 4
MAX_ARCHIVE = 4
MIN_GAP = timedelta(minutes=15)
PREDICT_TIMEOUT_S = 20 * 60
ARCHIVE_TIMEOUT_S = 10 * 60
KILL_GRACE_S = 30
BACKUP_BLOCK = (time(10, 0), time(15, 45))  # 이 사이에는 C 를 시작하지 않는다
BACKUP_LIMIT_S = 60 * 60

BEFORE, OPEN, CLOSED = "BEFORE", "OPEN", "CLOSED"


def kst(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        raise ValueError("시각에 시간대가 없다")
    return dt.astimezone(KST)


def day(dt: datetime) -> str:
    return kst(dt).date().isoformat()


def window(now: datetime) -> str:
    t = kst(now).time()
    if t < WINDOW_OPEN:
        return BEFORE
    return OPEN if t < WINDOW_CLOSE else CLOSED


def _at(d: date, t: time) -> datetime:
    return datetime.combine(d, t, KST)


def reason(now: datetime) -> str:
    """일정 시각 + 2분 안이면 SCHEDULED, 아니면 CATCH_UP(로그인 · 깨어남 · 수동) — 추정."""
    n = kst(now)
    for s in SLOTS:
        at = _at(n.date(), s)
        if at <= n <= at + SCHEDULE_TOLERANCE:
            return "SCHEDULED"
    return "CATCH_UP"


def next_slot(now: datetime) -> datetime:
    n = kst(now)
    for s in SLOTS:
        at = _at(n.date(), s)
        if at > n:
            return at
    return _at(n.date() + timedelta(days=1), SLOTS[0])


def first_slot_passed(now: datetime) -> bool:
    n = kst(now)
    return n > _at(n.date(), SLOTS[0]) + SCHEDULE_TOLERANCE


def gap_ok(now: datetime, last_start: Optional[datetime]) -> bool:
    return last_start is None or now - last_start >= MIN_GAP


def backup_allowed(now: datetime) -> bool:
    t = kst(now).time()
    return not (BACKUP_BLOCK[0] <= t < BACKUP_BLOCK[1])


def hhmm(dt: Optional[datetime]) -> str:
    return "-" if dt is None else kst(dt).strftime("%H:%M")
