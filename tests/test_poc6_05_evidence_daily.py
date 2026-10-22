"""POC6-05 — OCI 일일 수집(collect-daily) 경계 시험.

tmp 보관소 · tmp 시장 DB · 가짜 목록 · 가짜 네이버/FDR · 가짜 Yahoo · 가짜 키움만 쓴다(라이브 DB · 외부 호출 0).
계약 출처: 설계 V1 §2 ~ §6 · §9 · PLAN 판정(2026-10-22) §3 ~ §6.
"""

from __future__ import annotations

import contextlib
import json
import os
import sqlite3
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest
import requests

from app import supply_fx_oil_refresh as rf
from app import supply_fx_oil_store as fst
from app.ml_evidence import daily, daily_naver, daily_tables, store

ROOT = Path(__file__).resolve().parents[1]
KST = timezone(timedelta(hours=9))
RUN_AT = datetime(2026, 10, 22, 0, 40, tzinfo=timezone.utc)  # 목 09:40 KST
TICKERS = ["069500", "102110", "114800", "229200", "360750", "0091P0"]


def weekdays(start: str, end: str) -> list[str]:
    d, out = date.fromisoformat(start), []
    while d <= date.fromisoformat(end):
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


KOSPI = weekdays("2025-09-01", "2026-10-21")
KOSPI_CLOSE = {d: 2500.0 + i for i, d in enumerate(KOSPI)}


def make_db(path: Path, kospi=KOSPI) -> Path:
    con = sqlite3.connect(path)
    con.execute(
        "CREATE TABLE market_benchmark_daily_price (benchmark_id TEXT NOT NULL, "
        "benchmark_name TEXT, date TEXT NOT NULL, close REAL, source TEXT, created_at TEXT, "
        "PRIMARY KEY (benchmark_id, date))"
    )
    for bid in ("KOSPI", "VIX"):
        con.executemany(
            "INSERT INTO market_benchmark_daily_price VALUES (?,?,?,?,?,?)",
            [(bid, bid, d, KOSPI_CLOSE[d], "T", "2026-10-21T23:10:05Z") for d in kospi],
        )
    for table in ("krx_etf_daily_price_unadjusted", "krx_stock_daily_price_unadjusted"):
        con.execute(
            f"CREATE TABLE {table} (date TEXT, ticker TEXT, close REAL, source TEXT, "
            "price_basis TEXT, collected_at TEXT, PRIMARY KEY (date, ticker))"
        )
        con.executemany(
            f"INSERT INTO {table} VALUES (?,?,?,?,?,?)",
            [
                (
                    d,
                    t,
                    1000.0,
                    "KRX_OPEN_API",
                    "UNADJUSTED_TRADED_PRICE",
                    "2026-10-21T23:10:37+00:00",
                )
                for d in KOSPI[-25:]
                for t in TICKERS[:3]
            ],
        )
    con.commit()
    con.close()
    return path


class FakeTime:
    def __init__(self, start: datetime = RUN_AT) -> None:
        self.base, self.t, self.sleeps = start, 0.0, []

    def now(self) -> datetime:
        return self.base + timedelta(seconds=self.t)

    def clock(self) -> float:
        return self.t

    def sleep(self, s: float) -> None:
        self.sleeps.append(s)
        self.t += s


def listing(tickers=TICKERS):
    return pd.DataFrame(
        {
            "Symbol": tickers,
            "Name": [f"ETF {t}" for t in tickers],
            "Category": ["1"] * len(tickers),
        }
    )


class Prices:
    """가짜 FDR — 오늘(진행 중) 봉까지 돌려준다. fail = {ticker: 예외}."""

    def __init__(self, ft: FakeTime, fail=None, shift=0.0) -> None:
        self.ft, self.fail, self.calls, self.shift = ft, dict(fail or {}), [], shift

    def __call__(self, ticker, start, end):
        self.calls.append(ticker)
        self.ft.t += 0.05
        if ticker in self.fail:
            raise self.fail[ticker]
        idx = pd.bdate_range(start, end)
        close = [100.0 + i + self.shift for i in range(len(idx))]
        df = pd.DataFrame(
            {
                "Open": close,
                "High": close,
                "Low": close,
                "Close": close,
                "Volume": [10] * len(idx),
            },
            index=idx,
        )
        df["Change"] = df["Close"].pct_change()
        return df


class _Resp:
    def __init__(self, body) -> None:
        self._b, self.status_code = body, 200

    def json(self):
        return self._b

    def raise_for_status(self):
        return None


def fx_get(url, params=None, headers=None, timeout=None):
    tz = "Europe/London" if "KRW" in url else "America/New_York"
    days = ["2026-10-19", "2026-10-20"]
    import zoneinfo

    z = zoneinfo.ZoneInfo(tz)
    ts = [int(datetime.fromisoformat(d).replace(tzinfo=z).timestamp()) for d in days]
    start = int(datetime(2026, 10, 21, tzinfo=z).timestamp())
    body = {
        "chart": {
            "result": [
                {
                    "meta": {
                        "exchangeTimezoneName": tz,
                        "currentTradingPeriod": {"regular": {"start": start}},
                    },
                    "timestamp": ts,
                    "indicators": {"quote": [{"close": [1400.5, 1401.5]}]},
                }
            ]
        }
    }
    return _Resp(body)


class Kiwoom:
    def __init__(self, fail=None) -> None:
        self.fail, self.asked = set(fail or ()), []

    def kospi_net_by_investor(self, d):
        self.asked.append(d)
        if d in self.fail:
            from app.kiwoom_investor_flow import KiwoomFlowError

            raise KiwoomFlowError(f"{d} 조회 실패")
        return {inv: 10**8 for inv in fst.INVESTORS}, KOSPI_CLOSE[d]


@pytest.fixture
def world(tmp_path, monkeypatch):
    db = make_db(tmp_path / "market.sqlite")
    (tmp_path / "cal").mkdir()
    state = tmp_path / "batch_state.json"
    state.write_text('{"status": "success"}', encoding="utf-8")
    corr = tmp_path / "corr"
    corr.mkdir()
    (corr / "kospi_correction_1.json").write_text(
        '{"stage": "before_write"}', encoding="utf-8"
    )
    state2 = tmp_path / "krx_reinforcement_state.json"
    state2.write_text('{"status": "already_loaded"}', encoding="utf-8")
    monkeypatch.setattr(daily_tables, "batch_state_files", lambda: (state, state2))
    monkeypatch.setattr(daily_tables, "KOSPI_CORRECTIONS_DIR", corr)
    return {"root": tmp_path / "ev", "db": db, "cal": tmp_path / "cal", "tmp": tmp_path}


def deps(ft, prices=None, lister=None, kiwoom=None):
    return daily.Deps(
        now=ft.now,
        clock=ft.clock,
        sleep=ft.sleep,
        list_fetcher=lister or (lambda: listing()),
        price_fetcher=prices or Prices(ft),
        request_timeout=contextlib.nullcontext,
        fx_http_get=fx_get,
        kiwoom_client=kiwoom or Kiwoom(),
        git_head=lambda: "a" * 40,
    )


def run(world, ft, **kw):
    return daily.collect_daily(
        root=world["root"],
        db_path=world["db"],
        calendar_dir=world["cal"],
        deps=deps(ft, **kw),
        site="TEST",
    )


def windows(world, m):
    return {
        x["ticker"]: x
        for x in store.read_jsonl_gz(
            world["root"], m["sources"]["naver_etf_windows"]["object"]
        )
    }


def test_full_run_archives_sources_and_writes_only_flow_tables(world):
    before = (
        sqlite3.connect(world["db"])
        .execute("SELECT count(*) FROM krx_etf_daily_price_unadjusted")
        .fetchone()
    )
    status, m = run(world, FakeTime())
    assert status == "OK", m["sources"]
    src = m["sources"]
    assert src["date_axis"]["latest_completed_trading_day"] == "2026-10-21"
    assert src["etf_list"]["effective"]["count"] == len(TICKERS)
    w = windows(world, m)
    assert sorted(w) == sorted(TICKERS)
    one = w["069500"]
    assert (
        one["status"] == "OK" and one["dropped_in_progress"] == 1
    )  # 오늘(10-22) 진행 중 봉 뺌
    assert one["rows"][-1][0] == "2026-10-21" and one["observed_at"].startswith(
        "2026-10-22T00:40"
    )
    assert (
        src["krx_etf_close"]["first_archive"]
        and src["krx_etf_close"]["window_keys"] == 21
    )
    assert src["fx_wti"]["status"] == "OK" and src["investor_flow"]["status"] == "OK"
    con = sqlite3.connect(world["db"])
    tables = {
        r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert {"market_macro_daily", "market_investor_flow_daily"} <= tables
    assert (
        not {"etf_daily_price", "etf_master", "market_refresh_log"} & tables
    )  # 운영 가격 표 · 기록 쓰기 0
    assert (
        con.execute("SELECT count(*) FROM krx_etf_daily_price_unadjusted").fetchone()
        == before
    )
    runs, problems = store.list_runs(world["root"])
    assert not problems and store.verify_run(world["root"], runs[0]) == []
    assert m["resources"]["network_received_bytes"] is None and m["resources"][
        "max_rss"
    ]["unit"] in ("KiB", "bytes")
    assert (
        m["code_commit_kind"] == "collector_run_commit"
        and m["published_at"] >= m["finished_at"]
    )


def test_target_list_is_independent_of_holdings(world, tmp_path, monkeypatch):
    from app import holdings_store
    from app.three_push_runtime import market_data_batch as mdb

    def banned(*a, **k):
        pytest.fail("보유 · 개인 값 · seed 대상 사용 금지")

    monkeypatch.setattr(mdb, "collect_approved_tickers", banned)
    for name in ("read_document", "materialize", "commit"):
        monkeypatch.setattr(holdings_store, name, banned)
    _, m1 = run(world, FakeTime())
    other = dict(world, root=tmp_path / "ev2")
    _, m2 = run(other, FakeTime())
    a = m1["sources"]["naver_etf_windows"]["object"]
    assert (
        a == m2["sources"]["naver_etf_windows"]["object"]
    )  # 같은 입력 = 같은 바이트(보유와 무관)
    assert m1["sources"]["etf_list"]["effective"]["count"] == len(TICKERS)


def test_same_day_partial_retry_fetches_only_missing_and_reuses_previous(world):
    ft = FakeTime()
    p1 = Prices(ft, fail={"102110": RuntimeError("x"), "229200": RuntimeError("y")})
    s1, m1 = run(world, ft, prices=p1)
    w1 = m1["sources"]["naver_etf_windows"]
    assert (
        s1 == "PARTIAL"
        and w1["status"] == "PARTIAL"
        and sorted(w1["missing"]) == ["102110", "229200"]
    )
    ft2 = FakeTime(RUN_AT + timedelta(hours=1))
    p2 = Prices(ft2)
    s2, m2 = run(world, ft2, prices=p2)
    w2 = m2["sources"]["naver_etf_windows"]
    assert p2.calls == ["102110", "229200"]  # 같은 기준일 · 미확보분만
    assert s2 == "OK" and w2["have_total"] == len(TICKERS) and w2["missing"] == []
    assert w2["objects_for_target_day"][0] == w1["object"]
    old = next(o for o in m2["objects"] if o["sha256"] == w1["object"])
    assert old["reused_from"] == m1["run_id"]
    ft3 = FakeTime(RUN_AT + timedelta(hours=2))
    p3 = Prices(ft3)
    _, m3 = run(world, ft3, prices=p3)
    assert (
        p3.calls == []
        and m3["sources"]["naver_etf_windows"]["status"] == "SKIPPED_NO_NEW"
    )


SEQ = [
    datetime(2026, 10, d, 0, 40, tzinfo=timezone.utc) for d in (23, 24, 25, 26, 27)
]  # 금 ~ 화 09:40


@pytest.mark.parametrize(
    "idx, expect_fetch",
    [
        (1, True),  # 토: 금요일 봉 처음
        (2, False),  # 일: 새 완료 거래일 없음
        (3, False),  # 월 09:40: 기준일 = 금 그대로
        (4, True),  # 화: 월요일 봉
    ],
)
def test_new_completed_trading_day_rule(world, idx, expect_fetch):
    for at in SEQ[:idx]:
        run(world, FakeTime(at))
    when = SEQ[idx]
    ft = FakeTime(when)
    p = Prices(ft)
    _, m = run(world, ft, prices=p)
    assert bool(p.calls) is expect_fetch
    w = m["sources"]["naver_etf_windows"]
    if expect_fetch:
        line = windows(world, m)["069500"]
        assert (
            line["observed_at"][:10] == when.date().isoformat()
        )  # 토요일 확보 = 토요일 시각
    else:
        assert w["status"] == "SKIPPED_NO_NEW"
    if (
        idx == 1
    ):  # 토: 금요일 수급은 KOSPI 저장 전(월 08:10) → 계획 밖 미시도로 기록(상태 낮추지 않음)
        f = m["sources"]["investor_flow"]
        assert f["failed"] == {} and f["not_attempted"] == []
        assert f["not_attempted_extra"][0]["date"] == "2026-10-23"
        assert f["status"] == "OK"


class ListWriter:
    def __init__(self) -> None:
        self.lines = []

    def write(self, obj):
        self.lines.append(obj)


def _fw(fetcher, ft, tickers=None, **kw):
    w = ListWriter()
    out = daily_naver.fetch_windows(
        tickers or [f"{i:06d}" for i in range(60)],
        writer=w,
        target_day="2026-10-21",
        today_kst=date(2026, 10, 22),
        fetcher=fetcher,
        request_timeout=contextlib.nullcontext,
        now=ft.now,
        clock=ft.clock,
        sleep=ft.sleep,
        **kw,
    )
    return out, w.lines


def _http(code):
    r = requests.Response()
    r.status_code = code
    return requests.exceptions.HTTPError(response=r)


@pytest.mark.parametrize(
    "exc, attempts, reason",
    [
        (requests.exceptions.ReadTimeout(), 5, "연속 시간 초과 5회"),
        (RuntimeError("bad"), 20, "연속 실패 20회"),
        (_http(403), 1, "HTTP 403"),
        (_http(429), 1, "HTTP 429"),
    ],
)
def test_naver_stop_rules(exc, attempts, reason):
    ft = FakeTime()
    out, lines = _fw(Prices(ft, fail={f"{i:06d}": exc for i in range(60)}), ft)
    assert out["attempted"] == attempts and reason in out["stop_reason"]
    assert out["counts"]["NOT_ATTEMPTED"] == 60 - attempts and len(out["missing"]) == 60
    assert all(
        x["status"] == "NOT_ATTEMPTED" and x["reason"] == out["stop_reason"]
        for x in lines[attempts:]
    )


def test_success_resets_failure_streaks():
    ft = FakeTime()
    fail = {
        f"{i:06d}": requests.exceptions.ReadTimeout() for i in range(60) if i % 5 != 4
    }
    out, _ = _fw(Prices(ft, fail=fail), ft)
    assert out["stop_reason"] is None and out["attempted"] == 60


def test_time_budget_stops_new_requests_and_gap_is_kept():
    ft = FakeTime()

    def slow(t, s, e):
        ft.t += 400.0
        return Prices(ft)(t, s, e)

    out, lines = _fw(slow, ft, tickers=[f"{i:06d}" for i in range(10)])
    assert (
        out["attempted"] == 5 and "시간 예산" in out["stop_reason"]
    )  # 5 × 400초 > 30분 뒤 새 요청 없음
    ft2 = FakeTime()
    _fw(Prices(ft2), ft2, tickers=["000001", "000002", "000003"])
    assert ft2.sleeps == [0.25, 0.25]  # 요청이 끝날 때마다 0.25초(POC6-01 CALL_GAP_S)


def test_timeout_streak_equals_pc_rule():
    from app.market_refresh_service import PRICE_TIMEOUT_STOP_STREAK

    assert daily_naver.Limits().timeout_streak == PRICE_TIMEOUT_STOP_STREAK


def test_provider_without_target_row_is_not_failure():
    ft = FakeTime()

    def old(t, s, e):
        return Prices(ft)(t, s, date(2026, 10, 16))

    out, lines = _fw(old, ft, tickers=["000001"])
    assert out["counts"]["NO_NEW_ROW"] == 1 and out["missing"] == []


@pytest.mark.parametrize(
    "lister, prev, reason_part",
    [
        (lambda: (_ for _ in ()).throw(RuntimeError("down")), True, "목록 조회 실패"),
        (lambda: listing(TICKERS[:3]), True, "95% 미만"),
        (lambda: listing([]), True, "비어 있음"),
    ],
)
def test_list_failure_uses_previous_list_as_stale(world, lister, prev, reason_part):
    run(world, FakeTime())
    ft = FakeTime(RUN_AT + timedelta(days=1))
    _, m = run(world, ft, lister=lister)
    lst = m["sources"]["etf_list"]
    assert (
        lst["status"] == "PARTIAL"
        and reason_part in lst["reason"]
        and lst["effective"]["stale"]
    )
    assert lst["effective"]["object"] in {o["sha256"] for o in m["objects"]}


def test_no_list_at_all_fails_domestic_without_fetch(world):
    ft = FakeTime()
    p = Prices(ft)
    s, m = run(world, ft, prices=p, lister=lambda: listing([]))
    assert m["sources"]["naver_etf_windows"]["status"] == "FAILED" and p.calls == []
    assert s == "PARTIAL"  # 다른 자료원은 유효


def test_table_delta_keeps_previous_refs_and_changed_dates_only(world):
    _, m1 = run(world, FakeTime())
    con = sqlite3.connect(world["db"])
    con.execute(
        "UPDATE krx_etf_daily_price_unadjusted SET close=1001 WHERE date=? AND ticker='069500'",
        (KOSPI[-3],),
    )
    con.commit()
    con.close()
    _, m2 = run(world, FakeTime(RUN_AT + timedelta(hours=1)))
    k1, k2 = m1["sources"]["krx_etf_close"], m2["sources"]["krx_etf_close"]
    assert k2["changed_keys"] == [KOSPI[-3]] and not k2["first_archive"]
    assert (
        k2["map"][KOSPI[-4]]["obj"] == k1["object"]
        and k2["map"][KOSPI[-3]]["obj"] == k2["object"]
    )
    prev = next(o for o in m2["objects"] if o["sha256"] == k1["object"])
    assert prev["reused_from"] == m1["run_id"]
    b2 = m2["sources"]["benchmarks"]
    assert b2["status"] == "SKIPPED_NO_NEW" and b2["object"] is None


def test_axis_archives_calendar_and_kospi_dates_contents(world):
    csv = world["cal"] / "krx_trading_days_2026.csv"
    csv.write_text(
        "date\n" + "\n".join(weekdays("2026-01-02", "2026-12-30")) + "\n",
        encoding="utf-8",
    )
    _, m = run(world, FakeTime())
    ax = m["sources"]["date_axis"]
    assert ax["calendar_missing"] is False
    assert (
        store.read_object(world["root"], ax["calendar_files"][0]["sha256"])
        == csv.read_bytes()
    )
    got = json.loads(
        store.read_object(world["root"], ax["kospi_stored_dates"]["object"])
    )
    assert got["dates"] == KOSPI


def test_flow_partial_failures_and_missing_kospi_are_counted(world):
    db2 = make_db(
        world["tmp"] / "m2.sqlite", kospi=KOSPI[:-1]
    )  # T-1(10-21) KOSPI 미저장
    w2 = dict(world, db=db2)
    k = Kiwoom(fail={KOSPI[-3], KOSPI[-4], KOSPI[-5]})
    _, m = run(w2, FakeTime(), kiwoom=k)
    f = m["sources"]["investor_flow"]
    assert f["status"] == "PARTIAL" and f["received"] == [KOSPI[-2]]
    assert set(f["failed"]) == {KOSPI[-3], KOSPI[-4], KOSPI[-5]}
    assert f["not_attempted"] and all(
        x["reason"] == "연속 실패 3회" for x in f["not_attempted"]
    )
    assert f["not_attempted_extra"][0]["date"] == "2026-10-21"
    behind = m["sources"]["benchmarks"]["behind_target"]
    assert behind["latest"] == KOSPI[-2] and behind["target_day"] == "2026-10-21"
    assert (
        "behind_target" not in m["sources"]["krx_etf_close"]
    )  # KRX 표는 기준일까지 있음
    assert f["planned"] == len(f["received"]) + len(f["failed"]) + len(
        f["not_attempted"]
    )


def test_missing_kiwoom_credentials_is_failed_not_hidden(world, monkeypatch):
    monkeypatch.delenv("KIWOOM_APP_KEY", raising=False)
    monkeypatch.delenv("KIWOOM_APP_SECRET", raising=False)
    w = dict(world)
    ft = FakeTime()
    d = deps(ft)
    d.kiwoom_client = None
    s, m = daily.collect_daily(
        root=w["root"], db_path=w["db"], calendar_dir=w["cal"], deps=d, site="TEST"
    )
    f = m["sources"]["investor_flow"]
    assert (
        f["status"] == "FAILED"
        and "키움 인증 정보 없음" in f["reason"]
        and s == "PARTIAL"
    )


def test_capture_failure_blocks_upsert(tmp_path):
    db = make_db(tmp_path / "m.sqlite")

    class Cap:
        def fx_received(self, sid, rows, since):
            if sid == fst.USDKRW:
                raise OSError("보관 실패")

        def fx_fail(self, sid, reason):
            self.last = (sid, reason)

    failed = rf.refresh_fx_wti(
        db_path=db,
        now_utc=RUN_AT,
        start=date(2026, 10, 1),
        http_get=fx_get,
        capture=Cap(),
    )
    assert failed == ["원/달러"]
    got = {
        r[0]
        for r in sqlite3.connect(db).execute("SELECT series_id FROM market_macro_daily")
    }
    assert got == {fst.WTI}  # 보관 실패 계열은 표에 없음 · 다른 계열은 그대로
    cap = daily_flow_capture(tmp_path / "ev")
    import app.ml_evidence.store as st

    real = st.put_bytes
    st.put_bytes = lambda root, data: (_ for _ in ()).throw(OSError("디스크 가득"))
    try:
        rf.refresh_investor_flows(
            db_path=db,
            now_utc=RUN_AT,
            start=date(2026, 10, 1),
            client=Kiwoom(),
            sleep=lambda s: None,
            capture=cap,
        )
    finally:
        st.put_bytes = real
    assert fst.read_investor_flows(db_path=db)[0] == {}  # 확정 저장 실패 = 표 반영 0
    assert cap.received == {} and set(cap.failed.values()) == {"OSError"}


def daily_flow_capture(root):
    from app.ml_evidence.daily_flow import FlowCapture

    return FlowCapture(root, lambda info, role, fmt: info["sha256"], lambda: RUN_AT)


@pytest.mark.parametrize(
    "statuses, expect",
    [
        (["OK", "OK"], "OK"),
        (["OK", "SKIPPED_NO_NEW"], "OK"),
        (["SKIPPED_NO_NEW"], "SKIPPED_NO_NEW"),
        (["OK", "FAILED"], "PARTIAL"),
        (["PARTIAL", "OK"], "PARTIAL"),
        (["FAILED", "FAILED", "SKIPPED_NO_NEW"], "FAILED"),
    ],
)
def test_combine_status(statuses, expect):
    assert daily.combine(statuses) == expect


def test_storage_failure_publishes_failed_or_nothing_and_keeps_previous(
    world, monkeypatch
):
    _, m1 = run(world, FakeTime())
    real = store.put_bytes

    def boom(root, data):
        raise OSError("디스크 가득")

    monkeypatch.setattr(store, "put_bytes", boom)
    s, m2 = run(world, FakeTime(RUN_AT + timedelta(days=1)))
    assert s == "FAILED" and m2["integrity_error"].startswith("OSError")
    monkeypatch.setattr(store, "put_bytes", real)
    monkeypatch.setattr(
        store, "_publish", lambda *a, **k: (_ for _ in ()).throw(OSError("full"))
    )
    with pytest.raises(OSError):
        run(world, FakeTime(RUN_AT + timedelta(days=2)))
    runs, _ = store.list_runs(world["root"])
    assert [r.run_id for r in runs] == sorted([m1["run_id"], m2["run_id"]])
    assert store.verify_run(world["root"], runs[0]) == []


def test_busy_lock_writes_nothing(world):
    with store.file_lock(world["root"] / ".collect.lock") as ok:
        assert ok
        s, m = run(world, FakeTime())
    assert s == "BUSY" and store.list_runs(world["root"]) == ([], [])


def test_secrets_never_reach_evidence(world, monkeypatch):
    monkeypatch.setenv("KIWOOM_APP_KEY", "SECRET-KEY-POC605")
    monkeypatch.setenv("KIWOOM_APP_SECRET", "SECRET-SECRET-POC605")
    run(world, FakeTime())
    for p in world["root"].rglob("*"):
        if p.is_file():
            raw = p.read_bytes()
            if p.suffix == "" and raw[:2] == b"\x1f\x8b":
                import gzip

                raw = gzip.decompress(raw)
            assert b"SECRET-" not in raw, p


def test_collector_modules_do_not_import_training_code():
    code = (
        "import sys, importlib.util as u\n"
        "import app.ml_evidence.daily, app.ml_evidence.transfer\n"
        "import app.ml_evidence.export, app.ml_evidence.research\n"
        "spec = u.spec_from_file_location('cli', 'scripts/run_ml_evidence.py')\n"
        "m = u.module_from_spec(spec); spec.loader.exec_module(m)\n"
        "bad = [n for n in sys.modules if n.split('.')[0] in ('torch', 'sklearn') or n.startswith("
        "('app.d20', 'app.reentry_review', 'app.price_basis_check', 'app.holdings'))]\n"
        "print(sorted(bad))"
    )
    out = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "[]"


def test_pc_path_without_capture_is_unchanged(tmp_path):
    db = make_db(tmp_path / "m.sqlite")
    k = Kiwoom()
    msg = rf.refresh_investor_flows(
        db_path=db,
        now_utc=RUN_AT,
        start=date(2026, 10, 1),
        client=k,
        sleep=lambda s: None,
    )
    assert msg is None and len(k.asked) == len([d for d in KOSPI if d >= "2026-10-01"])


def _http_403_send(self, request, **kw):
    r = requests.Response()
    r.status_code, r._content, r.url, r.request = (
        403,
        b"Forbidden",
        request.url,
        request,
    )
    return r


def test_real_fdr_path_403_empty_frame_stops_immediately(monkeypatch):
    from app.market_data_fdr import _default_price_fetcher
    from app.three_push_runtime.market_data_batch import fdr_request_timeout

    monkeypatch.setattr(requests.Session, "send", _http_403_send)  # 네트워크 없음
    ft = FakeTime()
    w = ListWriter()
    out = daily_naver.fetch_windows(
        ["069500", "102110", "114800"],
        writer=w,
        target_day="2026-10-21",
        today_kst=date(2026, 10, 22),
        fetcher=_default_price_fetcher,
        request_timeout=fdr_request_timeout,
        now=ft.now,
        clock=ft.clock,
        sleep=ft.sleep,
    )
    assert out["attempted"] == 1 and "HTTP 403" in out["stop_reason"]
    assert w.lines[0]["http_status"] == 403 and w.lines[0]["error"] == "빈 응답"
    assert [x["status"] for x in w.lines[1:]] == ["NOT_ATTEMPTED", "NOT_ATTEMPTED"]


def test_corrupt_previous_object_is_rearchived_not_blocking(world):
    _, m1 = run(world, FakeTime())
    sha = m1["sources"]["krx_etf_close"]["object"]
    p = store.object_path(world["root"], sha)
    os.chmod(p, 0o644)
    raw = bytearray(p.read_bytes())
    raw[-1] ^= 0xFF  # 크기는 같고 내용만 다른 손상(크기 확인만으로는 못 잡는다)
    p.write_bytes(bytes(raw))
    s2, m2 = run(world, FakeTime(RUN_AT + timedelta(days=1)))
    k = m2["sources"]["krx_etf_close"]
    assert s2 != "FAILED" and k["previous_bad_objects"] == [sha]
    assert k["repaired_keys"] and m2["repaired_objects"] == [
        sha
    ]  # 같은 내용으로 되살림
    assert store.read_object(world["root"], sha)  # 이제 이름과 내용이 맞다
    assert list(
        (world["root"] / "objects" / ".corrupt").iterdir()
    )  # 손상본은 격리 보존
    runs, _ = store.list_runs(world["root"])
    assert store.verify_run(world["root"], runs[-1]) == []


def test_failed_previous_run_is_not_reused(world, monkeypatch):
    real = daily_tables.batch_records
    monkeypatch.setattr(
        daily_tables, "batch_records", lambda *a: (_ for _ in ()).throw(OSError("x"))
    )
    s1, m1 = run(world, FakeTime())
    assert s1 == "FAILED"
    monkeypatch.setattr(daily_tables, "batch_records", real)
    ft = FakeTime(RUN_AT + timedelta(hours=1))
    p = Prices(ft)
    _, m2 = run(world, ft, prices=p)
    assert sorted(p.calls) == sorted(TICKERS)  # 같은 기준일이어도 FAILED 판은 잇지 않음
    assert m2["previous_run"] is None and m2["skipped_failed_runs"] == [m1["run_id"]]
    from app.ml_evidence import export

    sel = export.select(world["root"], store.iso(RUN_AT + timedelta(days=1)))
    assert sorted(sel["windows"]) == sorted(TICKERS)


def test_all_acquisitions_failed_is_failed(world, monkeypatch):
    monkeypatch.delenv("KIWOOM_APP_KEY", raising=False)
    monkeypatch.delenv("KIWOOM_APP_SECRET", raising=False)
    ft = FakeTime()
    d = deps(ft, lister=lambda: (_ for _ in ()).throw(RuntimeError("down")))
    d.kiwoom_client = None
    d.fx_http_get = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("yahoo down"))
    s, m = daily.collect_daily(
        root=world["root"],
        db_path=world["tmp"] / "no.sqlite",
        calendar_dir=world["cal"],
        deps=d,
        site="TEST",
    )
    assert s == "FAILED" and m["status"] == "FAILED"
    fx = m["sources"]["fx_wti"]["series"]
    assert {v["state"] for v in fx.values()} == {"FETCH_OR_KEEP_FAILED"}
    assert all(v["reason"] == "RuntimeError" for v in fx.values())


def test_fx_fetch_failure_is_labelled_with_reason(world):
    def half(url, **kw):
        if "CL=F" in url:
            raise RuntimeError("wti down")
        return fx_get(url, **kw)

    ft = FakeTime()
    d = deps(ft)
    d.fx_http_get = half
    _, m = daily.collect_daily(
        root=world["root"],
        db_path=world["db"],
        calendar_dir=world["cal"],
        deps=d,
        site="T",
    )
    fx = m["sources"]["fx_wti"]
    assert fx["status"] == "PARTIAL"
    assert fx["series"][fst.WTI]["state"] == "FETCH_OR_KEEP_FAILED"
    assert fx["series"][fst.USDKRW]["state"] == "OK" and len(fx["objects"]) == 1


def test_restore_check_on_real_collector_bundle(world):
    run(world, FakeTime())
    _, m2 = run(world, FakeTime(RUN_AT + timedelta(days=1)))
    rep = store.restore_check(world["root"], m2["run_id"], world["tmp"] / "restore")
    assert (
        rep["status"] == "OK" and rep["same_read_result"] and rep["same_hash_and_list"]
    )
    assert "kospi_stored_dates" in {o["role"] for o in m2["objects"]}
    assert any(o.get("reused_from") for o in m2["objects"])  # 이전 판 참조까지 복원


def test_status_summary_shows_sources_failures_and_second_copy(world):
    from app.ml_evidence import status as st_mod

    ft = FakeTime()
    p = Prices(ft, fail={"102110": RuntimeError("x")})
    _, m = run(world, ft, prices=p)
    out = st_mod.summarize(
        world["root"], remote_rows=[{"run_id": "x", "manifest_sha256": "0"}]
    )
    d = out["latest_daily"]
    assert d["naver_etf_windows"]["missing"] == ["102110"]
    assert d["naver_etf_windows"]["observed_at_latest"].startswith("2026-10-22T00:40")
    assert (
        d["fx_wti"][fst.USDKRW]["observed_at"] and d["investor_flow"]["latest_received"]
    )
    assert out["second_copy"]["remote_only(이 장소에 사본 없음)"] == ["x"]
    assert out["second_copy"]["local_only(원격에 없음)"] == [m["run_id"]]


def test_missing_batch_state_file_downgrades_ok_to_partial(world, monkeypatch):
    monkeypatch.setattr(
        daily_tables, "batch_state_files", lambda: (world["tmp"] / "none.json",)
    )
    s, m = run(world, FakeTime())
    assert m["sources"]["batch_records"]["status"] == "FAILED" and s == "PARTIAL"


def test_observed_at_is_after_receipt_and_list_date_is_kst(world):
    ft = FakeTime()
    out, lines = _fw(Prices(ft), ft, tickers=["000001"])
    assert lines[0]["observed_at"] == store.iso(RUN_AT + timedelta(seconds=0.05))
    late = datetime(2026, 10, 22, 15, 30, tzinfo=timezone.utc)  # KST 10-23 00:30
    _, m = run(world, FakeTime(late))
    assert m["sources"]["etf_list"]["effective"]["list_date"] == "2026-10-23"


def test_single_flow_failure_without_stop_is_partial(world):
    k = Kiwoom(
        fail={KOSPI[-3]}
    )  # 한 날짜만 실패 · 다음 날짜는 성공(연속 아님 · 멈춤 없음)
    _, m = run(world, FakeTime(), kiwoom=k)
    f = m["sources"]["investor_flow"]
    assert f["not_attempted"] == [] and list(f["failed"]) == [KOSPI[-3]]
    assert f["status"] == "PARTIAL" and m["status"] == "PARTIAL"


def test_real_fdr_listing_path_gets_request_timeout(world, monkeypatch):
    seen = []

    def fake_send(self, request, **kw):
        seen.append(kw.get("timeout"))
        r = requests.Response()
        r.status_code, r._content, r.url, r.request = 500, b"{}", request.url, request
        return r

    monkeypatch.setattr(requests.Session, "send", fake_send)  # 네트워크 없음
    ft = FakeTime()
    d = daily.Deps(
        now=ft.now,
        clock=ft.clock,
        sleep=ft.sleep,
        price_fetcher=Prices(ft),
        fx_http_get=fx_get,
        kiwoom_client=Kiwoom(),
        git_head=lambda: None,
    )  # 목록 조회기 · 요청 상한 = 실제 기본값(FDR · fdr_request_timeout)
    _, m = daily.collect_daily(
        root=world["root"],
        db_path=world["db"],
        calendar_dir=world["cal"],
        deps=d,
        site="T",
    )
    assert seen and all(t == 20.0 for t in seen)  # 목록 요청에도 기존 20초 상한
    assert m["sources"]["etf_list"]["status"] == "FAILED"
