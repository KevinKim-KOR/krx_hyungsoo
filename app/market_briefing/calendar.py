"""POC3-OPS-02B-2 — 국내 거래일 Gate.

설계자 §M-5 확정. **구현은 진행하고 활성화만 차단**한다.

```text
ACTIVATION_BLOCKED = true
BLOCK_REASON       = KRX_TRADING_CALENDAR_NOT_PROVIDED
```

**왜 필요한가** — 한국 휴장 중 미국시장이 추가로 열리면, 확인한 S&P500 방향이
**실제 다음 한국 개장 직전의 방향이 아니다.** `SP500_SIGN_V1` 검증 조건과
달라지므로 문구만 바꿔 우회할 수 없다.

**하지 않는 것**

- 공휴일 라이브러리·미국시장 일정·주말 규칙으로 **대체하지 않는다**
- 런타임 다운로드·브라우저 자동화 **없음**
- 2026년 자료를 **추정값·빈 placeholder 로 만들지 않는다**

실제 공식 snapshot 은 **사용자 승인·제공 후 별도 반영**한다. 그전까지 이 Gate 는
`KRX_CALENDAR_REFRESH_REQUIRED` 로 fail-closed 되고, **autosend 가 켜져 있어도
발송이 0건**이 된다.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

REASON_NON_TRADING_DAY = "non_trading_day"
REASON_CALENDAR_REFRESH_REQUIRED = "KRX_CALENDAR_REFRESH_REQUIRED"

# versioned snapshot 기본 경로. 사용자가 공식 자료를 제공하면 여기에 둔다.
CALENDAR_DIR = Path("state/market_meta")
CALENDAR_GLOB = "krx_trading_days_*.csv"


@dataclass(frozen=True)
class CalendarVerdict:
    """거래일 Gate 결과."""

    ok: bool
    reason: Optional[str]
    date_kst: str
    source_path: Optional[str] = None
    covered_years: tuple[int, ...] = ()
    rows: int = 0

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "reason": self.reason,
            "date_kst": self.date_kst,
            "source_path": self.source_path,
            "covered_years": list(self.covered_years),
            "rows": self.rows,
        }


@dataclass(frozen=True)
class TradingCalendar:
    """versioned 거래일 snapshot."""

    days: frozenset[str]
    source_path: str
    rows: int

    @property
    def covered_years(self) -> tuple[int, ...]:
        return tuple(sorted({int(d[:4]) for d in self.days if len(d) >= 4}))

    def covers(self, year: int) -> bool:
        return year in self.covered_years


def load_calendar(directory: Optional[Path] = None) -> Optional[TradingCalendar]:
    """공식 거래일 snapshot 을 읽는다. 없거나 깨졌으면 `None`.

    파일 형식은 `date` 컬럼 1개짜리 CSV (`YYYY-MM-DD`). 여러 파일이 있으면
    **전부 합친다** — 연도별 파일을 나눠 받을 수 있기 때문이다.
    """
    base = directory or CALENDAR_DIR
    if not base.exists():
        return None
    paths = sorted(base.glob(CALENDAR_GLOB))
    if not paths:
        return None
    days: set[str] = set()
    used: list[str] = []
    for p in paths:
        try:
            rows = list(csv.DictReader(p.read_text(encoding="utf-8").splitlines()))
        except (OSError, UnicodeDecodeError, csv.Error):
            return None
        if not rows or "date" not in rows[0]:
            return None
        for r in rows:
            d = (r.get("date") or "").strip()
            if d:
                days.add(d)
        used.append(str(p))
    if not days:
        return None
    return TradingCalendar(
        days=frozenset(days), source_path=",".join(used), rows=len(days)
    )


def check_trading_day(
    date_kst: str, *, directory: Optional[Path] = None
) -> CalendarVerdict:
    """`date_kst` 가 **실제 KRX 거래일**인지 판정한다.

    | 상황 | reason |
    |---|---|
    | 거래일 | `None` (통과) |
    | 휴장일 | `non_trading_day` |
    | 파일 없음·손상 | `KRX_CALENDAR_REFRESH_REQUIRED` |
    | **해당 연도 미포함** | `KRX_CALENDAR_REFRESH_REQUIRED` |

    연도가 빠진 캘린더로 "목록에 없으니 휴장일" 이라고 판정하면 **한 해 전체가
    조용히 미발송**된다. 그래서 연도 커버리지를 먼저 본다.
    """
    cal = load_calendar(directory)
    if cal is None:
        return CalendarVerdict(
            ok=False, reason=REASON_CALENDAR_REFRESH_REQUIRED, date_kst=date_kst
        )
    year = int(date_kst[:4]) if len(date_kst) >= 4 and date_kst[:4].isdigit() else 0
    if not cal.covers(year):
        return CalendarVerdict(
            ok=False,
            reason=REASON_CALENDAR_REFRESH_REQUIRED,
            date_kst=date_kst,
            source_path=cal.source_path,
            covered_years=cal.covered_years,
            rows=cal.rows,
        )
    ok = date_kst in cal.days
    return CalendarVerdict(
        ok=ok,
        reason=None if ok else REASON_NON_TRADING_DAY,
        date_kst=date_kst,
        source_path=cal.source_path,
        covered_years=cal.covered_years,
        rows=cal.rows,
    )


__all__ = [
    "CALENDAR_DIR",
    "CALENDAR_GLOB",
    "CalendarVerdict",
    "REASON_CALENDAR_REFRESH_REQUIRED",
    "REASON_NON_TRADING_DAY",
    "TradingCalendar",
    "check_trading_day",
    "load_calendar",
]
