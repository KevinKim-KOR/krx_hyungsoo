"""POC3-02D-OPS-03 설계자 RESULT STEP 3 — 08:10 배치의 KOSPI 재시도.

08:10 결과가 T-1 이 아니면 08:15 · 08:20 · 08:24(마감 08:27)에 **ETF 적재와 독립으로**
다시 조회한다. T-1 저장 즉시 끝 · KOSPI 실패가 ETF 시도 · 판정 · 정합성 JSON 을 늦추지
않음 · ETF 성공이 KOSPI 재시도를 멈추지 않음 · 09:20 `--krx-only` 는 KOSPI 없음 ·
08:00 전 시작은 재시도 없음 · 08:27 뒤 시작은 1회 · 모두 실패면 기준일 지연(Telegram
없음) · 시도 기록에 키 · 가격 값 없음 · 재시도는 이미 확인한 날짜를 다시 부르지 않음.

배치 `run()` 을 실제 KRX 단계(`sync_krx_target`) · 실제 KOSPI 적재(tmp DB)로 관통한다.
**외부 조회 0건(KRX 경계 대역) · 라이브 DB · state · logs 미접근 · 실제 sleep 0.**
"""

from __future__ import annotations

import functools
import json
from datetime import datetime, time, timedelta
from types import SimpleNamespace

import pytest

import app.market_benchmark_batch as bench_mod
from app import market_benchmark_kospi_retry as kr
from app import market_benchmark_store as store
from app.market_benchmark_freshness import kospi_freshness
from app.market_briefing import calendar as _cal
from app.market_briefing import krx_store, krx_sync, krx_target_sync, meta_gate
from app.three_push_runtime import market_data_batch as mdb
from app.three_push_runtime.market_data_batch import RefreshResult
from app.three_push_runtime.runner_market_briefing import batch_failure_reasons
from tests import test_poc3_02d_ops03_krx_batch as kb

KEY = "DEADBEEF"
TODAY = kb.TODAY  # 2026-09-30(수)
T1, T2 = kb.T1, kb.T2  # 09-29 · 09-28
# KRX 공식 종가(PLAN STEP 1-6 실측 09-23 · 09-28) · 09-29 는 합성값.
OFFICIAL = {"2026-09-23": 6901.55, "2026-09-28": 6889.74, "2026-09-29": 6912.30}
PRICE_TEXTS = ("6901", "6889", "6912", "6880", "CLSPRC")


def _hm(hh, mm, ss=0):
    return datetime.combine(TODAY, time(hh, mm, ss), tzinfo=kb.KST)


class Source:
    """KRX 경계 대역 — 호출(이름 · 시각 · 날짜)을 `events` 에 남기고 시계를 2초 민다."""

    def __init__(self, name, clock, events, respond):
        self.name, self.clock, self.events, self.respond = name, clock, events, respond

    def __call__(self, bas_dd, key):
        assert key == KEY
        at = self.clock()
        self.events.append((self.name, at.strftime("%H:%M:%S"), bas_dd))
        self.clock.t += timedelta(seconds=2)
        return self.respond(bas_dd, at)


def _kospi_rows(bas_dd):
    iso = f"{bas_dd[:4]}-{bas_dd[4:6]}-{bas_dd[6:]}"
    return [
        {"BAS_DD": bas_dd, "IDX_NM": "코스피 200", "CLSPRC_IDX": "900.12"},
        {"BAS_DD": bas_dd, "IDX_NM": "코스피", "CLSPRC_IDX": f"{OFFICIAL[iso]:,.2f}"},
    ]


@pytest.fixture
def rig(monkeypatch, tmp_path):
    """가격 앞 단계만 대역 · benchmark(KOSPI) · KRX 단계는 실제 코드(tmp DB · 가짜 시계)."""
    import scripts.run_oci_market_data_batch as batch
    from app import three_push_runner_common as common

    cal = kb._calendar(tmp_path)
    db = tmp_path / "market_data.sqlite"
    kb._seed(db, kb._window_before_t1(cal))  # ETF 창 20일(T-1 제외) — 채우기 호출 0
    # KOSPI 저장 최신일 = T-2 · 공식 자료원 · 같은 값(첫 시도 재확인에서 정정 없음).
    store.upsert_benchmark_prices(
        benchmark_id="KOSPI",
        benchmark_name="KOSPI",
        rows=[("2026-09-23", OFFICIAL["2026-09-23"]), (T2, OFFICIAL[T2])],
        source=store.KOSPI_SOURCE,
        db_path=db,
    )
    monkeypatch.setattr(_cal, "CALENDAR_DIR", cal)
    monkeypatch.setattr(store, "KOSPI_EVIDENCE_DIR", tmp_path / "kospi_evidence")
    monkeypatch.setattr(krx_sync, "read_api_key", lambda env_path=None: KEY)
    # 공식 CSV 는 배치가 넘기는 폴더(conftest 격리 폴더)에 둔다.
    kb._csv(batch.MARKET_META_DIR)

    clock = kb.Clock(8, 10, 20)
    monkeypatch.setattr(krx_target_sync, "_now_kst", clock)
    monkeypatch.setattr(krx_target_sync, "_sleep", clock.sleep)

    monkeypatch.setattr(mdb, "MARKET_DATA_BATCH_STATE_PATH", tmp_path / "bs.json")
    monkeypatch.setattr(mdb, "KRX_REINFORCEMENT_STATE_PATH", tmp_path / "re.json")
    monkeypatch.setattr(batch, "_kst_today", lambda: TODAY)
    monkeypatch.setattr(batch, "collect_approved_tickers", lambda: ["069500"])
    monkeypatch.setattr(
        batch,
        "refresh_approved_prices",
        lambda tickers, *, end_date, **kw: RefreshResult(
            attempted=1, success=1, fail=0, price_data_as_of=T1
        ),
    )
    monkeypatch.setattr(
        batch,
        "_build_universe_artifact",
        lambda *, price_data_as_of: ({"summary": {}}, f"{TODAY}T08:10:30", "ok"),
    )
    monkeypatch.setattr(
        "app.universe_bootstrap.artifact_validator.validate_artifact",
        lambda *a, **k: (True, None, {}),
    )
    monkeypatch.setattr(
        batch, "evaluate_freshness", lambda **kw: SimpleNamespace(ok=True, reason="")
    )
    monkeypatch.setattr(
        "app.momentum.universe_mode.save_latest_artifact",
        lambda result: tmp_path / "art.json",
    )
    # benchmark — VIX · 미국은 대역 · KOSPI 는 실제 적재(tmp DB).
    ok = {"status": "ok", "as_of_date": T1, "error": None}
    monkeypatch.setattr(bench_mod, "refresh_vix", lambda **kw: ok)
    monkeypatch.setattr(bench_mod, "refresh_us_index", lambda *a, **kw: ok)
    real_kospi = bench_mod.refresh_kospi
    kospi_kwargs: list[dict] = []

    def _kospi(**kw):
        kospi_kwargs.append(dict(kw))
        return real_kospi(**{**kw, "db_path": db})

    monkeypatch.setattr(bench_mod, "refresh_kospi", _kospi)

    events: list[tuple] = []
    cpath = common.STATE_DIR / meta_gate.CONSISTENCY_STATE_NAME
    state = SimpleNamespace(
        batch=batch,
        clock=clock,
        cal=cal,
        db=db,
        cpath=cpath,
        events=events,
        kospi_kwargs=kospi_kwargs,
        kospi_from=None,  # 이 시각부터 KOSPI T-1 공개(None = 공개 안 됨)
        etf_from=_hm(8, 0),  # 이 시각부터 ETF T-1 공개(None = 공개 안 됨)
        consistency_at_kospi=[],  # KOSPI 호출 시점의 정합성 JSON 기준일
    )

    def _kospi_respond(bas_dd, at):
        seen = meta_gate.load_consistency(cpath)
        state.consistency_at_kospi.append(
            (at.strftime("%H:%M:%S"), seen and seen.evaluated_api_basis_date)
        )
        if bas_dd < "20260929":
            return _kospi_rows(bas_dd)
        if state.kospi_from is not None and at >= state.kospi_from:
            return _kospi_rows(bas_dd)
        return []  # 공개 전 — 행 0

    def _etf_respond(bas_dd, at):
        if state.etf_from is not None and at >= state.etf_from:
            return kb._rows(bas_dd)
        return []

    monkeypatch.setattr(
        krx_sync,
        "_default_kospi_fetcher",
        Source("kospi", clock, events, _kospi_respond),
    )
    real_sync = krx_target_sync.sync_krx_target
    monkeypatch.setattr(
        krx_target_sync,
        "sync_krx_target",
        functools.partial(
            real_sync,
            db_path=db,
            calendar_dir=cal,
            fetcher=Source("etf", clock, events, _etf_respond),
            required_tickers=kb.REPS,
        ),
    )
    return state


def _calls(rig, name):
    return [(t, d) for n, t, d in rig.events if n == name]


def _saved():
    return json.loads(mdb.MARKET_DATA_BATCH_STATE_PATH.read_text("utf-8"))


# ── 시각표 ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "start, mode, slots",
    [
        ((7, 59, 0), "skipped_before_open", []),
        ((8, 5, 0), "scheduled", ["08:10", "08:15", "08:20", "08:24"]),
        ((8, 10, 20), "scheduled", ["08:15", "08:20", "08:24"]),
        ((8, 14, 30), "scheduled", ["08:20", "08:24"]),
        ((8, 26, 30), "scheduled", []),
        ((8, 27, 0), "single_attempt", []),
        ((8, 28, 0), "single_attempt", []),
    ],
)
def test_retry_slots_follow_krx_schedule(start, mode, slots):
    got_mode, got = kr.retry_slots(_hm(*start))
    assert (got_mode, [s.strftime("%H:%M") for s in got]) == (mode, slots)


# ── 검증 3 — 08:10 실패 뒤 후속 슬롯 성공 ────────────────────────────────────


def test_0810_not_t1_then_0815_success_stops_and_etf_is_unaffected(rig):
    rig.kospi_from = _hm(8, 14)
    rec = rig.batch.run(mode="run")

    assert _calls(rig, "kospi") == [
        ("08:10:20", "20260928"),  # 첫 시도 — 저장 최신일 재확인(포함)
        ("08:10:22", "20260929"),  # 공개 전 · 행 0
        ("08:15:00", "20260929"),  # 재시도 — 빠진 T-1 만 · 성공하면 끝
    ]
    # ETF 는 08:10 한 번에 성공 · KOSPI 재시도는 ETF 판정 · 정합성 JSON 뒤에 돈다.
    assert _calls(rig, "etf") == [("08:10:24", "20260929")]
    assert rig.consistency_at_kospi[-1] == ("08:15:00", "20260929")
    assert rig.kospi_kwargs[0].get("recheck_latest", True) is True
    assert rig.kospi_kwargs[1]["recheck_latest"] is False

    assert (rec["status"], rec["reason"]) == ("success", None)
    assert rec["benchmark_status"] == "ok" and rec["kospi_as_of"] == T1
    bench = rec["benchmark_refresh"]
    assert bench["failed"] == [] and bench["status"] == "ok"
    kospi = bench["kospi"]
    assert (kospi["status"], kospi["error"], kospi["as_of_date"]) == ("ok", None, T1)
    # 결과서 · 운영 문서가 가리키는 기존 필드는 그대로(이번 실행 합계).
    assert {
        "source",
        "expected_as_of_date",
        "calls",
        "attempts",
        "corrections",
        "evidence_path",
        "before",
        "after",
    } <= set(kospi)
    assert kospi["calls"] == 3 and [a["date"] for a in kospi["attempts"]] == [
        T2,
        T1,
        T1,
    ]
    assert kospi["before"]["as_of"] == T2 and kospi["after"]["as_of"] == T1
    assert rec["kospi_retry"] == {
        "mode": "scheduled",
        "slots": ["08:15", "08:20", "08:24"],
        "retries": 1,
        "stopped": kr.STOP_T1_STORED,
    }
    first, retry = rec["kospi_attempts"]
    assert (first["kind"], first["at_kst"][11:19], first["result"]) == (
        kr.KIND_FIRST,
        "08:10:20",
        "failed",
    )
    assert first["error"].startswith("source_stale:as_of=2026-09-28,expected=")
    assert [c["result"] for c in first["calls"]] == ["ok", "no_rows"]
    assert (retry["kind"], retry["slot"], retry["result"], retry["as_of"]) == (
        kr.KIND_RETRY,
        "08:15",
        "ok",
        T1,
    )
    assert retry["calls"] == [{"date": T1, "rows": 2, "result": "ok"}]
    saved = _saved()
    assert saved["status"] == "success" and saved["kospi_as_of"] == T1
    assert saved["benchmark_failed"] == [] and saved["benchmark_status"] == "ok"
    assert saved["kospi_attempts"] == rec["kospi_attempts"]
    assert saved["kospi_retry"]["stopped"] == kr.STOP_T1_STORED
    assert saved["stage_status"]["krx"] == "ok"
    assert [d for d, _ in store.fetch_benchmark_history("KOSPI", db_path=rig.db)][
        -1
    ] == T1


# ── 검증 4 — 네 번 모두 실패 ─────────────────────────────────────────────────


def test_all_four_slots_fail_stale_etf_on_time_no_telegram_notice(rig):
    rec = rig.batch.run(mode="run")

    assert _calls(rig, "kospi") == [
        ("08:10:20", "20260928"),
        ("08:10:22", "20260929"),
        ("08:15:00", "20260929"),
        ("08:20:00", "20260929"),
        ("08:24:00", "20260929"),
    ]
    # ETF 판정 · 정합성 JSON 은 08:10 에 이미 끝났다 — KOSPI 재시도가 늦추지 않는다.
    assert _calls(rig, "etf") == [("08:10:24", "20260929")]
    assert [c for c in rig.consistency_at_kospi if c[0] >= "08:15"] == [
        ("08:15:00", "20260929"),
        ("08:20:00", "20260929"),
        ("08:24:00", "20260929"),
    ]
    assert rig.clock() < _hm(8, 27)  # 08:27 뒤 새 시도 없음

    kospi = rec["benchmark_refresh"]["kospi"]
    assert kospi["status"] == "failed" and kospi["calls"] == 5
    assert kospi["error"] == (
        "source_stale:as_of=2026-09-28,expected=2026-09-29,lag=1,"
        "reason=no_rows@2026-09-29"
    )
    assert rec["kospi_retry"]["stopped"] == kr.STOP_SLOTS_EXHAUSTED
    assert rec["kospi_retry"]["retries"] == 3
    assert [a["slot"] for a in rec["kospi_attempts"]] == [
        None,
        "08:15",
        "08:20",
        "08:24",
    ]
    assert rec["status"] == "success_with_benchmark_failure"
    assert rec["reason"] == "benchmark_partial:kospi"
    assert rec["krx_sync_status"] == "ok" and rec["price_pipeline_status"] == "success"
    saved = _saved()
    assert saved["kospi_as_of"] == T2 and saved["benchmark_failed"] == ["kospi"]
    # 저장 기준일이 그대로 → 같은 최신성 함수가 기준일 지연(PC 화면 · source_stale).
    fresh = kospi_freshness(saved["kospi_as_of"], today_kst=TODAY.isoformat())
    assert (fresh.is_fresh, fresh.reason, fresh.expected_date) == (
        False,
        "before_expected",
        T1,
    )
    # Telegram 별도 경고 없음 — 08:30 배치 실패 고지 사유에 KOSPI 는 들어가지 않는다.
    assert batch_failure_reasons(saved, TODAY.isoformat()) == []


def test_etf_ok_at_0810_while_kospi_succeeds_at_0820(rig):
    rig.kospi_from = _hm(8, 19)
    rec = rig.batch.run(mode="run")

    assert [t for t, _ in _calls(rig, "kospi")] == [
        "08:10:20",
        "08:10:22",
        "08:15:00",
        "08:20:00",
    ]
    assert _calls(rig, "etf") == [("08:10:24", "20260929")]
    assert rec["kospi_retry"]["retries"] == 2
    assert rec["kospi_retry"]["stopped"] == kr.STOP_T1_STORED
    assert rec["status"] == "success" and rec["kospi_as_of"] == T1


def test_etf_fails_every_slot_while_kospi_ok_at_0810_makes_no_extra_call(rig):
    rig.kospi_from, rig.etf_from = _hm(8, 0), None
    rec = rig.batch.run(mode="run")

    assert _calls(rig, "kospi") == [("08:10:20", "20260928"), ("08:10:22", "20260929")]
    assert [t for t, _ in _calls(rig, "etf")] == [
        "08:10:24",
        "08:15:00",
        "08:20:00",
        "08:24:00",
    ]
    assert rec["krx_sync_status"] == krx_target_sync.STATUS_TARGET_NOT_OBTAINED
    assert rec["kospi_retry"] == {
        "mode": "scheduled",
        "slots": ["08:15", "08:20", "08:24"],
        "retries": 0,
        "stopped": kr.STOP_T1_STORED,
    }
    assert len(rec["kospi_attempts"]) == 1 and rec["kospi_as_of"] == T1
    assert rec["status"] == "success"


def test_kospi_retries_while_etf_still_retrying_and_etf_goes_first_at_shared_slot(
    rig,
):
    rig.kospi_from, rig.etf_from = _hm(8, 14), _hm(8, 19)
    rec = rig.batch.run(mode="run")

    assert rig.events == [
        ("kospi", "08:10:20", "20260928"),
        ("kospi", "08:10:22", "20260929"),
        ("etf", "08:10:24", "20260929"),
        ("etf", "08:15:00", "20260929"),  # 같은 시각 — ETF 먼저 · 제시각
        ("kospi", "08:15:02", "20260929"),  # ETF 가 재시도 중이어도 KOSPI 는 돈다
        ("etf", "08:20:00", "20260929"),  # KOSPI 가 ETF 시각을 밀지 않는다
    ]
    assert rec["krx_sync_status"] == "ok" and rec["kospi_as_of"] == T1
    assert rec["kospi_attempts"][1]["slot"] == "08:15"


def test_etf_fails_every_slot_kospi_still_retries_at_0824(rig):
    """ETF 가 네 시각 모두 실패해도 KOSPI 남은 시각(08:24)은 돈다 — 단계가 끝난 뒤에도."""
    rig.kospi_from, rig.etf_from = _hm(8, 23), None
    rec = rig.batch.run(mode="run")

    assert [t for t, _ in _calls(rig, "etf")] == [
        "08:10:24",
        "08:15:00",
        "08:20:00",
        "08:24:00",
    ]
    assert [t for t, _ in _calls(rig, "kospi")] == [
        "08:10:20",
        "08:10:22",
        "08:15:02",
        "08:20:02",
        "08:24:02",  # ETF 목표일 미확보로 단계가 끝난 뒤 — 남은 KOSPI 시각
    ]
    assert rec["krx_sync_status"] == krx_target_sync.STATUS_TARGET_NOT_OBTAINED
    assert rec["kospi_as_of"] == T1 and rec["status"] == "success"
    assert rec["kospi_retry"]["stopped"] == kr.STOP_T1_STORED


def test_etf_stage_exception_still_runs_remaining_kospi_slots(rig, monkeypatch):
    """ETF 판정이 예외로 끝나도(배치가 감싼다) KOSPI 남은 시각은 돈다."""

    def _boom(*a, **k):
        raise RuntimeError("judge bug")

    monkeypatch.setattr(krx_sync, "judge_and_save_consistency", _boom)
    rig.kospi_from = _hm(8, 14)
    rec = rig.batch.run(mode="run")

    assert _calls(rig, "etf") == [("08:10:24", "20260929")]
    assert _calls(rig, "kospi")[-1] == ("08:15:00", "20260929")
    assert rec["krx_sync_status"] == "unexpected:RuntimeError"
    assert rec["kospi_as_of"] == T1 and rec["benchmark_status"] == "ok"


def test_kospi_slot_due_at_krx_start_waits_for_the_first_etf_attempt(rig, monkeypatch):
    """앞 단계가 늦어 KRX 단계 시작(08:15:30)에 KOSPI 08:15 가 이미 지났다 — ETF 먼저."""

    def _slow_artifact(*, price_data_as_of):
        rig.clock.t = _hm(8, 15, 30)
        return {"summary": {}}, f"{TODAY}T08:15:30", "ok"

    monkeypatch.setattr(rig.batch, "_build_universe_artifact", _slow_artifact)
    rig.kospi_from = _hm(8, 14)
    rec = rig.batch.run(mode="run")

    assert rig.events == [
        ("kospi", "08:10:20", "20260928"),
        ("kospi", "08:10:22", "20260929"),
        ("etf", "08:15:30", "20260929"),
        ("kospi", "08:15:32", "20260929"),
    ]
    assert rec["kospi_attempts"][1]["slot"] == "08:15"
    assert rec["kospi_as_of"] == T1 and rec["krx_sync_status"] == "ok"


def test_already_loaded_etf_still_runs_kospi_slots(rig):
    """ETF T-1 을 이미 받은 재실행 — ETF 는 조회 0 이어도 KOSPI 남은 시각은 돈다."""
    krx_store.upsert_snapshot(
        [krx_store.SnapshotRow(date=T1, ticker=t, close=1.0) for t in kb.TICKERS],
        db_path=rig.db,
    )
    meta_gate.save_consistency(
        meta_gate.ConsistencyResult(
            status="ok",
            evaluated_api_basis_date="20260929",
            evaluated_at_kst="2026-09-30T08:10:05+09:00",
        ),
        rig.cpath,
    )
    rig.kospi_from = _hm(8, 14)
    rec = rig.batch.run(mode="run")

    assert rec["krx_stage_mode"] == krx_target_sync.MODE_ALREADY_LOADED
    assert _calls(rig, "etf") == []
    assert [t for t, _ in _calls(rig, "kospi")] == ["08:10:20", "08:10:22", "08:15:00"]
    assert rec["kospi_as_of"] == T1 and rec["status"] == "success"


# ── 재시도 창 밖 · 09:20 보강 ─────────────────────────────────────────────────


def test_started_before_0800_makes_no_retry(rig):
    rig.clock.t = _hm(7, 59)
    rec = rig.batch.run(mode="run")

    assert [t for t, _ in _calls(rig, "kospi")] == ["07:59:00", "07:59:02"]
    assert _calls(rig, "etf") == []  # KRX 단계도 건너뜀
    assert rig.clock.sleeps == []
    assert rec["kospi_retry"] == {
        "mode": "skipped_before_open",
        "slots": [],
        "retries": 0,
        "stopped": kr.STOP_NO_RETRY_WINDOW,
    }
    assert rec["kospi_as_of"] == T2


def test_started_after_0827_is_the_single_benchmark_attempt(rig):
    rig.clock.t = _hm(8, 28)
    rec = rig.batch.run(mode="run")

    assert [t for t, _ in _calls(rig, "kospi")] == ["08:28:00", "08:28:02"]
    assert _calls(rig, "etf") == [("08:28:04", "20260929")]  # KRX 1회
    assert rig.clock.sleeps == []
    assert rec["kospi_retry"]["mode"] == "single_attempt"
    assert rec["kospi_retry"]["stopped"] == kr.STOP_NO_RETRY_WINDOW
    assert len(rec["kospi_attempts"]) == 1


def test_krx_only_0920_never_calls_kospi(rig, monkeypatch):
    rig.clock.t = _hm(9, 20)
    forbidden: list[str] = []
    monkeypatch.setattr(
        bench_mod, "refresh_kospi", lambda **kw: forbidden.append("kospi") or {}
    )
    monkeypatch.setattr(
        bench_mod, "refresh_benchmarks", lambda **kw: forbidden.append("bench") or {}
    )
    rec = rig.batch.run_krx_only()

    assert rec["status"] == "ok" and _calls(rig, "etf") == [("09:20:00", "20260929")]
    assert forbidden == [] and _calls(rig, "kospi") == []
    assert "kospi_attempts" not in rec and "kospi_retry" not in rec


# ── 기록 — 키 · 가격 값 없음 · 기존 필드 뜻 유지 ─────────────────────────────


def test_attempt_records_have_no_key_or_price_values(rig):
    rig.kospi_from = _hm(8, 19)
    rec = rig.batch.run(mode="run")
    saved = _saved()

    for blob in (rec["kospi_attempts"], saved["kospi_attempts"], saved["kospi_retry"]):
        text = json.dumps(blob, ensure_ascii=False)
        assert KEY not in text
        assert not [p for p in PRICE_TEXTS if p in text], text
    assert KEY not in json.dumps(saved, ensure_ascii=False)
    for a in saved["kospi_attempts"]:
        assert set(a) == {
            "kind",
            "slot",
            "at_kst",
            "calls",
            "result",
            "as_of",
            "error",
            "error_type",
        }


def test_first_attempt_correction_evidence_survives_the_retry_merge(rig):
    """첫 시도의 정정 · 증거 경로가 재시도 뒤에도 `benchmark_refresh.kospi` 에 남는다."""
    store.upsert_benchmark_prices(
        benchmark_id="KOSPI",
        benchmark_name="KOSPI",
        rows=[(T2, 6880.00)],
        source="FinanceDataReader/KS11",
        db_path=rig.db,
    )
    rig.kospi_from = _hm(8, 14)
    rec = rig.batch.run(mode="run")

    kospi = rec["benchmark_refresh"]["kospi"]
    assert kospi["status"] == "ok" and kospi["calls"] == 3
    assert [c["date"] for c in kospi["corrections"]] == [T2]
    assert kospi["replaced"] == 1 and kospi["evidence_path"]
    assert rec["kospi_attempts"][0]["calls"][0]["date"] == T2
    evidence = json.loads(open(kospi["evidence_path"], encoding="utf-8").read())
    assert evidence["stage"] == "after_write"


def test_first_attempt_stopped_on_stored_latest_is_rechecked_by_the_retry(
    rig, monkeypatch
):
    """08:10 첫 호출(저장 최신일 재확인)이 예외로 멈췄다 — 08:15 재시도가 그 날짜부터
    다시 불러 증거와 함께 정정한다(확정 계약 9 ③ · 다음 날로 넘기면 영영 빠진다)."""
    store.upsert_benchmark_prices(
        benchmark_id="KOSPI",
        benchmark_name="KOSPI",
        rows=[(T2, 6880.00)],
        source="FinanceDataReader/KS11",
        db_path=rig.db,
    )
    source = krx_sync._default_kospi_fetcher
    blips: list[tuple] = []

    def _flaky(bas_dd, key):
        if not blips:
            blips.append((rig.clock().strftime("%H:%M:%S"), bas_dd))
            raise ConnectionResetError("blip")
        return source(bas_dd, key)

    monkeypatch.setattr(krx_sync, "_default_kospi_fetcher", _flaky)
    rig.kospi_from = _hm(8, 14)
    rec = rig.batch.run(mode="run")

    assert blips == [("08:10:20", "20260928")]
    assert _calls(rig, "kospi") == [("08:15:00", "20260928"), ("08:15:02", "20260929")]
    assert rig.kospi_kwargs[1]["recheck_latest"] is True
    assert rec["kospi_attempts"][0]["calls"] == [
        {"date": T2, "result": "fetch_error", "error_type": "ConnectionResetError"}
    ]
    kospi = rec["benchmark_refresh"]["kospi"]
    assert kospi["status"] == "ok" and kospi["as_of_date"] == T1
    assert [c["date"] for c in kospi["corrections"]] == [T2] and kospi["evidence_path"]
    after = store._kospi_rows(rig.db)
    assert after[T2]["source"] == store.KOSPI_SOURCE
    assert after[T2]["close"] == OFFICIAL[T2]


def test_benchmark_stage_exception_stays_failed_after_kospi_retry_success(
    rig, monkeypatch
):
    """벤치마크 단계 전체 예외(VIX · 미국 결과 없음) — KOSPI 재시도가 성공해도 '일부 실패'가
    아니라 단계 실패로 남는다."""

    def _boom(**kw):
        raise TimeoutError("stage")

    monkeypatch.setattr(bench_mod, "refresh_benchmarks", _boom)
    rig.kospi_from = _hm(8, 0)
    rec = rig.batch.run(mode="run")

    bench = rec["benchmark_refresh"]
    assert bench["kospi"]["status"] == "ok" and rec["kospi_as_of"] == T1
    assert bench["failed"] == ["unexpected:TimeoutError"]
    assert bench["status"] == rec["benchmark_status"] == "failed"
    assert rec["stage_status"]["benchmark"] == "failed"
    assert rec["status"] == "success_with_benchmark_failure"
    assert rec["reason"] == "benchmark_failed:unexpected:TimeoutError"
    # 적재 전 기록이 없으니 저장 최신일을 다시 포함해 부른다.
    assert rig.kospi_kwargs[0]["recheck_latest"] is True
    assert _calls(rig, "kospi") == [("08:15:00", "20260928"), ("08:15:02", "20260929")]


def test_write_batch_state_old_callers_leave_kospi_fields_none(tmp_path):
    p = tmp_path / "bs.json"
    mdb.write_batch_state(
        status="success",
        price_data_as_of=T1,
        artifact_generated_at=None,
        refresh_date_kst=TODAY.isoformat(),
        refresh_completed_at="x",
        state_path=p,
    )
    saved = json.loads(p.read_text("utf-8"))
    assert saved["kospi_attempts"] is None and saved["kospi_retry"] is None


# ── 저장 층 — 재시도는 확인한 날짜를 다시 부르지 않는다 ────────────────────────


def test_retry_fetch_skips_stored_latest_and_calls_only_missing_dates(tmp_path):
    cal = kb._calendar(tmp_path)
    db = tmp_path / "m.sqlite"
    store.upsert_benchmark_prices(
        benchmark_id="KOSPI",
        benchmark_name="KOSPI",
        rows=[("2026-09-23", OFFICIAL["2026-09-23"])],
        source=store.KOSPI_SOURCE,
        db_path=db,
    )
    calls: list[str] = []

    def _fetch(bas_dd, key):
        calls.append(bas_dd)
        return _kospi_rows(bas_dd)

    common = dict(
        end_date=TODAY,
        fetcher=_fetch,
        api_key=KEY,
        db_path=db,
        calendar_dir=cal,
        evidence_dir=tmp_path / "ev",
    )
    res = store.refresh_kospi_benchmark(recheck_latest=False, **common)
    # 09-23 다음 거래일은 09-28(추석 연휴) — 저장 최신일 09-23 은 부르지 않는다.
    assert calls == ["20260928", "20260929"] and res["status"] == "ok"
    calls.clear()
    res = store.refresh_kospi_benchmark(recheck_latest=False, **common)
    assert calls == [] and res["status"] == "ok" and res["calls"] == 0
    store.refresh_kospi_benchmark(**common)  # 기본(첫 시도)은 저장 최신일 포함
    assert calls == ["20260929"]


# ── 객체 단위 — 마감 · 재시도 안 함 · 예외 격리 ────────────────────────────────


def _failed(error="source_stale:x", as_of=T2):
    return {
        "status": "failed",
        "as_of_date": as_of,
        "expected_as_of_date": T1,
        "error": error,
    }


def test_deadline_passed_makes_no_new_attempt():
    tried: list = []
    r = kr.KospiRetry(
        _failed(),
        first_at=_hm(8, 10, 20),
        end_date=TODAY,
        attempt=lambda d, recheck: tried.append(d) or _failed(),
    )
    r.run_due(_hm(8, 27, 30))  # 밀린 시각 3개 — 마감 뒤라 부르지 않는다
    assert tried == [] and r.next_slot() is None
    assert r.summary()["stopped"] == kr.STOP_DEADLINE


def test_overdue_slots_collapse_into_one_attempt():
    tried: list = []
    r = kr.KospiRetry(
        _failed(),
        first_at=_hm(8, 10, 20),
        end_date=TODAY,
        attempt=lambda d, recheck: tried.append(d) or _failed(),
    )
    r.run_due(_hm(8, 21))  # 08:15 · 08:20 이 밀렸다 — 한 번만
    assert len(tried) == 1 and r.attempts[-1]["slot"] == "08:20"
    assert r.next_slot() == _hm(8, 24)


@pytest.mark.parametrize(
    "first, stopped",
    [
        (_failed("api_key_missing", None), kr.STOP_NOT_RETRIABLE),
        (_failed("expected_date_unknown", None), kr.STOP_NOT_RETRIABLE),
        # 무결성 오류라도 기준일이 T-1 이면 다시 부르지 않는다(실패는 그대로 남는다).
        (_failed("readback_mismatch:2026-09-29", T1), kr.STOP_T1_STORED),
    ],
)
def test_not_retried_when_retry_cannot_change_the_result(first, stopped):
    r = kr.KospiRetry(
        first,
        first_at=_hm(8, 10, 20),
        end_date=TODAY,
        attempt=lambda d, recheck: pytest.fail("재시도하면 안 된다"),
    )
    assert r.next_slot() is None and r.summary()["stopped"] == stopped
    record = {"benchmark_refresh": {"kospi": first, "failed": ["kospi"]}}
    r.apply(record)
    assert record["benchmark_refresh"]["kospi"]["status"] == "failed"


def test_retry_exception_is_recorded_and_keeps_previous_as_of():
    def _boom(d, recheck):
        raise ConnectionResetError("x")

    r = kr.KospiRetry(_failed(), first_at=_hm(8, 10, 20), end_date=TODAY, attempt=_boom)
    r.run_due(_hm(8, 15))
    entry = r.attempts[-1]
    assert (entry["result"], entry["error_type"], entry["as_of"]) == (
        "failed",
        "ConnectionResetError",
        T2,
    )
    assert entry["error"] == "kospi_retry:ConnectionResetError"
    assert r.next_slot() == _hm(8, 20)  # 다음 시각은 그대로 남는다


def test_side_task_error_does_not_change_the_etf_result(tmp_path):
    env = {
        "cal": kb._calendar(tmp_path),
        "db": tmp_path / "m.sqlite",
        "cpath": tmp_path / "c.json",
        "env": kb._env(tmp_path),
        "csv": kb._csv(tmp_path),
    }
    kb._seed(env["db"], kb._window_before_t1(env["cal"]))
    clock = kb.Clock(8, 10, 20)
    f = kb.Fetcher(clock, lambda b, i: kb._rows(b) if i >= 2 else [])

    class Broken:
        def run_due(self, now):
            raise RuntimeError("side bug")

        def next_slot(self):
            return _hm(8, 12)

    out = kb._sync(env, clock, f, side_task=Broken())
    assert out["status"] == "ok"
    assert [a["at_kst"][11:16] for a in out["attempts"]] == ["08:10", "08:15"]


# ── 재시도의 저장 최신일 재확인 판정 ─────────────────────────────────────────────


@pytest.mark.parametrize(
    "results, confirmed",
    [
        # 첫 시도가 저장 최신일을 확인했다(그 뒤 날짜는 공개 전).
        (
            [
                {
                    "before": {"as_of": T2},
                    "attempts": [
                        {"date": T2, "result": "ok"},
                        {"date": T1, "result": "no_rows"},
                    ],
                }
            ],
            True,
        ),
        # 저장 최신일에서 예외로 멈췄다.
        (
            [
                {
                    "before": {"as_of": T2},
                    "attempts": [{"date": T2, "result": "fetch_error"}],
                }
            ],
            False,
        ),
        # 받았지만 증거를 못 남겨 정정이 저장되지 않았다.
        (
            [
                {
                    "before": {"as_of": T2},
                    "error": "evidence_write_failed:OSError",
                    "attempts": [{"date": T2, "result": "ok"}],
                }
            ],
            False,
        ),
        # 앞 재시도가 확인했다.
        (
            [
                {
                    "before": {"as_of": T2},
                    "attempts": [{"date": T2, "result": "fetch_error"}],
                },
                {"attempts": [{"date": T2, "result": "ok"}]},
            ],
            True,
        ),
        # 벤치마크 단계 예외 — 적재 전 기록이 없다.
        ([{}], False),
        # 빈 표 — 다시 확인할 날짜가 없다.
        ([{"before": {"as_of": None}, "attempts": []}], True),
    ],
)
def test_latest_confirmed(results, confirmed):
    assert kr.latest_confirmed(results) is confirmed


def test_retry_rechecks_until_the_stored_latest_is_confirmed():
    seen: list[bool] = []
    first = {
        **_failed("fetch_failed:ConnectionResetError"),
        "before": {"as_of": T2},
        "attempts": [{"date": T2, "result": "fetch_error"}],
    }

    def _attempt(d, recheck):
        seen.append(recheck)
        return {
            **_failed(),
            "attempts": [
                {"date": T2, "result": "ok"},
                {"date": T1, "result": "no_rows"},
            ],
        }

    r = kr.KospiRetry(first, first_at=_hm(8, 10, 20), end_date=TODAY, attempt=_attempt)
    r.run_due(_hm(8, 15))
    r.run_due(_hm(8, 20))
    assert seen == [True, False]
