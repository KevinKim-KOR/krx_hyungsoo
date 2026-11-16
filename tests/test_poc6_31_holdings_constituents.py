"""POC6-31 STEP 2 — [최신 자료 갱신]의 '보유 구성종목' 단계 · 보유 구성 상태 읽기 · API.

보유 파일 · 시장 DB 는 tmp(conftest 격리 + tmp DB) · 수집기는 가짜다(라이브 DB · 외부 호출 0).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app import api as api_module
from app import api_etf_constituents, etf_constituents_batch, etf_constituents_store
from app import holdings as holdings_module
from app import holdings_constituents_refresh as HC
from app import pc_refresh_all
from app import etf_constituents_status as ST
from app.etf_constituents_batch import Collector
from app.holdings import Holding
from app.market_data_store import EtfMasterRow, upsert_etf_master
from tests.test_poc6_31_constituents_collect import FakeFetcher, _seed

KST = timezone(timedelta(hours=9))
NOW = datetime(2026, 11, 14, 15, 7, tzinfo=KST)  # 토요일 → 목표일 11/13(판정 §4 M1)
TARGET = "2026-11-13"


@pytest.fixture()
def db(tmp_path):
    p = tmp_path / "market.sqlite"
    upsert_etf_master(
        [
            EtfMasterRow(
                ticker=t,
                name=f"ETF {t}",
                category=None,
                price=None,
                volume=None,
                market_cap=None,
            )
            for t in ("E1", "E2", "E3", "E4")
        ],
        source="test",
        db_path=p,
    )
    return p


def _hold(*tickers):
    holdings_module.save(
        [
            Holding(
                ticker=t,
                quantity=1,
                avg_buy_price=1000,
                name=f"보유 {t}",
                account_group=g,
            )
            for t, g in tickers
        ]
    )


def _step(db, fetcher, collector=None, **kw):
    return HC.constituents_step(
        now=NOW,
        db_path=db,
        calendar_dir=db.parent / "no_calendar",
        collector=collector or Collector(),
        fetcher=fetcher,
        wait_fn=lambda s: None,
        **kw,
    )


def test_targets_dedupe_accounts_and_skip_stocks(db):
    # 직접 보유 주식(STK001)과 두 계좌에 든 같은 ETF 는 한 번만(판정 Q16 종목 단위)
    _hold(("E1", "계좌1"), ("E1", "계좌2"), ("STK001", "계좌1"), ("E2", "계좌1"))
    targets, reason = HC.holdings_etf_targets(db_path=db)
    assert reason is None and [t for t, _ in targets] == ["E1", "E2"]


@pytest.mark.parametrize(
    "setup, reason",
    [
        ("empty", HC.REASON_EMPTY),
        ("broken", HC.REASON_INVALID),
        ("no_etf_list", HC.REASON_NO_ETF_LIST),
    ],
)
def test_step_skips_with_reason(tmp_path, db, setup, reason):
    f = FakeFetcher()
    if setup == "broken":
        holdings_module.HOLDINGS_DIR.mkdir(parents=True, exist_ok=True)
        holdings_module.HOLDINGS_FILE.write_text("{not json", encoding="utf-8")
    elif setup == "no_etf_list":
        _hold(("E1", "계좌1"))
        db = tmp_path / "empty.sqlite"
    elif setup == "empty":
        _hold()
    out = _step(db, f)
    assert out["status"] == "skipped" and out["reason"] == reason and f.calls == []


def test_step_runs_needed_etfs_only_and_reports_counts(db):
    _hold(
        ("E1", "계좌1"),
        ("E2", "계좌1"),
        ("E3", "계좌1"),
        ("E4", "계좌1"),
        ("STK001", "계좌1"),
    )
    _seed(db, "E1", TARGET, confirmed=True)  # 기존 자료(목표일 충족)
    f = FakeFetcher({"E2": "2026-11-13", "E3": "2026-11-12", "E4": "fail"})
    progress: list[dict[str, Any]] = []
    out = _step(db, f, on_progress=progress.append)
    assert out["status"] == "done" and out["target_date"] == TARGET
    assert sorted(f.calls) == ["E2", "E3", "E4"] and out["calls"] == 3
    c = out["counts"]
    assert (c[ST.EXISTING], c[ST.FETCHED], c[ST.TARGET_WAIT], c[ST.FAILED]) == (
        1,
        1,
        1,
        1,
    )
    assert out["update_failed"] == 1 and out["total"] == 4
    names = {i["ticker"]: i["name"] for i in out["items"]}
    assert names["E1"] == "보유 E1"


def test_step_progress_reported_while_running(db):
    import threading

    _hold(("E1", "계좌1"), ("E2", "계좌1"))
    gate = threading.Event()
    seen: list[dict[str, Any]] = []

    def on_progress(s):
        seen.append(s)
        gate.set()  # 첫 진행 알림 뒤 수집기를 풀어 준다

    out = _step(db, FakeFetcher(block=gate), on_progress=on_progress)
    assert seen and seen[0]["status"] == "running" and seen[0]["batch_total"] == 1
    assert out["status"] == "done"


def test_status_after_restart_and_needs_check_count(db):
    _hold(
        ("E1", "계좌1"),
        ("E2", "계좌1"),
        ("E3", "계좌1"),
        ("E4", "계좌2"),
        ("STK001", "계좌1"),
    )
    _seed(db, "E4", "2026-06-22", confirmed=False)  # 예전 저장분(원천 기준일 미확인)
    _step(
        db,
        FakeFetcher(
            {"E1": "2026-11-13", "E2": "2026-11-12", "E3": "fail", "E4": "nodate"}
        ),
    )
    # 새 프로세스처럼 다른 수집 관리자로 저장 자료만 읽는다
    st = HC.holdings_constituents_status(
        now=NOW, db_path=db, calendar_dir=db.parent / "x", collector=Collector()
    )
    by = {i["ticker"]: i for i in st["items"]}
    assert st["total"] == 4 and st["target_date"] == TARGET  # 주식 · 계좌 행 제외
    assert by["E1"]["result"] == ST.EXISTING
    assert (
        by["E2"]["result"] == ST.TARGET_WAIT and by["E2"]["source_asof"] == "2026-11-12"
    )
    assert by["E3"]["result"] == ST.FAILED
    assert (
        by["E4"]["result"] == ST.NO_SOURCE_DATE
        and by["E4"]["kept_asof"] == "2026-06-22"
    )
    assert st["needs_check"] == 3


def test_status_not_checked_reasons(db):
    _hold(("E1", "계좌1"), ("E2", "계좌1"), ("E3", "계좌1"))
    _seed(db, "E2", "2026-06-22", confirmed=False)
    _seed(db, "E3", "2026-11-12", confirmed=True)
    st = HC.holdings_constituents_status(
        now=NOW, db_path=db, calendar_dir=db.parent / "x", collector=Collector()
    )
    by = {i["ticker"]: i for i in st["items"]}
    assert all(i["result"] == ST.NOT_CHECKED for i in st["items"])
    assert by["E1"]["reason"].startswith("구성 자료 없음")
    assert "예전 자료 6/22 · 원천 기준일 미확인" in by["E2"]["reason"]
    assert "11/12 구성 · 목표일 11/13 자료 아직 확인 안 함" in by["E3"]["reason"]
    assert st["needs_check"] == 3


def test_status_read_does_not_start_collection(db):
    _hold(("E1", "계좌1"))
    col = Collector()
    HC.holdings_constituents_status(
        now=NOW, db_path=db, calendar_dir=db.parent / "x", collector=col
    )
    assert col.current(etf_constituents_batch.KIND_HOLDINGS) is None


# ---------- 묶음 작업 연결 ----------


def _market(status: str):
    from types import SimpleNamespace

    return lambda: SimpleNamespace(
        status=status, refresh_id="m", message="", cooldown_remaining_seconds=0
    )


def _start(constituents_runner, market_status="accepted", prevday=None):
    pc_refresh_all.reset_for_testing()
    pc_refresh_all.start_refresh_all(
        quick_refresher=lambda: {
            "status": "done",
            "fetched_at": "x",
            "items": {},
            "message": None,
        },
        holdings_refresher=lambda: (_ for _ in ()).throw(RuntimeError("x")),
        market_starter=_market(market_status),
        prevday_filler=prevday or (lambda: {"status": "done", "id": "p", "items": {}}),
        constituents_runner=constituents_runner,
        thread_runner=lambda fn: fn(),
    )
    return pc_refresh_all.snapshot()


@pytest.mark.parametrize("market_status", ["accepted", "skipped_cooldown"])
def test_refresh_all_runs_constituents_after_market_and_prevday(market_status):
    order: list[str] = []

    def runner(on_progress):
        order.append("constituents")
        on_progress({"status": "running", "batch_index": 1, "batch_total": 3})
        assert pc_refresh_all.snapshot()["steps"]["constituents"]["batch_index"] == 1
        return {"status": "done", "items": [], "counts": {}}

    def prevday():
        order.append("prevday")
        return {"status": "done", "id": "p", "items": {}}

    snap = _start(runner, market_status, prevday)
    # ② 시작 요청 · 해당하는 ③ 뒤 · ② 대기여도 보유 구성종목은 확인(판정 Q5 (b))
    assert order == (
        ["prevday", "constituents"]
        if market_status == "skipped_cooldown"
        else ["constituents"]
    )
    assert snap["state"] == "done" and snap["steps"]["constituents"]["status"] == "done"


def test_refresh_all_constituents_failure_is_recorded_and_job_ends():
    def runner(_p):
        raise RuntimeError("boom")

    snap = _start(runner)
    assert snap["state"] == "done"
    assert snap["steps"]["constituents"] == {
        "status": "failed",
        "reason": HC.STEP_ERROR_TEXT,
        "items": [],
    }


# ---------- API ----------


@pytest.fixture()
def api_env(db, monkeypatch):
    monkeypatch.setattr(etf_constituents_store, "DEFAULT_DB_PATH", db)
    col = Collector()
    monkeypatch.setattr(api_etf_constituents, "COLLECTOR", col)
    monkeypatch.setattr(HC, "COLLECTOR", col)
    fake = FakeFetcher()
    monkeypatch.setattr(etf_constituents_batch, "default_fetcher", lambda: fake)
    monkeypatch.setattr(
        api_etf_constituents, "collect_target_date", lambda _now: TARGET
    )
    return TestClient(api_module.app), col, fake


def test_api_holdings_status_reads_only(api_env):
    client, col, fake = api_env
    _hold(("E1", "계좌1"), ("STK001", "계좌1"))
    r = client.get("/market/constituents/holdings-status")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1 and body["items"][0]["ticker"] == "E1"
    assert (
        fake.calls == [] and col.current(etf_constituents_batch.KIND_HOLDINGS) is None
    )


def test_api_collect_status_idle_then_job(api_env):
    client, col, fake = api_env
    assert client.get("/market/constituents/collect/status").json()["state"] == "idle"
    r = client.post("/market/constituents/collect", json={"tickers": ["E1", "E2"]})
    assert r.status_code == 200 and r.json()["kind"] == "candidates"
    import time as _t

    for _ in range(300):
        s = client.get("/market/constituents/collect/status").json()
        if s["state"] == "done":
            break
        _t.sleep(0.01)
    assert s["state"] == "done" and sorted(fake.calls) == ["E1", "E2"]
    assert {i["result"] for i in s["items"]} == {ST.FETCHED}


def test_api_collect_rejects_empty_list(api_env):
    client, _col, _fake = api_env
    assert (
        client.post("/market/constituents/collect", json={"tickers": []}).status_code
        == 422
    )


# ---------- 검토 지적 정정(번들 A) ----------


def test_api_candidate_status_rebuilt_from_stored_logs(api_env):
    # 지적 backend#7 — 메모리 작업이 없어도(서버 재시작 · 다른 목록 작업 뒤) 저장 기록으로 ETF별 상태
    client, _col, _fake = api_env
    db = etf_constituents_store.DEFAULT_DB_PATH
    _seed(db, "C1", TARGET, confirmed=True)
    _seed(db, "C2", "2026-11-12", confirmed=True)
    etf_constituents_store.log_constituent_refresh(
        etf_ticker="C2",
        asof=TARGET,
        status=ST.LOG_TARGET_WAIT,
        source=None,
        message="source=2026-11-12",
        db_path=db,
    )
    _seed(db, "C3", "2026-06-22", confirmed=False)
    r = client.get("/market/constituents/collect/status?tickers=C1,C2,C3,C4")
    assert r.status_code == 200
    body = r.json()
    assert (
        body["stored"] is True
        and body["state"] == "idle"
        and body["target_date"] == TARGET
    )
    by = {i["ticker"]: i for i in body["items"]}
    assert [by[t]["result"] for t in ("C1", "C2", "C3", "C4")] == [
        ST.EXISTING,
        ST.TARGET_WAIT,
        ST.NOT_CHECKED,
        ST.NOT_CHECKED,
    ]
    assert by["C2"]["source_asof"] == "2026-11-12" and by["C2"]["last_checked_at"]
    assert (
        "[구성종목 수집]" in by["C3"]["reason"]
        and "원천 기준일 미확인" in by["C3"]["reason"]
    )
    assert body["needs_check"] == 3 and body["other_job"] is None


def test_api_candidate_status_with_other_running_list(api_env):
    # 지적 frontend#1 — 다른 목록 작업이 돌면 이 목록은 저장 상태 + other_job(그 작업을 이 목록 결과로 쓰지 않음)
    client, col, _fake = api_env
    import threading

    gate = threading.Event()
    slow = FakeFetcher(block=gate)
    col.start(
        etf_constituents_batch.KIND_CANDIDATES,
        ["X1", "X2"],
        target_date=TARGET,
        db_path=etf_constituents_store.DEFAULT_DB_PATH,
        fetcher=slow,
        sleep_fn=lambda s: None,
    )
    try:
        mine = client.get("/market/constituents/collect/status?tickers=C1").json()
        assert mine["stored"] is True and mine["other_job"]["total"] == 2
        assert [i["ticker"] for i in mine["items"]] == ["C1"]
        posted = client.post(
            "/market/constituents/collect", json={"tickers": ["C1"]}
        ).json()
        assert posted["other_list"] is True and posted["tickers"] == ["X1", "X2"]
        same = client.get("/market/constituents/collect/status?tickers=X2,X1").json()
        assert (
            same["stored"] is False
            and same["kind"] == "candidates"
            and same["other_list"] is False
        )
    finally:
        gate.set()


def test_api_candidate_status_done_job_for_same_list(api_env):
    client, _col, fake = api_env
    client.post("/market/constituents/collect", json={"tickers": ["E1"]})
    import time as _t

    for _ in range(300):
        s = client.get("/market/constituents/collect/status?tickers=E1").json()
        if s.get("state") == "done":
            break
        _t.sleep(0.01)
    assert s["stored"] is False and s["items"][0]["result"] == ST.FETCHED
    assert fake.calls == ["E1"]


def test_holdings_status_locked_read_is_read_failed(db, monkeypatch):
    # 지적 backend#1(둘째 문장) — 상태 읽기 잠김은 500 · '할 일 없음'이 아니라 '읽지 못함'
    _hold(("E1", "계좌1"))
    import sqlite3

    real = sqlite3.connect

    def connect(*a, **kw):
        kw.setdefault("timeout", 0.2)
        return real(*a, **kw)

    _seed(db, "E1", "2026-11-12", confirmed=True)
    lock = real(str(db), isolation_level=None)
    lock.execute("BEGIN EXCLUSIVE")
    monkeypatch.setattr(sqlite3, "connect", connect)
    try:
        monkeypatch.setattr(HC, "_etf_tickers", lambda _db: {"E1"})
        out = HC.holdings_constituents_status(
            now=NOW, db_path=db, calendar_dir=db.parent / "x", collector=Collector()
        )
    finally:
        lock.execute("ROLLBACK")
        lock.close()
    assert out["status"] == ST.READ_FAILED and out["reason"] == ST.READ_LOCKED_TEXT
    assert out["items"] == [] and out["total"] == 0


# ---------- 검증자 r1 정정(F3 · 2026-11-16) ----------


def test_f3_targets_fixed_at_refresh_start_even_if_holdings_change_mid_run(
    db, monkeypatch
):
    # 검증자 r1 F3 — 시작 때 보유 ETF 1개(E1) · 빠른 시세 단계 도중 보유를 다른 ETF 2개(E2 · E3)로 바꿈 →
    # 구성 단계는 시작 때 대상(E1)만 · 호출 한도 = 1
    monkeypatch.setattr(etf_constituents_store, "DEFAULT_DB_PATH", db)
    col = Collector()
    monkeypatch.setattr(HC, "COLLECTOR", col)
    fake = FakeFetcher()
    monkeypatch.setattr(etf_constituents_batch, "default_fetcher", lambda: fake)
    _hold(("E1", "계좌1"))

    def quick_then_swap():
        _hold(("E2", "계좌1"), ("E3", "계좌1"))  # 형수님이 도중에 보유를 바꿈
        return {"status": "done", "fetched_at": "x", "items": {}, "message": None}

    pc_refresh_all.reset_for_testing()
    pc_refresh_all.start_refresh_all(
        quick_refresher=quick_then_swap,
        holdings_refresher=lambda: (_ for _ in ()).throw(RuntimeError("x")),
        market_starter=_market("accepted"),
        prevday_filler=lambda: {"status": "done", "id": "p", "items": {}},
        thread_runner=lambda fn: fn(),
    )
    step = pc_refresh_all.snapshot()["steps"]["constituents"]
    assert fake.calls == ["E1"]
    assert step["total"] == 1 and [i["ticker"] for i in step["items"]] == ["E1"]


def test_f3_plan_unreadable_at_start_fails_only_that_step(db, monkeypatch):
    # 시작 때 대상을 못 읽으면 그 단계만 실패(단계에 들어가서 다시 읽지 않음 — 도중 바뀐 보유로 대체하지 않게)
    def boom(**_):
        raise RuntimeError("x")

    monkeypatch.setattr(HC, "plan_step", boom)
    called = []
    monkeypatch.setattr(HC, "constituents_step", lambda **kw: called.append(kw) or {})
    pc_refresh_all.reset_for_testing()
    pc_refresh_all.start_refresh_all(
        quick_refresher=lambda: {
            "status": "done",
            "fetched_at": "x",
            "items": {},
            "message": None,
        },
        holdings_refresher=lambda: (_ for _ in ()).throw(RuntimeError("x")),
        market_starter=_market("accepted"),
        prevday_filler=lambda: {"status": "done", "id": "p", "items": {}},
        thread_runner=lambda fn: fn(),
    )
    assert called == []
    assert pc_refresh_all.snapshot()["steps"]["constituents"]["status"] == "failed"
