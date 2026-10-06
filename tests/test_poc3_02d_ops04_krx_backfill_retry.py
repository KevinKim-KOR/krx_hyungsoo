"""POC3-02D-OPS-04 항목 5 — 09:20 누락일 1회 재시도(설계자 Q6 b · 2026-10-04).

```text
일시 오류(timeout · 연결 오류 · RemoteProtocolError · HTTP 5xx · 429)   09:20 보강이 1회 더 부른다
영구 실패(그 밖 예외 · 3xx · 다른 4xx · 검증 실패)  같은 날 다시 부르지 않는다
날짜별 하루 최대                                    최초 1회 + 보강 1회
08:10 같은 실행 재채우기 · 수동 재실행               보강하지 않는다(지금처럼 건너뜀)
보강 실행                                          새 보강 대상을 만들지 않는다
```

합성 캘린더 · 임시 DB · 가짜 fetcher · 가짜 시계만 쓴다. **외부 조회 0건 · 라이브 DB ·
state · logs 미접근 · 실제 sleep 0.**
"""

from __future__ import annotations

import functools
import json
import logging
from datetime import datetime, timezone

import httpx
import pytest

from app.market_briefing import krx_backfill, krx_store, krx_target_sync
from app.market_briefing.krx_target_checks import is_transient_fetch_error
from app.three_push_runtime import market_data_batch as mdb
from tests import test_poc3_02d_ops03_krx_batch as kb

TODAY = kb.TODAY  # 2026-09-30
D = "2026-09-18"
D_BAS = "20260918"


@pytest.fixture
def env(tmp_path):
    cal = kb._calendar(tmp_path)
    db = tmp_path / "m.sqlite"
    kb._seed(db, kb._window_before_t1(cal))
    krx_store.delete_date(D, db_path=db)
    return {
        "cal": cal,
        "db": db,
        "cpath": tmp_path / "consistency.json",
        "env": kb._env(tmp_path),
        "csv": kb._csv(tmp_path),
        "ledger": tmp_path / "ledger.json",
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
        clock=clock,
        sleep=clock.sleep,
        backfill_ledger_path=env["ledger"],
        required_tickers=kb.REPS,
    )
    args.update(kw)
    return krx_target_sync.sync_krx_target(**args)


def _http_error(code):
    req = httpx.Request("GET", "https://example.invalid/x")
    return httpx.HTTPStatusError(
        "x", request=req, response=httpx.Response(code, request=req)
    )


def _morning(env, failure):
    """08:10 — T-1 은 받고 창 안 빈 날(09-18)은 `failure` 로 끝난다."""
    clock = kb.Clock(8, 10, 20)

    def _respond(b, i):
        return failure if b == D_BAS else kb._rows(b)

    f = kb.Fetcher(clock, _respond)
    return _sync(env, clock, f), f


def _reinforce(env, *, respond=None, reinforcement=True, hh=9, mm=20):
    """09:20 보강(이미 받은 날) — 창 안 빈 날만 본다."""
    clock = kb.Clock(hh, mm, 0)
    f = kb.Fetcher(clock, respond or (lambda b, i: kb._rows(b)))
    out = _sync(env, clock, f, max_attempts=1, backfill_reinforcement=reinforcement)
    assert out["mode"] == krx_target_sync.MODE_ALREADY_LOADED
    return out, f


def _ledger(env):
    return json.loads(env["ledger"].read_text(encoding="utf-8"))


def _t1_loaded(env):
    """08:10 에 T-1 을 받고 창도 찼던 상태를 만든 뒤 09-18 만 비운다(ledger 미기록)."""
    kb._seed(env["db"], [D])
    clock = kb.Clock(8, 10, 20)
    out = _sync(env, clock, kb.Fetcher(clock, lambda b, i: kb._rows(b)))
    assert out["status"] == krx_target_sync.STATUS_OK and "backfill" in out
    assert out["backfill"]["missing_before"] == [] and not env["ledger"].exists()
    krx_store.delete_date(D, db_path=env["db"])


# ── 분류 ────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "exc",
    [
        httpx.ReadTimeout("t"),
        httpx.ConnectTimeout("t"),
        httpx.WriteTimeout("t"),
        httpx.PoolTimeout("t"),
        httpx.ConnectError("c"),
        httpx.ReadError("c"),
        # 설계자 2026-10-06 — 잘못된 응답 · 연결 끊김 모두(오류 문자열로 나누지 않는다).
        httpx.RemoteProtocolError("illegal status line"),
        httpx.RemoteProtocolError("server disconnected"),
        _http_error(500),
        _http_error(503),
        _http_error(429),
    ],
    ids=lambda e: type(e).__name__
    + (getattr(getattr(e, "response", None), "reason_phrase", "") or str(e)[:6]),
)
def test_transient_errors_are_classified_transient(exc):
    assert is_transient_fetch_error(exc) is True


@pytest.mark.parametrize(
    "exc",
    [
        _http_error(404),
        _http_error(401),
        _http_error(403),
        _http_error(302),
        RuntimeError("boom"),
        AssertionError("live KRX blocked"),
        json.JSONDecodeError("x", "doc", 0),
    ],
    ids=lambda e: type(e).__name__ + str(e)[:6],
)
def test_other_errors_are_not_transient(exc):
    assert is_transient_fetch_error(exc) is False


# ── 09:20 보강 1회 ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "failure",
    [
        httpx.ReadTimeout("t"),
        httpx.ConnectError("c"),
        httpx.RemoteProtocolError("server disconnected"),
        _http_error(503),
        _http_error(429),
    ],
    ids=["timeout", "connect", "remote_protocol", "http503", "http429"],
)
def test_0810_transient_failure_is_reinforced_once_at_0920(env, failure):
    first, _ = _morning(env, failure)
    assert first["backfill"]["called"] == [D]
    assert first["backfill"]["failed"][0]["transient"] is True
    assert _ledger(env) == {
        "date_kst": TODAY.isoformat(),
        "calls": {D: 1},
        "retryable": [D],
    }

    out, f = _reinforce(env)
    assert [c[1] for c in f.calls] == [D_BAS]
    assert out["backfill"]["called"] == out["backfill"]["retried"] == [D]
    assert out["backfill"]["filled"] == [D]
    assert out["backfill"]["calls_today"] == {D: 2}
    # 보강 기회를 썼다 — retryable 은 비어 키가 빠진다.
    assert _ledger(env) == {"date_kst": TODAY.isoformat(), "calls": {D: 2}}

    # 같은 날 다시 --krx-only — 세 번째 호출은 없다.
    krx_store.delete_date(D, db_path=env["db"])
    again, f2 = _reinforce(env, hh=10, mm=5)
    assert f2.calls == []
    assert again["backfill"]["skipped_called_today"] == [D]


@pytest.mark.parametrize(
    "failure",
    [
        RuntimeError("blip"),
        AssertionError("blocked"),
        _http_error(404),
        _http_error(401),
        json.JSONDecodeError("x", "doc", 0),
    ],
    ids=["runtime", "assertion", "http404", "http401", "json"],
)
def test_0810_permanent_fetch_failure_is_not_called_again(env, failure):
    first, _ = _morning(env, failure)
    assert first["backfill"]["failed"][0]["transient"] is False
    assert "retryable" not in _ledger(env)

    out, f = _reinforce(env)
    assert f.calls == []
    assert out["backfill"]["skipped_called_today"] == [D]
    assert out["backfill"]["retried"] == []


def test_0810_invalid_response_is_not_called_again(env):
    """조회는 됐지만 검증 실패(다른 기준일 응답) — 영구 실패라 같은 날 다시 부르지 않는다."""
    first, _ = _morning(env, kb._rows("20260917"))
    assert first["backfill"]["failed"][0]["result"] == "basis_date_mismatch"
    assert first["backfill"]["failed"][0]["transient"] is False
    out, f = _reinforce(env)
    assert f.calls == [] and out["backfill"]["skipped_called_today"] == [D]


def test_same_0810_run_backfill_retry_does_not_reinforce(env):
    """08:10 같은 실행의 재채우기(`backfill_retry`)는 보강하지 않는다."""
    clock = kb.Clock(8, 10, 20)

    def _respond(b, i):
        if i == 1:
            return []  # 08:10 목표일 공개 전(원천에는 닿았다)
        return httpx.ReadTimeout("t") if b == D_BAS else kb._rows(b)

    f = kb.Fetcher(clock, _respond)
    out = _sync(env, clock, f)
    assert out["backfill"]["called"] == [D]
    assert out["backfill_retry"]["skipped_called_today"] == [D]
    assert out["backfill_retry"]["retried"] == []
    assert [c[1] for c in f.calls].count(D_BAS) == 1
    assert _ledger(env)["retryable"] == [D]  # 09:20 보강 기회는 남는다


def test_manual_rerun_without_reinforcement_does_not_retry(env):
    _morning(env, httpx.ReadTimeout("t"))
    out, f = _reinforce(env, reinforcement=False, hh=10, mm=5)
    assert f.calls == []
    assert out["backfill"]["skipped_called_today"] == [D]
    assert _ledger(env)["retryable"] == [D]


def test_reinforcement_run_does_not_create_new_retryable(env):
    """09:20 에 처음 부른 날짜가 일시 오류여도 보강 대상이 되지 않는다."""
    _t1_loaded(env)
    out, f = _reinforce(env, respond=lambda b, i: httpx.ReadTimeout("t"))
    assert [c[1] for c in f.calls] == [D_BAS]
    assert out["backfill"]["failed"][0]["transient"] is True
    assert _ledger(env) == {"date_kst": TODAY.isoformat(), "calls": {D: 1}}
    again, f2 = _reinforce(env, hh=10, mm=5)
    assert f2.calls == [] and again["backfill"]["skipped_called_today"] == [D]


def test_reinforcement_failing_again_stops_remaining_dates(env):
    """보강 호출이 다시 원천 오류면 남은 보강 날짜는 부르지 않는다(원천 장애 가정)."""
    _t1_loaded(env)
    krx_store.delete_date("2026-09-21", db_path=env["db"])
    env["ledger"].write_text(
        json.dumps(
            {
                "date_kst": TODAY.isoformat(),
                "calls": {D: 1, "2026-09-21": 1},
                "retryable": [D, "2026-09-21"],
            }
        ),
        "utf-8",
    )
    out, f = _reinforce(env, respond=lambda b, i: httpx.ConnectError("c"))
    assert [c[1] for c in f.calls] == [D_BAS]
    assert out["backfill"]["stopped"] == krx_backfill.STOP_FETCH_ERROR
    assert _ledger(env) == {
        "date_kst": TODAY.isoformat(),
        "calls": {D: 2, "2026-09-21": 1},
        "retryable": ["2026-09-21"],
    }


def test_ledger_write_failure_before_reinforcement_keeps_first_record(env, monkeypatch):
    """보강 직전 기록 실패 — 부르지 않고, 첫 호출 기록 · 보강 기회를 그대로 둔다."""
    _morning(env, httpx.ReadTimeout("t"))
    before = _ledger(env)
    real = krx_backfill._write_calls

    def _fail(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(krx_backfill, "_write_calls", _fail)
    out, f = _reinforce(env)
    assert f.calls == [] and out["backfill"]["stopped"] == "ledger_error:OSError"
    assert _ledger(env) == before  # calls 1 · retryable 유지(하루 3회가 열리지 않는다)

    monkeypatch.setattr(krx_backfill, "_write_calls", real)
    out2, f2 = _reinforce(env, hh=9, mm=40)
    assert [c[1] for c in f2.calls] == [D_BAS]
    assert out2["backfill"]["calls_today"] == {D: 2}


def test_old_format_ledger_without_retryable_gives_no_reinforcement(env):
    _t1_loaded(env)
    env["ledger"].write_text(
        json.dumps({"date_kst": TODAY.isoformat(), "calls": {D: 1}}), "utf-8"
    )
    out, f = _reinforce(env)
    assert f.calls == [] and out["backfill"]["skipped_called_today"] == [D]


@pytest.mark.parametrize(
    "hh, mm, ss, expected",
    [
        (9, 19, 59, False),
        (9, 20, 0, True),
        (9, 29, 59, True),
        (9, 30, 0, False),
        (8, 40, 0, False),
        (10, 5, 0, False),
    ],
)
def test_reinforcement_window_is_the_0920_slot(hh, mm, ss, expected):
    t = datetime(2026, 9, 30, hh, mm, ss, tzinfo=kb.KST)
    assert krx_backfill.in_reinforcement_window(t) is expected
    # UTC 로 줘도 KST 로 바꿔 본다(00:20 UTC = 09:20 KST).
    assert krx_backfill.in_reinforcement_window(t.astimezone(timezone.utc)) is expected


def test_call_allowed_rule():
    calls, retry = {"a": 1, "b": 1, "c": 2}, {"a", "c"}
    assert krx_backfill.call_allowed("new", calls, retry, reinforcement=False)
    assert not krx_backfill.call_allowed("a", calls, retry, reinforcement=False)
    assert krx_backfill.call_allowed("a", calls, retry, reinforcement=True)
    assert not krx_backfill.call_allowed("b", calls, retry, reinforcement=True)
    assert not krx_backfill.call_allowed("c", calls, retry, reinforcement=True)


# ── 배치 연결: 09:20 만 보강 ──────────────────────────────────────────────────


@pytest.fixture
def batch(monkeypatch, tmp_path):
    import scripts.run_oci_market_data_batch as batch

    monkeypatch.setattr(mdb, "MARKET_DATA_BATCH_STATE_PATH", tmp_path / "bs.json")
    monkeypatch.setattr(
        mdb, "KRX_REINFORCEMENT_STATE_PATH", tmp_path / "reinforce.json"
    )
    monkeypatch.setattr(batch, "_kst_today", lambda: TODAY)
    return batch


def test_run_krx_only_reinforces_transient_date(batch, monkeypatch, tmp_path):
    cal = kb._calendar(tmp_path)
    db = tmp_path / "m.sqlite"
    kb._seed(db, kb._window_before_t1(cal))
    kb._seed(db, [kb.T1])  # T-1 은 08:10 에 받았다
    krx_store.delete_date(D, db_path=db)
    ledger = krx_backfill.ledger_path_for(db)
    ledger.write_text(
        json.dumps({"date_kst": TODAY.isoformat(), "calls": {D: 1}, "retryable": [D]}),
        "utf-8",
    )
    # 정합성 판정 기록이 없어 09:20 단일 시도 경로를 탄다(목표일 1회 → 첫 채우기에 보강
    # 표시가 넘어간다). already_loaded 경로는 위 `_reinforce` 사례들이 덮는다.
    calls: list[str] = []

    def _fetch(bas_dd, key):
        calls.append(bas_dd)
        return kb._rows(bas_dd)

    t = datetime(2026, 9, 30, 9, 20, tzinfo=kb.KST)
    real = krx_target_sync.sync_krx_target
    seen: dict = {}

    def _spy(**kw):
        seen.update(kw)
        return functools.partial(
            real,
            db_path=db,
            env_path=kb._env(tmp_path),
            calendar_dir=cal,
            fetcher=_fetch,
            clock=lambda: t,
            sleep=lambda s: pytest.fail("09:20 보강은 기다리지 않는다"),
        )(**kw)

    monkeypatch.setattr(krx_target_sync, "sync_krx_target", _spy)
    monkeypatch.setattr(batch, "_now", lambda: t)  # 09:20 정기 회차
    rec = batch.run_krx_only()
    assert seen["backfill_reinforcement"] is True
    assert rec["backfill_reinforcement"] is True
    assert D_BAS in calls
    assert json.loads(ledger.read_text("utf-8"))["calls"][D] == 2


def test_0810_run_does_not_reinforce(batch, monkeypatch):
    seen: dict = {}

    def _krx(**kw):
        seen.update(kw)
        raise RuntimeError("stop here")  # 인자만 본다 · 배치가 감싼다

    monkeypatch.setattr(krx_target_sync, "sync_krx_target", _krx)
    rec: dict = {}
    batch._krx_stage(rec, TODAY, logging.getLogger("t"))
    assert seen.get("backfill_reinforcement") is False


# ── 독립 검토 보강 사례 ───────────────────────────────────────────────────────


def test_0920_mixed_retryable_and_never_called_dates(env):
    """가장 흔한 실제 모양 — 08:10 이 A 에서 일시 오류로 멈춰 B 는 못 불렀다.

    09:20 은 A 를 보강하고 B 를 처음으로 부른다. 09:20 에 B 가 일시 오류여도 B 는
    보강 대상이 되지 않는다(보강 실행은 새 보강 대상을 만들지 않는다).
    """
    krx_store.delete_date("2026-09-21", db_path=env["db"])
    first, _ = _morning(env, httpx.ReadTimeout("t"))
    assert first["backfill"]["called"] == [D]  # 09-21 은 못 불렀다(원천 오류로 멈춤)
    out, f = _reinforce(
        env,
        respond=lambda b, i: (
            httpx.ConnectError("c") if b == "20260921" else kb._rows(b)
        ),
    )
    assert [c[1] for c in f.calls] == [D_BAS, "20260921"]
    assert out["backfill"]["retried"] == [D]
    assert out["backfill"]["calls_today"] == {D: 2, "2026-09-21": 1}
    assert "retryable" not in _ledger(env)


def test_retryable_created_by_0810_backfill_retry_is_reinforced(env):
    """08:10 같은 실행의 재채우기(3번 호출 자리)에서 처음 부른 날짜도 일시 오류면 09:20 대상."""
    krx_store.delete_date("2026-09-21", db_path=env["db"])
    clock = kb.Clock(8, 10, 20)

    def _respond(b, i):
        if i == 1:
            return []  # 목표일 공개 전
        if b == D_BAS:
            return RuntimeError("down")  # 첫 채우기 — 영구 실패로 멈춤
        if b == "20260921":
            return _http_error(502)  # 재채우기에서 처음 부름 — 일시 오류
        return kb._rows(b)

    out = _sync(env, clock, kb.Fetcher(clock, _respond))
    assert out["backfill_retry"]["called"] == ["2026-09-21"]
    assert _ledger(env)["retryable"] == ["2026-09-21"]
    again, f = _reinforce(env)
    assert [c[1] for c in f.calls] == ["20260921"]  # 09-18(영구)은 부르지 않는다
    assert again["backfill"]["retried"] == ["2026-09-21"]


def test_post_fetch_retryable_write_failure_gives_no_reinforcement(env, monkeypatch):
    """호출 뒤 보강 대상 기록이 실패하면 보강 없음 쪽으로 둔다 — 예외를 올리지 않는다."""
    real = krx_backfill._write_calls
    n = {"i": 0}

    def _second_fails(*a, **k):
        n["i"] += 1
        if n["i"] == 2:
            raise OSError("disk full")
        return real(*a, **k)

    monkeypatch.setattr(krx_backfill, "_write_calls", _second_fails)
    first, _ = _morning(env, httpx.ReadTimeout("t"))
    assert first["backfill"]["retryable_write_error"] == "OSError"
    monkeypatch.setattr(krx_backfill, "_write_calls", real)
    assert _ledger(env) == {"date_kst": TODAY.isoformat(), "calls": {D: 1}}
    out, f = _reinforce(env)
    assert f.calls == [] and out["backfill"]["skipped_called_today"] == [D]


def test_0920_single_attempt_fetch_error_loses_the_reinforcement(env):
    """09:20 에 T-1 도 없고 목표일 조회가 원천 오류면 채우기를 부르지 않는다(원천 불통 중
    채우기 금지 · 설계자 RESULT STEP 6). 그날 보강 기회는 잃는다 — 결과서 §5 에 적은 한계."""
    env["ledger"].write_text(
        json.dumps({"date_kst": TODAY.isoformat(), "calls": {D: 1}, "retryable": [D]}),
        "utf-8",
    )
    clock = kb.Clock(9, 20, 0)
    f = kb.Fetcher(clock, lambda b, i: httpx.ConnectError("c"))
    out = _sync(env, clock, f, max_attempts=1, backfill_reinforcement=True)
    assert [c[1] for c in f.calls] == ["20260929"]
    assert "backfill" not in out
    assert _ledger(env)["retryable"] == [D]  # 기록은 남지만 그날 다시 도는 실행이 없다


def test_manual_krx_only_outside_0920_window_does_not_reinforce(
    batch, monkeypatch, tmp_path
):
    """PLAN §2-5 — 수동 재실행은 보강하지 않는다(검증자 r1).

    cron 09:20 줄과 수동 `--krx-only` 는 같은 명령이라 시작 시각으로 가른다. T-1 을 08:10 에
    받은 날 08:40 수동 실행은 보강하지 않고 보강 기회도 쓰지 않는다 → 09:20 정기 회차가
    보강한다 → 10:05 수동 실행은 다시 부르지 않는다. T-1 을 못 받은 날은 아래
    `test_manual_krx_only_attempting_t1_blocks_the_0920_run`(알려진 한계).
    """
    import app.three_push_runner_common as common
    from app.market_briefing import meta_gate

    cal = kb._calendar(tmp_path)
    db = tmp_path / "m.sqlite"
    state_dir = tmp_path / "state"
    monkeypatch.setattr(common, "STATE_DIR", state_dir)  # 배치가 읽는 정합성 경로
    kb._seed(db, kb._window_before_t1(cal))
    clock = kb.Clock(8, 10, 20)
    loaded = krx_target_sync.sync_krx_target(
        today=TODAY,
        consistency_path=state_dir / meta_gate.CONSISTENCY_STATE_NAME,
        official_csv_path=kb._csv(tmp_path),
        db_path=db,
        env_path=kb._env(tmp_path),
        calendar_dir=cal,
        fetcher=kb.Fetcher(clock, lambda b, i: kb._rows(b)),
        clock=clock,
        sleep=clock.sleep,
        required_tickers=kb.REPS,
    )
    assert loaded["status"] == krx_target_sync.STATUS_OK
    krx_store.delete_date(D, db_path=db)
    ledger = krx_backfill.ledger_path_for(db)
    krx_backfill.write_ledger(ledger, TODAY.isoformat(), {D: 1}, {D})
    calls: list[str] = []
    now = {"t": datetime(2026, 9, 30, 8, 40, tzinfo=kb.KST)}

    def _fetch(bas_dd, key):
        calls.append(bas_dd)
        return kb._rows(bas_dd)

    real = krx_target_sync.sync_krx_target
    monkeypatch.setattr(
        krx_target_sync,
        "sync_krx_target",
        lambda **kw: real(
            **{
                **kw,
                "db_path": db,
                "env_path": kb._env(tmp_path),
                "calendar_dir": cal,
                "official_csv_path": kb._csv(tmp_path),
                "meta_dir": None,
                "fetcher": _fetch,
                "clock": lambda: now["t"],
                "sleep": lambda s: pytest.fail("기다리지 않는다"),
            }
        ),
    )
    monkeypatch.setattr(batch, "_now", lambda: now["t"])

    rec1 = batch.run_krx_only()  # 08:40 수동
    assert rec1["backfill_reinforcement"] is False
    assert calls == []
    assert rec1["krx_backfill"]["backfill"]["skipped_called_today"] == [D]
    assert json.loads(ledger.read_text("utf-8")) == {
        "date_kst": TODAY.isoformat(),
        "calls": {D: 1},
        "retryable": [D],
    }  # 보강 기회를 쓰지 않았다

    now["t"] = datetime(2026, 9, 30, 9, 20, 1, tzinfo=kb.KST)
    rec2 = batch.run_krx_only()  # 09:20 정기 회차
    assert rec2["backfill_reinforcement"] is True
    assert calls == [D_BAS]
    assert rec2["krx_backfill"]["backfill"]["retried"] == [D]

    now["t"] = datetime(2026, 9, 30, 10, 5, tzinfo=kb.KST)
    krx_store.delete_date(D, db_path=db)
    rec3 = batch.run_krx_only()  # 10:05 수동
    assert rec3["backfill_reinforcement"] is False
    assert calls == [D_BAS]  # 다시 부르지 않는다


def test_manual_krx_only_attempting_t1_blocks_the_0920_run(
    batch, monkeypatch, tmp_path
):
    """알려진 한계(결과서 §5 · 설계자 질문) — 지금 동작을 고정한다.

    08:10 에 ETF T-1 을 못 받은 날 창 밖 수동 `--krx-only`(08:40)가 목표일을 조회하면 OPS-03
    하루 1회 가드(확정 계약 7 · `attempted`)가 09:20 정기 회차를 통째로 건너뛴다 → 그날 보강이
    돌지 않는다(보강 기회는 ledger 에 남지만 쓰는 실행이 없다).
    """
    import app.three_push_runner_common as common

    cal = kb._calendar(tmp_path)
    db = tmp_path / "m.sqlite"
    monkeypatch.setattr(common, "STATE_DIR", tmp_path / "state")
    kb._seed(db, kb._window_before_t1(cal))  # T-1 없음(08:10 미확보)
    krx_store.delete_date(D, db_path=db)
    ledger = krx_backfill.ledger_path_for(db)
    krx_backfill.write_ledger(ledger, TODAY.isoformat(), {D: 1}, {D})
    calls: list[str] = []
    now = {"t": datetime(2026, 9, 30, 8, 40, tzinfo=kb.KST)}

    def _fetch(bas_dd, key):
        calls.append(bas_dd)
        return kb._rows(bas_dd)

    real = krx_target_sync.sync_krx_target
    monkeypatch.setattr(
        krx_target_sync,
        "sync_krx_target",
        lambda **kw: real(
            **{
                **kw,
                "db_path": db,
                "env_path": kb._env(tmp_path),
                "calendar_dir": cal,
                "official_csv_path": kb._csv(tmp_path),
                "meta_dir": None,
                "fetcher": _fetch,
                "clock": lambda: now["t"],
                "sleep": lambda s: pytest.fail("기다리지 않는다"),
            }
        ),
    )
    monkeypatch.setattr(batch, "_now", lambda: now["t"])

    rec1 = batch.run_krx_only()  # 08:40 수동 — 목표일을 조회했다
    assert rec1["attempted"] is True and rec1["backfill_reinforcement"] is False
    assert calls == ["20260929"]  # D 는 보강하지 않는다(창 밖)

    now["t"] = datetime(2026, 9, 30, 9, 20, 1, tzinfo=kb.KST)
    rec2 = batch.run_krx_only()  # 09:20 정기 회차
    assert rec2["status"] == "skipped_already_ran_today"
    assert calls == ["20260929"]
    assert json.loads(ledger.read_text("utf-8"))["retryable"] == [D]
