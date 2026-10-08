"""POC5-04 — 리포트 날짜: 운영 거래일 캘린더(02 와 같은 파일 · 같은 규칙)만 쓴다.

PLAN §1-3. 가격 행 유무로 휴장일을 추정하지 않는다.

```text
캘린더      ledger_outcome_prices.Calendar(state/market_meta) — 실행당 1회 · 파일 없는 해는 평일 기본
종료일      --end 없으면 오늘(KST)보다 이전의 마지막 거래일(오늘 장중은 완료일이 아니다)
D10         시작일(원장 meta primary_start_date) 포함 10번째 거래일
평가일      02 `_mature_target` 과 같은 식 — 15:30 이전 사건은 사건일이 +1 · 이후는 다음 거래일부터
```
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from app.three_push_runtime import ledger_outcome
from app.three_push_runtime import ledger_outcome_prices as px

KST = timezone(timedelta(hours=9))
OFFICIAL_DAYS = 10


def calendar(calendar_dir: Optional[Path] = None) -> px.Calendar:
    from app.three_push_runtime import ledger_context

    return px.Calendar(
        calendar_dir if calendar_dir is not None else ledger_context.CALENDAR_DIR
    )


def today_kst() -> str:
    return datetime.now(KST).date().isoformat()


def default_end(cal: px.Calendar, today: str) -> Optional[str]:
    """오늘보다 이전의 마지막 거래일."""
    return cal.previous(today)


def trading_days(cal: px.Calendar, start: str, end: str) -> list[str]:
    """`start` ~ `end`(둘 다 포함)의 운영 거래일 — 알림 없는 날도 들어간다.

    하루씩 직접 걷는다(`Calendar.days_from` 은 120 달력일까지만 걸어 긴 기간이 잘린다)."""
    first, last = date.fromisoformat(start), date.fromisoformat(end)
    out = []
    while first <= last:
        day = first.isoformat()
        if cal.is_trading(day):
            out.append(day)
        first += timedelta(days=1)
    return out


def validate_end(cal: px.Calendar, end: str, today: str) -> str:
    """`--end` 검사 — YYYY-MM-DD · 오늘(KST)보다 이전(장중 제외) · 운영 거래일. 아니면 ValueError."""
    try:
        parsed = date.fromisoformat(end)
    except ValueError as e:
        raise ValueError("종료일 형식은 YYYY-MM-DD") from e
    if parsed.isoformat() != end:
        raise ValueError("종료일 형식은 YYYY-MM-DD")
    if end >= today:
        raise ValueError(
            "종료일은 오늘(KST)보다 이전이어야 한다(오늘 장중은 완료일이 아니다)"
        )
    if not cal.is_trading(end):
        raise ValueError("종료일이 운영 거래일이 아니다")
    return end


def official_day(cal: px.Calendar, start: str) -> Optional[str]:
    """시작일 포함 10번째 거래일(D10)."""
    got = cal.days_from(start, OFFICIAL_DAYS)
    return got[-1] if len(got) == OFFICIAL_DAYS else None


def eval_dates(
    cal: px.Calendar, signal_date: str, schedule: Optional[str]
) -> dict[int, Optional[str]]:
    """horizon → 평가일(02 와 같은 첫날 규칙). 캘린더가 모자라면 None."""
    if (schedule or "") >= ledger_outcome.CLOSE_CUTOFF:
        first = cal.next_after(signal_date)
    else:
        got = cal.days_from(signal_date, 1)
        first = got[0] if got else None
    if first is None:
        return {h: None for h in ledger_outcome.HORIZONS}
    days = cal.days_from(first, max(ledger_outcome.HORIZONS))
    return {
        h: (days[h - 1] if len(days) >= h else None) for h in ledger_outcome.HORIZONS
    }


def rows_known_by(rows: list[dict], end: str) -> list[dict]:
    """종료일까지 알 수 있는 결과 행 — 평가일이 종료일 뒤인 행은 빼고(그 슬롯은 미도래로 센다)
    평가일이 없는 행(미지원 계열 · 기준 가격 없음)은 둔다. R0 · R1 이 같은 기준을 쓴다."""
    return [r for r in rows if not r.get("eval_date") or str(r["eval_date"]) <= end]


def parse_kst(text: Optional[str]) -> Optional[datetime]:
    """ISO 시각 → aware datetime(오프셋이 없으면 KST 로 본다). 읽을 수 없으면 None."""
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.strip())
    except ValueError:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=KST)


def at_kst(day: str, hhmm: str) -> datetime:
    h, m = hhmm.split(":")
    return datetime.fromisoformat(day).replace(hour=int(h), minute=int(m), tzinfo=KST)
