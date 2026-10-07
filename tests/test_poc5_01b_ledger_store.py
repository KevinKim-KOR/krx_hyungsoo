"""POC5-01B — 원장 저장소 · 활성 판정 · 예정 시각 · meta · 대조(임시 DB 만).

```text
권한        폴더 0700 · DB 0600(-wal · -shm 포함) · 못 맞추면 LedgerUnavailable(보정 1)
스키마      4테이블만(evaluation_run · signal_item · delivery · ledger_meta) · WAL
종료 확정    1회만 · 두 번째는 거부 · 기존 행 불변(스냅샷) · 실패하면 롤백(STARTED 남음 = gap)
meta        INSERT OR IGNORE · git 실패면 키를 비워 다음 실행에 다시(Q-F)
대조        정상 · 원장 누락 · STARTED gap · 원장에만 있음 — 건수와 ID
```

conftest 가 원장 경로 · 캘린더를 tmp 로 돌린다. 라이브 state · logs · 운영 DB 미접근.
"""

from __future__ import annotations

import os
import sqlite3
import stat
from pathlib import Path

import pytest

from app.three_push_runtime import ledger_context as lc
from app.three_push_runtime import ledger_store as ls


def _mode(p: Path) -> int:
    return stat.S_IMODE(os.stat(p).st_mode)


def _run(event_id: str, **over) -> dict:
    row = {
        "event_id": event_id,
        "push_kind": "holdings_risk_alert",
        "contract_version": "holdings_risk_alert.v1",
        "runtime_kst": "2026-10-07T10:30:05+09:00",
        "runtime_date_kst": "2026-10-07",
        "mode": "send",
        "started_at": f"2026-10-07T01:30:05.{event_id[-4:]}+00:00",
        "off_schedule": 0,
    }
    row.update(over)
    return row


def _finalize(con, event_id, *, status="sent", items=(), delivery=None, **run):
    ls.finalize(
        con,
        event_id,
        {"status": status, **run},
        lambda c: list(items),
        delivery or {"delivery_status": "sent"},
    )


def _item(subject_id, state, disposition="sent", **over):
    row = {
        "subject_kind": "ticker",
        "subject_id": subject_id,
        "state": state,
        "disposition": disposition,
        "values_json": "{}",
    }
    row.update(over)
    return row


# ── 연결 · 권한 · 스키마 ──────────────────────────────────────────────────────


def test_connect_secures_dir_and_file_and_creates_only_four_tables():
    con = ls.connect()
    db = ls.DEFAULT_DB_PATH
    try:
        ls.insert_started(con, _run("ev_0001"))  # WAL · -shm 파일이 생긴다
        tables = {
            r[0]
            for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        mode = con.execute("PRAGMA journal_mode").fetchone()[0]
        # 연결이 열린 동안만 -wal · -shm 이 있다(닫으면 체크포인트 뒤 지워진다).
        for extra in (db.with_name(db.name + "-wal"), db.with_name(db.name + "-shm")):
            assert extra.exists() and _mode(extra) == 0o600, extra.name
    finally:
        con.close()
    assert tables == {"evaluation_run", "signal_item", "delivery", "ledger_meta"}
    assert mode == "wal"
    assert _mode(db.parent) == 0o700
    assert _mode(db) == 0o600


def test_permission_failure_makes_ledger_unavailable(monkeypatch):
    """보정 1 — 0700/0600 을 만들거나 확인하지 못하면 원장을 쓰지 않는다."""
    monkeypatch.setattr(ls, "_mode", lambda p: 0o755)
    with pytest.raises(ls.LedgerUnavailable):
        ls.connect()

    def _boom(*a, **k):
        raise PermissionError("no")

    monkeypatch.setattr(ls, "_mode", lambda p: 0o644)
    monkeypatch.setattr(ls.os, "chmod", _boom)
    with pytest.raises(ls.LedgerUnavailable):
        ls.connect()


def test_db_file_permission_failure_stops_before_any_table(monkeypatch):
    """보정 1 의 파일 갈래 — 폴더는 0700 으로 통과 · DB 파일 0600 을 못 맞추면 테이블 0."""
    real_chmod = os.chmod

    def _chmod(path, mode):
        if Path(path).suffix == ".sqlite":
            raise PermissionError("db")
        return real_chmod(path, mode)

    monkeypatch.setattr(ls.os, "chmod", _chmod)
    with pytest.raises(ls.LedgerUnavailable):
        ls.connect()
    db = ls.DEFAULT_DB_PATH
    assert _mode(db.parent) == 0o700
    con = sqlite3.connect(db)
    try:
        assert con.execute("SELECT COUNT(*) FROM sqlite_master").fetchone()[0] == 0
    finally:
        con.close()


# ── run · 종료 확정 · 스냅샷 ──────────────────────────────────────────────────


def test_finalize_once_second_is_rejected_and_rows_unchanged():
    con = ls.connect()
    try:
        ls.insert_started(con, _run("ev_0001"))
        _finalize(con, "ev_0001", items=[_item("A", "D5_7")])
        before = con.execute("SELECT * FROM signal_item").fetchall()
        # 항목 0 · delivery 없음 — PK 충돌 없이 run_state 가드만으로 막는다(파괴 시험 L5).
        with pytest.raises(ls.LedgerUnavailable):
            ls.finalize(con, "ev_0001", {"status": "failed"}, lambda c: [], None)
        with pytest.raises(ls.LedgerUnavailable):
            _finalize(con, "ev_0001", status="failed", items=[_item("B", None)])
        after = con.execute("SELECT * FROM signal_item").fetchall()
        run = con.execute("SELECT run_state, status FROM evaluation_run").fetchone()
        deliveries = con.execute("SELECT COUNT(*) FROM delivery").fetchone()[0]
    finally:
        con.close()
    assert before == after
    assert run == ("FINALIZED", "sent")
    assert deliveries == 1


def test_finalize_failure_rolls_back_and_leaves_started_gap():
    con = ls.connect()
    try:
        ls.insert_started(con, _run("ev_0001"))

        def _bad(c):
            raise RuntimeError("item build")

        with pytest.raises(RuntimeError):
            ls.finalize(
                con, "ev_0001", {"status": "sent"}, _bad, {"delivery_status": "sent"}
            )
        state = con.execute("SELECT run_state FROM evaluation_run").fetchone()[0]
        n_items = con.execute("SELECT COUNT(*) FROM signal_item").fetchone()[0]
        n_del = con.execute("SELECT COUNT(*) FROM delivery").fetchone()[0]
    finally:
        con.close()
    assert (state, n_items, n_del) == ("STARTED", 0, 0)


def test_mid_transaction_failure_rolls_back_items_already_inserted():
    """item INSERT 뒤 delivery INSERT 가 실패하면 item 도 남지 않는다(같은 연결 · 롤백)."""
    con = ls.connect()
    try:
        ls.insert_started(con, _run("ev_0001"))
        with pytest.raises(sqlite3.IntegrityError):
            ls.finalize(
                con,
                "ev_0001",
                {"status": "sent"},
                lambda c: [_item("A", "D5_7")],
                {"delivery_status": None},  # NOT NULL 위반
            )
        ls.insert_started(con, _run("ev_0002"))  # 같은 연결로 다음 쓰기
        assert con.execute("SELECT COUNT(*) FROM signal_item").fetchone()[0] == 0
        assert con.execute("SELECT COUNT(*) FROM delivery").fetchone()[0] == 0
        assert con.execute(
            "SELECT run_state FROM evaluation_run WHERE event_id = 'ev_0001'"
        ).fetchone() == ("STARTED",)
    finally:
        con.close()


def test_no_code_path_updates_item_or_delivery():
    """스냅샷 불변 — item · delivery 를 고치는 SQL 이 원장 코드에 없다."""
    src = "\n".join(
        Path(m.__file__).read_text(encoding="utf-8")
        for m in (
            ls,
            lc,
            __import__("app.three_push_runtime.ledger_items", fromlist=["x"]),
        )
    ).upper()
    assert "UPDATE SIGNAL_ITEM" not in src and "UPDATE DELIVERY" not in src
    assert "DELETE FROM" not in src


def test_meta_put_once_never_overwrites():
    con = ls.connect()
    try:
        assert ls.meta_put_once(con, "deploy_commit", "a" * 40) is True
        assert ls.meta_put_once(con, "deploy_commit", "b" * 40) is False
        assert ls.meta_get(con, "deploy_commit") == "a" * 40
    finally:
        con.close()


def test_previous_item_skips_off_schedule_and_unevaluable_rows():
    con = ls.connect()
    try:
        ls.insert_started(con, _run("ev_0001"))
        _finalize(con, "ev_0001", items=[_item("A", "D5_7")])
        ls.insert_started(con, _run("ev_0002", off_schedule=1))
        _finalize(con, "ev_0002", items=[_item("A", "D10_PLUS")])
        ls.insert_started(con, _run("ev_0003"))
        _finalize(
            con,
            "ev_0003",
            items=[_item("A", None, disposition="data_unavailable", evaluable=0)],
        )
        prev = ls.previous_item(
            con, push_kind="holdings_risk_alert", subject_kind="ticker", subject_id="A"
        )
    finally:
        con.close()
    assert prev == ("D5_7", "2026-10-07")


# ── 대조 ─────────────────────────────────────────────────────────────────────


def _runtime_row(con, run_id, started_at, push_kind="holdings_risk_alert", mode="send"):
    con.execute(
        "INSERT INTO runtime_execution_status (run_id, push_kind, mode, status, started_at,"
        " finished_at, runtime_kst, runtime_date_kst, param_id, param_source, duplicate_key,"
        " inserted_at) VALUES (?, ?, ?, 'sent', ?, ?, '', '', 'p', 'db', '', ?)",
        (run_id, push_kind, mode, started_at, started_at, started_at),
    )


def test_reconcile_separates_ok_missing_gap_and_ledger_only(tmp_path):
    from app import runtime_state_db

    rt = tmp_path / "rt.sqlite"
    runtime_state_db.init_db(rt)
    con = ls.connect()
    try:
        ls.meta_put_once(con, "first_active_at", "2026-10-07T00:00:00+00:00")
        ok = _run("ev_0001")
        ls.insert_started(con, ok)
        _finalize(con, "ev_0001")
        ls.insert_started(con, _run("ev_0002"))  # STARTED gap
        orphan = _run("ev_0003")
        ls.insert_started(con, orphan)
        _finalize(con, "ev_0003", status="failed")  # _finish 를 거치지 않은 예외
    finally:
        con.close()
    rcon = sqlite3.connect(rt)
    with rcon:
        _runtime_row(rcon, 1, ok["started_at"])
        _runtime_row(rcon, 2, "2026-10-07T01:30:05.0002+00:00")  # STARTED 와 같은 키
        _runtime_row(
            rcon, 3, "2026-10-07T02:30:00+00:00"
        )  # 원장에 없음(최초 INSERT 실패)
        _runtime_row(rcon, 4, "2026-10-06T23:00:00+00:00")  # 원장 활성 전 — 대상 아님
        _runtime_row(rcon, 5, "2026-10-07T03:00:00+00:00", mode="dry-run")
    rcon.close()
    out = ls.reconcile(ls.DEFAULT_DB_PATH, rt, kinds=lc.CONTRACT_VERSIONS)
    assert out["ok"] == {"count": 1, "ids": ["ev_0001"]}
    assert out["started_gap"] == {"count": 1, "ids": ["ev_0002"]}
    assert out["ledger_only"] == {"count": 1, "ids": ["ev_0003"]}
    assert out["missing_in_ledger"]["count"] == 1
    # 읽기 전용 — 대조 연결(mode=ro)은 쓰기를 거부한다.
    ro = ls._ro(ls.DEFAULT_DB_PATH)
    try:
        with pytest.raises(sqlite3.OperationalError):
            ro.execute("DELETE FROM evaluation_run")
    finally:
        ro.close()
    assert ls.reconcile(ls.DEFAULT_DB_PATH, rt, kinds=lc.CONTRACT_VERSIONS) == out


def test_reconcile_cli_prints_counts_and_returns_zero(tmp_path, capsys):
    from app import runtime_state_db
    from scripts import run_decision_ledger_reconcile as cli

    rt = tmp_path / "rt.sqlite"
    runtime_state_db.init_db(rt)
    con = ls.connect()
    try:
        ls.meta_put_once(con, "first_active_at", "2026-10-07T00:00:00+00:00")
    finally:
        con.close()
    rc = cli.main(["--ledger", str(ls.DEFAULT_DB_PATH), "--runtime", str(rt)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "ok=0" in out and "started_gap=0" in out
    assert (
        cli.main(["--ledger", str(tmp_path / "none.sqlite"), "--runtime", str(rt)]) == 3
    )


# ── 활성 · 예정 시각 · meta ───────────────────────────────────────────────────


@pytest.mark.parametrize(
    "env, mode, kind, expected",
    [
        (None, "send", "market_briefing", False),  # PC — 플래그 없음
        ("true", "send", "market_briefing", True),
        ("true", "dry-run", "market_briefing", False),
        ("true", "send", "spike_or_falling_alert", False),
        ("false", "send", "holdings_briefing", False),
    ],
)
def test_is_active_requires_flag_send_and_operating_kind(
    monkeypatch, env, mode, kind, expected
):
    if env is not None:
        monkeypatch.setenv(lc.FLAG_ENV, env)
    assert lc.is_active(kind, mode) is expected


@pytest.mark.parametrize(
    "kind, runtime_kst, slot, expected",
    [
        ("market_briefing", "2026-10-07T08:30:04+09:00", None, (0, "08:30")),
        # 한계(Q-A) — cron 이 1분 넘게 늦으면 예정 밖으로 잡힌다.
        ("market_briefing", "2026-10-07T08:31:02+09:00", None, (1, None)),
        ("market_briefing", "2026-10-10T08:30:00+09:00", None, (1, "08:30")),  # 토요일
        ("holdings_briefing", "2026-10-07T09:15:01+09:00", "OPEN", (0, "09:15")),
        ("holdings_briefing", "2026-10-07T09:15:01+09:00", "MIDDAY", (1, None)),
        ("holdings_risk_alert", "2026-10-07T15:20:00+09:00", None, (0, "15:20")),
        ("holdings_risk_alert", "2026-10-07T21:54:00+09:00", None, (1, None)),
    ],
)
def test_schedule_for_matches_cron_times(kind, runtime_kst, slot, expected):
    assert lc.schedule_for(kind, runtime_kst, slot) == expected


def test_git_failure_leaves_deploy_commit_empty_then_retries(monkeypatch):
    """Q-F — `git rev-parse` 가 실패하면 `unknown` 을 쓰지 않고 다음 실행에서 다시 시도한다."""
    run = lc.LedgerRun(
        active=True, push_kind="market_briefing", mode="send", logger=None
    )
    run.base = {
        "started_at": "2026-10-07T00:00:00+00:00",
        "runtime_date_kst": "2026-10-07",
    }
    monkeypatch.setattr(lc, "_git_head", lambda: None)
    con = ls.connect()
    try:
        run._meta_once(con, 1)
        assert ls.meta_get(con, "deploy_commit") is None
        monkeypatch.setattr(lc, "_git_head", lambda: "c" * 40)
        run._meta_once(con, 1)
        assert ls.meta_get(con, "deploy_commit") == "c" * 40
        assert ls.meta_get(con, "contract_version.market_briefing.market_briefing.v1")
        assert (
            ls.meta_get(con, "primary_start_date") is None
        )  # 예정 밖 실행은 정하지 않는다
    finally:
        con.close()


def test_git_head_returns_none_outside_a_git_checkout(monkeypatch, tmp_path):
    """Q-F 앞 절반 — 대역 없이 실제 함수가 git 실패를 None 으로 바꾼다(예외 없음)."""
    monkeypatch.setattr(lc, "PROJECT_ROOT", tmp_path)  # git 저장소가 아닌 폴더
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))
    assert lc._git_head() is None


def test_primary_start_date_is_first_on_schedule_trading_day(monkeypatch):
    run = lc.LedgerRun(
        active=True, push_kind="market_briefing", mode="send", logger=None
    )
    run.base = {
        "started_at": "2026-10-07T00:00:00+00:00",
        "runtime_date_kst": "2026-10-07",
    }
    monkeypatch.setattr(lc, "_git_head", lambda: None)
    con = ls.connect()
    try:
        run._meta_once(con, 0)  # 캘린더 파일 없음 = 평일 기본 → 거래일
        run.base["runtime_date_kst"] = "2026-10-08"
        run._meta_once(con, 0)
        assert ls.meta_get(con, "primary_start_date") == "2026-10-07"
    finally:
        con.close()
