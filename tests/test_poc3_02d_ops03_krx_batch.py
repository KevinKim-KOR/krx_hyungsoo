"""POC3-02D-OPS-03 — KRX 목표일(T-1) 수집 · 시도 시각표 · 적재 성공 조건 · 날짜 창.

설계자 판정 STEP 12 검증 시나리오 1 · 2 · 3 · 4 · 5 · 9 · 10 · 12 (확정 계약 1 · 2 · 3 ·
5 · 6). 설계자 RESULT STEP 2 — 대표 커버리지(옛 ②)는 적재 성공 조건이 아니다(대표 누락
시나리오는 `test_poc3_02d_ops03_consumer_isolation.py`). 합성 캘린더 · 임시 DB · 가짜
fetcher · 가짜 시계만 쓴다. **외부 조회 0건 · 라이브 DB 미접근 · 실제 sleep 0.**
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

import pytest

from app import trading_day_lag
from app.market_briefing import krx_store, krx_target_checks, krx_target_sync, meta_gate

KST = timezone(timedelta(hours=9))
# 2026 실제 KRX 평일 휴장(광복절 대체 · 추석 · 개천절 대체 · 한글날).
HOLIDAYS = {"2026-08-17", "2026-09-24", "2026-09-25", "2026-10-05", "2026-10-09"}
TODAY = date(2026, 9, 30)
T1 = "2026-09-29"
T2 = "2026-09-28"
TICKERS = [f"T{i:03d}" for i in range(40)]
REPS = TICKERS[:27]


def _calendar(tmp_path):
    d = tmp_path / "cal"
    d.mkdir(exist_ok=True)
    day, lines = date(2026, 7, 1), ["date"]
    while day <= date(2026, 12, 30):
        if day.weekday() < 5 and day.isoformat() not in HOLIDAYS:
            lines.append(day.isoformat())
        day += timedelta(days=1)
    (d / "krx_trading_days_2026.csv").write_text("\n".join(lines) + "\n", "utf-8")
    return d


def _row(bas_dd, t, close=10000.0, **over):
    r = {
        "ISU_CD": t,
        "BAS_DD": bas_dd,
        "TDD_CLSPRC": f"{close:g}",
        "TDD_OPNPRC": f"{close:g}",
        "TDD_HGPRC": f"{close:g}",
        "TDD_LWPRC": f"{close:g}",
        "IDX_IND_NM": "코스피 200",
    }
    r.update(over)
    return r


def _rows(bas_dd, tickers=TICKERS):
    return [_row(bas_dd, t) for t in tickers]


def _seed(db, days, tickers=TICKERS):
    for d in days:
        krx_store.upsert_snapshot(
            [krx_store.SnapshotRow(date=d, ticker=t, close=10000.0) for t in tickers],
            db_path=db,
        )


def _window_before_t1(cal):
    """T-1 을 뺀 창 20거래일(창 21 = 이 20일 + T-1)."""
    return trading_day_lag.trading_days_ending(T2, 20, calendar_dir=cal)


def _env(tmp_path):
    p = tmp_path / ".env"
    p.write_text("KRX_API_KEY=DEADBEEF\n", encoding="utf-8")
    return p


def _csv(tmp_path, tickers=TICKERS):
    head = "단축코드,기초지수명,지수산출기관,기초자산분류,추적배수,복제방법\n"
    body = "".join(f"{t},코스피 200,KRX,주식,일반,실물(패시브)\n" for t in tickers)
    p = tmp_path / "krx_etf_basic_20260909.csv"
    p.write_bytes((head + body).encode("cp949"))
    return p


class Clock:
    """가짜 시계. `sleep` 은 시각만 앞으로 민다(실제로 기다리지 않는다)."""

    def __init__(self, hh, mm, ss=0, day=TODAY):
        self.t = datetime(day.year, day.month, day.day, hh, mm, ss, tzinfo=KST)
        self.sleeps = []

    def __call__(self):
        return self.t

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.t += timedelta(seconds=seconds)


class Fetcher:
    """`responses` 를 호출 순서대로 돌려준다. 함수면 `(bas_dd, n)` 으로 부른다."""

    def __init__(self, clock, respond, cost_seconds=2):
        self.clock, self.respond, self.cost = clock, respond, cost_seconds
        self.calls = []

    def __call__(self, bas_dd, key):
        assert key == "DEADBEEF"
        self.calls.append((self.clock().strftime("%H:%M:%S"), bas_dd))
        self.clock.t += timedelta(seconds=self.cost)
        out = self.respond(bas_dd, len(self.calls))
        if isinstance(out, Exception):
            raise out
        return out


@pytest.fixture
def env(tmp_path):
    cal = _calendar(tmp_path)
    db = tmp_path / "m.sqlite"
    _seed(db, _window_before_t1(cal))
    return {
        "cal": cal,
        "db": db,
        "cpath": tmp_path / "consistency.json",
        "env": _env(tmp_path),
        "csv": _csv(tmp_path),
    }


def _sync(env, clock, fetcher, **kw):
    args = dict(
        today=TODAY,
        consistency_path=env["cpath"],
        official_csv_path=env["csv"],
        db_path=env["db"],
        env_path=env["env"],
        calendar_dir=env["cal"],
        fetcher=fetcher,
        required_tickers=REPS,
        clock=clock,
        sleep=clock.sleep,
    )
    args.update(kw)
    return krx_target_sync.sync_krx_target(**args)


def _t1_on_first(n):
    return lambda bas_dd, i: _rows(bas_dd) if i > n else []


# ── 시나리오 1 · 2 · 3 — 시도 시각표 ──────────────────────────────────────────


def test_s1_t1_returned_at_0810_first_attempt(env):
    clock = Clock(8, 10, 20)
    f = Fetcher(clock, lambda b, i: _rows(b))
    out = _sync(env, clock, f)

    assert out["status"] == krx_target_sync.STATUS_OK, out
    assert out["mode"] == krx_target_sync.MODE_SCHEDULED
    assert out["target_date"] == T1 and out["basis_date"] == "20260929"
    assert [c[1] for c in f.calls] == ["20260929"]  # 목표일 단일 조회 · 역탐색 없음
    assert clock.sleeps == []
    (a,) = out["attempts"]
    assert a["result"] == "ok" and a["at_kst"].endswith("08:10:20+09:00")
    assert a["http"] == 200 and a["rows"] == a["priced_rows"] == len(TICKERS)
    assert a["write"] == "inserted" and a["readback_rows"] == len(TICKERS)
    assert krx_store.row_count_on(T1, db_path=env["db"]) == len(TICKERS)
    saved = meta_gate.load_consistency(env["cpath"])
    assert saved.evaluated_api_basis_date == "20260929"
    d20 = trading_day_lag.trading_days_back(T1, 20, calendar_dir=env["cal"])
    assert saved.evaluated_window_d20_date == d20
    assert out["window"]["usable"] is True and out["backfill"]["missing_before"] == []


@pytest.mark.parametrize("fail_first, slot", [(1, "08:15"), (2, "08:20"), (3, "08:24")])
def test_s2_success_on_later_slot(env, fail_first, slot):
    clock = Clock(8, 10, 20)
    f = Fetcher(clock, _t1_on_first(fail_first))
    out = _sync(env, clock, f)

    assert out["status"] == "ok", out
    times = [a["at_kst"][11:16] for a in out["attempts"]]
    assert times == ["08:10", "08:15", "08:20", "08:24"][: fail_first + 1]
    assert times[-1] == slot
    assert [a["result"] for a in out["attempts"]][:-1] == ["not_published"] * fail_first
    assert all(c[1] == "20260929" for c in f.calls)
    assert krx_store.row_count_on(T1, db_path=env["db"]) == len(TICKERS)


def test_s3_not_published_until_0827_fails_closed(env):
    # 직전 판정(T-2)이 있던 날 — '판정 못 함' 으로 바뀌어 08:30 은 구역을 닫는다.
    meta_gate.save_consistency(
        meta_gate.ConsistencyResult(
            status="ok",
            evaluated_api_basis_date="20260928",
            evaluated_at_kst="2026-09-29T08:10:30+09:00",
        ),
        env["cpath"],
    )
    clock = Clock(8, 10, 20)
    f = Fetcher(clock, lambda b, i: [])
    out = _sync(env, clock, f)

    assert out["status"] == krx_target_sync.STATUS_TARGET_NOT_OBTAINED
    times = [a["at_kst"][11:19] for a in out["attempts"]]
    assert times == ["08:10:20", "08:15:00", "08:20:00", "08:24:00"]
    assert all(t < "08:27:00" for t in times)
    assert krx_store.row_count_on(T1, db_path=env["db"]) == 0
    saved = meta_gate.load_consistency(env["cpath"])
    assert saved.status == meta_gate.STATUS_API_FETCH_FAILED
    assert (
        saved.evaluated_api_basis_date is None
    )  # T-2 판정을 오늘 것처럼 남기지 않는다
    assert "target_not_obtained:not_published" in saved.error


def test_schedule_boundaries():
    plan = krx_target_sync.attempt_plan
    at = lambda h, m, s=0: datetime(2026, 9, 30, h, m, s, tzinfo=KST)  # noqa: E731
    assert plan(at(7, 20, 25)) == (krx_target_sync.MODE_SKIPPED_BEFORE_OPEN, [])
    assert plan(at(7, 59, 59))[1] == []
    mode, p = plan(at(8, 5))
    assert mode == "scheduled" and [x.strftime("%H:%M") for x in p] == [
        "08:10",
        "08:15",
        "08:20",
        "08:24",
    ]
    assert [x.strftime("%H:%M:%S") for x in plan(at(8, 16, 30))[1]] == [
        "08:16:30",
        "08:20:00",
        "08:24:00",
    ]
    assert plan(at(8, 26, 59))[1] == [at(8, 26, 59)]
    assert plan(at(8, 27)) == (krx_target_sync.MODE_SINGLE, [at(8, 27)])
    assert plan(at(9, 20)) == (krx_target_sync.MODE_SINGLE, [at(9, 20)])
    assert plan(at(8, 12), max_attempts=1) == (krx_target_sync.MODE_SINGLE, [at(8, 12)])
    # 단계 시작 60초 안의 슬롯은 시작 시도에 합친다(1초 간격 연속 시도 없음).
    assert plan(at(8, 23, 59))[1] == [at(8, 23, 59)]
    assert plan(at(8, 14, 59))[1] == [at(8, 14, 59), at(8, 20), at(8, 24)]
    assert plan(at(8, 14))[1] == [at(8, 14), at(8, 15), at(8, 20), at(8, 24)]


def test_started_before_0800_is_skipped_and_touches_nothing(tmp_path):
    cal = _calendar(tmp_path)
    clock = Clock(7, 20, 25)
    f = Fetcher(clock, lambda b, i: _rows(b))
    db, cpath = tmp_path / "m.sqlite", tmp_path / "c.json"
    out = krx_target_sync.sync_krx_target(
        today=TODAY,
        consistency_path=cpath,
        official_csv_path=_csv(tmp_path),
        db_path=db,
        env_path=_env(tmp_path),
        calendar_dir=cal,
        fetcher=f,
        required_tickers=REPS,
        clock=clock,
        sleep=clock.sleep,
    )
    assert out["status"] == krx_target_sync.STATUS_SKIPPED_BEFORE_OPEN
    assert f.calls == [] and clock.sleeps == []
    assert not db.exists() and not cpath.exists()  # 표 · 정합성 JSON 을 건드리지 않았다


def test_started_0805_waits_for_0810(env):
    clock = Clock(8, 5, 0)
    f = Fetcher(clock, lambda b, i: _rows(b))
    out = _sync(env, clock, f)
    assert out["status"] == "ok"
    assert clock.sleeps == [300.0] and f.calls[0][0] == "08:10:00"


def test_started_after_0827_single_attempt(env):
    clock = Clock(8, 40, 0)
    f = Fetcher(clock, lambda b, i: [])
    out = _sync(env, clock, f)
    assert out["mode"] == krx_target_sync.MODE_SINGLE
    assert len(out["attempts"]) == 1 and clock.sleeps == []
    assert out["status"] == krx_target_sync.STATUS_TARGET_NOT_OBTAINED


def test_no_new_attempt_after_deadline_when_attempts_are_slow(env):
    # 시도 하나가 6분 걸리면 08:24 슬롯은 08:28 이 되어 시도하지 않는다.
    clock = Clock(8, 22, 0)
    f = Fetcher(clock, lambda b, i: [], cost_seconds=360)
    out = _sync(env, clock, f)
    assert len(out["attempts"]) == 1 and out.get("deadline_reached") is True


# ── 시나리오 4 · 5 — 성공 조건 ────────────────────────────────────────────────


def test_s4_only_t2_returned_is_not_success(env):
    before = krx_store.row_count_on(T2, db_path=env["db"])
    clock = Clock(8, 10, 20)
    f = Fetcher(clock, lambda b, i: _rows("20260928"))
    out = _sync(env, clock, f)
    assert out["status"] == krx_target_sync.STATUS_TARGET_NOT_OBTAINED
    assert {a["result"] for a in out["attempts"]} == {"basis_date_mismatch"}
    assert out["attempts"][0]["returned_basis_dates"] == ["20260928"]
    assert krx_store.row_count_on(T1, db_path=env["db"]) == 0
    assert krx_store.row_count_on(T2, db_path=env["db"]) == before


def _bad_then_good(bad):
    return lambda b, i: bad(b) if i == 1 else _rows(b)


@pytest.mark.parametrize(
    "bad, expected",
    [
        (lambda b: [], "not_published"),
        (lambda b: [_row(b, t, TDD_CLSPRC="") for t in TICKERS], "not_published"),
        (lambda b: _rows(b, TICKERS[:37]), "row_drop"),  # 37/40 = 92.5% < 95%
        (
            lambda b: _rows(b)[:-1] + [_row(b, TICKERS[-1], TDD_CLSPRC="")],
            "invalid_snapshot",
        ),  # 공개 도중 가격 일부 빈 응답
        (lambda b: _rows(b) + [_row(b, TICKERS[0])], "invalid_snapshot"),  # 중복
        (
            lambda b: _rows(b)[:-1] + [_row(b, TICKERS[-1], TDD_HGPRC="9000")],
            "invalid_snapshot",
        ),  # 관계식(종가 > 고가)
    ],
)
def test_s5_bad_response_is_retried_and_never_partially_saved(env, bad, expected):
    clock = Clock(8, 10, 20)
    f = Fetcher(clock, _bad_then_good(bad))
    out = _sync(env, clock, f)
    first, second = out["attempts"]
    assert first["result"] == expected, first
    assert second["result"] == "ok" and second["at_kst"][11:16] == "08:15"
    assert krx_store.row_count_on(T1, db_path=env["db"]) == len(TICKERS)


def test_s5_row_ratio_boundary_is_95_percent_of_previous_load(env):
    # 직전 정상 적재 40행 → 38행(95%) 통과 · 고정 행 수 비교가 아니다.
    clock = Clock(8, 10, 20)
    f = Fetcher(clock, lambda b, i: _rows(b, TICKERS[:38]))
    out = _sync(env, clock, f, required_tickers=TICKERS[:27])
    (a,) = out["attempts"]
    assert a["result"] == "ok" and a["baseline_rows"] == 40 and a["baseline_date"] == T2


def test_s5_zero_volume_rows_are_not_relation_violations():
    rows = [_row("20260929", "A"), _row("20260929", "B", TDD_OPNPRC="0")]
    rows[1].update(TDD_HGPRC="0", TDD_LWPRC="0")
    assert krx_target_checks.relation_violation(rows) is None
    rows[1]["TDD_HGPRC"] = "10000"  # 일부만 0 — 위반
    assert krx_target_checks.relation_violation(rows) == "B"


def test_readback_mismatch_rolls_back_the_date(env, monkeypatch):
    real_rows, real_upsert = krx_store.rows_on, krx_store.upsert_snapshot
    written = {"flag": False}

    def _upsert(rows, *, db_path=None):
        written["flag"] = True
        return real_upsert(rows, db_path=db_path)

    def _short(date_, *, db_path=None):
        got = real_rows(date_, db_path=db_path)
        # 쓰기 직후 read-back 만 어긋난다(저장 계층이 행을 잃은 경우).
        if written["flag"] and date_ == T1 and got:
            got.pop(sorted(got)[0])
        return got

    monkeypatch.setattr(krx_store, "upsert_snapshot", _upsert)
    monkeypatch.setattr(krx_store, "rows_on", _short)
    clock = Clock(8, 40, 0)
    out = _sync(env, clock, Fetcher(clock, lambda b, i: _rows(b)))
    (a,) = out["attempts"]
    assert a["result"] == "readback_mismatch" and a["write"] == "rolled_back"
    assert krx_store.row_count_on(T1, db_path=env["db"]) == 0  # 부분 snapshot 없음


def test_attempt_log_has_no_key_or_price_values(env):
    clock = Clock(8, 10, 20)
    out = _sync(env, clock, Fetcher(clock, _t1_on_first(1)))
    text = json.dumps(out["attempts"], ensure_ascii=False)
    assert "DEADBEEF" not in text and "10000" not in text
    keys = {"at_kst", "target", "http", "rows", "priced_rows", "result", "error_type"}
    assert keys <= set(out["attempts"][0])


def test_fetch_exception_is_recorded_with_type(env):
    class _Resp:
        status_code = 503

    class _HTTPError(Exception):
        response = _Resp()

    clock = Clock(8, 40, 0)
    out = _sync(env, clock, Fetcher(clock, lambda b, i: _HTTPError("boom")))
    (a,) = out["attempts"]
    assert a["result"] == "fetch_error" and a["error_type"] == "_HTTPError"
    assert a["http"] == 503


# ── 시나리오 9 — 한국 휴장일 ─────────────────────────────────────────────────


def test_s9_expected_t1_skips_korean_holidays(tmp_path):
    cal = _calendar(tmp_path)
    exp = trading_day_lag.expected_previous_trading_day
    assert exp("2026-09-28", calendar_dir=cal) == "2026-09-23"  # 추석 · 주말
    assert exp("2026-10-06", calendar_dir=cal) == "2026-10-02"  # 개천절 대체 · 주말
    assert exp("2026-09-30", calendar_dir=cal) == T1
    # 캘린더가 그해를 덮지 않으면 평일 fallback — 휴장일이 T-1 로 잡혀 보수적으로 막힌다.
    assert exp("2027-01-04", calendar_dir=cal) == "2027-01-01"
    assert exp("not-a-date", calendar_dir=cal) is None


def test_s9_sync_fetches_only_the_calendar_t1_after_holidays(tmp_path):
    cal = _calendar(tmp_path)
    db = tmp_path / "m.sqlite"
    _seed(db, trading_day_lag.trading_days_ending("2026-09-22", 20, calendar_dir=cal))
    clock = Clock(8, 10, 20, day=date(2026, 9, 28))
    f = Fetcher(clock, lambda b, i: _rows(b))
    out = krx_target_sync.sync_krx_target(
        today=date(2026, 9, 28),
        consistency_path=tmp_path / "c.json",
        official_csv_path=_csv(tmp_path),
        db_path=db,
        env_path=_env(tmp_path),
        calendar_dir=cal,
        fetcher=f,
        required_tickers=REPS,
        clock=clock,
        sleep=clock.sleep,
    )
    assert out["status"] == "ok" and out["target_date"] == "2026-09-23"
    assert [c[1] for c in f.calls] == [
        "20260923"
    ]  # 0927 · 0926 · 0925 · 0924 조회 없음


# ── 시나리오 10 — 거래일 날짜 기준 5일 · 20일 ─────────────────────────────────


def test_s10_one_missing_day_does_not_shift_d5_d20(tmp_path):
    cal = _calendar(tmp_path)
    db = tmp_path / "m.sqlite"
    # 22거래일 중 창 가운데 하루 누락 — 저장일은 21개라 옛 행 순서 창도 만들어진다.
    days = trading_day_lag.trading_days_ending(T1, 22, calendar_dir=cal)
    _seed(db, [d for d in days if d != "2026-09-21"])

    w = krx_store.resolve_calendar_window(T1, calendar_dir=cal, db_path=db)
    assert (w.latest, w.d5, w.d20) == (T1, "2026-09-18", "2026-08-28")
    assert w.missing_days == ("2026-09-21",) and w.usable is True
    # 저장 행 순서 창은 밀린다 — 이 차이가 확정 계약 5 의 결함이다.
    rows_window = krx_store.resolve_window(db_path=db)
    assert (rows_window.d5, rows_window.d20) == ("2026-09-17", "2026-08-27")


def test_s10_missing_required_date_fails_closed(tmp_path):
    cal = _calendar(tmp_path)
    db = tmp_path / "m.sqlite"
    days = trading_day_lag.trading_days_ending(T1, 21, calendar_dir=cal)
    _seed(db, [d for d in days if d != "2026-09-18"])  # d5 누락
    w = krx_store.resolve_calendar_window(T1, calendar_dir=cal, db_path=db)
    assert w.usable is False and w.missing_required == ("2026-09-18",)
    assert w.to_dict()["missing_required"] == ["2026-09-18"]


def test_s10_sync_fills_missing_window_day_once(env):
    krx_store.delete_date("2026-09-21", db_path=env["db"])
    clock = Clock(8, 10, 20)
    f = Fetcher(clock, lambda b, i: _rows(b))
    out = _sync(env, clock, f)
    assert [c[1] for c in f.calls] == ["20260929", "20260921"]  # 날짜당 1회
    assert out["backfill"]["filled"] == ["2026-09-21"]
    assert out["window"]["missing_days"] == [] and out["window"]["usable"] is True


def test_s10_unfilled_d5_leaves_window_unusable_and_records_calendar_d20(env):
    krx_store.delete_date("2026-09-18", db_path=env["db"])
    clock = Clock(8, 10, 20)

    def _respond(b, i):
        return RuntimeError("down") if b == "20260918" else _rows(b)

    out = _sync(env, clock, Fetcher(clock, _respond))
    assert out["status"] == "ok"  # T-1 자체는 받았다
    assert out["backfill"]["stopped"] == "fetch_error"
    assert out["window"]["usable"] is False
    assert out["window"]["missing_required"] == ["2026-09-18"]
    saved = meta_gate.load_consistency(env["cpath"])
    assert saved.evaluated_window_d20_date == "2026-08-28"  # 캘린더 날짜 · 밀리지 않음


def test_s10_backfill_stops_at_first_fetch_error(env):
    """조회 예외가 나면 남은 빈 날을 부르지 않는다(원천 장애 · timeout 누적 방지)."""
    for d in ("2026-09-18", "2026-09-21"):
        krx_store.delete_date(d, db_path=env["db"])
    clock = Clock(8, 10, 20)

    def _respond(b, i):
        return RuntimeError("down") if b == "20260918" else _rows(b)

    f = Fetcher(clock, _respond)
    out = _sync(env, clock, f)
    assert [c[1] for c in f.calls] == ["20260929", "20260918"]  # 09-21 은 안 부른다
    assert out["backfill"]["missing_before"] == ["2026-09-18", "2026-09-21"]
    assert out["backfill"]["stopped"] == "fetch_error"
    assert [x["date"] for x in out["backfill"]["failed"]] == ["2026-09-18"]


def test_s10_backfill_stops_at_0827_deadline(env):
    """08:27 뒤에는 빈 날 채우기도 새 조회를 시작하지 않는다(확정 계약 2)."""
    for d in ("2026-09-18", "2026-09-21", "2026-09-22"):
        krx_store.delete_date(d, db_path=env["db"])
    clock = Clock(8, 26, 50)
    f = Fetcher(clock, lambda b, i: _rows(b), cost_seconds=5)
    out = _sync(env, clock, f)
    # 08:26:50 T-1 → 08:26:55 09-18 → 08:27:00 마감(09-21 · 09-22 안 부름).
    assert f.calls == [("08:26:50", "20260929"), ("08:26:55", "20260918")]
    assert out["backfill"]["stopped"] == "deadline"
    assert out["backfill"]["filled"] == ["2026-09-18"]


def test_s10_backfill_retried_once_after_later_t1_success(env):
    """08:10 일시 장애로 못 부른 빈 날은 T-1 을 받은 뒤 한 번 더 채운다(PLAN STEP 3-3).

    설계자 RESULT STEP 6 — 재시도는 **오늘 아직 부르지 않은 날만**. 08:10 에 이미
    부른 09-18 은 다시 부르지 않는다(ledger).
    """
    for d in ("2026-09-18", "2026-09-21"):
        krx_store.delete_date(d, db_path=env["db"])
    clock = Clock(8, 10, 20)

    def _respond(b, i):
        # 08:10 목표일은 공개 전(원천에는 닿았다) · 채우기 첫 날짜에서 일시 장애.
        if i == 1:
            return []
        return RuntimeError("blip") if i == 2 else _rows(b)

    f = Fetcher(clock, _respond)
    out = _sync(env, clock, f)
    assert [c[1] for c in f.calls] == ["20260929", "20260918", "20260929", "20260921"]
    assert out["backfill"]["stopped"] == "fetch_error"
    assert out["backfill"]["called"] == ["2026-09-18"]
    assert out["backfill_retry"]["skipped_called_today"] == ["2026-09-18"]
    assert (
        out["backfill_retry"]["called"]
        == out["backfill_retry"]["filled"]
        == ["2026-09-21"]
    )
    assert out["backfill_retry"]["calls_today"] == {"2026-09-18": 1, "2026-09-21": 1}
    assert out["window"]["missing_required"] == ["2026-09-18"]  # d5 는 내일 다시


def test_s10_backfill_waits_while_target_fetch_cannot_reach_source(env, tmp_path):
    """08:10 원천 불통(목표일 `fetch_error`) — 채우기를 부르지 않고 원천에 닿은 시도 뒤로
    미룬다. 불통 중에 부르면 ledger 가 그 날짜를 오늘 부른 것으로 남겨 원천이 돌아와도
    오늘(09:20 포함) 다시 부르지 못한다(설계자 RESULT STEP 6)."""
    krx_store.delete_date("2026-09-18", db_path=env["db"])
    ledger = tmp_path / "ledger.json"
    clock = Clock(8, 10, 20)

    def _respond(b, i):
        # Fetcher 는 응답을 만들기 전에 시계를 2초 민다 — 부른 시각으로 판정한다.
        return RuntimeError("down") if f.calls[-1][0] < "08:15:00" else _rows(b)

    f = Fetcher(clock, _respond)
    out = _sync(env, clock, f, backfill_ledger_path=ledger)
    assert f.calls == [
        ("08:10:20", "20260929"),  # 원천 불통 — 채우기 없음
        ("08:15:00", "20260929"),
        ("08:15:02", "20260918"),  # 원천에 닿은 시도 뒤 첫 채우기
    ]
    assert out["attempts"][0]["result"] == "fetch_error"
    assert out["backfill"]["called"] == out["backfill"]["filled"] == ["2026-09-18"]
    assert "backfill_retry" not in out
    assert out["window"]["usable"] is True
    assert json.loads(ledger.read_text("utf-8"))["calls"] == {"2026-09-18": 1}


def test_s10_no_backfill_when_every_target_attempt_is_fetch_error(env, tmp_path):
    krx_store.delete_date("2026-09-18", db_path=env["db"])
    ledger = tmp_path / "ledger.json"
    clock = Clock(8, 10, 20)
    f = Fetcher(clock, lambda b, i: RuntimeError("down"))
    out = _sync(env, clock, f, backfill_ledger_path=ledger)
    assert [c[1] for c in f.calls] == ["20260929"] * 4
    assert "backfill" not in out and not ledger.exists()


def test_s11_already_loaded_run_fills_window_gap_without_t1_refetch(env):
    """T-1 은 받았고 창에 빈 날 — 09:20 실행이 빈 날만 채운다(T-1 재조회 · 재판정 없음).

    설계자 RESULT STEP 6 — 08:10 에 이미 부른 날(09-18)은 09:20 에 다시 부르지 않고,
    08:10 에 원천 오류로 멈춰 못 부른 날(09-21)만 부른다.
    """
    clock = Clock(8, 10, 20)

    def _first(b, i):
        return RuntimeError("down") if b == "20260918" else _rows(b)

    for d in ("2026-09-18", "2026-09-21"):
        krx_store.delete_date(d, db_path=env["db"])
    first = _sync(env, clock, Fetcher(clock, _first))
    assert first["status"] == "ok" and first["window"]["usable"] is False
    assert first["backfill"]["called"] == ["2026-09-18"]  # 09-21 은 못 불렀다
    snap = env["cpath"].read_bytes()

    clock2 = Clock(9, 20, 0)
    f = Fetcher(clock2, lambda b, i: _rows(b))
    again = _sync(env, clock2, f)
    assert again["mode"] == "already_loaded"
    assert f.calls == [("09:20:00", "20260921")]
    assert again["backfill"]["skipped_called_today"] == ["2026-09-18"]
    assert again["backfill"]["filled"] == ["2026-09-21"]
    assert env["cpath"].read_bytes() == snap
    w = krx_store.resolve_calendar_window(
        T1, calendar_dir=env["cal"], db_path=env["db"]
    )
    assert w.missing_days == ("2026-09-18",)


def test_uncovered_year_unstored_weekday_fails_window_closed(tmp_path):
    """캘린더 없는 해 — 평일 fallback 날이 저장돼 있지 않으면(휴장일일 수 있다) 창을 닫는다.

    2027-01-01(금 · 신정)을 거래일로 치면 d5 · d20 이 하루씩 늦은 날로 잡혀 4 · 19거래일
    수익률을 5 · 20일로 보고한다(리뷰 L2-2). 저장된 평일만 있으면 그대로 쓴다.
    """
    cal = _calendar(tmp_path)  # 2026 만 덮는다
    db = tmp_path / "m.sqlite"
    latest = "2027-01-05"
    days = trading_day_lag.trading_days_ending(latest, 21, calendar_dir=cal)
    assert "2027-01-01" in days  # fallback 이 휴장일을 거래일로 친다
    _seed(db, [d for d in days if d != "2027-01-01"])
    w = krx_store.resolve_calendar_window(latest, calendar_dir=cal, db_path=db)
    assert w.unconfirmed_days == ("2027-01-01",)
    assert w.usable is False and "2027-01-01" in w.to_dict()["missing_required"]

    _seed(db, ["2027-01-01"])  # 그 평일이 실제로 저장돼 있으면(거래일) 쓸 수 있다
    w2 = krx_store.resolve_calendar_window(latest, calendar_dir=cal, db_path=db)
    assert w2.unconfirmed_days == () and w2.usable is True


def test_window_helpers_match_calendar(tmp_path):
    cal = _calendar(tmp_path)
    assert trading_day_lag.trading_window_dates(T1, calendar_dir=cal) == (
        T1,
        "2026-09-18",
        "2026-08-28",
    )
    assert trading_day_lag.trading_days_back("2026-09-24", 5, calendar_dir=cal) is None
    assert trading_day_lag.trading_days_back(T1, 0, calendar_dir=cal) == T1
    assert len(trading_day_lag.trading_days_ending(T1, 21, calendar_dir=cal)) == 21


# ── 시나리오 12 — 재실행 · 성공한 T-1 보존 ────────────────────────────────────


def test_s12_rerun_does_not_refetch_or_duplicate(env):
    clock = Clock(8, 10, 20)
    first = _sync(env, clock, Fetcher(clock, lambda b, i: _rows(b)))
    assert first["status"] == "ok"
    snap = env["cpath"].read_bytes()
    n = krx_store.row_count_on(T1, db_path=env["db"])

    # 뒤 실행이 T-2 · 실패 응답을 받아도 성공한 T-1 을 덮지 않는다(조회 자체가 없다).
    for respond in (lambda b, i: _rows("20260928"), lambda b, i: RuntimeError("x")):
        clock2 = Clock(9, 20, 0)
        f = Fetcher(clock2, respond)
        again = _sync(env, clock2, f)
        assert again["status"] == "ok" and again["mode"] == "already_loaded"
        assert f.calls == []
        assert env["cpath"].read_bytes() == snap
        assert krx_store.row_count_on(T1, db_path=env["db"]) == n


def test_s12_t1_judgment_is_not_overwritten_by_later_failure(env):
    # 정합성 JSON 은 T-1 판정인데 표에 T-1 이 없는 어긋난 상태 — 실패가 판정을 지우지 않는다.
    meta_gate.save_consistency(
        meta_gate.ConsistencyResult(
            status="ok",
            evaluated_api_basis_date="20260929",
            evaluated_at_kst="2026-09-30T08:10:30+09:00",
        ),
        env["cpath"],
    )
    snap = env["cpath"].read_bytes()
    clock = Clock(9, 20, 0)
    out = _sync(env, clock, Fetcher(clock, lambda b, i: []))
    assert out["status"] == krx_target_sync.STATUS_TARGET_NOT_OBTAINED
    assert out["consistency_kept"] is True
    assert env["cpath"].read_bytes() == snap


def test_s12_existing_t1_rows_are_kept_only_when_identical(env):
    # T-1 은 표에 있으나 판정이 없다(판정 전 중단) — 응답과 저장분이 같으면 다시 쓰지 않는다.
    _seed(env["db"], [T1])
    clock = Clock(9, 20, 0)
    out = _sync(env, clock, Fetcher(clock, lambda b, i: _rows(b)))
    (a,) = out["attempts"]
    assert a["result"] == "ok" and a["write"] == "kept_existing"
    assert a["readback_rows"] == len(TICKERS)
    assert meta_gate.load_consistency(env["cpath"]).evaluated_api_basis_date == (
        "20260929"
    )


@pytest.mark.parametrize(
    "stored, response, closes",
    [
        (TICKERS[:20], TICKERS, None),  # 판정 전 중단으로 남은 부분 저장 — 채운다
        (TICKERS, TICKERS[:39], None),  # 저장분이 더 많다 — 판정한 snapshot 과 같게
        (TICKERS, TICKERS, 10100.0),  # 종목은 같고 값이 다르다
    ],
)
def test_s12_existing_t1_rows_that_differ_are_replaced_and_read_back(
    env, stored, response, closes
):
    """검증자 r1 A-1 — 기존 행이 있다는 이유로 건수 · 값 확인 없이 성공하지 않는다."""
    _seed(env["db"], [T1], tickers=stored)
    clock = Clock(9, 20, 0)
    value = closes or 10000.0
    out = _sync(
        env, clock, Fetcher(clock, lambda b, i: [_row(b, t, value) for t in response])
    )
    (a,) = out["attempts"]
    assert a["result"] == "ok" and a["write"] == "replaced"
    assert a["replaced_rows"] == len(stored) and a["readback_rows"] == len(response)
    assert krx_store.rows_on(T1, db_path=env["db"]) == {t: value for t in response}
    saved = meta_gate.load_consistency(env["cpath"])
    assert saved.evaluated_api_basis_date == "20260929"


def test_s12_replaced_rows_that_do_not_read_back_leave_the_date_empty(env, monkeypatch):
    _seed(env["db"], [T1], tickers=TICKERS[:20])
    real_rows, real_replace = krx_store.rows_on, krx_store.replace_date
    written = {"flag": False}

    def _replace(rows, *, db_path=None):
        written["flag"] = True
        return real_replace(rows, db_path=db_path)

    def _short(date_, *, db_path=None):
        got = real_rows(date_, db_path=db_path)
        if written["flag"] and date_ == T1 and got:
            got.pop(sorted(got)[0])
        return got

    monkeypatch.setattr(krx_store, "replace_date", _replace)
    monkeypatch.setattr(krx_store, "rows_on", _short)
    clock = Clock(9, 20, 0)
    out = _sync(env, clock, Fetcher(clock, lambda b, i: _rows(b)))
    (a,) = out["attempts"]
    assert a["result"] == "readback_mismatch" and a["write"] == "rolled_back"
    assert out["status"] == krx_target_sync.STATUS_TARGET_NOT_OBTAINED
    assert krx_store.row_count_on(T1, db_path=env["db"]) == 0  # fail-closed
    saved = meta_gate.load_consistency(env["cpath"])
    assert saved.evaluated_api_basis_date != "20260929"


def test_replace_date_is_one_transaction(tmp_path):
    db = tmp_path / "m.sqlite"
    _seed(db, [T1], tickers=TICKERS[:5])
    rows = [krx_store.SnapshotRow(date=T1, ticker=t, close=1.0) for t in TICKERS[:3]]
    assert krx_store.replace_date(rows, db_path=db) == 3
    assert krx_store.rows_on(T1, db_path=db) == {t: 1.0 for t in TICKERS[:3]}


# ── 필수 대표 ETF · API 키 ───────────────────────────────────────────────────


def test_required_representatives_come_from_active_config(monkeypatch):
    from app.intraday_config import store

    payload = {
        "sector_representative_universe": {
            "sectors": [
                {"representative": {"ticker": "A"}, "alternate": {"ticker": "A2"}},
                {"representative": {"ticker": "B"}},
            ]
        },
        "intraday_alert_policy": {"enabled": False},
    }
    monkeypatch.setattr(
        store, "get_active", lambda **kw: {"payload_json": json.dumps(payload)}
    )
    assert krx_target_checks.load_required_representatives() == ["A", "B"]
    # 대표 없는 사업군이 있으면 전체 대표를 모른다 — 줄여 세지 않는다.
    broken = json.loads(json.dumps(payload))
    broken["sector_representative_universe"]["sectors"].append({"sector_key": "C"})
    monkeypatch.setattr(
        store, "get_active", lambda **kw: {"payload_json": json.dumps(broken)}
    )
    assert krx_target_checks.load_required_representatives() is None
    monkeypatch.setattr(store, "get_active", lambda **kw: None)
    assert krx_target_checks.load_required_representatives() is None

    def _boom(**kw):
        raise RuntimeError("db")

    monkeypatch.setattr(store, "get_active", _boom)
    assert krx_target_checks.load_required_representatives() is None


def test_missing_api_key_makes_no_call(env, tmp_path):
    clock = Clock(8, 10, 20)
    f = Fetcher(clock, lambda b, i: _rows(b))
    out = _sync(env, clock, f, env_path=tmp_path / "none.env")
    assert out["status"] == krx_target_sync.STATUS_NO_API_KEY and f.calls == []
