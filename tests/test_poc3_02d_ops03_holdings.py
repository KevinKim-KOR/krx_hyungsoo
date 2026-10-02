"""POC3-02D-OPS-03 — 보유 브리핑 20거래일 기준일 · 장중 위험 직전 종가 (확정 계약 10).

예전 축은 `069500` 의 `etf_daily_price` 저장 날짜였다. 08:10 배치가 실패해 T-1
행이 없으면 축 마지막이 T-2 가 되어 **21거래일 전 종가를 '20거래일' 로** 보고했다.
이제 축은 실행일 기준 **거래일 캘린더**다(`holdings_selection_source.trading_day_axis`).

```text
배치 실패(T-1 가격 없음)   기준일 = 캘린더 T-20 (밀리지 않는다) · 고점 대비 보조값만 생략
기준일 종가 없음           그 종목 `데이터 확인 필요`(21일 전 값으로 대신하지 않는다)
장중 위험 직전 종가 날짜   캘린더 T-1 (네이버 전일 대비의 기준일)
```

실 Naver · Telegram 호출 0건 · 캘린더 · 상태 파일은 tmp 경로다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

from app.runtime_evidence.holdings_risk_flow import build_holdings_risk_alert
from app.runtime_evidence.holdings_selection import reference_trading_day
from app.runtime_evidence.holdings_selection_flow import build_holdings_selection
from app.runtime_evidence.holdings_selection_source import trading_day_axis
from tests._helpers import etf_basis_source

TODAY = "2026-09-30"
HOLIDAYS = {"2026-09-24", "2026-09-25"}  # 2026 추석 휴장


def _trading_days() -> list[str]:
    d, out = date(2026, 7, 20), []
    while d <= date.fromisoformat(TODAY):
        if d.weekday() < 5 and d.isoformat() not in HOLIDAYS:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


DAYS = _trading_days()
PAST = [d for d in DAYS if d < TODAY]
T1 = PAST[-1]
BASE = PAST[-20]  # 캘린더 20거래일 전
SLIPPED = PAST[-21]  # 옛 축이 배치 실패일에 고르던 날


@dataclass
class H:
    ticker: str
    name: str
    account_group: str = "일반"


@dataclass
class Q:
    current_price: float
    price_asof: str = f"{TODAY}T09:14:00+09:00"
    day_return_pct: Optional[float] = None

    def has_day_return(self):
        v = self.day_return_pct
        return isinstance(v, (int, float)) and not isinstance(v, bool)


def _calendar(tmp_path):
    cal = tmp_path / "cal"
    cal.mkdir(exist_ok=True)
    (cal / "krx_trading_days_2026.csv").write_text(
        "date\n" + "\n".join(DAYS) + "\n", encoding="utf-8"
    )
    return cal


def _history(*, drop=(), special=None):
    """전 종목 · 069500 공통 종가 이력. 기본 100 · `special` 은 날짜별 값."""
    special = special or {}
    rows = [(d, special.get(d, 100.0)) for d in PAST if d not in set(drop)]
    return lambda ticker, **kw: list(rows)


def _selection(tmp_path, fetch_history, *, current=88.0):
    return build_holdings_selection(
        holdings_loader=lambda: [H("AAA", "가나다")],
        fetch_history=fetch_history,
        market_quotes={"AAA": Q(current)},
        state_path=tmp_path / "sel.json",
        slot_id="OPEN",
        runtime_kst=f"{TODAY}T09:15:00+09:00",
        today_kst=TODAY,
        calendar_dir=_calendar(tmp_path),
        # 설계자 RESULT STEP 1 — ETF 과거 종가는 KRX 무조정 표에서 온다. 이 파일의
        # 이력을 그 표의 값으로 넣는다(단언의 뜻 그대로 · 가격 기준은 price_basis 테스트).
        price_basis_source=etf_basis_source(fetch_history),
    )


def test_axis_is_the_calendar_not_stored_prices(tmp_path):
    axis = trading_day_axis(TODAY, calendar_dir=_calendar(tmp_path))
    assert axis == PAST[-20:] and axis[-1] == T1
    assert "2026-09-24" not in axis and "2026-09-25" not in axis
    assert trading_day_axis("not-a-date", calendar_dir=_calendar(tmp_path)) == []
    assert trading_day_axis(None) == []


def test_batch_failure_does_not_slip_the_20_day_base(tmp_path):
    """T-1 가격이 없는 날(08:10 배치 실패)에도 기준일은 캘린더 T-20 이다.

    옛 축(저장 가격 날짜)이면 21거래일 전(`SLIPPED`)을 골랐다 — 같은 입력으로
    값이 달라지는 것을 보인다: 기준 100 → -12% · 밀린 기준 90 → -2.2%(미선정).
    """
    fetch = _history(drop=[T1], special={SLIPPED: 90.0})
    old_axis = [d for d, _ in fetch("069500")]
    assert reference_trading_day(old_axis, TODAY, 20) == SLIPPED  # 옛 결함 재현

    out = _selection(tmp_path, fetch)
    assert not out.error, out.error
    assert out.diagnostics["holdings_base_trading_day"] == BASE
    assert out.diagnostics["holdings_axis_last_trading_day"] == T1
    assert f"20거래일 전 종가 {BASE}" in out.message_text
    assert "20거래일 -12.0%" in out.message_text
    # 20거래일 구간에 T-1 종가가 없다 — 고점 대비 보조값만 생략된다.
    assert "고점 대비" not in out.message_text


def test_complete_history_keeps_drawdown(tmp_path):
    fetch = _history(special={PAST[-5]: 110.0})
    out = _selection(tmp_path, fetch)
    assert "20거래일 -12.0%" in out.message_text
    assert "고점 대비 -20.0%" in out.message_text  # 88 / 110 - 1


def test_missing_base_close_is_data_unavailable_not_shifted(tmp_path):
    """기준일 종가가 없으면 21일 전 종가로 대신하지 않는다 — 기존 `데이터 확인 필요`."""
    out = _selection(tmp_path, _history(drop=[BASE]))
    assert (
        out.selected and out.selected[0].primary_reason == "DATA_UNAVAILABLE_OR_STALE"
    )
    assert "데이터 확인 필요" in out.message_text
    # 설계자 RESULT STEP 1 — 현재가는 멀쩡하다. 값 칸은 `현재가 조회 실패` 가 아니다.
    assert "20거래일 데이터 확인 불가" in out.message_text
    assert "20거래일 -" not in out.message_text


def test_base_day_skips_holidays(tmp_path):
    """추석 이틀을 건너 센다 — 평일로 셌다면 이틀 뒤 날짜가 된다."""
    weekdays = []
    d = date.fromisoformat(TODAY) - timedelta(days=1)
    while len(weekdays) < 20:
        if d.weekday() < 5:
            weekdays.append(d.isoformat())
        d -= timedelta(days=1)
    out = _selection(tmp_path, _history())
    assert out.diagnostics["holdings_base_trading_day"] == BASE != weekdays[-1]


def _risk(tmp_path, fetch_history, *, day_return=-6.0):
    return build_holdings_risk_alert(
        holdings_loader=lambda: [H("AAA", "가나다")],
        fetch_history=fetch_history,
        market_quotes={"AAA": Q(94.0, day_return_pct=day_return)},
        state_path=tmp_path / "risk.json",
        runtime_kst=f"{TODAY}T10:30:00+09:00",
        today_kst=TODAY,
        calendar_dir=_calendar(tmp_path),
        price_basis_source=etf_basis_source(fetch_history),
    )


def test_risk_previous_close_date_is_calendar_t1_on_batch_failure(tmp_path):
    """직전 종가 날짜 = 네이버 전일 대비의 기준일(캘린더 T-1) — T-2 로 밀리지 않는다."""
    out = _risk(tmp_path, _history(drop=[T1]))
    assert not out.error, out.error
    assert out.diagnostics["risk_prev_trading_day"] == T1
    assert f"직전 거래일 종가 {T1}" in out.message_text
    # 20거래일 고점 대비는 T-1 종가가 없으니 생략(T-2 로 끝나는 구간을 쓰지 않는다).
    assert out.selected and out.selected[0].drawdown_pct is None


def test_risk_drawdown_uses_calendar_window_when_complete(tmp_path):
    out = _risk(tmp_path, _history())
    assert out.selected[0].drawdown_pct == -6.0  # 94 / 100 - 1
    assert out.diagnostics["risk_prev_trading_day"] == T1


def test_year_without_calendar_falls_back_to_weekdays(tmp_path):
    """캘린더가 그해를 덮지 않으면 평일 축(보수적) — 빈 축으로 전 종목을 막지 않는다."""
    empty = tmp_path / "no_cal"
    empty.mkdir()
    axis = trading_day_axis("2027-01-06", calendar_dir=empty)
    assert len(axis) == 20 and axis[-1] == "2027-01-05"
    assert all(date.fromisoformat(d).weekday() < 5 for d in axis)


# ── 캘린더 없는 해 — 평일 fallback 날이 저장돼 있지 않으면 빈 축(리뷰 L2-2) ─────────

NEXT_YEAR_TODAY = "2027-01-06"  # 2027 캘린더 없음 · 01-01(신정)을 평일로 친다
NEW_YEAR = "2027-01-01"


def _calendar_2026_only(tmp_path):
    """2026 한 해만 덮는다(평일 · 12-25 · 12-31 휴장). 2027 은 평일 fallback."""
    cal = tmp_path / "cal2026"
    cal.mkdir(exist_ok=True)
    d, days = date(2026, 1, 1), []
    while d.year == 2026:
        if d.weekday() < 5 and d.isoformat() not in ("2026-12-25", "2026-12-31"):
            days.append(d.isoformat())
        d += timedelta(days=1)
    (cal / "krx_trading_days_2026.csv").write_text(
        "date\n" + "\n".join(days) + "\n", encoding="utf-8"
    )
    return cal


def test_uncovered_year_unstored_weekday_is_skipped_not_emptied(tmp_path):
    """연도 파일이 없는 해 — 저장 자료가 없는 평일은 휴장으로 건너뛰고 축을 비우지 않는다
    (한국 거래일 계약 2026-09-11 · 설계자 2026-10-02 복원). 그 평일이 이력에 있으면 센다."""
    cal = _calendar_2026_only(tmp_path)
    axis = trading_day_axis(NEXT_YEAR_TODAY, calendar_dir=cal)
    assert NEW_YEAR in axis and axis[-1] == "2027-01-05" and len(axis) == 20
    unstored = set(axis) - {NEW_YEAR}
    skipped = trading_day_axis(NEXT_YEAR_TODAY, calendar_dir=cal, stored_dates=unstored)
    assert NEW_YEAR not in skipped and len(skipped) == 20
    assert skipped[-1] == "2027-01-05" and skipped[0] < axis[0]  # 하루 앞에서 채운다
    assert (
        trading_day_axis(NEXT_YEAR_TODAY, calendar_dir=cal, stored_dates=set(axis))
        == axis
    )


def test_uncovered_year_gap_reaches_both_holdings_flows(tmp_path):
    """두 흐름이 보유 이력 날짜를 축에 넘긴다 — 저장 자료가 없는 평일은 건너뛰고 계산한다."""
    from app import trading_day_lag

    cal = _calendar_2026_only(tmp_path)
    axis = trading_day_axis(NEXT_YEAR_TODAY, calendar_dir=cal)
    wide = trading_day_lag.trading_days_ending("2027-01-05", 25, calendar_dir=cal)
    asof = f"{NEXT_YEAR_TODAY}T09:14:00+09:00"

    def _run(days):
        rows = [(d, 100.0) for d in days]
        fetch = lambda ticker, **kw: list(rows)  # noqa: E731
        sel = build_holdings_selection(
            holdings_loader=lambda: [H("AAA", "가나다")],
            fetch_history=fetch,
            market_quotes={"AAA": Q(88.0, price_asof=asof)},
            state_path=tmp_path / "sel.json",
            slot_id="OPEN",
            runtime_kst=f"{NEXT_YEAR_TODAY}T09:15:00+09:00",
            today_kst=NEXT_YEAR_TODAY,
            calendar_dir=cal,
            price_basis_source=etf_basis_source(fetch),
        )
        risk = build_holdings_risk_alert(
            holdings_loader=lambda: [H("AAA", "가나다")],
            fetch_history=fetch,
            market_quotes={"AAA": Q(94.0, price_asof=asof, day_return_pct=-6.0)},
            state_path=tmp_path / "risk.json",
            runtime_kst=f"{NEXT_YEAR_TODAY}T10:30:00+09:00",
            today_kst=NEXT_YEAR_TODAY,
            calendar_dir=cal,
            price_basis_source=etf_basis_source(fetch),
        )
        return sel, risk

    sel, risk = _run(
        [d for d in wide if d != NEW_YEAR]
    )  # 신정 행 없음 · 하루 앞 행 있음
    assert (
        "20거래일 -12.0%" in sel.message_text
    )  # 축이 신정을 건너뛰어 기준일 종가가 있다
    assert risk.selected[0].drawdown_pct == -6.0
    assert risk.diagnostics["risk_prev_trading_day"] == "2027-01-05"

    sel, risk = _run(axis)
    assert "20거래일 -12.0%" in sel.message_text
    assert risk.selected[0].drawdown_pct == -6.0
    assert risk.diagnostics["risk_prev_trading_day"] == "2027-01-05"
