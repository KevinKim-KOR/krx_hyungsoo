"""POC5-06 — 선택 ETF 저장 종가 · 연구 축 · 감지된 가격 경계(읽기 전용 · 설계 개정 2 §4 · §10-2 · §10-3).

```text
가격     PC etf_daily_price 의 네이버 계열 저장 종가(NAVER_FDR · FinanceDataReader) — 한 번의 SELECT
         (호출부가 연 mode=ro 연결 · 같은 읽기 트랜잭션). KRX 무조정 · 봉인 KRX · 원장 결과는 쓰지 않는다
연구 축   연도 파일이 있는 해 = 파일 · 없는 해 = 평일 기본 ∩ KOSPI 저장일
         (`trading_day_lag.trading_days_ending(..., stored=KOSPI 저장일)`) — 선택 ETF 의 저장일로
         축을 만들지 않는다 · 공식 휴장 목록이 아니다
경계     FinanceDataReader 행의 |change − (종가 / 직전 저장 종가 − 1)| > 1e-6(절대 비율) · 첫 행이
         아닌 FinanceDataReader 행의 change 누락 · FinanceDataReader → NAVER_FDR 재전환 · 허용 밖 출처
         · 유한한 양수가 아닌 종가 · 축 날짜의 종가 없음. NAVER_FDR → FinanceDataReader 라벨 변경
         자체는 경계가 아니다(같은 네이버 reader · change 로 연속성 확인)
```

NAVER_FDR 구간은 change 가 없어 그 안의 계단을 감지할 수 없다 — 경계 검사가 부분적이다(§10-3).
"""

from __future__ import annotations

import bisect
import hashlib
import json
import math
import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Optional

from app import trading_day_lag as tdl
from app.market_briefing import calendar as cal

PRICE_TABLE = "etf_daily_price"
MASTER_TABLE = "etf_master"
KOSPI_TABLE = "market_benchmark_daily_price"
KOSPI_ID = "KOSPI"
FDR = "FinanceDataReader"
NAVER = "NAVER_FDR"
ALLOWED_SOURCES = frozenset({FDR, NAVER})
CHANGE_TOLERANCE = 1e-6  # 절대 비율(= 0.0001%p)

PRICE_BASIS_LABEL = "저장 종가(네이버 계열 · 분배락 조정 흔적 · 총수익 여부 미확정)"
AXIS_LABEL = "공식 휴장 목록이 아닌 KOSPI 저장일 보정 연구 축"
AXIS_LIMIT_NOTE = (
    "연도 파일이 없는 해는 KOSPI 저장일만 거래일로 셉니다 — 건너뛴 평일이 모두 확인된 "
    "휴장일은 아니며, KOSPI 저장이 빠진 실제 거래일도 축에서 빠질 수 있습니다."
)
PARTIAL_CHECK_NOTE = (
    "change 가 없는 NAVER_FDR 구간은 가격 기준 변화(계단)를 감지할 수 없어 경계 검사가 "
    "부분적입니다 — 감지하지 못한 계단이 남을 수 있습니다."
)

MODE_FILE = "FILE"
MODE_KOSPI = "KOSPI_CORRECTED"

# 창 제외 사유(우선순위 순서)
MISSING_PRICE = "MISSING_PRICE"
SOURCE_NOT_ALLOWED = "SOURCE_NOT_ALLOWED"
BAD_CLOSE = "BAD_CLOSE"
CHANGE_MISSING = "CHANGE_MISSING"
SOURCE_RESWITCH = "SOURCE_RESWITCH"
BASIS_BREAK = "BASIS_BREAK"
REASON_ORDER = (
    MISSING_PRICE,
    SOURCE_NOT_ALLOWED,
    BAD_CLOSE,
    CHANGE_MISSING,
    SOURCE_RESWITCH,
    BASIS_BREAK,
)
REASON_TEXT = {
    MISSING_PRICE: "연구 축 날짜의 저장 종가 없음",
    SOURCE_NOT_ALLOWED: "허용 밖 가격 출처",
    BAD_CLOSE: "유한한 양수가 아닌 종가",
    CHANGE_MISSING: "change 누락으로 연속성 확인 불가",
    SOURCE_RESWITCH: "FinanceDataReader → NAVER_FDR 재전환",
    BASIS_BREAK: "저장 change 와 종가 변화 불일치(가격 기준 변화)",
}


@dataclass(frozen=True)
class PriceRow:
    date: str
    close: Any
    source: Optional[str]
    fetched_at: Optional[str]
    change: Any

    def as_json(self) -> dict[str, Any]:
        return {
            "date": self.date,
            "close": self.close,
            "source": self.source,
            "fetched_at": self.fetched_at,
            "change": self.change,
        }


def _has_table(con: sqlite3.Connection, name: str) -> bool:
    row = con.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)
    ).fetchone()
    return row is not None


def is_etf(con: sqlite3.Connection, ticker: str) -> Optional[bool]:
    """etf_master 에 있으면 True · 없으면 False · 표가 없으면 None(확인 불가)."""
    if not _has_table(con, MASTER_TABLE):
        return None
    row = con.execute(
        f"SELECT 1 FROM {MASTER_TABLE} WHERE ticker = ? LIMIT 1", (ticker,)
    ).fetchone()
    return row is not None


def read_rows(con: sqlite3.Connection, ticker: str) -> list[PriceRow]:
    """선택 ETF 의 저장 행 전체(날짜순). 표가 없으면 []."""
    if not _has_table(con, PRICE_TABLE):
        return []
    return [
        PriceRow(*r)
        for r in con.execute(
            f"SELECT date, close, source, fetched_at, change FROM {PRICE_TABLE}"
            " WHERE ticker = ? ORDER BY date",
            (ticker,),
        )
    ]


def read_kospi_dates(con: sqlite3.Connection) -> list[str]:
    """KOSPI 저장일(close > 0) — 연구 축의 보정 근거."""
    if not _has_table(con, KOSPI_TABLE):
        return []
    return [
        d
        for (d,) in con.execute(
            f"SELECT date FROM {KOSPI_TABLE} WHERE benchmark_id = ?"
            " AND close IS NOT NULL AND close > 0 ORDER BY date",
            (KOSPI_ID,),
        )
    ]


def _valid_close(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
        and float(value) > 0
    )


def research_axis(
    t: str,
    first: str,
    kospi_dates: list[str],
    *,
    calendar_dir: Optional[Path] = None,
) -> dict[str, Any]:
    """[first, t] 연구 축 · 연도별 적용 방식 · 건너뛴 평일 · KOSPI 최신일(§10-2)."""
    cdir = Path(calendar_dir) if calendar_dir is not None else cal.CALENDAR_DIR
    stored = set(kospi_dates)
    t_day, f_day = date.fromisoformat(t), date.fromisoformat(first)
    span = (t_day - f_day).days + 1
    dates = [
        d
        for d in tdl.trading_days_ending(t, span, calendar_dir=cdir, stored=stored)
        if d >= first
    ]
    try:
        loaded = cal.load_calendar(cdir)
    except Exception:  # noqa: BLE001 — 운영 helper 와 같게 읽지 못하면 평일 기본
        loaded = None
    covered = set(loaded.covered_years) if loaded is not None else set()
    modes: dict[str, str] = {}
    skipped: list[str] = []
    d = f_day
    while d <= t_day:
        file_year = d.year in covered
        modes.setdefault(str(d.year), MODE_FILE if file_year else MODE_KOSPI)
        if (
            not file_year
            and d < t_day
            and cal.is_fallback_trading_day(d)
            and d.isoformat() not in stored
        ):
            skipped.append(d.isoformat())
        d += timedelta(days=1)
    return {
        "label": AXIS_LABEL,
        "limit_note": AXIS_LIMIT_NOTE,
        "rule": "연도 파일 있는 해 = 파일 · 없는 해 = 평일 기본 ∩ KOSPI 저장일",
        "dates": dates,
        "modes": modes,
        "skipped_weekdays": skipped,
        "skipped_weekday_count": len(skipped),
        "kospi_latest": kospi_dates[-1] if kospi_dates else None,
        "calendar_years": sorted(covered),
    }


def axis_problem(t: str, axis: dict[str, Any]) -> Optional[str]:
    """AXIS_UNCERTAIN 사유 — t 가 축에 없음 · 파일 없는 해에 KOSPI 최신일이 t 보다 이른 경우."""
    dates = axis["dates"]
    if not dates or dates[-1] != t:
        return "기준일이 연구 축에 없습니다."
    if axis["modes"].get(t[:4]) == MODE_KOSPI:
        latest = axis["kospi_latest"]
        if latest is None or latest < t:
            return "연도 파일이 없는 해인데 KOSPI 저장 최신일이 기준일보다 이릅니다."
    return None


class AxisSeries:
    """연구 축에 맞춘 종가 · 축 날짜별 무효 사유 · 날짜 사이 경계."""

    def __init__(self, axis_dates: list[str], rows: list[PriceRow]) -> None:
        self.dates = axis_dates
        n = len(axis_dates)
        pos = {d: i for i, d in enumerate(axis_dates)}
        self.closes: list[Optional[float]] = [None] * n
        self.invalid: list[Optional[str]] = [MISSING_PRICE] * n
        self.breaks: dict[int, str] = {}  # i = (i-1 → i) 사이가 끊김
        prev: Optional[PriceRow] = None
        for row in rows:
            reason = None
            if row.source not in ALLOWED_SOURCES:
                reason = SOURCE_NOT_ALLOWED
            elif not _valid_close(row.close):
                reason = BAD_CLOSE
            if row.date in pos:
                i = pos[row.date]
                self.invalid[i] = reason
                self.closes[i] = float(row.close) if reason is None else None
            if prev is not None:
                brk = self._break(prev, row)
                if brk is not None:
                    j = self._axis_index_at_or_after(row.date)
                    if j is not None and j not in self.breaks:
                        self.breaks[j] = brk
            prev = row
        self._prefix()

    @staticmethod
    def _break(prev: PriceRow, row: PriceRow) -> Optional[str]:
        if row.source == FDR:
            if row.change is None:
                return CHANGE_MISSING
            if _valid_close(prev.close) and _valid_close(row.close):
                calc = float(row.close) / float(prev.close) - 1.0
                if abs(float(row.change) - calc) > CHANGE_TOLERANCE:
                    return BASIS_BREAK
        if prev.source == FDR and row.source == NAVER:
            return SOURCE_RESWITCH
        return None

    def _axis_index_at_or_after(self, day: str) -> Optional[int]:
        j = bisect.bisect_left(self.dates, day)
        return j if j < len(self.dates) else None

    def _prefix(self) -> None:
        n = len(self.dates)
        self._bad = [0] * (n + 1)
        self._brk = [0] * (n + 1)
        for i in range(n):
            self._bad[i + 1] = self._bad[i] + (1 if self.invalid[i] else 0)
            self._brk[i + 1] = self._brk[i] + (1 if i in self.breaks else 0)

    def window_ok(self, lo: int, hi: int) -> bool:
        """축 위치 lo..hi 의 종가가 모두 있고 (lo, hi] 사이에 경계가 없다."""
        if lo < 0 or hi >= len(self.dates) or lo > hi:
            return False
        if self._bad[hi + 1] - self._bad[lo]:
            return False
        return self._brk[hi + 1] - self._brk[lo + 1] == 0

    def window_reasons(self, lo: int, hi: int) -> list[str]:
        """창이 안 되는 사유 전부(REASON_ORDER 순서). 되면 []."""
        if self.window_ok(lo, hi):
            return []
        last = min(hi, len(self.dates) - 1)
        found = {self.invalid[k] for k in range(max(lo, 0), last + 1)}
        found |= {self.breaks[k] for k in range(lo + 1, hi + 1) if k in self.breaks}
        return [r for r in REASON_ORDER if r in found] or [MISSING_PRICE]

    def window_reason(self, lo: int, hi: int) -> Optional[str]:
        """창이 안 되는 첫 사유(REASON_ORDER 순서 · 학습 표본 제외 집계용). 되면 None."""
        reasons = self.window_reasons(lo, hi)
        return reasons[0] if reasons else None


def canonical_hash(payload: Any) -> str:
    """정렬 키 · 공백 없는 JSON 의 sha256 — 같은 입력 · recipe 를 식별한다."""
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(text.encode("ascii")).hexdigest()
