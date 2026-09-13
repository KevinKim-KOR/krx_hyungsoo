"""POC3-OPS-02B-2 — 국내 거래일 Gate.

**2026-09-13 사용자 운영정책으로 판정 방식이 바뀌었다.** 이전 §M-5 의
"캘린더 없으면 fail-closed" 는 폐기됐다.

## 판정 우선순위 (사용자 확정)

1. 해당 연도의 거래일 snapshot 이 있으면 **그것을 쓴다** — 목록에 없으면 휴장.
2. snapshot 이 없거나 그 연도를 덮지 않으면 **평일 fallback**:
   - 토·일 → 미발송
   - 월~금 → **거래일로 간주**하고 나머지 Gate 를 계속 평가한다.

즉 2027년 CSV 가 없어도 평일이면 브리핑을 막지 않는다.

## 이것은 허용된 운영 오차다

확인하지 못한 임시공휴일·거래소 특별휴장일에 푸시가 가는 것은 **1인 운영체계에서
사용자가 수용한 오차**이며 시스템 결함으로 분류하지 않는다(연 2~3회 수준).

**여전히 결함인 것** — 주말 발송 · 정상 snapshot 과 반대 판정 · 캘린더 판단 중
예외로 러너 중단.

## 하지 않는 것

- 공휴일 라이브러리·외부 API·신규 의존성 추가
- 매년 공식 거래일 확보를 활성화 선행조건으로 만들기
- snapshot 이 있는데 평일 fallback 으로 덮어쓰기
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date as _date
from pathlib import Path
from typing import Optional

REASON_NON_TRADING_DAY = "non_trading_day"
# 캘린더 부재는 더 이상 차단 사유가 아니다(2026-09-13 사용자 정책). 상수는
# 진단·이력 호환을 위해 남긴다 — 판정 결과로는 쓰지 않는다.
REASON_CALENDAR_REFRESH_REQUIRED = "KRX_CALENDAR_REFRESH_REQUIRED"

SOURCE_SNAPSHOT = "snapshot"
SOURCE_WEEKDAY_FALLBACK = "weekday_fallback"

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
    # 무엇으로 판정했나. 평일 fallback 은 내부 진단으로만 남기고 본문에 쓰지 않는다.
    decided_by: str = SOURCE_SNAPSHOT

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "reason": self.reason,
            "date_kst": self.date_kst,
            "source_path": self.source_path,
            "covered_years": list(self.covered_years),
            "rows": self.rows,
            "decided_by": self.decided_by,
        }


@dataclass(frozen=True)
class TradingCalendar:
    """versioned 거래일 snapshot."""

    days: frozenset[str]
    source_path: str
    rows: int
    # 형식이 맞지 않아 버린 행 수. 조용히 줄어드는 것을 보이게 남긴다.
    dropped_rows: int = 0

    @property
    def covered_years(self) -> tuple[int, ...]:
        """수록된 연도.

        `load_calendar` 가 **형식이 맞는 행만** 싣기 때문에 여기서 다시 검사하지
        않는다. 예전에는 `int(d[:4])` 를 그냥 실행해 `not-a-date` 한 줄이
        `ValueError` 로 러너를 멈췄고(r1), 앞 4자리만 검사하자 이번에는
        `20260918` 같은 손상 행이 그 해를 덮는 것으로 오인됐다(r2).
        """
        return tuple(sorted({int(d[:4]) for d in self.days}))

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
    dropped = 0
    for p in paths:
        try:
            rows = list(csv.DictReader(p.read_text(encoding="utf-8").splitlines()))
        except (OSError, UnicodeDecodeError, csv.Error):
            return None
        if not rows or "date" not in rows[0]:
            return None
        for r in rows:
            d = (r.get("date") or "").strip()
            # **형식이 맞는 행만 싣는다.** 예전에는 앞 4자리만 숫자면 그 연도를
            # 덮는 것으로 쳐서, `20260918` 한 줄짜리 손상 파일이 그 해 평일을
            # 전부 `non_trading_day` 로 막았다(검증자 r2 실측 2026-09-13).
            if d and parse_date(d) is not None:
                days.add(d)
            elif d:
                dropped += 1
        used.append(str(p))
    if not days:
        # 유효한 행이 하나도 없다 = snapshot 이 없는 것과 같다 → 평일 fallback.
        return None
    return TradingCalendar(
        days=frozenset(days),
        source_path=",".join(used),
        rows=len(days),
        dropped_rows=dropped,
    )


REASON_INVALID_DATE = "invalid_date_kst"


def parse_date(date_kst: str) -> Optional[_date]:
    """**`YYYY-MM-DD` 형식만** 읽는다. 아니면 `None`.

    `fromisoformat` 은 Python 3.11+ 에서 `YYYYMMDD` 도 받는다. 그런데 snapshot
    경로는 `date_kst in cal.days` 로 **문자열 비교**를 하므로 같은 날짜가 형식에
    따라 다르게 판정된다. 두 경로가 갈리지 않게 형식을 고정한다.
    """
    text = date_kst or ""
    # **자르지 않는다.** 예전에는 `[:10]` 으로 잘라 `2026-09-18junk` ·
    # `2026-09-18T09:00:00` 이 통과했고, snapshot 경로(문자열 비교)와 판정이
    # 갈렸다(검증자 r2 실측 2026-09-13).
    if len(text) != 10 or text[4] != "-" or text[7] != "-":
        return None
    try:
        return _date.fromisoformat(text)
    except (ValueError, TypeError):
        return None


def is_weekend(date_kst: str) -> bool:
    """토·일인가. 주말 휴장은 규칙이 아니라 정의다(KRX 는 토·일에 거래하지 않는다).

    **읽을 수 없는 날짜는 `False` 를 돌려주지만, 그것을 "평일" 로 해석하면 안 된다**
    — 호출부는 `parse_date()` 로 먼저 판별한다.
    """
    d = parse_date(date_kst)
    return d.weekday() >= 5 if d else False


def _fallback_verdict(date_kst: str, cal: Optional[TradingCalendar]) -> CalendarVerdict:
    """snapshot 이 없거나 그 연도를 안 덮을 때. **평일이면 통과시킨다.**

    단 **읽을 수 없는 실행일은 통과시키지 않는다.** 평일인지 주말인지 모르는데
    "평일이니 거래일" 로 넘기면 주말 발송을 막는 계약이 무력화된다(검증자 실측
    2026-09-13). 모르면 보내지 않는다 — 예외는 올리지 않는다.
    """
    if parse_date(date_kst) is None:
        return CalendarVerdict(
            ok=False,
            reason=REASON_INVALID_DATE,
            date_kst=date_kst,
            source_path=cal.source_path if cal else None,
            covered_years=cal.covered_years if cal else (),
            rows=cal.rows if cal else 0,
            decided_by=SOURCE_WEEKDAY_FALLBACK,
        )
    weekend = is_weekend(date_kst)
    return CalendarVerdict(
        ok=not weekend,
        reason=REASON_NON_TRADING_DAY if weekend else None,
        date_kst=date_kst,
        source_path=cal.source_path if cal else None,
        covered_years=cal.covered_years if cal else (),
        rows=cal.rows if cal else 0,
        decided_by=SOURCE_WEEKDAY_FALLBACK,
    )


def check_trading_day(
    date_kst: str, *, directory: Optional[Path] = None
) -> CalendarVerdict:
    """`date_kst` 가 거래일인지 판정한다.

    | 상황 | ok | reason | decided_by |
    |---|---|---|---|
    | snapshot 있음 · 목록에 있음 | O | `None` | `snapshot` |
    | snapshot 있음 · 목록에 없음 | X | `non_trading_day` | `snapshot` |
    | snapshot 없음·손상·연도 미지원 · **평일** | **O** | `None` | `weekday_fallback` |
    | snapshot 없음·손상·연도 미지원 · 주말 | X | `non_trading_day` | `weekday_fallback` |

    **예외를 올리지 않는다** — 캘린더 판단으로 러너가 멈추면 안 된다.
    """
    try:
        cal = load_calendar(directory)
    except Exception:  # noqa: BLE001
        cal = None
    if cal is None:
        return _fallback_verdict(date_kst, None)
    parsed = parse_date(date_kst)
    if parsed is None:
        return _fallback_verdict(date_kst, cal)
    if not cal.covers(parsed.year):
        return _fallback_verdict(date_kst, cal)
    ok = date_kst in cal.days
    return CalendarVerdict(
        ok=ok,
        reason=None if ok else REASON_NON_TRADING_DAY,
        date_kst=date_kst,
        source_path=cal.source_path,
        covered_years=cal.covered_years,
        rows=cal.rows,
        decided_by=SOURCE_SNAPSHOT,
    )


__all__ = [
    "CALENDAR_DIR",
    "CALENDAR_GLOB",
    "CalendarVerdict",
    "REASON_CALENDAR_REFRESH_REQUIRED",
    "REASON_INVALID_DATE",
    "REASON_NON_TRADING_DAY",
    "SOURCE_SNAPSHOT",
    "SOURCE_WEEKDAY_FALLBACK",
    "TradingCalendar",
    "check_trading_day",
    "is_weekend",
    "parse_date",
    "load_calendar",
]
