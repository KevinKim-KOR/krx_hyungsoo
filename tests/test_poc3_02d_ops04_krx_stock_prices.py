"""POC3-02D-OPS-04 항목 1 — 보유 코스피 개별주 KRX 공식 종가(설계자 Q1 a · 사용자 승인 2026-10-04).

```text
저장      market_data.sqlite 의 별도 표 krx_stock_daily_price_unadjusted — 보유 행만 · ETF 표 불변
조회      sto/stk_bydd_trd(기존 키) · 테스트 가드가 기본 경계를 막는다
곁 작업  KRX 단계 시각표(08:10 · 08:15 · 08:20 · 08:24 · 마감 08:27 · 09:20 · 수동 = 1칸) ·
          ETF 와 독립(ETF T-1 을 못 받은 날도 돈다) · 같은 시각이면 ETF 먼저 · 곁 작업끼리 격리
채우기    목표일(ledger 밖 · 칸마다 저장될 때까지) → 31거래일 창(목표일 저장 여부와 무관) ·
          창 날짜별 하루 1회 + 09:20 일시 오류 보강 1회
          ledger 는 따로(krx_stock_backfill_ledger.json) — ETF ledger 와 서로 막지 않는다
보유 0    응답에 보유 행이 없으면 그 실행을 끝낸다 · 보유 파일 없음 · 손상 = 호출 0
기록      08:10 배치 상태 · 09:20 보강 기록 모두 `krx_holdings_stocks`
```

합성 캘린더 · 임시 DB · 가짜 fetcher · 가짜 시계만 쓴다. **외부 조회 0건 · 라이브 DB ·
state · logs 미접근 · 실제 sleep 0.**
"""

from __future__ import annotations

import functools
import json
import sqlite3
from datetime import datetime

import httpx
import pytest

import app.holdings as holdings_module
from app.market_briefing import (
    krx_backfill,
    krx_stock_store,
    krx_stock_sync,
    krx_store,
    krx_sync,
    krx_target_sync,
)
from app.runtime_evidence import holdings_price_basis as hpb
from app.three_push_runtime import market_data_batch as mdb
from tests import test_poc3_02d_ops03_krx_batch as kb

TODAY = kb.TODAY  # 2026-09-30
T1 = kb.T1  # 2026-09-29
T1_BAS = "20260929"
HELD = ["005930", "000660", "006400", "069500"]  # 개별주 3 + ETF 1
STOCKS = ["000660", "005930", "006400"]


def _srow(bas_dd, t, close=1000.0, **over):
    c = close if isinstance(close, str) else f"{close:g}"
    r = {
        "BAS_DD": bas_dd,
        "ISU_CD": t,
        "ISU_NM": f"종목{t}",
        "MKT_NM": "KOSPI",
        "TDD_CLSPRC": c,
        "TDD_OPNPRC": c,
        "TDD_HGPRC": c,
        "TDD_LWPRC": c,
    }
    r.update(over)
    return r


def _market(bas_dd, extra=("999990", "123450")):
    """코스피 응답 — 보유 개별주 3 + 보유 아닌 종목. ETF 는 응답에 없다(실측 2026-10-06)."""
    return [_srow(bas_dd, t) for t in (*STOCKS, *extra)]


class _StockFetch:
    def __init__(self, clock, respond=None, cost_seconds=1):
        self.clock, self.cost = clock, cost_seconds
        self.respond = respond or (lambda b, i: _market(b))
        self.calls: list[str] = []

    def __call__(self, bas_dd, key):
        assert key == "DEADBEEF"
        self.calls.append(bas_dd)
        self.clock.t += kb.timedelta(seconds=self.cost)
        out = self.respond(bas_dd, len(self.calls))
        if isinstance(out, Exception):
            raise out
        return out


@pytest.fixture
def env(tmp_path):
    cal = kb._calendar(tmp_path)
    db = tmp_path / "m.sqlite"
    return {"tmp": tmp_path, "cal": cal, "db": db}


def _window(env):
    from app import trading_day_lag

    return trading_day_lag.trading_days_ending(
        T1, krx_stock_sync.WINDOW_TRADING_DAYS, calendar_dir=env["cal"]
    )


def _at(hh, mm, ss=0):
    return datetime(2026, 9, 30, hh, mm, ss, tzinfo=kb.KST)


def _task(env, clock, fetch, **kw):
    """기본 = 한 칸(09:20 · 수동 실행과 같다 · 마감 없음)."""
    args = dict(
        today=TODAY,
        target_iso=T1,
        key="DEADBEEF",
        mode=krx_target_sync.MODE_SINGLE,
        slots=[clock()],
        deadline=None,
        clock=clock,
        db_path=env["db"],
        calendar_dir=env["cal"],
        fetch=fetch,
        tickers=HELD,
    )
    args.update(kw)
    return krx_stock_sync.HoldingsStockTask(**args)


def _scheduled(clock):
    """08:10 배치 시각표 그대로(`krx_target_sync.attempt_plan`)."""
    mode, slots = krx_target_sync.attempt_plan(clock())
    return dict(mode=mode, slots=slots, deadline=_at(8, 27))


def _drive(task, clock):
    """`krx_target_sync._drain_side` 처럼 남은 칸을 차례로 돈다(가짜 시계)."""
    for _ in range(10):
        nxt = task.next_slot()
        if nxt is None:
            return
        if nxt > clock():
            clock.sleep((nxt - clock()).total_seconds())
        task.run_due(clock())


def _stock_sync(env, clock, fetch, **kw):
    task = _task(env, clock, fetch, **kw)
    _drive(task, clock)
    return task.summary()


def _fresh(env, name):
    (env["tmp"] / name).mkdir()
    return dict(env, db=env["tmp"] / name / "m.sqlite")


def _ledger(env):
    path = krx_stock_sync.ledger_path_for(env["db"])
    return json.loads(path.read_text(encoding="utf-8"))


def _http_error(code):
    req = httpx.Request("GET", "https://example.invalid/x")
    return httpx.HTTPStatusError(
        "x", request=req, response=httpx.Response(code, request=req)
    )


def _tables(db):
    con = sqlite3.connect(db)
    try:
        return sorted(
            r[0]
            for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")
        )
    finally:
        con.close()


# ── 저장소 ───────────────────────────────────────────────────────────────────


def test_held_rows_keep_only_held_priced_unique_rows():
    rows = [
        _srow("20260929", "005930", 276000),
        _srow("20260929", "000660", "1,833,000"),
        _srow("20260929", "006400", 0),  # 종가 0 — 버린다
        _srow("20260929", "999990", 10),  # 보유 아님
        _srow("20260929", "035720", 5, TDD_CLSPRC=""),  # 가격 없음
        _srow("20260928", "005930", 1),  # 다른 기준일 행
    ]
    got = krx_stock_store.held_rows(
        rows, bas_dd="20260929", tickers=["005930", "000660", "006400"]
    )
    assert [(r.date, r.ticker, r.close) for r in got] == [
        ("2026-09-29", "000660", 1833000.0),
        ("2026-09-29", "005930", 276000.0),
    ]
    dup = [_srow("20260929", "005930", 1), _srow("20260929", "005930", 2)]
    assert krx_stock_store.held_rows(dup, bas_dd="20260929", tickers=["005930"]) == []


def test_store_uses_its_own_table_and_reader_is_read_only(tmp_path):
    db = tmp_path / "m.sqlite"
    krx_stock_store.upsert(
        [krx_stock_store.StockRow("2026-09-29", "005930", 276000.0)], db_path=db
    )
    assert _tables(db) == ["krx_stock_daily_price_unadjusted"]  # ETF 표 · FDR 표 0
    present, closes = krx_stock_store.read_holdings_stock_prices(
        ["005930", "000660"], ["2026-09-29"], db_path=db
    )
    assert present == {"005930"} and closes == {"005930": {"2026-09-29": 276000.0}}

    missing = tmp_path / "none.sqlite"
    with pytest.raises(sqlite3.Error):
        krx_stock_store.read_holdings_stock_prices(["005930"], [T1], db_path=missing)
    assert not missing.exists()
    empty = tmp_path / "empty.sqlite"
    sqlite3.connect(empty).close()
    with pytest.raises(sqlite3.Error):
        krx_stock_store.read_holdings_stock_prices(["005930"], [T1], db_path=empty)
    assert _tables(empty) == []
    assert krx_stock_store.read_holdings_stock_prices([], [T1], db_path=missing) == (
        set(),
        {},
    )


def test_default_source_reads_stock_table_read_only(tmp_path):
    db = tmp_path / "m.sqlite"
    krx_stock_store.upsert(
        [krx_stock_store.StockRow(T1, "005930", 276000.0)], db_path=db
    )
    src = hpb.default_source(meta_dir=tmp_path / "no_meta", db_path=db)
    assert src.stock_prices(["005930"], [T1]) == (
        {"005930"},
        {"005930": {T1: 276000.0}},
    )
    empty = tmp_path / "empty.sqlite"
    sqlite3.connect(empty).close()
    with pytest.raises(sqlite3.Error):
        hpb.default_source(db_path=empty).stock_prices(["005930"], [T1])
    assert _tables(empty) == []


# ── 곁 작업 — 목표일 · 창 ─────────────────────────────────────────────────────────


def test_first_run_fills_target_then_window_and_keeps_only_held_rows(env):
    clock = kb.Clock(8, 12, 0)
    f = _StockFetch(clock)
    out = _stock_sync(env, clock, f)
    window = _window(env)
    rest = [d for d in window if d != T1]
    assert len(window) == 31
    assert f.calls[0] == T1_BAS  # 목표일 먼저(ledger 밖)
    assert f.calls[1:] == [d.replace("-", "") for d in rest]  # 창은 오래된 날부터
    assert out["status"] == krx_stock_sync.STATUS_OK and out["stopped"] is None
    assert out["held_tickers"] == 4
    assert [a["result"] for a in out["target_attempts"]] == ["ok"]
    assert sorted(out["filled"]) == sorted(window)
    present, closes = krx_stock_store.read_holdings_stock_prices(
        HELD + ["999990"], window, db_path=env["db"]
    )
    assert present == set(STOCKS)  # ETF · 보유 아닌 종목은 저장하지 않는다
    assert all(len(closes[t]) == 31 for t in STOCKS)
    # 목표일은 ledger 에 넣지 않는다(ETF 목표일 시도와 같다) — 창 날짜만 하루 1회.
    assert _ledger(env)["calls"] == {d: 1 for d in rest}
    # 다음 실행 — 다 차 있으면 조회 0회.
    f2 = _StockFetch(clock)
    again = _stock_sync(env, clock, f2)
    assert f2.calls == [] and again["status"] == krx_stock_sync.STATUS_OK


def test_no_held_kospi_stock_ends_the_run_after_one_call(env):
    """보유 코스피 개별주 0 — 응답에 보유 행이 없으면 그 실행을 끝낸다(남은 칸 · 창 호출 0)."""
    clock = kb.Clock(8, 10, 20)
    f = _StockFetch(clock, lambda b, i: _market(b)[3:])  # 보유 개별주 없음
    out = _stock_sync(env, clock, f, **_scheduled(clock))
    assert f.calls == [T1_BAS]
    assert out["status"] == krx_stock_sync.STATUS_NO_HELD_KOSPI_STOCKS
    assert out["stopped"] == krx_stock_sync.R_NO_HELD_ROWS
    assert clock.sleeps == []  # 남은 칸(08:15 · 08:20 · 08:24)을 기다리지 않는다
    assert krx_stock_store.stored_dates(db_path=env["db"]) == set()
    assert not krx_stock_sync.ledger_path_for(env["db"]).exists()
    # 같은 날 09:20 · 수동 실행은 목표일만 1회(ledger 밖) — 창은 부르지 않는다.
    c2 = kb.Clock(9, 20, 0)
    f2 = _StockFetch(c2, lambda b, i: _market(b)[3:])
    again = _stock_sync(env, c2, f2, reinforcement=True)
    assert f2.calls == [T1_BAS]
    assert again["status"] == krx_stock_sync.STATUS_NO_HELD_KOSPI_STOCKS


def test_window_no_held_rows_also_ends_the_run(env):
    """목표일이 공개 전이어도 창 어느 날의 응답에 보유 행이 없으면 끝낸다(헛조회 방지)."""
    window = _window(env)
    clock = kb.Clock(9, 20, 0)
    f = _StockFetch(clock, lambda b, i: [] if b == T1_BAS else _market(b)[3:])
    out = _stock_sync(env, clock, f)
    assert f.calls == [T1_BAS, window[0].replace("-", "")]
    assert out["status"] == krx_stock_sync.STATUS_NO_HELD_KOSPI_STOCKS
    assert _ledger(env)["calls"] == {window[0]: 1}

    # 목표일은 저장된 날 — 실행은 끝내지만 보유 0 이 아니다(창 앞쪽이 상장 전 등) → incomplete.
    env2 = _fresh(env, "d2")
    c2 = kb.Clock(9, 20, 0)
    f2 = _StockFetch(c2, lambda b, i: _market(b) if b == T1_BAS else _market(b)[3:])
    out2 = _stock_sync(env2, c2, f2)
    assert f2.calls == [T1_BAS, window[0].replace("-", "")]
    assert out2["status"] == krx_stock_sync.STATUS_INCOMPLETE
    assert out2["stopped"] == krx_stock_sync.R_NO_HELD_ROWS


def test_window_fills_even_when_target_is_not_stored_and_target_retries(env):
    """PLAN §2-1 3 — 목표일 저장 여부와 무관하게 창을 채운다 · 목표일은 다음 칸에 다시(시각표)."""
    window = _window(env)
    clock = kb.Clock(8, 10, 20)
    f = _StockFetch(clock, lambda b, i: [] if (b == T1_BAS and i == 1) else _market(b))
    out = _stock_sync(env, clock, f, **_scheduled(clock))
    rest = [d.replace("-", "") for d in window if d != T1]
    # 08:10 목표일 공개 전 → 창 30날 → 08:15 목표일.
    assert f.calls == [T1_BAS] + rest + [T1_BAS]
    assert [a["result"] for a in out["target_attempts"]] == ["not_published", "ok"]
    assert out["target_attempts"][1]["at_kst"][11:19] == "08:15:00"
    assert out["status"] == krx_stock_sync.STATUS_OK
    assert out["slots"] == ["08:10:20", "08:15:00", "08:20:00", "08:24:00"]


def test_target_fetch_error_skips_the_window_until_next_slot(env):
    """목표일 조회가 원천 오류면 그 칸에서는 창을 부르지 않는다(불통 중 ledger 소모 방지)."""
    clock = kb.Clock(8, 10, 20)
    f = _StockFetch(
        clock, lambda b, i: httpx.ReadTimeout("t") if i == 1 else _market(b)
    )
    out = _stock_sync(env, clock, f, **_scheduled(clock))
    assert f.calls[:2] == [T1_BAS, T1_BAS] and len(f.calls) == 32
    assert out["target_attempts"][0]["transient"] is True
    assert out["status"] == krx_stock_sync.STATUS_OK

    # 한 칸(09:20 · 수동)뿐인데 원천 오류 — 창 호출 0 · ledger 없음 · 멈춤 = 원천 오류.
    env2 = _fresh(env, "d2")
    c2 = kb.Clock(9, 20, 0)
    f2 = _StockFetch(c2, lambda b, i: httpx.ConnectError("c"))
    out2 = _stock_sync(env2, c2, f2, reinforcement=True)
    assert f2.calls == [T1_BAS]
    assert out2["stopped"] == krx_backfill.STOP_FETCH_ERROR
    assert out2["status"] == krx_stock_sync.STATUS_INCOMPLETE
    assert not krx_stock_sync.ledger_path_for(env2["db"]).exists()


@pytest.mark.parametrize(
    "respond, result",
    [
        (lambda b, i: [], "not_published"),  # 공개 전 — 0행
        (
            lambda b, i: [_srow(b, t, TDD_CLSPRC="") for t in STOCKS],
            "not_published",
        ),  # 평일 휴장 — 가격 없는 행
        (lambda b, i: _market("19990104"), "basis_date_mismatch"),
    ],
    ids=["zero_rows", "holiday_rows", "other_basis"],
)
def test_unusable_responses_are_not_stored_and_not_ok(env, respond, result):
    clock = kb.Clock(8, 12, 0)
    f = _StockFetch(clock, respond)
    out = _stock_sync(env, clock, f)
    assert out["target_attempts"][0]["result"] == result
    assert out["failed"][0]["result"] == result
    assert out["status"] == krx_stock_sync.STATUS_INCOMPLETE
    assert out["stopped"] == krx_stock_sync.STOP_SLOTS_EXHAUSTED
    assert out["filled"] == []
    assert krx_stock_store.stored_dates(db_path=env["db"]) == set()


def test_window_fetch_error_ends_the_slot_and_next_slot_continues(env):
    window = _window(env)
    clock = kb.Clock(8, 12, 0)
    f = _StockFetch(
        clock, lambda b, i: httpx.ConnectError("c") if i == 2 else _market(b)
    )
    one = _stock_sync(env, clock, f)  # 한 칸
    assert f.calls == [T1_BAS, window[0].replace("-", "")]
    assert one["stopped"] == krx_backfill.STOP_FETCH_ERROR
    assert one["failed"][0]["transient"] is True
    assert one["status"] == krx_stock_sync.STATUS_INCOMPLETE

    # 시각표 — 다음 칸이 남은 날을 잇는다(이번 실행에서 부른 날은 다시 다루지 않는다 · 보강 없음).
    env2 = _fresh(env, "d2")
    c2 = kb.Clock(8, 10, 20)
    f2 = _StockFetch(c2, lambda b, i: httpx.ConnectError("c") if i == 2 else _market(b))
    out = _stock_sync(env2, c2, f2, **_scheduled(c2))
    assert len(f2.calls) == 31 and f2.calls.count(window[0].replace("-", "")) == 1
    # 이번 실행에서 부른 날은 다음 칸이 다시 다루지 않는다(`called` · `failed` 에 있다).
    assert out["skipped_called_today"] == [] and out["called"][0] == window[0]
    assert out["status"] == krx_stock_sync.STATUS_INCOMPLETE
    assert (
        out["stopped"] is None
    )  # 이번 실행에서 할 일은 끝났다(빈 날은 09:20 보강 대상)
    assert _ledger(env2)["retryable"] == [window[0]]


def test_deadline_stops_new_calls(env):
    window = _window(env)
    # 08:27 마감 — 새 호출을 시작하지 않는다.
    clock = kb.Clock(8, 26, 57)
    f = _StockFetch(clock, cost_seconds=1)
    out = _stock_sync(env, clock, f, slots=[clock()], deadline=_at(8, 27))
    # 08:26:57 T-1 → 08:26:58 창 첫날 → 08:26:59 둘째 날 → 08:27:00 마감.
    assert f.calls == [T1_BAS] + [d.replace("-", "") for d in window[:2]]
    assert out["stopped"] == krx_backfill.STOP_DEADLINE

    # 마감 뒤 도래한 칸은 부르지 않는다.
    env2 = _fresh(env, "d2")
    c2 = kb.Clock(8, 27, 5)
    f2 = _StockFetch(c2)
    task = _task(env2, c2, f2, slots=[_at(8, 24)], deadline=_at(8, 27))
    task.run_due(c2())
    assert f2.calls == [] and task.next_slot() is None
    assert task.summary()["stopped"] == krx_backfill.STOP_DEADLINE


def test_transient_failure_is_reinforced_once_at_0920_permanent_is_not(env):
    window = _window(env)
    first_old = window[0].replace("-", "")
    second_old = window[1].replace("-", "")
    clock = kb.Clock(8, 12, 0)

    def _respond(b, i):
        if b == first_old:
            return _http_error(503)  # 일시 오류 → 그 칸 끝 · 보강 대상
        return _market(b)

    f = _StockFetch(clock, _respond)
    out = _stock_sync(env, clock, f)
    assert out["stopped"] == krx_backfill.STOP_FETCH_ERROR
    assert _ledger(env)["retryable"] == [window[0]]

    # 09:20 보강 — 일시 오류 날짜는 한 번 더 · 아직 안 부른 날은 처음으로.
    c2 = kb.Clock(9, 20, 0)
    f2 = _StockFetch(
        c2, lambda b, i: _http_error(404) if b == second_old else _market(b)
    )
    out2 = _stock_sync(env, c2, f2, reinforcement=True)
    assert f2.calls == [
        first_old,
        second_old,
    ]  # 목표일은 이미 저장 — 다시 부르지 않는다
    assert out2["retried"] == [window[0]] and out2["filled"] == [window[0]]
    # 404 — 영구 실패(보강 대상 아님). HTTP 예외라 원천 오류로 보고 그 칸을 끝낸다(ETF 와 같다).
    assert out2["failed"][0]["transient"] is False
    assert out2["stopped"] == krx_backfill.STOP_FETCH_ERROR
    led = _ledger(env)
    assert led["calls"][window[0]] == 2 and "retryable" not in led

    # 같은 날 다시 — 404 날짜 · 2회 부른 날짜는 부르지 않는다 · 안 부른 날만 처음으로.
    krx_stock_store.delete_date(window[0], db_path=env["db"])  # 2회 상한을 시험한다
    c3 = kb.Clock(10, 5, 0)
    f3 = _StockFetch(c3)
    out3 = _stock_sync(env, c3, f3, reinforcement=True)
    assert first_old not in f3.calls and second_old not in f3.calls
    assert window[0] in out3["skipped_called_today"]
    assert window[1] in out3["skipped_called_today"]
    assert out3["retried"] == []


def test_stock_ledger_is_separate_from_etf_ledger(env):
    """ETF 채우기가 같은 날짜를 불렀어도 개별주는 막히지 않는다(그 반대도)."""
    etf_ledger = krx_backfill.ledger_path_for(env["db"])
    krx_backfill.write_ledger(etf_ledger, TODAY.isoformat(), {T1: 1, "2026-09-18": 1})
    clock = kb.Clock(8, 12, 0)
    f = _StockFetch(clock)
    _stock_sync(env, clock, f)
    assert T1_BAS in f.calls and "20260918" in f.calls
    assert json.loads(etf_ledger.read_text("utf-8")) == {
        "date_kst": TODAY.isoformat(),
        "calls": {T1: 1, "2026-09-18": 1},
    }
    assert (
        krx_stock_sync.ledger_path_for(env["db"]).name
        == "krx_stock_backfill_ledger.json"
    )


@pytest.mark.parametrize(
    "setup, status",
    [
        (None, krx_stock_sync.STATUS_HOLDINGS_MISSING),
        ("{broken", "holdings_unreadable:JSONDecodeError"),
        (json.dumps({"rows": []}), "holdings_unreadable:HoldingsValidationError"),
    ],
    ids=["missing", "corrupt", "no_holdings_key"],
)
def test_holdings_file_problems_make_no_call(env, setup, status):
    if setup is not None:
        holdings_module.HOLDINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        holdings_module.HOLDINGS_FILE.write_text(setup, encoding="utf-8")
    clock = kb.Clock(8, 12, 0)
    f = _StockFetch(clock)
    out = _stock_sync(env, clock, f, tickers=None)
    assert f.calls == [] and out["status"] == status


@pytest.mark.parametrize(
    "over, status",
    [
        ({"tickers": []}, krx_stock_sync.STATUS_NO_HOLDINGS),
        ({"key": None}, krx_sync.STATUS_NO_API_KEY),
        ({"target_iso": None}, krx_stock_sync.STATUS_NO_TARGET_DATE),
        ({"slots": []}, krx_stock_sync.STATUS_SKIPPED_BEFORE_OPEN),
    ],
    ids=["no_tickers", "no_key", "no_target", "before_open"],
)
def test_nothing_to_call_records_status_only(env, over, status):
    clock = kb.Clock(8, 12, 0)
    f = _StockFetch(clock)
    task = _task(env, clock, f, **over)
    assert task.next_slot() is None
    _drive(task, clock)
    out = task.summary()
    assert f.calls == [] and out["status"] == status and out["stopped"] is None


def test_live_guard_blocks_default_stock_fetcher(env):
    """`fetch` 없이 부르면 conftest 가드가 막는다 — 시도 기록은 fetch_error · AssertionError."""
    clock = kb.Clock(8, 12, 0)
    out = _stock_sync(env, clock, None)
    entry = out["target_attempts"][0]
    assert entry["result"] == "fetch_error"
    assert entry["error_type"] == "AssertionError"
    assert entry["transient"] is False
    assert krx_sync.KRX_STOCK_DAILY_URL.endswith("/sto/stk_bydd_trd")


# ── KRX 단계 연결 ─────────────────────────────────────────────────────────────


def _save_holdings():
    holdings_module.save(
        [
            holdings_module.Holding(ticker=t, quantity=1.0, avg_buy_price=1.0, name=t)
            for t in HELD
        ]
    )


@pytest.fixture
def krx_env(tmp_path):
    cal = kb._calendar(tmp_path)
    db = tmp_path / "m.sqlite"
    kb._seed(db, kb._window_before_t1(cal))
    return {
        "tmp": tmp_path,
        "cal": cal,
        "db": db,
        "cpath": tmp_path / "consistency.json",
        "env": kb._env(tmp_path),
        "csv": kb._csv(tmp_path),
    }


def _krx_sync(e, clock, etf_fetch, stock_fetch, **kw):
    args = dict(
        today=TODAY,
        consistency_path=e["cpath"],
        official_csv_path=e["csv"],
        db_path=e["db"],
        env_path=e["env"],
        calendar_dir=e["cal"],
        fetcher=etf_fetch,
        stock_fetcher=stock_fetch,
        clock=clock,
        sleep=clock.sleep,
        backfill_ledger_path=e["tmp"] / "etf_ledger.json",
        required_tickers=kb.REPS,
    )
    args.update(kw)
    return krx_target_sync.sync_krx_target(**args)


def test_0810_etf_goes_first_then_stock_task_and_etf_table_untouched(krx_env):
    _save_holdings()
    clock = kb.Clock(8, 10, 20)
    order: list[str] = []
    etf = kb.Fetcher(clock, lambda b, i: (order.append("etf"), kb._rows(b))[1])
    stock = _StockFetch(clock, lambda b, i: (order.append("stock"), _market(b))[1])
    out = _krx_sync(krx_env, clock, etf, stock)
    assert out["status"] == krx_target_sync.STATUS_OK
    assert order[0] == "etf" and order.count("etf") == 1  # ETF 창은 이미 차 있다
    assert stock.calls[0] == T1_BAS
    hs = out["holdings_stocks"]
    assert hs["status"] == krx_stock_sync.STATUS_OK and hs["held_tickers"] == 4
    assert hs["mode"] == krx_target_sync.MODE_SCHEDULED
    assert hs["slots"] == ["08:10:20", "08:15:00", "08:20:00", "08:24:00"]
    assert out["representatives"]["status"] == "ok"
    assert (
        clock.sleeps == []
    )  # 할 일을 다 하면 남은 칸(08:15 ~ 08:24)을 기다리지 않는다
    # ETF 표에는 개별주 행이 없다.
    assert krx_store.closes_on([T1], db_path=krx_env["db"])[T1].keys() == set(
        kb.TICKERS
    )


def test_stock_task_runs_on_timetable_even_when_etf_t1_not_obtained(krx_env):
    """PLAN §2-1 2 — ETF 와 독립. ETF T-1 을 끝내 못 받은 날도 개별주는 시각표대로 돈다."""
    _save_holdings()
    clock = kb.Clock(8, 10, 20)
    etf = kb.Fetcher(clock, lambda b, i: [])
    stock = _StockFetch(
        clock, lambda b, i: [] if (b == T1_BAS and i == 1) else _market(b)
    )
    out = _krx_sync(krx_env, clock, etf, stock)
    assert out["status"] == krx_target_sync.STATUS_TARGET_NOT_OBTAINED
    # ETF 시각표는 그대로(같은 시각이면 ETF 가 먼저).
    assert [c[0] for c in etf.calls] == ["08:10:20", "08:15:00", "08:20:00", "08:24:00"]
    hs = out["holdings_stocks"]
    assert [a["at_kst"][11:16] for a in hs["target_attempts"]] == ["08:10", "08:15"]
    assert hs["target_attempts"][1]["at_kst"][11:19] > "08:15:00"  # ETF 08:15 뒤
    assert hs["status"] == krx_stock_sync.STATUS_OK
    assert krx_stock_store.stored_dates(db_path=krx_env["db"]) == set(_window(krx_env))


def test_0920_already_loaded_reinforces_stock_date_without_etf_call(krx_env):
    _save_holdings()
    window = _window(krx_env)
    old = window[0].replace("-", "")
    clock = kb.Clock(8, 10, 20)
    etf = kb.Fetcher(clock, lambda b, i: kb._rows(b))
    stock = _StockFetch(
        clock, lambda b, i: httpx.ReadTimeout("t") if b == old else _market(b)
    )
    first = _krx_sync(krx_env, clock, etf, stock)
    hs1 = first["holdings_stocks"]
    assert hs1["failed"][0]["date"] == window[0] and hs1["failed"][0]["transient"]
    assert stock.calls.count(old) == 1 and len(stock.calls) == 31  # 08:15 칸이 이었다
    assert hs1["status"] == krx_stock_sync.STATUS_INCOMPLETE

    c2 = kb.Clock(9, 20, 0)
    etf2 = kb.Fetcher(c2, lambda b, i: pytest.fail("09:20 ETF 재조회 없음"))
    stock2 = _StockFetch(c2)
    out = _krx_sync(
        krx_env, c2, etf2, stock2, max_attempts=1, backfill_reinforcement=True
    )
    assert out["mode"] == krx_target_sync.MODE_ALREADY_LOADED
    assert etf2.calls == []
    assert stock2.calls == [old] and out["holdings_stocks"]["retried"] == [window[0]]
    assert out["holdings_stocks"]["mode"] == krx_target_sync.MODE_SINGLE
    assert out["holdings_stocks"]["status"] == krx_stock_sync.STATUS_OK


def test_before_open_stage_makes_no_stock_call(krx_env):
    _save_holdings()
    clock = kb.Clock(7, 59, 0)
    stock = _StockFetch(clock)
    out = _krx_sync(
        krx_env, clock, kb.Fetcher(clock, lambda b, i: pytest.fail("x")), stock
    )
    assert stock.calls == []
    assert out["holdings_stocks"]["status"] == krx_stock_sync.STATUS_SKIPPED_BEFORE_OPEN


# ── 배치 기록 ─────────────────────────────────────────────────────────────────


@pytest.fixture
def batch(monkeypatch, tmp_path):
    import scripts.run_oci_market_data_batch as batch

    monkeypatch.setattr(mdb, "MARKET_DATA_BATCH_STATE_PATH", tmp_path / "bs.json")
    monkeypatch.setattr(
        mdb, "KRX_REINFORCEMENT_STATE_PATH", tmp_path / "reinforce.json"
    )
    monkeypatch.setattr(batch, "_kst_today", lambda: TODAY)
    return batch


def test_0810_batch_state_and_0920_record_carry_stock_result(
    batch, monkeypatch, tmp_path
):
    from tests import test_poc3_02d_ops03_consumer_isolation as ci

    ci._stub_price_stages(monkeypatch, batch, tmp_path)
    hs = {"status": "ok", "called": [T1], "calls_today": {T1: 1}}

    seen: list = []

    def _krx(**kw):
        seen.append(kw.get("backfill_reinforcement"))
        return {
            "status": "ok",
            "mode": "scheduled",
            "target_date": T1,
            "basis_date": T1_BAS,
            "attempts": [{"result": "ok"}],
            "consistency_status": "ok",
            "refresh_due": False,
            "holdings_stocks": hs,
        }

    monkeypatch.setattr(krx_target_sync, "sync_krx_target", _krx)
    batch.run(mode="run")
    assert mdb.read_batch_state()["krx_holdings_stocks"] == hs

    monkeypatch.setattr(
        batch, "_now", lambda: datetime(2026, 9, 30, 9, 20, tzinfo=kb.KST)
    )
    batch.run_krx_only()
    assert mdb.read_krx_reinforcement_state()["krx_holdings_stocks"] == hs
    # 실제 호출 자리 — 08:10 은 보강 표시 False · 09:20 회차는 True(ETF · 개별주 ledger 공통).
    assert seen == [False, True]


def test_run_krx_only_passes_stock_reinforcement_through_real_sync(
    batch, monkeypatch, tmp_path
):
    """실제 sync 경로 — 09:20 보강 표시가 개별주 채우기까지 간다."""
    e = {"cal": kb._calendar(tmp_path), "db": tmp_path / "m.sqlite"}
    kb._seed(e["db"], kb._window_before_t1(e["cal"]) + [T1])
    _save_holdings()
    window = _window(e)
    krx_stock_store.upsert(
        [krx_stock_store.StockRow(d, t, 1.0) for d in window[1:] for t in STOCKS],
        db_path=e["db"],
    )
    krx_backfill.write_ledger(
        krx_stock_sync.ledger_path_for(e["db"]),
        TODAY.isoformat(),
        {window[0]: 1},
        {window[0]},
    )
    calls: list[str] = []

    def _stock(bas, key):
        calls.append(bas)
        return _market(bas)

    t = datetime(2026, 9, 30, 9, 20, tzinfo=kb.KST)
    real = krx_target_sync.sync_krx_target
    monkeypatch.setattr(
        krx_target_sync,
        "sync_krx_target",
        functools.partial(
            real,
            db_path=e["db"],
            env_path=kb._env(tmp_path),
            calendar_dir=e["cal"],
            fetcher=lambda b, k: kb._rows(b),
            stock_fetcher=_stock,
            clock=lambda: t,
            sleep=lambda s: pytest.fail("09:20 보강은 기다리지 않는다"),
        ),
    )
    monkeypatch.setattr(batch, "_now", lambda: t)  # 09:20 정기 회차
    batch.run_krx_only()
    assert calls == [window[0].replace("-", "")]
    rec = mdb.read_krx_reinforcement_state()["krx_holdings_stocks"]
    assert rec["retried"] == [window[0]] and rec["status"] == krx_stock_sync.STATUS_OK


# ── 독립 검토 보강 사례(개별주 경로 · 저장 · 곁 작업 격리) ──────────────────────────


def test_stock_ledger_unreadable_today_skips_the_window_only(env):
    path = krx_stock_sync.ledger_path_for(env["db"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{broken", "utf-8")
    now = datetime(2026, 9, 30, 8, 10, tzinfo=kb.KST).timestamp()
    import os

    os.utime(path, (now, now))
    clock = kb.Clock(8, 12, 0)
    f = _StockFetch(clock)
    out = _stock_sync(env, clock, f)
    assert f.calls == [T1_BAS]  # 목표일은 ledger 밖 — 창은 부르지 않는다
    assert out["stopped"] == krx_backfill.STOP_LEDGER_UNREADABLE
    assert out["status"] == krx_stock_sync.STATUS_INCOMPLETE


def _store_target(env):
    krx_stock_store.upsert(
        [krx_stock_store.StockRow(T1, t, 1.0) for t in STOCKS], db_path=env["db"]
    )


def test_stock_reinforcement_run_does_not_create_retryable(env):
    _store_target(env)
    window = _window(env)
    clock = kb.Clock(9, 20, 0)
    f = _StockFetch(clock, lambda b, i: httpx.ReadTimeout("t"))
    out = _stock_sync(env, clock, f, reinforcement=True)
    assert f.calls == [window[0].replace("-", "")]
    assert out["failed"][0]["transient"] is True
    assert _ledger(env) == {"date_kst": TODAY.isoformat(), "calls": {window[0]: 1}}


def test_stock_pre_call_ledger_write_failure_makes_no_call(env, monkeypatch):
    clock = kb.Clock(8, 12, 0)
    first = _stock_sync(
        env,
        clock,
        _StockFetch(
            clock, lambda b, i: httpx.ReadTimeout("t") if i == 2 else _market(b)
        ),
    )
    assert first["failed"][0]["transient"] is True
    before = _ledger(env)

    def _fail(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(krx_backfill, "_write_calls", _fail)
    c2 = kb.Clock(9, 20, 0)
    f2 = _StockFetch(c2)
    out = _stock_sync(env, c2, f2, reinforcement=True)
    assert f2.calls == [] and out["stopped"] == "ledger_error:OSError"
    assert _ledger(env) == before
    assert out["calls_today"] == before["calls"]  # 메모리 기록도 앞 값으로 되돌렸다


def test_stock_readback_mismatch_deletes_the_date(env, monkeypatch):
    monkeypatch.setattr(
        krx_stock_store, "closes_on_date", lambda date, **kw: {"005930": -1.0}
    )
    clock = kb.Clock(8, 12, 0)
    out = _stock_sync(env, clock, _StockFetch(clock))
    assert out["target_attempts"][0]["result"] == "readback_mismatch"
    assert out["failed"][0]["result"] == "readback_mismatch"
    monkeypatch.undo()
    assert krx_stock_store.stored_dates(db_path=env["db"]) == set()


def test_stock_store_errors_are_recorded_not_raised(env, monkeypatch):
    def _locked(*a, **k):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(krx_stock_store, "upsert", _locked)
    clock = kb.Clock(8, 12, 0)
    out = _stock_sync(env, clock, _StockFetch(clock))
    assert out["failed"][0]["result"] == "store_error"
    assert out["failed"][0]["error_type"] == "OperationalError"

    monkeypatch.setattr(krx_stock_store, "stored_dates", _locked)
    f2 = _StockFetch(clock)
    out2 = _stock_sync(env, clock, f2)
    assert f2.calls == []
    assert out2["status"] == krx_stock_sync.STATUS_INCOMPLETE
    assert out2["stopped"] == "store_error:OperationalError"


def test_stock_task_build_error_does_not_change_etf_result(krx_env, monkeypatch):
    _save_holdings()

    def _boom(*a, **k):
        raise RuntimeError("stock path bug")

    monkeypatch.setattr(krx_stock_sync, "HoldingsStockTask", _boom)
    clock = kb.Clock(8, 10, 20)
    out = _krx_sync(
        krx_env, clock, kb.Fetcher(clock, lambda b, i: kb._rows(b)), _StockFetch(clock)
    )
    assert out["status"] == krx_target_sync.STATUS_OK
    assert out["basis_date"] == T1_BAS and out["representatives"]["status"] == "ok"
    assert out["holdings_stocks"] == {"status": "unexpected:RuntimeError"}


class _Side:
    """KOSPI 재시도 자리의 가짜 곁 작업 — 도래한 칸을 기록한다."""

    def __init__(self, slots, boom=False):
        self.pending, self.ran, self.boom = list(slots), [], boom

    def next_slot(self):
        return self.pending[0] if self.pending else None

    def run_due(self, now):
        if self.boom:
            raise RuntimeError("side bug")
        due = [s for s in self.pending if s <= now]
        if due:
            self.pending = [s for s in self.pending if s > now]
            self.ran.append(due[-1].strftime("%H:%M"))


def test_stock_step_error_is_recorded_and_other_side_task_keeps_running(
    krx_env, monkeypatch
):
    _save_holdings()

    def _boom(self, at):
        raise RuntimeError("stock step bug")

    monkeypatch.setattr(krx_stock_sync.HoldingsStockTask, "_step", _boom)
    clock = kb.Clock(8, 10, 20)
    side = _Side([_at(8, 15), _at(8, 20)])
    out = _krx_sync(
        krx_env,
        clock,
        kb.Fetcher(clock, lambda b, i: kb._rows(b)),
        _StockFetch(clock),
        side_task=side,
    )
    assert out["status"] == krx_target_sync.STATUS_OK
    assert out["holdings_stocks"]["stopped"] == "unexpected:RuntimeError"
    assert side.ran == ["08:15", "08:20"]


def test_other_side_task_error_does_not_stop_the_stock_task(krx_env):
    _save_holdings()
    clock = kb.Clock(8, 10, 20)
    stock = _StockFetch(
        clock, lambda b, i: [] if (b == T1_BAS and i == 1) else _market(b)
    )
    out = _krx_sync(
        krx_env,
        clock,
        kb.Fetcher(clock, lambda b, i: kb._rows(b)),
        stock,
        side_task=_Side([_at(8, 12)], boom=True),
    )
    assert out["status"] == krx_target_sync.STATUS_OK
    hs = out["holdings_stocks"]
    assert [a["result"] for a in hs["target_attempts"]] == ["not_published", "ok"]
    assert hs["status"] == krx_stock_sync.STATUS_OK


def test_stock_fill_starts_after_etf_judgement_and_shares_deadline(krx_env):
    """개별주 첫 호출 때 ETF 정합성 판정 파일이 이미 있다 · 08:27 마감을 같이 쓴다."""
    _save_holdings()
    seen = {}
    clock = kb.Clock(8, 26, 55)

    def _respond(b, i):
        if i == 1:
            seen["consistency_written"] = krx_env["cpath"].exists()
        return _market(b)

    stock = _StockFetch(clock, _respond)
    out = _krx_sync(krx_env, clock, kb.Fetcher(clock, lambda b, i: kb._rows(b)), stock)
    assert out["status"] == krx_target_sync.STATUS_OK
    assert seen == {"consistency_written": True}
    hs = out["holdings_stocks"]
    assert hs["stopped"] == krx_backfill.STOP_DEADLINE  # 08:27 — 창을 다 못 채움
    assert stock.calls[0] == T1_BAS and len(stock.calls) < 31


# ── 재작업 검토 반영(다음 칸에서 멈춤 · 시각 다시 읽기 · ETF 예외 로그) ──────────────


def test_slow_stock_window_fill_does_not_push_back_etf_attempts(krx_env):
    """ETF 가 08:10 에 못 받은 날 — 개별주 창 채우기가 길어도 다음 칸에서 멈추고 그 칸에서 잇는다.

    호출 1회는 끊을 수 없으니 ETF 시도는 많아야 개별주 호출 1회만큼 늦다.
    """
    _save_holdings()
    clock = kb.Clock(8, 10, 20)
    etf = kb.Fetcher(clock, lambda b, i: [])  # ETF 는 끝내 공개 전
    stock = _StockFetch(clock, cost_seconds=20)
    out = _krx_sync(krx_env, clock, etf, stock)
    etf_at = [c[0] for c in etf.calls]
    assert len(etf_at) == 4
    for got, slot in zip(etf_at[1:], ["08:15:00", "08:20:00", "08:24:00"]):
        late = kb.datetime.strptime(got, "%H:%M:%S") - kb.datetime.strptime(
            slot, "%H:%M:%S"
        )
        assert late.total_seconds() < 20
    hs = out["holdings_stocks"]
    assert hs["status"] == krx_stock_sync.STATUS_OK and len(stock.calls) == 31


def test_stock_slot_rereads_the_clock_after_a_slow_side_task(krx_env):
    """같은 칸의 앞 곁 작업(KOSPI)이 오래 걸리면 개별주는 시각을 다시 읽는다 — 08:27 뒤 새 시도 0."""
    _save_holdings()
    window = _window(krx_env)
    krx_stock_store.upsert(
        [
            krx_stock_store.StockRow(d, t, 1.0)
            for d in window
            if d != T1
            for t in STOCKS
        ],
        db_path=krx_env["db"],
    )
    clock = kb.Clock(8, 10, 20)
    started: list[str] = []

    def _respond(b, i):
        started.append((clock() - kb.timedelta(seconds=1)).strftime("%H:%M:%S"))
        return []  # 개별주 목표일도 공개 전

    class _SlowSide:
        def __init__(self):
            self.pending = [_at(8, 24)]

        def next_slot(self):
            return self.pending[0] if self.pending else None

        def run_due(self, now):
            if self.pending and self.pending[0] <= now:
                self.pending = []
                clock.t += kb.timedelta(seconds=200)  # 08:24 칸에서 200초

    out = _krx_sync(
        krx_env,
        clock,
        kb.Fetcher(clock, lambda b, i: []),
        _StockFetch(clock, _respond),
        side_task=_SlowSide(),
    )
    hs = out["holdings_stocks"]
    assert started == ["08:10:22", "08:15:02", "08:20:02"]
    assert [a["at_kst"][11:19] for a in hs["target_attempts"]] == started
    assert hs["stopped"] == krx_backfill.STOP_DEADLINE


def test_etf_stage_exception_logs_the_stock_summary(krx_env, monkeypatch):
    """ETF 단계가 예외로 끝나면 배치 기록에 개별주가 실리지 않는다 — 대신 로그에 남긴다."""
    _save_holdings()

    def _boom(*a, **k):
        raise RuntimeError("judge bug")

    monkeypatch.setattr(krx_sync, "judge_and_save_consistency", _boom)
    lines: list[str] = []

    class _Log:
        def info(self, msg, *args):
            lines.append(msg % args)

    clock = kb.Clock(8, 10, 20)
    stock = _StockFetch(clock)
    with pytest.raises(RuntimeError):
        _krx_sync(
            krx_env,
            clock,
            kb.Fetcher(clock, lambda b, i: kb._rows(b)),
            stock,
            logger=_Log(),
        )
    assert len(stock.calls) == 31
    assert any(
        "개별주 곁 작업(ETF 단계 예외): status=ok" in line for line in lines
    ), lines


def test_last_stop_is_per_slot(env):
    """앞 칸의 원천 오류가 뒤 칸 결과로 남지 않는다(마지막 칸 기준)."""
    clock = kb.Clock(8, 10, 20)
    f = _StockFetch(
        clock,
        lambda b, i: (
            httpx.ConnectError("c") if i == 1 else ([] if b == T1_BAS else _market(b))
        ),
    )
    out = _stock_sync(env, clock, f, **_scheduled(clock))
    assert [a["result"] for a in out["target_attempts"]] == [
        "fetch_error",
        "not_published",
        "not_published",
        "not_published",
    ]
    assert out["stopped"] == krx_stock_sync.STOP_SLOTS_EXHAUSTED
    assert out["status"] == krx_stock_sync.STATUS_INCOMPLETE
