"""POC6-27 — PC 원장 사본 종류별 마지막 실행(`GET /decision-ledger/latest-by-kind`).

계약 출처: POC6-27 PLAN V1 쟁점 3 · 설계자 PLAN 판정 §3 Q6 · §4(기존 목록이 빼는 건너뜀 · 실패도 보이는 사본 전용
읽기 · 실행 발생일시 · 실행 결과 · 마지막 동기화 시각 분리 · 조회 실패와 사본 없음은 다른 상태). 사본은 tmp
(conftest 가 `ledger_copy.store.DEFAULT_DB_PATH` 를 tmp 로 바꿔 둔다 · 라이브 사본을 열지 않음).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.ledger_copy import store, views


def _copy(path: Path) -> Path:
    store.connect(
        path
    ).close()  # 사본 표 만들기(시험 준비 · 실제 동기화 첫 실행과 같은 DDL)
    return path


def _run(
    con,
    eid,
    kind,
    runtime,
    *,
    status="sent",
    delivery="sent",
    state="FINALIZED",
    started=None,
):
    con.execute(
        "INSERT INTO evaluation_run (event_id, run_state, push_kind, runtime_kst, runtime_date_kst,"
        " status, started_at, off_schedule) VALUES (?, ?, ?, ?, ?, ?, ?, 0)",
        (eid, state, kind, runtime, runtime[:10], status, started or runtime),
    )
    if delivery is not None:
        con.execute(
            "INSERT INTO delivery (event_id, delivery_status, body_withheld) VALUES (?, ?, 0)",
            (eid, delivery),
        )


def _sync(con, at, ok=True, kind=None):
    con.execute(
        "INSERT INTO ledger_sync_attempt (attempted_at, ok, failure_kind, counts_json)"
        " VALUES (?, ?, ?, NULL)",
        (at, 1 if ok else 0, kind),
    )


@pytest.fixture
def copy_db(tmp_path):
    p = _copy(tmp_path / "decision" / "copy.sqlite")
    con = sqlite3.connect(p)
    _run(con, "m1", "market_briefing", "2026-10-22T08:30:02+09:00")
    _run(con, "m2", "market_briefing", "2026-10-23T08:30:02+09:00")
    _run(
        con, "h1", "holdings_briefing", "2026-10-23T09:15:01+09:00", delivery="partial"
    )
    _run(con, "h2", "holdings_briefing", "2026-10-23T12:30:02+09:00")
    _run(
        con,
        "r1",
        "holdings_risk_alert",
        "2026-10-23T12:30:01+09:00",
        delivery="failed",
        status="failed",
    )
    _run(
        con,
        "r2",
        "holdings_risk_alert",
        "2026-10-23T13:30:01+09:00",
        delivery="skipped",
        status="skipped",
    )
    # 진행 중(STARTED) 실행은 마지막 실행으로 보지 않는다
    _run(
        con,
        "r3",
        "holdings_risk_alert",
        "2026-10-23T14:30:01+09:00",
        state="STARTED",
        delivery=None,
    )
    _sync(con, "2026-10-12T13:09:21+09:00")
    _sync(con, "2026-10-23T14:27:25+09:00")
    _sync(con, "2026-10-24T09:00:00+09:00", ok=False, kind="ssh_failed")
    con.commit()
    con.close()
    return p


def _by_kind(out):
    return {r["kind"]: r for r in out["kinds"]}


def test_latest_per_kind_includes_skipped_and_partial(copy_db):
    out = views.latest_by_kind(path=copy_db, today="2026-11-09")
    assert out["today_kst"] == "2026-11-09"
    assert out["sync"] == {
        "has_copy": True,
        "last_success_at": "2026-10-23T14:27:25+09:00",
        "last_failure_at": "2026-10-24T09:00:00+09:00",
        "last_failure_kind": "ssh_failed",
    }
    k = _by_kind(out)
    assert [r["kind"] for r in out["kinds"]] == [
        "market_briefing",
        "holdings_briefing",
        "holdings_risk_alert",
    ]
    assert (k["market_briefing"]["label"], k["market_briefing"]["time_kst"]) == (
        "시장 브리핑",
        "2026-10-23T08:30:02+09:00",
    )
    assert k["market_briefing"]["delivery_status"] == "sent"
    assert k["holdings_briefing"]["time_kst"].endswith("12:30:02+09:00")
    r = k["holdings_risk_alert"]
    assert (r["label"], r["run_date_kst"], r["delivery_status"], r["run_status"]) == (
        "장중 급등락",
        "2026-10-23",
        "skipped",
        "skipped",
    )


def test_failed_and_partial_are_returned_as_is(tmp_path):
    p = _copy(tmp_path / "c.sqlite")
    con = sqlite3.connect(p)
    _run(
        con,
        "a",
        "holdings_risk_alert",
        "2026-11-09T09:30:01+09:00",
        delivery="failed",
        status="failed",
    )
    _run(con, "b", "holdings_briefing", "2026-11-09T09:15:01+09:00", delivery="partial")
    _sync(con, "2026-11-09T09:40:00+09:00")
    con.commit()
    con.close()
    k = _by_kind(views.latest_by_kind(path=p, today="2026-11-09"))
    assert k["holdings_risk_alert"]["delivery_status"] == "failed"
    assert k["holdings_briefing"]["delivery_status"] == "partial"
    # 실행 없는 종류 = 빈 칸(없는 값을 만들지 않음)
    assert k["market_briefing"]["time_kst"] is None
    assert k["market_briefing"]["delivery_status"] is None


def test_same_runtime_ordered_by_started_at(tmp_path):
    p = _copy(tmp_path / "c.sqlite")
    con = sqlite3.connect(p)
    t = "2026-10-23T08:30:02+09:00"
    _run(
        con,
        "x1",
        "market_briefing",
        t,
        delivery="skipped",
        started="2026-10-23T08:30:02.100+09:00",
    )
    _run(
        con,
        "x2",
        "market_briefing",
        t,
        delivery="sent",
        started="2026-10-23T08:30:02.900+09:00",
    )
    con.commit()
    con.close()
    k = _by_kind(views.latest_by_kind(path=p, today="2026-11-09"))
    assert k["market_briefing"]["delivery_status"] == "sent"


def test_run_without_delivery_row_keeps_null_delivery(tmp_path):
    p = _copy(tmp_path / "c.sqlite")
    con = sqlite3.connect(p)
    _run(
        con,
        "n",
        "market_briefing",
        "2026-11-09T08:30:02+09:00",
        delivery=None,
        status="failed",
    )
    con.commit()
    con.close()
    k = _by_kind(views.latest_by_kind(path=p, today="2026-11-09"))
    assert (
        k["market_briefing"]["delivery_status"],
        k["market_briefing"]["run_status"],
    ) == (
        None,
        "failed",
    )


def test_missing_copy_is_no_copy_and_not_created(tmp_path):
    p = tmp_path / "decision" / "none.sqlite"
    out = views.latest_by_kind(path=p, today="2026-11-09")
    assert out["sync"]["has_copy"] is False
    assert all(r["time_kst"] is None for r in out["kinds"])
    assert not p.exists() and not p.parent.exists()


def test_empty_file_without_tables_is_no_copy(tmp_path):
    p = tmp_path / "empty.sqlite"
    sqlite3.connect(p).close()
    before = p.read_bytes()
    out = views.latest_by_kind(path=p, today="2026-11-09")
    assert out["sync"]["has_copy"] is False
    assert p.read_bytes() == before  # 표를 만들지 않음(mode=ro)


def test_read_is_read_only(copy_db):
    before = copy_db.read_bytes()
    views.latest_by_kind(path=copy_db, today="2026-11-09")
    assert copy_db.read_bytes() == before


def test_corrupt_copy_raises_not_no_copy(tmp_path):
    p = tmp_path / "bad.sqlite"
    p.write_bytes(b"not a sqlite file" * 100)
    with pytest.raises(sqlite3.DatabaseError):
        views.latest_by_kind(path=p, today="2026-11-09")


def test_get_endpoint(monkeypatch, tmp_path):
    p = store._db_path()  # conftest 가 tmp 로 바꿔 둔 사본 경로
    assert str(tmp_path) in str(p)
    _copy(p)
    con = sqlite3.connect(p)
    _run(
        con, "r", "holdings_risk_alert", "2026-10-23T13:30:01+09:00", delivery="skipped"
    )
    _sync(con, "2026-10-23T14:27:25+09:00")
    con.commit()
    con.close()
    from app.api import app

    body = TestClient(app).get("/decision-ledger/latest-by-kind").json()
    assert set(body) == {"today_kst", "sync", "kinds"}
    assert body["sync"]["has_copy"] is True
    k = {r["kind"]: r for r in body["kinds"]}
    assert k["holdings_risk_alert"]["delivery_status"] == "skipped"
    assert k["market_briefing"]["time_kst"] is None


def test_get_endpoint_without_copy(monkeypatch):
    p = store._db_path()
    from app.api import app

    body = TestClient(app).get("/decision-ledger/latest-by-kind").json()
    assert body["sync"]["has_copy"] is False and not Path(p).exists()


def test_get_endpoint_corrupt_copy_is_server_error(tmp_path):
    p = store._db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"garbage" * 200)
    from app.api import app

    r = TestClient(app, raise_server_exceptions=False).get(
        "/decision-ledger/latest-by-kind"
    )
    assert r.status_code == 500  # 화면 = '불러오지 못함'(사본 없음과 다름)
