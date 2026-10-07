"""POC5-03 — PC 원장 사본 · 원장 새로고침 · 피드백 · 가격 결과 숨김 · 결과 대상 판정.

PLAN `docs/ai_plan/POC5/POC5-03_PC_LEDGER_SYNC_AND_FEEDBACK_PLAN_V1.md` §4 · §8.

- '원격 원장' 은 tmp 경로에 실제 `ledger_store` 쓰기 함수로 만든다.
- export 는 실제 `remote_export.py` 를 `python -` 표준입력으로 실행해 얻는다(OCI 와 같은 실행 방식).
- PC 사본 · 이름 조회는 conftest 가 tmp 로 돌린다. 실제 SSH 는 0 이다(subprocess 차단).
"""

from __future__ import annotations

import ast
import hashlib
import inspect
import json
import logging
import os
import sqlite3
import stat
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import api as api_module
from app import decision_evidence_store
from app.ledger_copy import store, sync, views
from app.three_push_runtime import ledger_outcome as lo
from app.three_push_runtime import ledger_store as ls

DAY = "2026-10-08"
SCRIPT = Path(sync.EXPORT_SCRIPT)
_REAL_RUN = subprocess.run
_COPY_TABLES = (*store.TABLES, "user_feedback")


@pytest.fixture(autouse=True)
def _no_ssh(monkeypatch):
    """실제 SSH 0 — 대상 주소를 지우고 subprocess.run 을 막는다(필요한 테스트만 다시 바꾼다)."""
    monkeypatch.delenv("OCI_SSH_TARGET", raising=False)
    monkeypatch.delenv("OCI_SSH_KEY_PATH", raising=False)

    def _blocked(*_a, **_k):
        raise AssertionError("SSH 호출 금지")

    monkeypatch.setattr(sync.subprocess, "run", _blocked)


@pytest.fixture
def client():
    return TestClient(api_module.app)


# ── 원격 원장 fixture ────────────────────────────────────────────────────────


def _item(
    kind, sid, *, disposition="sent", evaluable=1, held=1, state="WATCH", t0=100.0
):
    return {
        "subject_kind": kind,
        "subject_id": sid,
        "held": held,
        "state": state,
        "prev_state": None,
        "disposition": disposition,
        "event_type": None,
        "exposure": None,
        "values_json": "{}",
        "t0_price": t0,
        "t0_price_asof": "2026-10-08T09:14:58+09:00",
        "evaluable": evaluable,
    }


def _started(con, eid, *, kind="holdings_briefing", hhmm="09:15", off=0, day=DAY):
    ts = f"{day}T{hhmm}:01+09:00"
    ls.insert_started(
        con,
        {
            "event_id": eid,
            "push_kind": kind,
            "runtime_kst": ts,
            "runtime_date_kst": day,
            "started_at": ts,
            "off_schedule": off,
            "schedule_expected": None if off else hhmm,
        },
    )


def _final(
    con, eid, items, *, status="sent", cohort="PRIMARY_LIVE", body="생성된 본문"
):
    delivery = {
        "delivery_status": status,
        "telegram_sent": 1 if status == "sent" else 0,
        "planned_chunk_count": 1,
        "body_text": None if status == "skipped" else body,
        "body_sha256": None if status == "skipped" else "h",
        "body_withheld": 0,
    }
    ls.finalize(
        con,
        eid,
        {"status": "ok", "cohort": cohort, "finished_at": f"{DAY}T10:00:00+00:00"},
        lambda _c: [dict(i) for i in items],
        delivery,
    )


def _event(
    con, eid, items, *, kind="holdings_briefing", hhmm="09:15", off=0, day=DAY, **kw
):
    _started(con, eid, kind=kind, hhmm=hhmm, off=off, day=day)
    _final(con, eid, items, **kw)


def _outcomes(con, rows):
    for stmt in lo.DDL:
        con.execute(stmt)
    con.executemany(
        "INSERT INTO price_outcome"
        " (event_id, item_seq, series_id, horizon, status, return_raw, computed_at)"
        " VALUES (?, ?, ?, ?, ?, ?, 'c')",
        rows,
    )
    con.commit()


@pytest.fixture
def remote(tmp_path):
    """원격 원장 — 08:30 시장 · 09:15 보유 · 10:30 장중(partial) · skipped · failed ·
    예정 외 · LEGACY · STARTED 잔류 · 가격 결과 3행."""
    p = tmp_path / "remote" / "decision" / "decision_evidence.sqlite"
    con = ls.connect(p)
    _event(
        con,
        "E1",
        [_item("ticker", "005930"), _item("ticker", "069500")],
        body="보유 브리핑 원문",
    )
    _event(
        con,
        "E2",
        [
            _item("market", "SP500", t0=None),
            _item("index_group", "KODEX|반도체", t0=None),
        ],
        kind="market_briefing",
        hhmm="08:30",
    )
    _event(
        con,
        "E3",
        [
            _item("ticker", "091160"),
            _item("sector", "반도체"),
            _item("sector_block", "BLOCK", t0=None),
            _item("ticker", "000660", disposition="data_unavailable", evaluable=0),
            _item("ticker", "035420", disposition="suppressed"),
        ],
        kind="holdings_risk_alert",
        hhmm="10:30",
        status="partial",
        body="장중 급등락 전체 본문(분할 전)",
    )
    _event(
        con,
        "E4",
        [_item("ticker", "005930")],
        kind="holdings_risk_alert",
        hhmm="11:30",
        status="skipped",
    )
    _event(
        con,
        "E5",
        [_item("ticker", "005930")],
        kind="holdings_risk_alert",
        hhmm="12:30",
        status="failed",
    )
    _event(
        con,
        "E6",
        [_item("ticker", "091160")],
        kind="holdings_risk_alert",
        hhmm="13:05",
        off=1,
    )
    _event(
        con, "E7", [_item("ticker", "005930")], hhmm="12:30", cohort="LEGACY_DIAGNOSTIC"
    )
    _started(con, "E8", hhmm="15:40")
    _outcomes(
        con,
        [
            ("E1", 1, "krx_stock:005930", 1, "MATURED", 0.0123),
            ("E1", 1, "krx_stock:005930", 5, "PRICE_MISSING", None),
            ("E3", 1, "krx_etf:091160", 1, "UNTRACKED_AFTER_EXIT", None),
        ],
    )
    yield p, con
    con.close()


def _export(path: Path) -> bytes:
    r = _REAL_RUN(
        [sys.executable, "-", str(path)],
        input=SCRIPT.read_bytes(),
        capture_output=True,
        check=False,
    )
    assert r.returncode == 0, r.stderr
    return r.stdout


def _sync(path: Path) -> dict:
    raw = _export(path)
    return sync.sync_once(runner=lambda: raw)


def _dump() -> dict:
    con = sqlite3.connect(str(store.DEFAULT_DB_PATH))
    try:
        names = {
            r[0]
            for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        return {
            t: sorted(map(repr, con.execute(f"SELECT * FROM {t}").fetchall()))
            for t in _COPY_TABLES
            if t in names
        }
    finally:
        con.close()


def _mutate(raw: bytes, fn) -> bytes:
    lines = [json.loads(x) for x in raw.decode("utf-8").splitlines()]
    fn(lines)
    return ("\n".join(json.dumps(x, ensure_ascii=False) for x in lines) + "\n").encode(
        "utf-8"
    )


def _sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# ── 원격 export (수용 기준 2) ────────────────────────────────────────────────


def test_export_is_read_only_snapshot(remote):
    path, con = remote
    before = {
        t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in store.TABLES
    }
    con.close()  # 러너 실행 사이처럼 -wal · -shm 이 없는 상태에서 읽는다
    assert not Path(f"{path}-wal").exists()
    before_sha = _sha(path)
    raw = _export(path)
    assert raw.isascii()  # 원격 locale · 줄 구분 문자와 무관
    lines = [json.loads(x) for x in raw.decode("ascii").split("\n") if x]
    assert lines[0]["kind"] == "header" and lines[0]["ledger"] == "present"
    assert all(lines[0]["tables"].values())
    assert lines[-1] == {"kind": "end", "counts": before}
    assert _sha(path) == before_sha  # 주 파일 불변
    ro = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    after = {
        t: ro.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in store.TABLES
    }
    ro.close()
    assert after == before


def test_line_separator_characters_survive(tmp_path):
    p = tmp_path / "r" / "decision_evidence.sqlite"
    con = ls.connect(p)
    body = "첫 줄\u2028둘째\u2029셋째\x85넷째\n다섯째"
    _event(con, "E1", [_item("ticker", "005930")], body=body)
    con.close()
    assert _sync(p)["ok"] is True
    assert views.alert_detail("E1", names={})["body_text"] == body


def test_export_without_outcome_table_is_not_an_error(tmp_path):
    p = tmp_path / "r" / "decision_evidence.sqlite"
    con = ls.connect(p)
    _event(con, "E1", [_item("ticker", "005930")])
    con.close()
    res = _sync(p)
    assert res["ok"] is True
    assert "outcome_table" not in res and "price_outcome" not in res["counts"]


def test_normal_empty_ledger_is_ok(tmp_path):
    p = tmp_path / "r" / "decision_evidence.sqlite"
    ls.connect(
        p
    ).close()  # 러너가 처음 연 원장 = 기본 4표 · 0행 · 결과 표 없음(성숙 전)
    res = _sync(p)
    assert res["ok"] is True
    assert all(
        c == {"inserted": 0, "updated": 0, "unchanged": 0}
        for c in res["counts"].values()
    )


@pytest.mark.parametrize(
    "drop", ["evaluation_run", "signal_item", "delivery", "ledger_meta", "ALL"]
)
def test_missing_core_table_is_not_a_normal_empty_ledger(tmp_path, drop):
    p = tmp_path / "r" / "decision_evidence.sqlite"
    if drop == "ALL":
        p.parent.mkdir(parents=True)
        sqlite3.connect(str(p)).close()  # 표가 하나도 없는 빈 SQLite 파일
    else:
        con = ls.connect(p)
        con.execute(f"DROP TABLE {drop}")
        con.commit()
        con.close()
    res = _sync(p)
    assert res["ok"] is False and res["failure_kind"] == sync.INVALID_EXPORT
    con = store.connect()
    status = store.sync_status(con)
    con.close()
    assert status["has_copy"] is False


def test_outcome_table_missing_after_it_was_created_is_invalid(tmp_path):
    p = tmp_path / "r" / "decision_evidence.sqlite"
    con = ls.connect(p)
    ls.meta_put_once(con, lo.META_KEY, lo.SCHEMA_VERSION)  # 성숙 단계가 표를 만든 기록
    con.close()
    res = _sync(p)
    assert res["ok"] is False and res["failure_kind"] == sync.INVALID_EXPORT


def test_rows_missing_from_remote_are_a_conflict(tmp_path, remote):
    path, _ = remote
    assert _sync(path)["ok"] is True
    store.add_feedback("E1", helpfulness="HELPFUL")
    before = _dump()

    def drop_item(lines):  # 원격에서 행 하나가 사라진 export(원격은 지우지 않는다)
        x = next(
            i
            for i in lines
            if i.get("table") == "signal_item" and i["row"]["event_id"] == "E2"
        )  # 가격 결과가 걸리지 않은 item(관계 검사가 아니라 손실 검사가 잡아야 한다)
        lines.remove(x)
        lines[-1]["counts"]["signal_item"] -= 1

    raw = _mutate(_export(path), drop_item)
    assert sync.sync_once(runner=lambda: raw)["failure_kind"] == sync.CONFLICT
    assert _dump() == before
    other = (
        tmp_path / "replaced" / "decision_evidence.sqlite"
    )  # 원장이 새 파일로 바뀐 경우
    con = ls.connect(other)
    _event(con, "E99", [_item("ticker", "005930")])
    con.close()
    res = _sync(other)
    assert res["ok"] is False and res["failure_kind"] == sync.CONFLICT
    assert _dump() == before


def test_absent_remote_ledger_keeps_copy(tmp_path, remote):
    path, _ = remote
    assert _sync(path)["ok"] is True
    before = _dump()
    res = _sync(tmp_path / "nowhere" / "decision_evidence.sqlite")
    assert res == {**res, "ok": False, "failure_kind": sync.NO_REMOTE_LEDGER}
    assert _dump() == before


# ── 반영 · 반복 · 갱신 (수용 기준 3) ─────────────────────────────────────────


def test_sync_is_idempotent_and_keeps_feedback(remote):
    path, _ = remote
    first = _sync(path)
    assert first["ok"] is True
    assert first["counts"]["evaluation_run"]["inserted"] == 8
    assert _dump()["user_feedback"] == []  # 동기화는 feedback 행을 만들지 않는다
    store.add_feedback("E1", helpfulness="HELPFUL")
    before = _dump()
    second = _sync(path)
    assert second["ok"] is True
    for c in second["counts"].values():
        assert c["inserted"] == 0 and c["updated"] == 0
    assert _dump() == before


def test_sync_response_and_record_hide_outcome_counts(remote, client, monkeypatch):
    path, _ = remote
    raw = _export(path)
    monkeypatch.setenv("OCI_SSH_TARGET", "oci-test")
    monkeypatch.setattr(
        sync.subprocess,
        "run",
        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, stdout=raw, stderr=b""),
    )
    r = client.post("/decision-ledger/sync")
    assert r.status_code == 200 and r.json()["ok"] is True
    assert "price_outcome" not in r.text and "outcome_table" not in r.text
    con = sqlite3.connect(str(store.DEFAULT_DB_PATH))
    (counts_json,) = con.execute(
        "SELECT counts_json FROM ledger_sync_attempt"
    ).fetchone()
    con.close()
    assert "price_outcome" not in counts_json and "evaluation_run" in counts_json


def test_success_record_is_part_of_the_copy_transaction(remote, monkeypatch):
    path, _ = remote
    real = store._insert_attempt

    def broken(*_a, **_k):
        raise sqlite3.OperationalError("주입")

    monkeypatch.setattr(store, "_insert_attempt", broken)
    res = _sync(path)
    assert res["ok"] is False and res["failure_kind"] == sync.LOCAL_WRITE_FAILED
    assert all(v == [] for k, v in _dump().items() if k in store.TABLES)  # 사본도 없다
    monkeypatch.setattr(
        store, "_insert_attempt", real
    )  # 이 함수만 되돌린다(tmp 격리 유지)
    ok = _sync(path)
    con = store.connect()
    status = store.sync_status(con)
    con.close()
    assert ok["ok"] is True and status["last_success_at"] == ok["attempted_at"]


def test_first_connect_failure_skips_ssh(monkeypatch):
    called = []

    def broken(_p=None):
        raise sqlite3.OperationalError("주입")

    monkeypatch.setattr(store, "connect", broken)
    res = sync.sync_once(runner=lambda: called.append(1) or b"")
    assert res["ok"] is False and res["failure_kind"] == sync.LOCAL_WRITE_FAILED
    assert called == []


def test_started_run_is_updated_once_finalized(remote):
    path, con = remote
    assert _sync(path)["ok"] is True
    local = sqlite3.connect(str(store.DEFAULT_DB_PATH))
    assert (
        local.execute(
            "SELECT run_state FROM evaluation_run WHERE event_id='E8'"
        ).fetchone()[0]
        == "STARTED"
    )
    _final(con, "E8", [_item("ticker", "005930")])
    res = _sync(path)
    assert res["counts"]["evaluation_run"]["updated"] == 1
    assert res["counts"]["signal_item"]["inserted"] == 1
    assert (
        local.execute(
            "SELECT run_state FROM evaluation_run WHERE event_id='E8'"
        ).fetchone()[0]
        == "FINALIZED"
    )
    local.close()


# ── 실패 시 전체 취소 (수용 기준 4) ──────────────────────────────────────────


def test_conflict_rolls_back_whole_sync(remote):
    path, con = remote
    assert _sync(path)["ok"] is True
    store.add_feedback("E1", helpfulness="NEUTRAL")
    local = sqlite3.connect(str(store.DEFAULT_DB_PATH))
    with local:
        local.execute(
            "UPDATE signal_item SET state = 'X' WHERE event_id = 'E1' AND item_seq = 1"
        )
    local.close()
    _event(
        con, "E9", [_item("ticker", "005930")], hhmm="14:30"
    )  # 앞 표(run)의 새 행도 취소돼야 한다
    before = _dump()
    res = _sync(path)
    assert res["ok"] is False and res["failure_kind"] == sync.CONFLICT
    assert _dump() == before


def test_finalized_run_never_goes_back(remote):
    path, _ = remote
    raw = _export(path)
    assert sync.sync_once(runner=lambda: raw)["ok"] is True

    def back(lines):
        for x in lines:
            if x.get("table") == "evaluation_run" and x["row"]["event_id"] == "E1":
                x["row"]["status"] = "changed"

    before = _dump()
    res = sync.sync_once(runner=lambda: _mutate(raw, back))
    assert res["failure_kind"] == sync.CONFLICT
    assert _dump() == before


def _change_e8(**fields):
    def fn(lines):
        for x in lines:
            if x.get("table") == "evaluation_run" and x["row"]["event_id"] == "E8":
                x["row"].update(fields)

    return fn


@pytest.mark.parametrize(
    "fields",
    [
        {"push_kind": "market_briefing"},  # 시작 열이 바뀜
        {"started_at": "2099-01-01T00:00:00+09:00"},
        {"status": "changed"},  # 원격도 STARTED 인데 값이 다름
    ],
)
def test_started_copy_only_accepts_its_finalize(remote, fields):
    path, con = remote
    assert _sync(path)["ok"] is True
    before = _dump()
    if "status" not in fields:
        _final(con, "E8", [])  # 원격 확정 — 시작 열을 바꾸면 충돌이어야 한다
    raw = _mutate(_export(path), _change_e8(**fields))
    res = sync.sync_once(runner=lambda: raw)
    assert res["failure_kind"] == sync.CONFLICT
    assert _dump() == before


def test_mid_apply_failure_leaves_nothing(remote, monkeypatch):
    path, con = remote
    assert _sync(path)["ok"] is True
    store.add_feedback("E1", helpfulness="HELPFUL")
    _event(con, "E9", [_item("ticker", "005930")], hhmm="14:30")
    before = _dump()
    real = store._apply_row

    def boom(con, table, row, counts):
        if table == "delivery":
            raise RuntimeError("주입")
        return real(con, table, row, counts)

    monkeypatch.setattr(store, "_apply_row", boom)
    res = _sync(path)
    assert res["ok"] is False and res["failure_kind"] == sync.LOCAL_WRITE_FAILED
    assert _dump() == before  # 기존 사본 · feedback 그대로 · E9 도 들어오지 않음


def _bump(table):
    def fn(lines):
        lines[-1]["counts"][table] += 1

    return fn


def _add_row(table, row, bump=True):
    def fn(lines):
        lines.insert(-1, {"kind": "row", "table": table, "row": row})
        if bump:
            lines[-1]["counts"][table] = lines[-1]["counts"].get(table, 0) + 1

    return fn


def _first_row(lines, table):
    return next(x for x in lines if x.get("table") == table)


_INVALID = {
    "non_utf8": (lambda raw: raw + b"\xff\xfe\n", sync.INVALID_EXPORT),
    "bad_json": (
        lambda raw: raw.replace(b'"kind":"end"', b'"kind":end'),
        sync.INVALID_EXPORT,
    ),
    "missing_end": (
        lambda raw: _mutate(raw, lambda ls_: ls_.pop()),
        sync.INVALID_EXPORT,
    ),
    "count_mismatch": (
        lambda raw: _mutate(raw, _bump("evaluation_run")),
        sync.INVALID_EXPORT,
    ),
    "unknown_table": (
        lambda raw: _mutate(raw, _add_row("evil", {"event_id": "x"}, bump=False)),
        sync.INVALID_EXPORT,
    ),
    "unknown_column": (
        lambda raw: _mutate(
            raw, lambda ls_: _first_row(ls_, "signal_item")["row"].update(x=1)
        ),
        sync.INVALID_EXPORT,
    ),
    "missing_not_null": (
        lambda raw: _mutate(
            raw,
            lambda ls_: _first_row(ls_, "evaluation_run")["row"].update(run_state=None),
        ),
        sync.INVALID_EXPORT,
    ),
    "duplicate_key": (
        lambda raw: _mutate(
            raw, lambda ls_: ls_.insert(-1, dict(_first_row(ls_, "delivery")))
        ),
        sync.INVALID_EXPORT,
    ),
    "item_of_started_run": (
        lambda raw: _mutate(
            raw,
            _add_row(
                "signal_item", {**_item("ticker", "1"), "event_id": "E8", "item_seq": 1}
            ),
        ),
        sync.INVALID_EXPORT,
    ),
    "orphan_outcome": (
        lambda raw: _mutate(
            raw,
            _add_row(
                "price_outcome",
                {
                    "event_id": "E1",
                    "item_seq": 99,
                    "series_id": "s",
                    "horizon": 1,
                    "status": "MATURED",
                    "computed_at": "c",
                },
            ),
        ),
        sync.INVALID_EXPORT,
    ),
    "list_value": (
        lambda raw: _mutate(
            raw, lambda ls_: _first_row(ls_, "signal_item")["row"].update(state=["x"])
        ),
        sync.INVALID_EXPORT,
    ),
    "rows_of_absent_table": (
        lambda raw: _mutate(
            raw, lambda ls_: ls_[0]["tables"].update(price_outcome=False)
        ),
        sync.INVALID_EXPORT,
    ),
    "partial_columns": (
        lambda raw: _mutate(
            raw, lambda ls_: _first_row(ls_, "evaluation_run")["row"].pop("cohort")
        ),
        sync.INVALID_EXPORT,
    ),
    "text_in_integer": (
        lambda raw: _mutate(
            raw,
            lambda ls_: _first_row(ls_, "signal_item")["row"].update(item_seq="abc"),
        ),
        sync.INVALID_EXPORT,
    ),
    "bool_in_text": (
        lambda raw: _mutate(
            raw, lambda ls_: _first_row(ls_, "signal_item")["row"].update(state=True)
        ),
        sync.INVALID_EXPORT,
    ),
    "nan": (
        lambda raw: _mutate(
            raw,
            lambda ls_: _first_row(ls_, "signal_item")["row"].update(
                t0_price=float("nan")
            ),
        ),
        sync.INVALID_EXPORT,
    ),
    "overflow_float": (
        lambda raw: raw.replace(b'"t0_price":100.0', b'"t0_price":1e400', 1),
        sync.INVALID_EXPORT,
    ),
    "huge_int": (
        lambda raw: _mutate(
            raw, lambda ls_: _first_row(ls_, "signal_item")["row"].update(held=2**70)
        ),
        sync.INVALID_EXPORT,
    ),
    "deep_nesting": (
        lambda raw: raw + b"[" * 100000 + b"]" * 100000 + b"\n",
        sync.INVALID_EXPORT,
    ),
    "bogus_run_state": (
        lambda raw: _mutate(raw, _change_e8(run_state="BOGUS")),
        sync.INVALID_EXPORT,
    ),
    "remote_error_line": (
        lambda raw: _mutate(
            raw, lambda ls_: ls_.insert(-1, {"kind": "error", "error_type": "X"})
        ),
        sync.REMOTE_ERROR,
    ),
}


@pytest.mark.parametrize("case", sorted(_INVALID))
def test_invalid_export_changes_nothing(remote, case):
    path, _ = remote
    make, kind = _INVALID[case]
    raw = make(_export(path))
    res = sync.sync_once(runner=lambda: raw)
    assert res["ok"] is False and res["failure_kind"] == kind
    dump = _dump()
    assert all(dump[t] == [] for t in store.TABLES)
    con = store.connect()
    status = store.sync_status(con)
    con.close()
    assert status["has_copy"] is False and status["last_failure_kind"] == kind


def test_coexists_with_ai_session_store(remote):
    path, _ = remote
    pc = Path(store.DEFAULT_DB_PATH)
    pc.parent.mkdir(parents=True, exist_ok=True)
    saved = decision_evidence_store.insert_record(
        db_path=pc,
        asof="2026-10-07",
        source_screen="market_discovery",
        filters={
            "exclude_inverse": True,
            "exclude_leveraged": True,
            "exclude_synthetic": True,
            "exclude_futures": True,
        },
        candidate_snapshot=[{"rank": 1, "ticker": "069500", "tags": []}],
        question_text="질문",
        gpt_answer_text="답변",
        gemini_answer_text="",
        claude_answer_text="",
        user_memo="메모",
        user_verdict="hold",
        next_checks=[],
        linked_market_refresh_id=None,
    )
    before = decision_evidence_store.get_record(saved["id"], db_path=pc)
    mode = stat.S_IMODE(os.stat(pc).st_mode)
    assert _sync(path)["ok"] is True
    assert stat.S_IMODE(os.stat(pc).st_mode) == mode  # 권한 불변
    con = sqlite3.connect(str(pc))
    assert con.execute("PRAGMA journal_mode").fetchone()[0] != "wal"  # 저널 방식 불변
    con.close()
    assert decision_evidence_store.get_record(saved["id"], db_path=pc) == before


# ── SSH (수용 기준 1 · 2 · 로그) ──────────────────────────────────────────────


def test_read_and_feedback_never_ssh(remote, client, monkeypatch):
    path, _ = remote
    assert _sync(path)["ok"] is True

    def no_export():
        raise AssertionError("조회 · 피드백은 원장 export 를 부르지 않는다")

    monkeypatch.setattr(sync, "run_export", no_export)
    assert (
        client.get("/decision-ledger/alerts", params={"date": DAY}).status_code == 200
    )
    assert client.get("/decision-ledger/alerts/E1").status_code == 200
    r = client.post(
        "/decision-ledger/alerts/E1/feedback", json={"helpfulness": "HELPFUL"}
    )
    assert r.status_code == 200
    assert "ledger" not in inspect.getsource(
        api_module._lifespan
    )  # 기동은 원장 동기화를 부르지 않는다


def test_sync_runs_one_fixed_ssh_command(remote, client, monkeypatch):
    path, _ = remote
    raw = _export(path)
    monkeypatch.setenv("OCI_SSH_TARGET", "oci-test")
    monkeypatch.setenv("OCI_SSH_KEY_PATH", "/k/id")
    calls = []

    def fake_run(cmd, **kw):
        calls.append((cmd, kw))
        return subprocess.CompletedProcess(cmd, 0, stdout=raw, stderr=b"")

    monkeypatch.setattr(sync.subprocess, "run", fake_run)
    r = client.post("/decision-ledger/sync")
    assert r.status_code == 200 and r.json()["ok"] is True
    assert len(calls) == 1
    cmd, kw = calls[0]
    assert cmd == [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=8",
        "-i",
        "/k/id",
        "-o",
        "IdentitiesOnly=yes",
        "oci-test",
        "python3 - /home/ubuntu/krx_hyungsoo/state/decision/decision_evidence.sqlite",
    ]
    assert kw["input"] == SCRIPT.read_bytes() and kw["timeout"] == 60
    assert (
        "text" not in kw and "encoding" not in kw
    )  # bytes 로 받아 UTF-8 로 직접 디코딩


@pytest.mark.parametrize(
    "outcome, kind",
    [
        (
            subprocess.CompletedProcess([], 255, stdout=b"", stderr=b"denied"),
            sync.SSH_FAILED,
        ),
        (
            subprocess.CompletedProcess([], 3, stdout=b'{"kind":"error"}', stderr=b""),
            sync.REMOTE_ERROR,
        ),
        (subprocess.TimeoutExpired(["ssh"], 60), sync.TIMEOUT),
        (FileNotFoundError("ssh"), sync.SSH_FAILED),
    ],
)
def test_ssh_failures_keep_copy(remote, monkeypatch, outcome, kind):
    path, _ = remote
    assert _sync(path)["ok"] is True
    before = _dump()
    monkeypatch.setenv("OCI_SSH_TARGET", "oci-test")

    def fake_run(cmd, **kw):
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    monkeypatch.setattr(sync.subprocess, "run", fake_run)
    res = sync.sync_once()
    assert res["ok"] is False and res["failure_kind"] == kind
    assert _dump() == before


def test_missing_ssh_target_fails_without_ssh(remote):
    res = sync.sync_once()  # OCI_SSH_TARGET 없음 · subprocess 차단 상태
    assert res["failure_kind"] == sync.SSH_FAILED


def test_logs_never_carry_body(remote, monkeypatch, caplog):
    path, _ = remote
    secret = "비밀본문-노출금지"
    monkeypatch.setenv("OCI_SSH_TARGET", "oci-test")
    bad = _mutate(
        _export(path),
        lambda ls_: _first_row(ls_, "delivery")["row"].update(body_text=secret, x=1),
    )

    def fake_run(cmd, **kw):
        return subprocess.CompletedProcess(
            cmd, 3, stdout=secret.encode(), stderr=secret.encode()
        )

    monkeypatch.setattr(sync.subprocess, "run", fake_run)
    with caplog.at_level(logging.DEBUG):
        assert sync.sync_once()["failure_kind"] == sync.REMOTE_ERROR
        assert sync.sync_once(runner=lambda: bad)["failure_kind"] == sync.INVALID_EXPORT
    assert secret not in caplog.text
    assert caplog.text  # 실패 종류는 남는다


def test_busy_sync_returns_409(client):
    assert sync._LOCK.acquire(blocking=False)
    try:
        assert client.post("/decision-ledger/sync").status_code == 409
    finally:
        sync._LOCK.release()


# ── 목록 · 피드백 (수용 기준 5 · 6) ──────────────────────────────────────────


def test_list_shows_only_sent_and_partial(remote, client):
    path, _ = remote
    assert _sync(path)["ok"] is True
    Path(views.HOLDINGS_FILE).write_text(
        json.dumps(
            {
                "holdings": [
                    {
                        "ticker": "005930",
                        "name": "삼성전자",
                        "quantity": 1,
                        "avg_buy_price": 1,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    body = client.get("/decision-ledger/alerts", params={"date": DAY}).json()
    assert [a["event_id"] for a in body["alerts"]] == ["E2", "E1", "E3", "E7", "E6"]
    by = {a["event_id"]: a for a in body["alerts"]}
    assert by["E3"]["delivery_status"] == "partial"
    assert by["E1"]["time_kst"] == "09:15"
    assert by["E1"]["key_items"][0] == {
        "subject_kind": "ticker",
        "subject_id": "005930",
        "name": "삼성전자",
    }
    assert [k["subject_id"] for k in by["E3"]["key_items"]] == [
        "091160",
        "반도체",
        "BLOCK",
    ]  # sent 만
    assert by["E6"]["off_schedule"] is True
    assert body["sync"]["has_copy"] is True and body["sync"]["last_success_at"]
    only = client.get(
        "/decision-ledger/alerts", params={"date": DAY, "kind": "market"}
    ).json()
    assert [a["event_id"] for a in only["alerts"]] == ["E2"]
    assert (
        client.get("/decision-ledger/alerts", params={"date": "2026-10-09"}).json()[
            "alerts"
        ]
        == []
    )


def test_list_without_copy_reports_no_copy(client):
    body = client.get("/decision-ledger/alerts", params={"date": DAY}).json()
    assert body["sync"] == {
        "has_copy": False,
        "last_success_at": None,
        "last_failure_at": None,
        "last_failure_kind": None,
    }
    assert body["alerts"] == []


def test_feedback_is_append_only_and_limited(remote, client):
    path, _ = remote
    assert _sync(path)["ok"] is True
    url = "/decision-ledger/alerts/{}/feedback"
    assert (
        client.post(url.format("E4"), json={"helpfulness": "HELPFUL"}).status_code
        == 409
    )  # skipped
    assert (
        client.post(url.format("E5"), json={"helpfulness": "HELPFUL"}).status_code
        == 409
    )  # failed
    assert (
        client.post(url.format("E8"), json={"helpfulness": "HELPFUL"}).status_code
        == 409
    )  # STARTED
    assert (
        client.post(url.format("NOPE"), json={"helpfulness": "HELPFUL"}).status_code
        == 404
    )
    assert (
        client.post(url.format("E1"), json={"helpfulness": "GOOD"}).status_code == 422
    )
    assert (
        client.post(
            url.format("E1"), json={"helpfulness": "HELPFUL", "action": "HOLD"}
        ).status_code
        == 422
    )
    assert (
        client.post(
            url.format("E1"), json={"helpfulness": "HELPFUL", "memo": "가" * 501}
        ).status_code
        == 422
    )
    assert _dump()["user_feedback"] == []  # 거부는 행을 남기지 않는다
    a = client.post(
        url.format("E1"), json={"helpfulness": "HELPFUL", "memo": "  "}
    ).json()
    b = client.post(
        url.format("E1"),
        json={
            "helpfulness": "UNHELPFUL_CONFUSING",
            "action": "WATCH_ONLY",
            "memo": "가" * 500,
        },
    ).json()
    c = client.post(
        url.format("E3"), json={"helpfulness": "NEUTRAL"}
    ).json()  # partial 도 대상
    assert (a["feedback_seq"], a["memo"], b["feedback_seq"], c["feedback_seq"]) == (
        1,
        None,
        2,
        1,
    )
    card = {
        x["event_id"]: x
        for x in client.get("/decision-ledger/alerts", params={"date": DAY}).json()[
            "alerts"
        ]
    }["E1"]
    assert (
        card["feedback_count"] == 2
        and card["latest_feedback"]["helpfulness"] == "UNHELPFUL_CONFUSING"
    )
    detail = client.get("/decision-ledger/alerts/E1").json()
    assert [f["feedback_seq"] for f in detail["feedback"]] == [1, 2]  # 이전 행 보존


# ── 가격 결과 · 결과 대상 (수용 기준 7 · 8 · 설계 개정 2) ─────────────────────


def _feedback_count() -> int:
    con = sqlite3.connect(str(store.DEFAULT_DB_PATH))
    try:
        return con.execute("SELECT COUNT(*) FROM user_feedback").fetchone()[0]
    finally:
        con.close()


def test_outcomes_visible_without_feedback(remote, client):
    path, _ = remote
    assert _sync(path)["ok"] is True
    r = client.get("/decision-ledger/alerts/E1")
    assert r.status_code == 200 and r.json()["feedback"] == []
    rows = r.json()["outcomes"]
    assert [
        (o["item_seq"], o["horizon"], o["status"], o["return_raw"]) for o in rows
    ] == [
        (1, 1, "MATURED", 0.0123),
        (1, 5, "PRICE_MISSING", None),
    ]
    assert rows[0]["series_name"] == "005930"
    e3 = client.get("/decision-ledger/alerts/E3").json()["outcomes"]
    assert [o["status"] for o in e3] == ["UNTRACKED_AFTER_EXIT"]
    assert (
        _feedback_count() == 0
    )  # 조회가 feedback 행을 만들지 않는다(무평가 = 평가 없음)


def test_feedback_changes_neither_outcomes_nor_targets(remote, client):
    path, _ = remote
    assert _sync(path)["ok"] is True
    events = ("E1", "E3", "E6", "E7")
    before = {e: client.get(f"/decision-ledger/alerts/{e}").json() for e in events}
    for e in events:
        store.add_feedback(e, helpfulness="UNHELPFUL_CONFUSING")
    for e in events:
        after = client.get(f"/decision-ledger/alerts/{e}").json()
        assert after["outcomes"] == before[e]["outcomes"]
        assert [i["outcome_target"] for i in after["items"]] == [
            i["outcome_target"] for i in before[e]["items"]
        ]


def test_default_date_is_latest_alert_day(remote, client):
    path, con = remote
    # 더 뒤 날짜라도 sent · partial 이 아니면 기본 날짜가 되지 않는다.
    _event(con, "E10", [_item("ticker", "005930")], status="skipped", day="2026-10-09")
    _event(con, "E11", [_item("ticker", "005930")], day="2026-10-06")
    assert _sync(path)["ok"] is True
    body = client.get("/decision-ledger/alerts").json()
    assert body["date"] == DAY and len(body["alerts"]) == 5
    market = client.get("/decision-ledger/alerts", params={"kind": "market"}).json()
    assert market["date"] == DAY  # 전체 종류 기준
    older = client.get("/decision-ledger/alerts", params={"date": "2026-10-06"}).json()
    assert [a["event_id"] for a in older["alerts"]] == ["E11"]  # 고른 날짜는 그대로


def test_default_date_without_copy_is_today(client):
    body = client.get("/decision-ledger/alerts").json()
    assert body["date"] == views.today_kst() and body["alerts"] == []


def test_outcome_target_for_event_and_item(remote):
    path, _ = remote
    assert _sync(path)["ok"] is True
    tgt = {
        eid: [
            (i["subject_kind"], i["outcome_target"])
            for i in views.alert_detail(eid, names={})["items"]
        ]
        for eid in ("E2", "E3", "E6", "E7")
    }
    assert tgt["E2"] == [("market", True), ("index_group", True)]
    assert tgt["E3"] == [
        ("ticker", True),
        ("sector", True),
        ("sector_block", False),  # POC5-02 가 결과를 만들지 않는 subject
        ("ticker", False),  # evaluable 0
        ("ticker", True),
    ]
    assert tgt["E6"] == [("ticker", False)]  # 예정 외 실행
    assert tgt["E7"] == [("ticker", False)]  # LEGACY_DIAGNOSTIC
    assert views.alert_detail("E6", names={})["outcome_event_target"] is False


def test_partial_detail_carries_generated_body(remote, client):
    path, _ = remote
    assert _sync(path)["ok"] is True
    d = client.get("/decision-ledger/alerts/E3").json()
    assert d["delivery_status"] == "partial" and d["body_partial_delivery"] is True
    assert (
        client.get("/decision-ledger/alerts/E1").json()["body_partial_delivery"]
        is False
    )
    assert d["body_text"] == "장중 급등락 전체 본문(분할 전)"
    assert client.get("/decision-ledger/alerts/NOPE").status_code == 404


# ── 경계 (수용 기준 9) ────────────────────────────────────────────────────────


def test_state_labels_follow_alert_kind():
    lab = views.state_label
    assert lab("holdings_risk_alert", "ticker", "D10_PLUS") == "전일 대비 하락 10% 이상"
    assert lab("holdings_briefing", "ticker", "D10_PLUS") == "20거래일 하락 10% 이상"
    assert lab("holdings_risk_alert", "ticker", "U5_7") == "전일 대비 상승 5~7%"
    assert lab("holdings_risk_alert", "sector", "AVOID_DROP") == "장중 급락"
    assert lab("market_briefing", "market", "DOWN") == "DOWN"  # 라벨 없음 = 코드
    assert lab("holdings_briefing", "ticker", None) is None


def test_market_target_is_sp500_only():
    assert views.item_target(True, "market", "SP500", 1) is True
    assert views.item_target(True, "market", "NASDAQ", 1) is False  # POC5-02 와 같음


def test_name_map_tolerates_odd_holdings_file():
    Path(views.HOLDINGS_FILE).write_text('{"holdings": 5}', encoding="utf-8")
    assert views.name_map() == {}


def test_new_modules_have_no_network_or_telegram_imports():
    root = Path(__file__).resolve().parents[1]
    files = [
        *sorted((root / "app" / "ledger_copy").glob("*.py")),
        root / "app" / "api_decision_ledger.py",
    ]
    banned = ("requests", "httpx", "urllib", "telegram", "aiohttp", "socket")
    for f in files:
        tree = ast.parse(f.read_text(encoding="utf-8"))
        mods = [
            *(
                a.name
                for n in ast.walk(tree)
                if isinstance(n, ast.Import)
                for a in n.names
            ),
            *(n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)),
        ]
        assert not [m for m in mods if any(b in m for b in banned)], f
        uses_subprocess = "subprocess" in mods
        assert uses_subprocess == (f.name == "sync.py"), f  # SSH 는 동기화 모듈 한 곳뿐
