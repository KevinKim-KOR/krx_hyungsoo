"""POC5-20 — 기준일 t 의 세 관측과 t 다음 20거래일의 두 결과(설계 §3 · §4 · PLAN §2 · §5).

```text
관측(t 이하 자료만)
  하락 구간   종가 유효 행(close IS NOT NULL AND close > 0 · PC `fetch_recent_price_rows` 와 같은 조건) 중
              t 이하 최근 21개 → `_window_return_pct(series, 20)`
              → `classify_decline(normalize_pct(...))`
              (PC `pc_price_basis._decline_band` 와 같은 식 · 값이 유한하지 않으면 판정하지 않음)
  거래량      같은 행의 t 이하 최근 21개(최신순) → `compute_stored_volume_evidence`(POC5-09 규칙 그대로)
              · 반올림 전 배수 > 1 = 평균 초과 · ≤ 1 = 평균 이하(PLAN 판정 Q1 (b))
  흔들림      원본 행(거르지 않음)의 t 이하 최근 41개 → `compute_price_volatility(E = D = t)`(POC5-16 그대로)
              · higher = 커짐 · lower · same = 커지지 않음(소수 둘째 자리 표시값 비교)
결과(t 뒤 · `--end` 이하)
  2026 캘린더에서 t 다음 20거래일 t+1 … t+20 · 날마다 종가 유효 저장 행이 정확히 있어야 함(결측을 더 먼
  날로 채우지 않음) · t → t+1 … t+19 → t+20 연결은 POC5-16 판정(`valid_close` · 허용 출처 · `link_break`)
  끝점 변화 = C(t+20)/C(t) − 1 · 최저 종가 변화 = min(0, min_h C(t+h)/C(t) − 1) — 둘 다 %
```

공통 표본에서 빠진 건은 `REASONS` 순서대로 처음 걸린 사유 하나로 센다.
"""

from __future__ import annotations

import bisect
import math
from dataclasses import dataclass
from typing import Any, Optional, Sequence

from app.pc_price_volatility import _link_unconfirmed, compute_price_volatility
from app.reentry_review.prices import ALLOWED_SOURCES, PriceRow, valid_close
from app.runtime_evidence.holdings_selection import classify_decline, normalize_pct
from app.short_term_momentum import _window_return_pct
from app.stored_volume_evidence import (
    VOLUME_ROWS_NEEDED,
    compute_stored_volume_evidence,
)

DECLINE_WINDOW = 20
DECLINE_ROWS = DECLINE_WINDOW + 1  # 21
VOLATILITY_ROWS = 41
PATH_DAYS = 20

BAND_NONE = "NONE"  # 구간 미해당(판정은 됨)

# (코드, 이름) — 이 순서대로 처음 걸린 사유 하나로 센다(PLAN §2).
REASONS: tuple[tuple[str, str], ...] = (
    ("before_first_stored", "저장 시작 전(그 종목의 첫 저장일 이전)"),
    ("no_close_on_t", "기준일 종가 없음"),
    ("decline_short", "하락 구간: 저장 종가 21개 미만"),
    ("decline_invalid", "하락 구간: 20저장일 변화 값 확인 불가"),
    ("volume_missing", "거래량: 기준일 거래량 없음"),
    ("avg_insufficient", "거래량: 직전 20개 저장일 평균 자료 부족"),
    ("avg_zero", "거래량: 직전 평균 0"),
    ("volatility_unavailable", "흔들림: 최근 · 직전 20구간 모두 계산 불가"),
    ("volatility_recent_only", "흔들림: 직전 20구간 계산 불가"),
    ("volatility_previous_only", "흔들림: 최근 20구간 계산 불가"),
    ("not_matured", "이후 20거래일 미도래"),
    ("path_missing", "이후 경로 저장 결측"),
    ("path_basis", "이후 경로 가격 기준 확인 필요"),
)
REASON_CODES = tuple(c for c, _ in REASONS)


@dataclass(frozen=True)
class RawRow:
    """시장 DB `etf_daily_price` 원본 한 행(읽은 값 그대로)."""

    date: str
    close: Any
    volume: Any
    source: Optional[str]
    fetched_at: Optional[str]
    change: Any


@dataclass(frozen=True)
class TickerSeries:
    """한 종목의 입력 사본 — 원본 행 · 종가 유효 행(둘 다 날짜 오름차순 · `--end` 이하)."""

    ticker: str
    raw: tuple[RawRow, ...]
    valid: tuple[RawRow, ...]  # close IS NOT NULL AND close > 0 (DB 가 고른 행)

    @property
    def raw_dates(self) -> list[str]:
        return [r.date for r in self.raw]

    @property
    def valid_dates(self) -> list[str]:
        return [r.date for r in self.valid]


@dataclass(frozen=True)
class Record:
    """공통 표본 한 건(종목 × 기준일)."""

    ticker: str
    date: str
    band: str  # D10_PLUS · D8_10 · D5_8 · NONE
    return_20d_pct_1dp: float
    volume_ratio: float  # 반올림 전
    volume_above: bool
    volatility_comparison: str  # higher · lower · same
    volatility_up: bool
    end_change_pct: float
    min_change_pct: float


def volume_above(ratio: float) -> bool:
    """반올림 전 배수가 1 보다 크면 평균 초과(1.000 은 평균 이하 · PLAN 판정 Q1 (b))."""
    return ratio > 1.0


def _upto(rows: Sequence[RawRow], dates: list[str], t: str) -> Sequence[RawRow]:
    return rows[: bisect.bisect_right(dates, t)]


def observe(s: TickerSeries, t: str) -> tuple[Optional[str], dict[str, Any]]:
    """t 이하 자료만으로 세 관측 → (빠진 사유 코드 | None, 관측 값)."""
    raw_dates, valid_dates = s.raw_dates, s.valid_dates
    if not raw_dates or t < raw_dates[0]:
        return "before_first_stored", {}
    valid_upto = _upto(s.valid, valid_dates, t)
    if not valid_upto or valid_upto[-1].date != t:
        return "no_close_on_t", {}

    series = [(r.date, r.close) for r in valid_upto[-DECLINE_ROWS:]]
    if len(series) < DECLINE_ROWS:
        return "decline_short", {}
    try:
        ret = _window_return_pct(series, DECLINE_WINDOW)
    except (TypeError, ValueError):
        ret = None
    if ret is None or isinstance(ret, bool) or not math.isfinite(ret):
        return "decline_invalid", {}
    pct = normalize_pct(float(ret))
    band = classify_decline(pct) or BAND_NONE

    rows_desc = [
        (r.date, r.close, r.volume, r.source)
        for r in reversed(valid_upto[-VOLUME_ROWS_NEEDED:])
    ]
    vol = compute_stored_volume_evidence(s.ticker, rows_desc)
    if vol.ratio_status != "ok" or vol.ratio is None:
        return vol.ratio_status, {}

    raw_upto = _upto(s.raw, raw_dates, t)[-VOLATILITY_ROWS:]
    price_rows = [
        PriceRow(r.date, r.close, r.source, r.fetched_at, r.change) for r in raw_upto
    ]
    pv = compute_price_volatility(price_rows, last_valid_date=t, reference_date=t)
    if pv.status != "ok" or pv.comparison is None:
        code = f"volatility_{pv.status}"
        if (
            code not in REASON_CODES
        ):  # E = D = t 라 date_mismatch · reference_unavailable 은 나올 수 없다
            raise ValueError(f"예상하지 못한 흔들림 상태: {pv.status}")
        return code, {}

    return None, {
        "band": band,
        "return_20d_pct_1dp": pct,
        "volume_ratio": float(vol.ratio),
        "volume_above": volume_above(float(vol.ratio)),
        "volatility_comparison": pv.comparison,
        "volatility_up": pv.comparison == "higher",
    }


def outcome(
    s: TickerSeries, t: str, calendar: list[str], end: str
) -> tuple[Optional[str], dict[str, float]]:
    """t 다음 2026 캘린더 20거래일의 두 결과 → (빠진 사유 코드 | None, 결과 %)."""
    i = bisect.bisect_left(calendar, t)
    on_calendar = i < len(calendar) and calendar[i] == t
    first, last = i + 1, i + 1 + PATH_DAYS
    future = calendar[first:last] if on_calendar else []
    if len(future) < PATH_DAYS or future[-1] > end:
        return "not_matured", {}
    by_date = {r.date: r for r in s.valid}
    path = [by_date[d] for d in [t, *future] if d in by_date]
    if len(path) != PATH_DAYS + 1:
        return "path_missing", {}
    rows = [PriceRow(r.date, r.close, r.source, r.fetched_at, r.change) for r in path]
    if any(not valid_close(r.close) or r.source not in ALLOWED_SOURCES for r in rows):
        return "path_basis", {}
    if any(_link_unconfirmed(rows[k - 1], rows[k]) for k in range(1, len(rows))):
        return "path_basis", {}
    c0 = float(rows[0].close)
    changes = [float(r.close) / c0 - 1.0 for r in rows[1:]]
    return None, {
        "end_change_pct": changes[-1] * 100.0,
        "min_change_pct": min(0.0, min(changes)) * 100.0,
    }


def classify_pair(
    s: TickerSeries, t: str, calendar: list[str], end: str
) -> tuple[Optional[str], Optional[Record]]:
    """한 건(종목 × 기준일) → (빠진 사유 | None, 공통 표본 기록 | None)."""
    reason, obs = observe(s, t)
    if reason is not None:
        return reason, None
    reason, out = outcome(s, t, calendar, end)
    if reason is not None:
        return reason, None
    return None, Record(ticker=s.ticker, date=t, **obs, **out)
