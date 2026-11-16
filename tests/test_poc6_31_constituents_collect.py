"""POC6-31 STEP 1 — 구성종목 수집 기반(목표일 · 계열 · 상태 읽기 · 수집 작업).

판정 §1 · §5 사례: 연타 · 두 작업 겹친 요청 · 이전 구성일 뒤 새 자료 · 일부 실패 · 시간 초과 · 저장 잠김 ·
원천 기준일 미확인 · 10개씩 묶음 · 간격이 묶음 경계와 두 작업 사이에도 이어짐 · 재시작 뒤 상태 구별.
tmp DB · 가짜 수집기만 쓴다(라이브 DB · 외부 호출 0).
"""

from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app import etf_constituents_batch as B
from app import etf_constituents_status as ST
from app.collect_target_date import collect_target_date
from app.constituent_row_kind import CASH, DOMESTIC_STOCK, FOREIGN_STOCK, row_kind
from app.etf_constituents_fetcher import (
    NAVER_STOCK_SOURCE,
    FetchedConstituent,
    FetchResult,
)
from app.etf_constituents_store import (
    ConstituentRow,
    log_constituent_refresh,
    upsert_constituents,
)
from app.index_family import DJ_DIVIDEND_100, family_of

KST = timezone(timedelta(hours=9))


def _kst(y, m, d, hh, mm):
    return datetime(y, m, d, hh, mm, tzinfo=KST)


# ---------- 수집 목표일 ----------


@pytest.mark.parametrize(
    "now, expected",
    [
        (_kst(2026, 11, 13, 15, 29), "2026-11-12"),  # 금요일 마감 전 → 직전 거래일
        (_kst(2026, 11, 13, 15, 30), "2026-11-13"),  # 마감 시각부터 그날
        (_kst(2026, 11, 13, 23, 59), "2026-11-13"),
        (_kst(2026, 11, 14, 15, 7), "2026-11-13"),  # 토요일 → 직전 거래일(판정 §4 M1)
        (_kst(2026, 11, 16, 9, 0), "2026-11-13"),  # 월요일 장중 → 금요일
        (_kst(2026, 11, 16, 0, 30), "2026-11-13"),
    ],
)
def test_collect_target_date_weekday_rule(tmp_path, now, expected):
    assert collect_target_date(now, calendar_dir=tmp_path) == expected


def test_collect_target_date_uses_calendar_holiday(tmp_path):
    # 연도 캘린더가 있으면 그 파일이 거래일을 정한다 — 11/13 을 휴장으로 둔 가상 달력
    days = [f"2026-11-{d:02d}" for d in (10, 11, 12, 16, 17)]
    (tmp_path / "krx_trading_days_2026.csv").write_text(
        "date\n" + "\n".join(days) + "\n", encoding="utf-8"
    )
    assert (
        collect_target_date(_kst(2026, 11, 13, 16, 0), calendar_dir=tmp_path)
        == "2026-11-12"
    )
    assert (
        collect_target_date(_kst(2026, 11, 16, 15, 30), calendar_dir=tmp_path)
        == "2026-11-16"
    )


def test_collect_target_date_converts_utc():
    utc = datetime(2026, 11, 13, 6, 30, tzinfo=timezone.utc)  # = KST 15:30
    assert collect_target_date(utc, calendar_dir=Path("/nonexistent")) == "2026-11-13"


# ---------- 지수 계열 ----------


def test_family_confirmed_dow_jones_dividend_four_names():
    names = [
        "Dow Jones U.S. Dividend 100 Price Return Index",
        "Dow Jones U.S. Dividend 100 10% Premium Covered Call Index(Total Return)",
        "DowJones U.S. Dividend 100 7% Premium Covered Call 지수 (TR)",
        "DowJones U.S. Dividend 100 3% Premium Covered Call 지수 (TR)",
    ]
    assert {family_of(n) for n in names} == {DJ_DIVIDEND_100}


@pytest.mark.parametrize(
    "name, expected",
    [
        ("Nifty 50 Index", "Nifty 50 Index"),  # 같은 이름 → 같은 계열(규칙 그대로)
        ("  Nifty 50 Index ", "Nifty 50 Index"),
        (
            "Dow Jones U.S. Dividend 100 5% Premium Covered Call",
            "Dow Jones U.S. Dividend 100 5% Premium Covered Call",
        ),
        ("S&P 500", "S&P 500"),
        (None, None),
        ("", None),
    ],
)
def test_family_other_names_not_merged(name, expected):
    # 확인된 4개 밖의 이름은 비슷해도 합치지 않는다(이름 규칙 자동 합치기 없음)
    assert family_of(name) == expected


def test_row_kind_moved_keeps_poc6_30_research_names():
    from app import sector_constituents_comparison as C

    assert C.row_kind is row_kind
    assert row_kind({"isin": "KRD010010001", "market_type": "0"}, set()) == CASH
    assert (
        row_kind(
            {"isin": "KR7005930003", "market_type": "0", "ticker": "005930"}, set()
        )
        == DOMESTIC_STOCK
    )
    assert (
        row_kind(
            {"isin": "US5324571083", "market_type": "2", "name": "Eli Lilly"}, set()
        )
        == FOREIGN_STOCK
    )


# ---------- 공통 도구 ----------


def _rows(tk, asof, n=3):
    return [
        ConstituentRow(
            etf_ticker=tk,
            asof=asof,
            source=NAVER_STOCK_SOURCE,
            rank=i + 1,
            constituent_ticker=f"{i:06d}",
            constituent_name=f"주식{i}",
            weight_pct=10.0 - i,
            etf_name=None,
            constituent_key=f"{i:06d}",
        )
        for i in range(n)
    ]


def _seed(db, tk, asof, *, confirmed: bool, n=3):
    rows = _rows(tk, asof, n)
    upsert_constituents(rows, db_path=db)
    log_constituent_refresh(
        etf_ticker=tk,
        asof=asof,
        status="ok",
        source=NAVER_STOCK_SOURCE,
        # 원천일 확인 = 그 행들의 내용 지문을 담은 문구(검증자 r2 F5)
        message=ST.confirmation_message(rows) if confirmed else None,
        db_path=db,
    )


class FakeFetcher:
    """원천 흉내 — ETF별 응답(날짜 · 실패 · 날짜 없음)과 호출 기록."""

    def __init__(self, answers=None, default="2026-11-13", block=None):
        self.answers = dict(answers or {})
        self.default = default
        self.calls: list[str] = []
        self.block = block  # threading.Event — 설정되면 그때까지 기다림
        self.lock = threading.Lock()

    def __call__(self, ticker, asof, top_k):  # noqa: ARG002
        with self.lock:
            self.calls.append(ticker)
        if self.block is not None:
            self.block.wait(5)
        a = self.answers.get(ticker, self.default)
        if a == "fail":
            return FetchResult(
                status="unavailable",
                source=NAVER_STOCK_SOURCE,
                constituents=[],
                message="http_status_500",
            )
        cons = [
            FetchedConstituent(
                rank=i + 1,
                constituent_ticker=f"{i:06d}",
                constituent_name=f"주식{i}",
                weight_pct=10.0 - i,
            )
            for i in range(4)
        ]
        if a == "nodate":
            return FetchResult(
                status="ok", source=NAVER_STOCK_SOURCE, constituents=cons
            )
        return FetchResult(
            status="ok", source=NAVER_STOCK_SOURCE, constituents=cons, effective_asof=a
        )


class Clock:
    def __init__(self):
        self.t = 0.0
        self.sleeps: list[float] = []

    def mono(self):
        return self.t

    def sleep(self, s):
        self.sleeps.append(round(s, 6))
        self.t += s


def _run(col, kind, tickers, db, fetcher, clock=None, target="2026-11-13"):
    clock = clock or Clock()
    return col.start(
        kind,
        tickers,
        target_date=target,
        db_path=db,
        fetcher=fetcher,
        sleep_fn=clock.sleep,
        mono_fn=clock.mono,
        run_async=False,
    )


def _items(snap):
    return {i["ticker"]: i for i in snap["items"]}


# ---------- 상태 읽기 ----------


def test_status_unconfirmed_old_data_is_not_reused(tmp_path):
    db = tmp_path / "m.sqlite"
    _seed(db, "A", "2026-11-13", confirmed=False)  # POC6-31 이전 저장분(표시 없음)
    _seed(db, "B", "2026-11-13", confirmed=True)
    st = ST.read_status(["A", "B", "C"], target_date="2026-11-13", db_path=db)
    assert st["A"]["result"] == ST.NOT_CHECKED and st["A"]["kept_asof"] == "2026-11-13"
    assert st["A"]["kept_confirmed"] is False and st["A"]["source_asof"] is None
    assert st["B"]["result"] == ST.EXISTING and st["B"]["source_asof"] == "2026-11-13"
    assert st["C"]["result"] == ST.NOT_CHECKED and st["C"]["kept_asof"] is None


def test_status_missing_db_reads_nothing(tmp_path):
    st = ST.read_status(
        ["A"], target_date="2026-11-13", db_path=tmp_path / "none.sqlite"
    )
    assert st["A"]["result"] == ST.NOT_CHECKED
    assert not (tmp_path / "none.sqlite").exists()  # 읽기만으로 파일을 만들지 않음


@pytest.mark.parametrize(
    "conf_asof, last_status, last_asof, expected",
    [
        ("2026-11-13", None, None, ST.EXISTING),
        ("2026-11-14", None, None, ST.EXISTING),  # 목표일보다 새 구성도 충족
        ("2026-11-12", "target_wait", "2026-11-13", ST.TARGET_WAIT),
        (
            "2026-11-12",
            "target_wait",
            "2026-11-12",
            ST.NOT_CHECKED,
        ),  # 다른 목표일의 시도
        ("2026-11-12", "unavailable", "2026-11-13", ST.FAILED),
        ("2026-11-12", "skipped_timeout", "2026-11-13", ST.TIMEOUT),
        ("2026-11-12", "save_locked", "2026-11-13", ST.LOCKED),
        ("2026-11-12", "no_source_date", "2026-11-13", ST.NO_SOURCE_DATE),
        (None, "unavailable", "2026-11-13", ST.FAILED),
        (None, None, None, ST.NOT_CHECKED),
    ],
)
def test_judge_table(conf_asof, last_status, last_asof, expected):
    snap = {
        "confirmed": (
            {"asof": conf_asof, "rows": 3, "saved_at": "x"} if conf_asof else None
        ),
        "latest": (
            {"asof": conf_asof, "rows": 3, "saved_at": "x"} if conf_asof else None
        ),
        "last_attempt": (
            {
                "asof": last_asof,
                "status": last_status,
                "message": None,
                "created_at": "t",
            }
            if last_status
            else None
        ),
    }
    j = ST.judge(snap, "2026-11-13")
    assert j["result"] == expected
    assert j["needs_check"] is (expected != ST.EXISTING)


# ---------- 수집 작업 ----------


def test_reuse_confirmed_target_met_no_call(tmp_path):
    db = tmp_path / "m.sqlite"
    _seed(db, "A", "2026-11-13", confirmed=True)
    f = FakeFetcher()
    snap = _run(B.Collector(), B.KIND_HOLDINGS, ["A"], db, f)
    assert f.calls == [] and snap["calls"] == 0
    assert _items(snap)["A"]["result"] == ST.EXISTING


def test_old_unconfirmed_data_is_refetched_and_marked(tmp_path):
    db = tmp_path / "m.sqlite"
    _seed(db, "A", "2026-06-22", confirmed=False, n=10)
    f = FakeFetcher()
    snap = _run(B.Collector(), B.KIND_HOLDINGS, ["A"], db, f)
    assert f.calls == ["A"]
    it = _items(snap)["A"]
    assert it["result"] == ST.FETCHED and it["source_asof"] == "2026-11-13"
    assert (
        ST.read_status(["A"], target_date="2026-11-13", db_path=db)["A"]["result"]
        == ST.EXISTING
    )


def test_target_wait_then_new_data_on_next_explicit_run(tmp_path):
    # 판정 §5 '이전 구성일 뒤 새 자료가 나온 경우'
    db = tmp_path / "m.sqlite"
    f = FakeFetcher({"A": "2026-11-12"})
    s1 = _run(B.Collector(), B.KIND_HOLDINGS, ["A"], db, f)
    it = _items(s1)["A"]
    assert it["result"] == ST.TARGET_WAIT and it["source_asof"] == "2026-11-12"
    st = ST.read_status(["A"], target_date="2026-11-13", db_path=db)["A"]
    assert (
        st["result"] == ST.TARGET_WAIT and st["source_asof"] == "2026-11-12"
    )  # 재시작 뒤에도 구별
    f.answers["A"] = "2026-11-13"
    s2 = _run(B.Collector(), B.KIND_HOLDINGS, ["A"], db, f)
    assert _items(s2)["A"]["result"] == ST.FETCHED and f.calls == ["A", "A"]


def test_partial_failure_and_restart_distinguishes_states(tmp_path):
    db = tmp_path / "m.sqlite"
    _seed(db, "D", "2026-06-22", confirmed=False)
    f = FakeFetcher({"A": "2026-11-13", "B": "fail", "C": "nodate", "D": "fail"})
    snap = _run(B.Collector(), B.KIND_HOLDINGS, ["A", "B", "C", "D"], db, f)
    it = _items(snap)
    assert [it[t]["result"] for t in "ABCD"] == [
        ST.FETCHED,
        ST.FAILED,
        ST.NO_SOURCE_DATE,
        ST.FAILED,
    ]
    assert it["D"]["kept_asof"] == "2026-06-22" and it["D"]["kept_confirmed"] is False
    assert snap["update_failed"] == 3 and snap["counts"][ST.FETCHED] == 1
    # 원천 날짜 없는 응답은 저장하지 않음
    with sqlite3.connect(db) as con:
        assert (
            con.execute(
                "SELECT COUNT(*) FROM etf_constituents WHERE etf_ticker='C'"
            ).fetchone()[0]
            == 0
        )
    st = ST.read_status(
        list("ABCD"), target_date="2026-11-13", db_path=db
    )  # 새 프로세스처럼 저장 자료만
    assert [st[t]["result"] for t in "ABCD"] == [
        ST.EXISTING,
        ST.FAILED,
        ST.NO_SOURCE_DATE,
        ST.FAILED,
    ]


def test_success_count_reads_only_ok_rows(tmp_path):
    # 판정 Q4 — 확인 기록(target_wait 등)을 성공 건수 · 원천 날짜로 읽지 않음
    db = tmp_path / "m.sqlite"
    _run(B.Collector(), B.KIND_HOLDINGS, ["A"], db, FakeFetcher({"A": "2026-11-12"}))
    with sqlite3.connect(db) as con:
        rows = con.execute(
            "SELECT asof, status, message FROM etf_constituent_refresh_log ORDER BY rowid"
        ).fetchall()
    assert [r[:2] for r in rows] == [
        ("2026-11-12", "ok"),
        ("2026-11-13", "target_wait"),
    ]
    assert (
        rows[0][2].startswith(ST.SOURCE_CONFIRMED + ":")
        and rows[1][2] == "source=2026-11-12"
    )


def test_batches_of_ten_budget_per_batch_and_timeout_without_call(tmp_path):
    db = tmp_path / "m.sqlite"
    tickers = [f"T{i:02d}" for i in range(25)]
    clock = Clock()

    class SlowFetcher(FakeFetcher):
        def __call__(self, ticker, asof, top_k):
            clock.t += 4.0  # 호출마다 4초 — 한 묶음 30초 예산 안에 8개만
            return super().__call__(ticker, asof, top_k)

    f = SlowFetcher()
    snap = _run(B.Collector(), B.KIND_HOLDINGS, tickers, db, f, clock=clock)
    it = _items(snap)
    assert snap["batch_total"] == 3
    timeouts = [t for t in tickers if it[t]["result"] == ST.TIMEOUT]
    assert len(f.calls) == snap["calls"] == 25 - len(timeouts)
    assert all(t not in f.calls for t in timeouts)  # 조회 전 시간 초과는 부르지 않음
    # 묶음마다 예산이 새로 시작 — 둘째 · 셋째 묶음 첫 ETF 는 불림
    assert "T10" in f.calls and "T20" in f.calls
    assert snap["counts"][ST.TIMEOUT] == len(timeouts) > 0


def test_gap_continues_across_batches_and_jobs(tmp_path):
    db = tmp_path / "m.sqlite"
    clock = Clock()
    col = B.Collector()
    _run(
        col,
        B.KIND_HOLDINGS,
        [f"H{i}" for i in range(11)],
        db,
        FakeFetcher(),
        clock=clock,
    )
    assert clock.sleeps == [0.5] * 10  # 묶음 경계(10 → 11번째)에도 간격
    _run(col, B.KIND_CANDIDATES, ["C1"], db, FakeFetcher(), clock=clock)
    assert clock.sleeps == [0.5] * 11  # 다른 작업의 첫 호출도 앞 호출과 간격


def test_each_etf_called_at_most_once_per_job_and_candidates_capped(tmp_path):
    db = tmp_path / "m.sqlite"
    f = FakeFetcher()
    tickers = ["A", "A", " B ", "B"] + [f"X{i:02d}" for i in range(40)]
    snap = _run(B.Collector(), B.KIND_CANDIDATES, tickers, db, f)
    assert snap["total"] == 30 and len(f.calls) == len(set(f.calls)) == 30
    assert f.calls[:2] == ["A", "B"]


def test_repeated_start_returns_running_job(tmp_path):
    # 판정 §5 '갱신 버튼 연타' — 같은 종류는 한 작업
    db = tmp_path / "m.sqlite"
    gate = threading.Event()
    f = FakeFetcher(block=gate)
    col = B.Collector()
    s1 = col.start(
        B.KIND_HOLDINGS,
        ["A", "B"],
        target_date="2026-11-13",
        db_path=db,
        fetcher=f,
        sleep_fn=lambda s: None,
    )
    s2 = col.start(
        B.KIND_HOLDINGS,
        ["A", "B", "C"],
        target_date="2026-11-13",
        db_path=db,
        fetcher=f,
        sleep_fn=lambda s: None,
    )
    assert s2["job_id"] == s1["job_id"] and s2["total"] == 2
    gate.set()
    _wait_done(col, B.KIND_HOLDINGS)
    assert sorted(f.calls) == ["A", "B"]


def _wait_done(col, kind, limit=5.0):
    import time as _t

    end = _t.monotonic() + limit
    while _t.monotonic() < end:
        cur = col.current(kind)
        if cur and cur["state"] == "done":
            return cur
        _t.sleep(0.01)
    raise AssertionError("job not done")


def test_overlapping_holdings_and_candidates_share_one_call(tmp_path):
    # 판정 §5 '두 화면의 겹친 요청'
    db = tmp_path / "m.sqlite"
    gate = threading.Event()
    f = FakeFetcher(block=gate)
    col = B.Collector()
    col.start(
        B.KIND_HOLDINGS,
        ["S"],
        target_date="2026-11-13",
        db_path=db,
        fetcher=f,
        sleep_fn=lambda s: None,
    )
    import time as _t

    for _ in range(200):  # 보유 작업이 S 를 부르기 시작할 때까지
        if f.calls:
            break
        _t.sleep(0.005)
    col.start(
        B.KIND_CANDIDATES,
        ["S", "Z"],
        target_date="2026-11-13",
        db_path=db,
        fetcher=f,
        sleep_fn=lambda s: None,
    )
    _t.sleep(0.05)
    gate.set()
    h = _wait_done(col, B.KIND_HOLDINGS)
    c = _wait_done(col, B.KIND_CANDIDATES)
    assert f.calls.count("S") == 1
    assert _items(c)["S"]["shared"] is True and _items(c)["S"]["result"] == ST.FETCHED
    assert _items(h)["S"]["result"] == ST.FETCHED


def test_save_locked_is_item_result_and_next_etf_continues(tmp_path, monkeypatch):
    db = tmp_path / "m.sqlite"
    _seed(db, "A", "2026-06-22", confirmed=True)
    real = B.replace_constituents_snapshot

    def flaky(rows, **kw):
        if rows and rows[0].etf_ticker == "A":
            raise sqlite3.OperationalError("database is locked")
        return real(rows, **kw)

    monkeypatch.setattr(B, "replace_constituents_snapshot", flaky)
    snap = _run(B.Collector(), B.KIND_HOLDINGS, ["A", "B"], db, FakeFetcher())
    it = _items(snap)
    assert it["A"]["result"] == ST.LOCKED and it["A"]["kept_asof"] == "2026-06-22"
    assert it["A"]["kept_confirmed"] is True and it["B"]["result"] == ST.FETCHED
    assert (
        ST.read_status(["A"], target_date="2026-11-13", db_path=db)["A"]["result"]
        == ST.LOCKED
    )


def test_non_lock_db_error_is_not_swallowed(tmp_path, monkeypatch):
    db = tmp_path / "m.sqlite"

    def broken(rows, **kw):  # noqa: ARG001
        raise sqlite3.OperationalError("disk I/O error")

    monkeypatch.setattr(B, "replace_constituents_snapshot", broken)
    snap = _run(B.Collector(), B.KIND_HOLDINGS, ["A"], db, FakeFetcher())
    assert snap["state"] == "done" and snap["reason"] and "A" not in _items(snap)


def test_fetcher_exception_is_failure_not_crash(tmp_path):
    db = tmp_path / "m.sqlite"

    def boom(ticker, asof, top_k):  # noqa: ARG001
        raise RuntimeError("x")

    snap = _run(B.Collector(), B.KIND_HOLDINGS, ["A", "B"], db, boom)
    assert [i["result"] for i in snap["items"]] == [ST.FAILED, ST.FAILED]


def test_unknown_kind_rejected(tmp_path):
    with pytest.raises(ValueError):
        B.Collector().start(
            "other", ["A"], target_date="2026-11-13", db_path=tmp_path / "m.sqlite"
        )


# ---------- 검토 지적 정정(번들 A) ----------


@pytest.fixture()
def fast_lock_timeout(monkeypatch):
    """진짜 잠금 시험용 — 모든 sqlite 연결의 잠김 대기를 0.2초로(기본 5초 · 잠금 의미는 그대로)."""
    real = sqlite3.connect

    def connect(*a, **kw):
        kw.setdefault("timeout", 0.2)
        return real(*a, **kw)

    monkeypatch.setattr(sqlite3, "connect", connect)
    return real


def _hold_exclusive(real_connect, db):
    con = real_connect(str(db), isolation_level=None)
    con.execute("BEGIN EXCLUSIVE")
    return con


def test_real_lock_on_read_is_item_result_and_job_continues(
    tmp_path, fast_lock_timeout
):
    # 지적 backend#1 — 다른 연결이 독점 잠금을 쥔 동안 읽기 잠김 → 작업 전체가 멈추지 않고 ETF별 '저장 잠김'
    db = tmp_path / "m.sqlite"
    _seed(db, "A", "2026-06-22", confirmed=True)
    lock = _hold_exclusive(fast_lock_timeout, db)
    try:
        f = FakeFetcher()
        snap = _run(B.Collector(), B.KIND_HOLDINGS, ["A", "B"], db, f)
    finally:
        lock.execute("ROLLBACK")
        lock.close()
    it = _items(snap)
    assert snap["state"] == "done" and snap["reason"] is None and snap["done"] == 2
    assert [it[t]["result"] for t in "AB"] == [ST.LOCKED, ST.LOCKED]
    assert it["A"]["detail"] == "read_locked" and f.calls == []
    # 잠김이 작업 끝까지 이어져 확인 기록 2줄을 끝내 못 씀 — 그 수를 응답에 남긴다
    assert snap["unlogged_logs"] == 2


def test_real_lock_on_save_log_is_retried_at_job_end(
    tmp_path, fast_lock_timeout, monkeypatch
):
    # 지적 backend#3 — 저장 중 진짜 잠김 · '저장 잠김' 기록도 같은 잠김으로 못 씀 → 작업 끝에 다시 써서
    # 서버를 다시 켜도 '저장 잠김'으로 구별(판정 §1 넷째)
    db = tmp_path / "m.sqlite"
    _seed(db, "A", "2026-06-22", confirmed=True)
    held: list = []

    class LockingFetcher(FakeFetcher):
        def __call__(self, ticker, asof, top_k):
            out = super().__call__(ticker, asof, top_k)
            held.append(
                _hold_exclusive(fast_lock_timeout, db)
            )  # 응답 직후 다른 연결이 잠금
            return out

    real_flush = B.Collector._flush_logs

    def flush_after_release(self, job, db_path):
        assert job.pending_logs, "잠김 기록이 다시 쓰기 목록에 있어야 한다"
        for con in held:
            con.execute("ROLLBACK")
            con.close()
        held.clear()
        return real_flush(self, job, db_path)

    monkeypatch.setattr(B.Collector, "_flush_logs", flush_after_release)
    snap = _run(B.Collector(), B.KIND_HOLDINGS, ["A"], db, LockingFetcher())
    assert _items(snap)["A"]["result"] == ST.LOCKED and snap["unlogged_logs"] == 0
    st = ST.read_status(["A"], target_date="2026-11-13", db_path=db)["A"]
    assert st["result"] == ST.LOCKED and st["kept_asof"] == "2026-06-22"


def test_real_lock_never_released_reports_unlogged(tmp_path, fast_lock_timeout):
    # 잠김이 작업 끝에도 풀리지 않으면 기록을 못 쓴 수를 숨기지 않는다(다시 켜면 '아직 확인 안 함'으로 보임)
    db = tmp_path / "m.sqlite"
    held: list = []

    class LockingFetcher(FakeFetcher):
        def __call__(self, ticker, asof, top_k):
            out = super().__call__(ticker, asof, top_k)
            held.append(_hold_exclusive(fast_lock_timeout, db))
            return out

    try:
        snap = _run(B.Collector(), B.KIND_HOLDINGS, ["A"], db, LockingFetcher())
    finally:
        for con in held:
            con.execute("ROLLBACK")
            con.close()
    assert _items(snap)["A"]["result"] == ST.LOCKED and snap["unlogged_logs"] == 1
    assert (
        ST.read_status(["A"], target_date="2026-11-13", db_path=db)["A"]["result"]
        == ST.NOT_CHECKED
    )


def test_start_with_other_list_is_flagged(tmp_path):
    # 지적 backend#5 — 돌고 있는 작업의 대상이 요청 목록과 다르면 other_list(같은 목록이면 False)
    db = tmp_path / "m.sqlite"
    gate = threading.Event()
    f = FakeFetcher(block=gate)
    col = B.Collector()
    kw = dict(target_date="2026-11-13", db_path=db, fetcher=f, sleep_fn=lambda s: None)
    s1 = col.start(B.KIND_CANDIDATES, ["A1", "A2"], **kw)
    s_same = col.start(B.KIND_CANDIDATES, ["A2", " A1", "A1"], **kw)
    s_other = col.start(B.KIND_CANDIDATES, ["B1"], **kw)
    gate.set()
    _wait_done(col, B.KIND_CANDIDATES)
    assert s1["other_list"] is False and s1["tickers"] == ["A1", "A2"]
    assert s_same["job_id"] == s1["job_id"] and s_same["other_list"] is False
    assert s_other["job_id"] == s1["job_id"] and s_other["other_list"] is True
    assert s_other["tickers"] == ["A1", "A2"] and "B1" not in f.calls


def test_owner_rereads_before_call(tmp_path, monkeypatch):
    # 지적 backend#4 — 처음 읽은 뒤 다른 작업이 목표일 이상 구성을 저장했으면, 조회 주인이 된 뒤 다시 읽어 부르지 않는다
    db = tmp_path / "m.sqlite"
    _seed(db, "A", "2026-11-13", confirmed=True)
    real = B.read_snapshots
    seen = {"n": 0}

    def stale_first(tickers, *, db_path):
        seen["n"] += 1
        if seen["n"] == 1:
            return {
                t: {"confirmed": None, "latest": None, "last_attempt": None}
                for t in tickers
            }
        return real(tickers, db_path=db_path)

    monkeypatch.setattr(B, "read_snapshots", stale_first)
    f = FakeFetcher()
    snap = _run(B.Collector(), B.KIND_HOLDINGS, ["A"], db, f)
    assert f.calls == [] and _items(snap)["A"]["result"] == ST.EXISTING
    assert seen["n"] == 2


def _overlap(tmp_path, owner_target, waiter_target, answers=None, patch=None):
    db = tmp_path / "m.sqlite"
    gate = threading.Event()
    f = FakeFetcher(answers or {}, block=gate)
    col = B.Collector()
    col.start(
        B.KIND_HOLDINGS,
        ["S"],
        target_date=owner_target,
        db_path=db,
        fetcher=f,
        sleep_fn=lambda s: None,
    )
    import time as _t

    for _ in range(400):
        if f.calls:
            break
        _t.sleep(0.005)
    col.start(
        B.KIND_CANDIDATES,
        ["S", "Z"],
        target_date=waiter_target,
        db_path=db,
        fetcher=f,
        sleep_fn=lambda s: None,
    )
    _t.sleep(0.05)
    if patch:
        patch()
    gate.set()
    return db, f, _wait_done(col, B.KIND_HOLDINGS), _wait_done(col, B.KIND_CANDIDATES)


def test_shared_result_rejudged_with_waiter_target_and_logged(tmp_path):
    # 지적 backend#8 — 같은 조회를 함께 받아도 기다린 작업의 목표일로 다시 판정 · 그 목표일 기록을 남긴다
    db, f, h, c = _overlap(
        tmp_path, "2026-11-13", "2026-11-16", {"S": "2026-11-13", "Z": "2026-11-16"}
    )
    assert f.calls.count("S") == 1
    assert _items(h)["S"]["result"] == ST.FETCHED
    cs = _items(c)["S"]
    assert (
        cs["shared"] is True
        and cs["result"] == ST.TARGET_WAIT
        and cs["label"] == "목표일 자료 대기"
    )
    assert (
        ST.read_status(["S"], target_date="2026-11-16", db_path=db)["S"]["result"]
        == ST.TARGET_WAIT
    )
    # 함께 받은 수 · 실제 호출 수(Z 만)를 따로 낸다(지적 frontend#11)
    assert c["shared"] == 1 and c["calls"] == 1


def test_shared_owner_error_is_failure_not_timeout(tmp_path, monkeypatch):
    # 지적 backend#8 — 부른 작업이 오류로 멈추면 기다린 작업은 '받기 실패'(시간 초과 아님)
    def broken(rows, **kw):  # noqa: ARG001
        raise sqlite3.OperationalError("disk I/O error")

    db, f, h, c = _overlap(
        tmp_path,
        "2026-11-13",
        "2026-11-13",
        patch=lambda: monkeypatch.setattr(B, "replace_constituents_snapshot", broken),
    )
    assert h["reason"] == B.JOB_ERROR_TEXT and h["reason_detail"] == "OperationalError"
    cs = _items(c)["S"]
    assert (
        cs["result"] == ST.FAILED
        and cs["detail"] == "shared_owner_error"
        and cs["shared"] is True
    )


@pytest.mark.parametrize("owner_result", [ST.TIMEOUT, ST.EXISTING])
def test_shared_not_called_by_owner_falls_back_to_own_check(tmp_path, owner_result):
    # 부른 작업이 실제로 부르지 않고 끝났으면(시간 초과 · 그 목표일 기준 기존 자료) 기다린 작업이 직접 확인한다
    col = B.Collector()
    job = B.Job(
        job_id="j",
        kind=B.KIND_CANDIDATES,
        target_date="2026-11-13",
        tickers=["S"],
        started_at="t",
    )
    fl = B._Flight(target="2026-11-12")
    fl.item = B.Collector._item("S", owner_result, {}, source_asof="2026-11-12")
    fl.done.set()
    assert col._shared(job, "S", fl, {}, tmp_path / "m.sqlite") is None


@pytest.mark.parametrize(
    "src",
    [
        "2026-02-30",
        "2026/11/13",
        "20261113",
        "2026-11-14",
        "2999-01-01",
        "  ",
        "2026-1-13",
    ],
)
def test_invalid_or_future_source_date_is_not_saved(tmp_path, src):
    # 지적 backend#9 — 모양만 맞는 날짜 · 오늘(한국 시각) 뒤 날짜는 '원천 기준일 미확인'(저장 안 함 · 기록)
    db = tmp_path / "m.sqlite"
    col = B.Collector()
    snap = col.start(
        B.KIND_HOLDINGS,
        ["A"],
        target_date="2026-11-13",
        db_path=db,
        fetcher=FakeFetcher({"A": src}),
        sleep_fn=lambda s: None,
        today_fn=lambda: datetime(2026, 11, 13).date(),
        run_async=False,
    )
    assert _items(snap)["A"]["result"] == ST.NO_SOURCE_DATE
    with sqlite3.connect(db) as con:
        assert con.execute("SELECT COUNT(*) FROM etf_constituents").fetchone()[0] == 0
    assert (
        ST.read_status(["A"], target_date="2026-11-13", db_path=db)["A"]["result"]
        == ST.NO_SOURCE_DATE
    )


def test_today_source_date_is_valid(tmp_path):
    db = tmp_path / "m.sqlite"
    snap = B.Collector().start(
        B.KIND_HOLDINGS,
        ["A"],
        target_date="2026-11-13",
        db_path=db,
        fetcher=FakeFetcher({"A": "2026-11-13"}),
        sleep_fn=lambda s: None,
        today_fn=lambda: datetime(2026, 11, 13).date(),
        run_async=False,
    )
    assert _items(snap)["A"]["result"] == ST.FETCHED


def test_job_error_reason_is_korean_with_detail(tmp_path, monkeypatch):
    # 지적 frontend#11 — 작업 오류 사유는 쉬운 한국어 · 예외 이름은 따로(화면 '자세히' 안)
    def broken(rows, **kw):  # noqa: ARG001
        raise sqlite3.OperationalError("disk I/O error")

    monkeypatch.setattr(B, "replace_constituents_snapshot", broken)
    snap = _run(
        B.Collector(), B.KIND_HOLDINGS, ["A"], tmp_path / "m.sqlite", FakeFetcher()
    )
    assert (
        snap["reason"] == B.JOB_ERROR_TEXT
        and snap["reason_detail"] == "OperationalError"
    )
    assert "Error" not in snap["reason"]


# ---------- 검증자 r1 정정(F1 · 2026-11-16) ----------


def _rows_fetcher(n_by_ticker, date="2026-11-12", names=None):
    """ETF별 행 수를 정한 가짜 원천(주식{i} · 같은 대조 키)."""

    def fetch(ticker, asof, top_k):  # noqa: ARG001
        n = n_by_ticker[ticker]
        return FetchResult(
            status="ok",
            source=NAVER_STOCK_SOURCE,
            constituents=[
                FetchedConstituent(
                    rank=i + 1,
                    constituent_ticker=f"{i:06d}",
                    constituent_name=f"주식{i}",
                    weight_pct=10.0 - i * 0.5,
                    constituent_isin=f"KR7{i:06d}003",  # 국내 주식 행(행 종류 판정이 주식으로 읽음)
                    market_type="0",
                )
                for i in range(n)
            ],
            effective_asof=date,
        )

    return fetch


def test_f1a_same_date_refetch_with_fewer_rows_replaces_snapshot(tmp_path):
    # 검증자 r1 F1 (a) — 목표일 11/13 · 원천 11/12 10행 → 다음 명시 수집에서 같은 원천일 4행 → 예전 5 ~ 10위가 남지 않음
    from app.constituents_cross_family import cross_family, read_confirmed_rows

    db = tmp_path / "m.sqlite"
    _run(
        B.Collector(),
        B.KIND_CANDIDATES,
        ["A", "Z"],
        db,
        _rows_fetcher({"A": 10, "Z": 10}),
    )
    s2 = _run(B.Collector(), B.KIND_CANDIDATES, ["A"], db, _rows_fetcher({"A": 4}))
    assert _items(s2)["A"]["rows"] == 4
    with sqlite3.connect(db) as con:
        assert con.execute(
            "SELECT COUNT(*), MAX(rank) FROM etf_constituents "
            "WHERE etf_ticker='A' AND asof='2026-11-12'"
        ).fetchone() == (4, 4)
    latest = read_confirmed_rows(["A", "Z"], db_path=db)
    assert len(latest["A"]["rows"]) == 4
    etfs = [
        {
            "ticker": "A",
            "name": "A",
            "rank": 1,
            "index_name": "지수 가",
            "strategy": False,
        },
        {
            "ticker": "Z",
            "name": "Z",
            "rank": 2,
            "index_name": "지수 나",
            "strategy": False,
        },
    ]
    out = cross_family(etfs, latest, set())
    assert len(out["stocks"]) == 4  # 예전 행이 남으면 10


def test_f1b_manual_overwrite_after_confirmation_is_not_reused(tmp_path):
    # 검증자 r1 F1 (b) — 원천일 확인 뒤 기존 수동 수집이 원천일 없는 응답을 요청일로 덮어쓰면 그 구성은 '원천 기준일 미확인'
    # (재사용 · 공통 주식 계산에 쓰지 않음 · 다음 수집이 다시 부름)
    from app.constituents_cross_family import read_confirmed_rows
    from app.etf_constituents_service import refresh_constituents

    db = tmp_path / "m.sqlite"
    _run(B.Collector(), B.KIND_HOLDINGS, ["A"], db, FakeFetcher({"A": "2026-11-13"}))
    assert (
        ST.read_status(["A"], target_date="2026-11-13", db_path=db)["A"]["result"]
        == ST.EXISTING
    )

    def no_date(ticker, asof, top_k):  # noqa: ARG001
        return FetchResult(
            status="ok",
            source=NAVER_STOCK_SOURCE,
            constituents=[
                FetchedConstituent(
                    rank=1,
                    constituent_ticker="999999",
                    constituent_name="다른 주식",
                    weight_pct=50.0,
                )
            ],
        )

    res = refresh_constituents(
        asof="2026-11-13",
        tickers=["A"],
        force=True,
        fetcher=no_date,
        db_path=db,
        sleep_fn=lambda s: None,
    )
    assert res.items[0].status == "ok"  # 기존 경로 계약 그대로(요청일로 저장)
    st = ST.read_status(["A"], target_date="2026-11-13", db_path=db)["A"]
    assert st["result"] == ST.NOT_CHECKED and st["kept_confirmed"] is False
    assert read_confirmed_rows(["A"], db_path=db) == {}
    f = FakeFetcher({"A": "2026-11-13"})
    _run(B.Collector(), B.KIND_HOLDINGS, ["A"], db, f)
    assert f.calls == ["A"]  # 다시 부름
    assert (
        ST.read_status(["A"], target_date="2026-11-13", db_path=db)["A"]["result"]
        == ST.EXISTING
    )


@pytest.mark.parametrize("marker_after_rows, expected", [(True, True), (False, False)])
def test_f1_confirmation_must_be_newer_than_last_write(
    tmp_path, marker_after_rows, expected
):
    # 상태 읽기 규칙(검증자 r2 F5 로 바꿈) — 기록 시각 순서와 상관없이, 지금 행의 내용이 확인 지문과 같을 때만 확인.
    # marker_after_rows=True: 확인한 그 내용 그대로 · False: 확인 뒤 다른 내용(주식 하나 바뀜)으로 덮어씀
    db = tmp_path / "m.sqlite"
    _seed(db, "A", "2026-11-13", confirmed=True)
    if not marker_after_rows:
        changed = _rows("A", "2026-11-13")
        changed[0].constituent_name = "다른 주식"
        upsert_constituents(changed, db_path=db)
    snap = ST.read_snapshots(["A"], db_path=db)["A"]
    assert (snap["confirmed"] is not None) is expected and snap["latest"][
        "asof"
    ] == "2026-11-13"


def test_f1_rows_and_confirmation_written_together_or_not_at_all(tmp_path, monkeypatch):
    # 같은 트랜잭션 — 기록 쓰기가 실패하면 행도 바뀌지 않는다(예전 구성 보존)
    from app import etf_constituents_store as S

    db = tmp_path / "m.sqlite"
    _seed(db, "A", "2026-11-13", confirmed=True, n=3)
    before = (
        sqlite3.connect(db)
        .execute("SELECT rank, constituent_name FROM etf_constituents ORDER BY rank")
        .fetchall()
    )
    rows = _rows("A", "2026-11-13", n=1)
    with pytest.raises(sqlite3.IntegrityError):
        S.replace_constituents_snapshot(
            rows, log_status=None, log_message=None, db_path=db
        )  # status NOT NULL 위반
    after = (
        sqlite3.connect(db)
        .execute("SELECT rank, constituent_name FROM etf_constituents ORDER BY rank")
        .fetchall()
    )
    assert after == before


def test_r2_last_attempt_follows_write_order_not_timestamp(tmp_path, monkeypatch):
    # 검증자 r2 F5 와 같은 뿌리 — 저장 경로가 시각을 먼저 정한 뒤 늦게 쓰면 기록 시각 순서가 실제 순서와 다르다.
    # '마지막 시도'는 기록된 순서(rowid)로 읽는다.
    from app import etf_constituents_store as S

    db = tmp_path / "m.sqlite"
    times = iter(["2026-11-16T06:00:00.000000Z", "2026-11-16T05:00:00.000000Z"])
    monkeypatch.setattr(S, "_utcnow_iso", lambda: next(times))
    log_constituent_refresh(
        etf_ticker="A",
        asof="2026-11-13",
        status="target_wait",
        source=None,
        message=None,
        db_path=db,
    )
    log_constituent_refresh(
        etf_ticker="A",
        asof="2026-11-13",
        status="unavailable",
        source=None,
        message=None,
        db_path=db,
    )
    st = ST.read_status(["A"], target_date="2026-11-13", db_path=db)["A"]
    assert (
        st["result"] == ST.FAILED
        and st["last_checked_at"] == "2026-11-16T05:00:00.000000Z"
    )


@pytest.mark.parametrize("zero", [-0.0, 0.0])
def test_f7_negative_zero_weight_stays_confirmed(tmp_path, zero):
    # 검증자 r3 F7 — 원천 비중 '-0.00'(파서 결과 -0.0)은 SQLite REAL 을 거치면 0.0 으로 읽힌다. 지문은 저장한 행을
    # DB 에서 다시 읽어 계산하므로 같은 자료가 미확인이 되지 않는다(재사용 · 공통 주식에 남음 · 다시 부르지 않음).
    from app.constituents_cross_family import read_confirmed_rows

    db = tmp_path / "m.sqlite"

    def fetch(ticker, asof, top_k):  # noqa: ARG001
        return FetchResult(
            status="ok",
            source=NAVER_STOCK_SOURCE,
            constituents=[
                FetchedConstituent(
                    rank=1,
                    constituent_ticker="005930",
                    constituent_name="주식0",
                    weight_pct=45.0,
                ),
                FetchedConstituent(
                    rank=2,
                    constituent_ticker="000660",
                    constituent_name="주식1",
                    weight_pct=zero,
                ),
            ],
            effective_asof="2026-11-13",
        )

    calls: list = []

    def counted(*a):
        calls.append(a[0])
        return fetch(*a)

    snap = _run(B.Collector(), B.KIND_CANDIDATES, ["A"], db, counted)
    assert _items(snap)["A"]["result"] == ST.FETCHED
    assert (
        ST.read_status(["A"], target_date="2026-11-13", db_path=db)["A"]["result"]
        == ST.EXISTING
    )
    assert len(read_confirmed_rows(["A"], db_path=db)["A"]["rows"]) == 2
    _run(B.Collector(), B.KIND_CANDIDATES, ["A"], db, counted)
    assert calls == ["A"]  # 같은 목표일에 다시 부르지 않음


def test_f7_fingerprint_treats_negative_zero_as_zero():
    from app.etf_constituents_store import fingerprint

    assert fingerprint([(1, "a", None, -0.0)]) == fingerprint([(1, "a", None, 0.0)])
