"""POC3-02D-OPS-03 — 장중 「신규 진입 검토」 추세 기준일 (확정 계약 5 · 8 · 13).

```text
표 최신 저장일 ≠ 기대 T-1       → 진입 검토 0건 · 구역 생략 · 회피 · 보유는 그대로
종목에 T-1 종가 없음             → 그 사업군만 진입 검토 제외
5일 · 20일                       → 거래일 캘린더 날짜의 종가(행 위치로 세지 않는다)
구역을 낼 때                     → 구역 머리 `추세 기준 YYYY-MM-DD 종가`
생략                             → 집계 틱 `entry_omitted` · 15:40 요약 한 줄
평가 불가(D2)                    → 직전 관측 ENTRY_REVIEW 는 회복으로 기록하지 않는다
```

실 Naver · KRX · Telegram 호출 0건. DB · 캘린더 · 상태 파일은 전부 tmp 경로다
(`_live_guard` — 라이브 DB 를 열지 않는다).
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timedelta

import pytest

from app.intraday_config import schema
from app.runtime_evidence import intraday_alert_flow as flow
from app.runtime_evidence import intraday_checkup_tally as tally_mod
from app.runtime_evidence import sector_signal as ss
from app.runtime_evidence.intraday_alert_render import (
    SECTION_AVOID,
    SECTION_ENTRY,
    build_section_plan,
    render_intraday_alert,
)
from app.runtime_evidence.sector_signal_state import (
    KST,
    load_sector_state,
    save_observation,
    save_sector_state,
)

TODAY = "2026-09-30"
ASOF = f"{TODAY}T10:30:00+09:00"
NOW = datetime(2026, 9, 30, 10, 30, tzinfo=KST)
# 2026 추석 휴장(09-24 · 09-25) — 행 위치와 거래일 날짜가 갈리는 실제 모양.
HOLIDAYS = {"2026-09-24", "2026-09-25"}


def _trading_days() -> list[str]:
    d, out = date(2026, 7, 20), []
    while d <= date.fromisoformat(TODAY):
        if d.weekday() < 5 and d.isoformat() not in HOLIDAYS:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


DAYS = _trading_days()
PAST = [d for d in DAYS if d < TODAY]
T1, T2 = PAST[-1], PAST[-2]
D5, D20 = PAST[-6], PAST[-21]
TICKERS = [f"T{i:05d}" for i in range(10)]


class Q:
    def __init__(self, ret, *, price=10000.0, asof=ASOF):
        self.current_price, self.day_return_pct, self.price_asof = price, ret, asof

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


def _close(day: str) -> float:
    """날짜마다 다른 값 — 행이 밀리면 수익률이 달라져 드러난다."""
    return 100.0 + PAST.index(day) * 1.0


def _db(tmp_path, *, drop_days=(), drop_rows=()):
    """무조정 표 대역. `drop_days` 는 표 전체에서 · `drop_rows` 는 (ticker, day)."""
    p = tmp_path / "m.sqlite"
    con = sqlite3.connect(p)
    con.execute(
        "CREATE TABLE krx_etf_daily_price_unadjusted(ticker TEXT,date TEXT,close REAL)"
    )
    rows = [
        (t, d, _close(d))
        for t in TICKERS
        for d in PAST
        if d not in set(drop_days) and (t, d) not in set(drop_rows)
    ]
    con.executemany("INSERT INTO krx_etf_daily_price_unadjusted VALUES(?,?,?)", rows)
    con.commit()
    con.close()
    return p


def _patch(monkeypatch):
    policy = dict(schema.INITIAL_POLICY_VALUES)
    policy.update({"enabled": True, "policy_status": schema.POLICY_CONFIGURED})
    sectors = [
        {
            "sector_key": f"S{i}",
            "representative": {"ticker": t, "short_name": f"대표{i}"},
        }
        for i, t in enumerate(TICKERS)
    ]
    monkeypatch.setattr(flow, "active_policy", lambda logger=None: policy)
    monkeypatch.setattr(flow, "_load_active_sectors", lambda logger=None: sectors)


# T00009 · T00007 = 상승 상위 20%(진입 검토 모양) · T00000 = 급락 회피.
QUOTES = {t: Q(0.0) for t in TICKERS} | {
    "T00009": Q(2.0),
    "T00007": Q(1.8),
    "T00000": Q(-2.5),
}


def _assemble(monkeypatch, tmp_path, db, *, state_path=None):
    _patch(monkeypatch)
    return flow.assemble_intraday_alert(
        held_drop=[],
        holding_rows=[],
        market_quotes=QUOTES,
        today_kst=TODAY,
        now_kst=NOW,
        state_path=state_path or tmp_path / "s.json",
        slot_label="10:30",
        quote_asof=f"{TODAY} 10:30",
        base_close_date=T1,
        db_path=db,
        calendar_dir=_calendar(tmp_path),
    )


def _pct(a: float, b: float) -> float:
    return round((a / b - 1.0) * 100.0, 1)


# ── 구역 단위 — 표 최신일 ≠ T-1 이면 진입 검토 0건 · 회피는 그대로 ─────────────


def test_t1_loaded_shows_entry_with_trend_basis_line(monkeypatch, tmp_path):
    out = _assemble(monkeypatch, tmp_path, _db(tmp_path))
    assert out.sector.trend.usable and out.sector.entry_omitted is False
    assert (out.sector.trend.d5, out.sector.trend.d20) == (D5, D20)
    r5, r20 = _pct(_close(T1), _close(D5)), _pct(_close(T1), _close(D20))
    # 구역 머리 바로 다음 줄이 추세 기준일이다(확정 계약 8).
    assert f"{SECTION_ENTRY}\n추세 기준 {T1} 종가\n• " in out.message_text
    assert (
        f"• S9 · 대표9: +2.0%\n  5일 {r5:+.1f}% · 20일 {r20:+.1f}%" in out.message_text
    )
    # 실시간 기준 줄과 추세 기준 줄은 분리돼 있다(설계 §3).
    assert f"기준\n현재가 {TODAY} 10:30 · 직전 종가 {T1}" in out.message_text
    assert out.message_text.count("추세 기준") == 1
    assert out.diagnostics["intraday_entry_omitted"] is False


def test_t2_only_omits_entry_but_keeps_avoid(monkeypatch, tmp_path):
    """08:27 · 09:20 모두 실패한 날 — 진입 검토만 빠지고 급락 회피는 나간다."""
    out = _assemble(monkeypatch, tmp_path, _db(tmp_path, drop_days=[T1]))
    assert out.sector.entry_omitted is True
    assert not out.sector.by_state(ss.STATE_ENTRY_REVIEW)
    assert SECTION_ENTRY not in out.message_text
    assert "추세 기준" not in out.message_text
    assert SECTION_AVOID in out.message_text and "S0 · 대표0: -2.5%" in out.message_text
    # T-2 날짜로 5일 · 20일을 계산해 내보내지 않는다.
    assert "5일" not in out.message_text and T2 not in out.message_text
    reasons = {(e["ticker"], e["reason"]) for e in out.sector.excluded}
    assert ("T00009", ss.REASON_TREND_NOT_T1) in reasons
    trend = out.diagnostics["intraday_trend_basis"]
    assert trend["expected_previous_trading_day"] == T1
    assert trend["table_latest"] == T2 and trend["usable"] is False
    assert out.diagnostics["intraday_entry_omitted"] is True


def test_basis_later_than_expected_is_not_used(monkeypatch, tmp_path):
    """정확 일치만 정상이다 — 표에 기대 T-1 보다 뒤 날짜가 있어도 생략한다."""
    db = _db(tmp_path)
    con = sqlite3.connect(db)
    con.execute(
        "INSERT INTO krx_etf_daily_price_unadjusted VALUES('T00009',?,1.0)", (TODAY,)
    )
    con.commit()
    con.close()
    out = _assemble(monkeypatch, tmp_path, db)
    assert out.sector.entry_omitted is True
    assert SECTION_ENTRY not in out.message_text


def test_missing_table_closes_entry_without_error(monkeypatch, tmp_path):
    """표가 없으면 추세 기준일을 확인하지 못한 것 — 예외 없이 진입 검토만 닫힌다."""
    empty = tmp_path / "empty.sqlite"
    sqlite3.connect(empty).close()
    out = _assemble(monkeypatch, tmp_path, empty)
    assert out.sector_error is None
    assert out.sector.entry_omitted is True
    assert out.sector.trend.table_latest is None


# ── 사업군 단위 — 그 종목에 T-1 · d5 · d20 날짜 종가가 없으면 그 사업군만 ──────


def test_alternate_without_t1_row_is_excluded_alone(monkeypatch, tmp_path):
    """대표는 모두 T-1 종가가 있고 **대체** 종목만 없다 — 그 사업군만 뺀다.

    대표에 T-1 종가가 없으면 구역 전체를 생략한다(설계자 RESULT STEP 2 ·
    `test_poc3_02d_ops03_consumer_isolation.py`).
    """
    db = _db(tmp_path)
    con = sqlite3.connect(db)
    con.executemany(
        "INSERT INTO krx_etf_daily_price_unadjusted VALUES(?,?,?)",
        [("A00009", d, _close(d)) for d in PAST if d != T1],
    )
    con.commit()
    con.close()
    _patch(monkeypatch)
    sectors = [dict(s) for s in flow._load_active_sectors()]
    sectors[9]["alternate"] = {"ticker": "A00009", "short_name": "대체9"}
    monkeypatch.setattr(flow, "_load_active_sectors", lambda logger=None: sectors)
    quotes = {k: v for k, v in QUOTES.items() if k != "T00009"} | {"A00009": Q(2.0)}
    out = flow.assemble_intraday_alert(
        held_drop=[],
        holding_rows=[],
        market_quotes=quotes,
        today_kst=TODAY,
        now_kst=NOW,
        state_path=tmp_path / "s.json",
        slot_label="10:30",
        quote_asof=f"{TODAY} 10:30",
        base_close_date=T1,
        db_path=db,
        calendar_dir=_calendar(tmp_path),
    )
    assert out.sector.entry_omitted is False and out.sector.representatives.ok
    assert [s.ticker for s in out.sector.by_state(ss.STATE_ENTRY_REVIEW)] == ["T00007"]
    reasons = {(e["ticker"], e["reason"]) for e in out.sector.excluded}
    assert ("A00009", ss.REASON_TICKER_NOT_T1) in reasons
    assert "대체9" not in out.message_text and "S7 · 대표7: +1.8%" in out.message_text


def test_missing_d5_date_fails_closed_instead_of_shifting(monkeypatch, tmp_path):
    """d5 날짜가 이력 전체에 없으면 6일 전 값으로 밀지 않는다 — 구역 생략으로 센다.

    예전에는 모든 사업군이 `short_history` 로 조용히 빠지고 `entry_omitted` 는
    거짓이었다(15:40 생략 집계 · 추세 기준 진단 누락 · 리뷰 L2-3). 08:30 기초지수
    창(`krx_store.CalendarWindow`)과 같은 규칙이다.
    """
    out = _assemble(monkeypatch, tmp_path, _db(tmp_path, drop_days=[D5]))
    assert out.sector.trend.table_latest == T1  # 표 최신일은 T-1 이다
    assert out.sector.trend.usable is False
    assert out.sector.trend.missing_days == (D5,)
    assert out.sector.entry_omitted is True
    assert out.diagnostics["intraday_entry_omitted"] is True
    assert out.diagnostics["intraday_trend_basis"]["missing_days"] == [D5]
    assert not out.sector.by_state(ss.STATE_ENTRY_REVIEW)
    reasons = {(e["ticker"], e["reason"]) for e in out.sector.excluded}
    assert ("T00009", ss.REASON_TREND_NOT_T1) in reasons
    assert SECTION_AVOID in out.message_text and "추세 기준" not in out.message_text


def test_one_ticker_missing_d5_is_excluded_alone(monkeypatch, tmp_path):
    """한 종목만 d5 종가가 없으면 그 사업군만 뺀다(구역은 그대로)."""
    out = _assemble(monkeypatch, tmp_path, _db(tmp_path, drop_rows=[("T00009", D5)]))
    assert out.sector.trend.usable and out.sector.entry_omitted is False
    reasons = {(e["ticker"], e["reason"]) for e in out.sector.excluded}
    assert ("T00009", ss.REASON_SHORT_HISTORY) in reasons
    assert [s.ticker for s in out.sector.by_state(ss.STATE_ENTRY_REVIEW)] == ["T00007"]


def test_missing_non_required_day_keeps_calendar_d20_value(monkeypatch, tmp_path):
    """창 안 다른 날 하나가 빠져도 20일은 **캘린더 d20** 종가로 계산한다."""
    gap = PAST[-3]
    out = _assemble(monkeypatch, tmp_path, _db(tmp_path, drop_days=[gap]))
    sig = {s.ticker: s for s in out.sector.signals}["T00009"]
    assert sig.return_20d_pct == _pct(_close(T1), _close(D20))
    # 행 위치로 셌다면 21번째 행은 PAST[-22] 다 — 그 값이 아니다.
    shifted = _pct(_close(T1), _close(PAST[-22]))
    assert shifted != sig.return_20d_pct


def test_trend_window_uses_trading_days_across_holiday():
    """추석(09-24 · 09-25)을 건너 5거래일 전을 센다 — 달력일 5일 전이 아니다."""
    trend = ss.TrendBasis(expected=T1, table_latest=T1, d5=D5, d20=D20)
    assert D5 == "2026-09-18" and "2026-09-24" not in PAST
    hist = [(d, _close(d)) for d in PAST]
    r5, r20, why = ss.trend_returns(hist, trend)
    assert why is None and r5 == _pct(_close(T1), _close("2026-09-18"))


def test_resolve_trend_basis_uses_calendar(tmp_path):
    cal = _calendar(tmp_path)
    ok = ss.resolve_trend_basis(TODAY, table_latest=T1, calendar_dir=cal)
    assert (ok.expected, ok.d5, ok.d20, ok.usable) == (T1, D5, D20, True)
    stale = ss.resolve_trend_basis(TODAY, table_latest=T2, calendar_dir=cal)
    assert (stale.expected, stale.d5, stale.usable) == (T1, None, False)
    assert ss.resolve_trend_basis(None, table_latest=T1).usable is False


def test_trend_basis_uncovered_year_unstored_weekday_is_not_usable(tmp_path):
    """캘린더 없는 해 — 평일 fallback 날(휴장일일 수 있다)이 이력에 없으면 닫는다.

    2027-01-01(신정)을 거래일로 치면 d5 · d20 이 하루씩 늦게 잡힌다(리뷰 L2-2).
    """
    from app import trading_day_lag

    cal = tmp_path / "cal2026"  # 2026 한 해(평일)만 덮는다
    cal.mkdir()
    d, lines = date(2026, 1, 1), ["date"]
    while d <= date(2026, 12, 30):
        if d.weekday() < 5:
            lines.append(d.isoformat())
        d += timedelta(days=1)
    (cal / "krx_trading_days_2026.csv").write_text("\n".join(lines) + "\n", "utf-8")
    today, expected = "2027-01-06", "2027-01-05"
    window = trading_day_lag.trading_days_ending(expected, 21, calendar_dir=cal)
    assert "2027-01-01" in window
    stored = set(window) - {"2027-01-01"}
    tb = ss.resolve_trend_basis(
        today, table_latest=expected, calendar_dir=cal, stored_days=stored
    )
    assert tb.expected == expected and tb.missing_days == ("2027-01-01",)
    assert tb.usable is False
    ok = ss.resolve_trend_basis(
        today, table_latest=expected, calendar_dir=cal, stored_days=set(window)
    )
    assert ok.missing_days == () and ok.usable is True


# ── 본문 — 추세 기준일 없는 진입 검토는 만들지 않는다 ───────────────────────


def test_entry_without_trend_date_is_refused():
    sig = ss.SectorSignal("S9", "T00009", "대표9", ss.STATE_ENTRY_REVIEW, 2.0, 1.0, 2.0)
    plan = build_section_plan(
        held_drop=[], held_surge=[], sector_signals=[sig], max_items_per_section=3
    )
    with pytest.raises(ValueError, match="추세 기준일"):
        render_intraday_alert(plan, slot_label="10:30")


def test_avoid_only_body_has_no_trend_line():
    sig = ss.SectorSignal("S0", "T00000", "대표0", ss.STATE_AVOID_DROP, -2.5)
    plan = build_section_plan(
        held_drop=[], held_surge=[], sector_signals=[sig], max_items_per_section=3
    )
    text = render_intraday_alert(plan, slot_label="10:30")
    assert "추세 기준" not in text and "5일" not in text


# ── 집계 · 15:40 요약 ─────────────────────────────────────────────────────


def test_tally_counts_entry_omitted_ticks_without_schema_change(tmp_path):
    p = tmp_path / "t.json"
    tally_mod.record_tick(p, today_kst=TODAY, outcome=tally_mod.OUTCOME_SENT)
    for _ in range(2):
        tally_mod.record_tick(
            p, today_kst=TODAY, outcome=tally_mod.OUTCOME_NO_SIGNAL, entry_omitted=True
        )
    body = json.loads(p.read_text(encoding="utf-8"))
    assert body["schema_version"] == tally_mod.SCHEMA_VERSION
    assert "entry_omitted" not in body["ticks"][0]
    assert body["ticks"][1]["entry_omitted"] is True
    tally = tally_mod.load_tally(p, today_kst=TODAY)
    assert (tally.checks, tally.entry_omitted) == (3, 2)
    assert tally_mod.render_summary_line(tally) == (
        "장중 점검 3회 · 알림 1건 · 중복 억제 0건 · 신호 없음 2건 · 신규 진입 검토 생략 2회"
    )


def test_summary_without_omission_is_byte_identical(tmp_path):
    p = tmp_path / "t.json"
    for o in [tally_mod.OUTCOME_SENT] * 2 + [tally_mod.OUTCOME_NO_SIGNAL]:
        tally_mod.record_tick(p, today_kst=TODAY, outcome=o)
    line = tally_mod.render_summary_line(tally_mod.load_tally(p, today_kst=TODAY))
    assert line == "장중 점검 3회 · 알림 2건 · 중복 억제 0건 · 신호 없음 1건"


# ── D2 — 추세 기준일 미확인은 진입 검토의 회복이 아니다 ──────────────────────


def test_unevaluable_entry_is_not_recorded_as_recovery(monkeypatch, tmp_path):
    """직전 관측 ENTRY_REVIEW → 이번 틱 T-1 미확인 · 여전히 진입 모양 → 보존.

    직전 관측이 회피(AVOID_CHASE)였던 사업군은 당일 등락률로 정상 평가됐으므로
    회복으로 기록한다.
    """
    state = tmp_path / "s.json"
    sent = (NOW - timedelta(minutes=60)).isoformat()
    save_sector_state(
        state,
        entries={
            "T00009": {
                "state": ss.STATE_ENTRY_REVIEW,
                "last_delivered_state": ss.STATE_ENTRY_REVIEW,
                "last_sent_at": sent,
                "continuous": True,
                "sector_key": "S9",
            },
            "T00007": {
                "state": ss.STATE_AVOID_CHASE,
                "last_delivered_state": ss.STATE_AVOID_CHASE,
                "last_sent_at": sent,
                "continuous": True,
                "sector_key": "S7",
            },
        },
        today_kst=TODAY,
        sent_today=1,
    )
    out = _assemble(
        monkeypatch, tmp_path, _db(tmp_path, drop_days=[T1]), state_path=state
    )
    assert "T00009" in out.unevaluable and "T00007" not in out.unevaluable
    save_observation(
        state, observed=out.observed, today_kst=TODAY, unevaluable=out.unevaluable
    )
    entries = load_sector_state(state, today_kst=TODAY).entries
    assert entries["T00009"]["continuous"] is True
    assert entries["T00009"]["state"] == ss.STATE_ENTRY_REVIEW
    assert entries["T00007"]["continuous"] is False


# ── 실제 run() 관통 — 러너 → 조립 → 본문 · 집계 · 실행 기록 ──────────────────


def _run_rig(monkeypatch, tmp_path, *, drop_last_day):
    from tests import test_intraday_alert_flow_through as ft
    from tests import test_poc3_02d_ops01_holdings_risk_flow as ops01

    p = tmp_path / "fixture_m.sqlite"
    con = sqlite3.connect(p)
    con.execute(
        "CREATE TABLE krx_etf_daily_price_unadjusted(ticker TEXT,date TEXT,close REAL)"
    )
    days = ft.FIXTURE_DAYS[:-1] if drop_last_day else ft.FIXTURE_DAYS
    con.executemany(
        "INSERT INTO krx_etf_daily_price_unadjusted VALUES(?,?,?)",
        [(f"T{i:05d}", d, 100.0 + n) for i in range(10) for n, d in enumerate(days)],
    )
    con.commit()
    con.close()
    rig = ops01._rig(monkeypatch, tmp_path, p)
    stamp = ft._asof(ft.TODAY)
    q = {"H00001": ft._Q(10000.0, stamp, 0.0)}
    q |= {f"T{i:05d}": ft._Q(10000.0, stamp, 0.0) for i in range(10)}
    q["T00009"] = ft._Q(10000.0, stamp, 2.0)  # 진입 검토 모양
    q["T00008"] = ft._Q(10000.0, stamp, 5.0)  # 추격 주의
    rig["quotes"] = q
    return rig, ft


def test_run_t2_only_sends_avoid_and_counts_omission(monkeypatch, tmp_path):
    rig, ft = _run_rig(monkeypatch, tmp_path, drop_last_day=True)
    rec = rig["runner"].run(ft.RISK_KIND, "send")
    assert rec["status"] == "sent", rec
    body = rig["sent"].calls[-1]
    assert SECTION_AVOID in body and "대표8" in body
    assert SECTION_ENTRY not in body and "추세 기준" not in body
    assert rec["intraday_entry_omitted"] is True
    assert rec["intraday_trend_basis"]["table_latest"] == ft.FIXTURE_DAYS[-2]
    ticks = json.loads(rig["tally"].read_text(encoding="utf-8"))["ticks"]
    assert ticks[-1]["entry_omitted"] is True
    line = tally_mod.render_summary_line(
        tally_mod.load_tally(rig["tally"], today_kst=ft.TODAY)
    )
    assert line.endswith("신규 진입 검토 생략 1회"), line


def test_run_t1_loaded_shows_trend_basis_line(monkeypatch, tmp_path):
    rig, ft = _run_rig(monkeypatch, tmp_path, drop_last_day=False)
    rec = rig["runner"].run(ft.RISK_KIND, "send")
    assert rec["status"] == "sent", rec
    body = rig["sent"].calls[-1]
    assert f"{SECTION_ENTRY}\n추세 기준 {ft.FIXTURE_DAYS[-1]} 종가\n" in body
    assert f"직전 종가 {ft.FIXTURE_DAYS[-1]}" in body
    assert rec["intraday_entry_omitted"] is False
    ticks = json.loads(rig["tally"].read_text(encoding="utf-8"))["ticks"]
    assert "entry_omitted" not in ticks[-1]
