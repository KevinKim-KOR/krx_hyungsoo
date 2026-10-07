"""POC5-01B — 러너 `run()` 관통: 원장 켜기 · 끄기 동등성 · 종료 경로 · 실패 주입(설계서 §8 AC).

```text
AC 1 · 2   같은 입력을 원장 끔 · 켬으로 돌린다 → 본문 · record · JSONL · runtime DB 행 · 상태 파일 ·
           부수효과 호출 순서 · 발송 수 · 시세 조회 수가 같다. 끄면 원장 파일 0
AC 3       dry-run · 플래그 없음(PC) · spike = 원장 0
AC 4       sent · skipped · Telegram 실패 · 부분 전송 → run FINALIZED · delivery 상태
AC 5 · 6   조립 예외 · 발송 뒤 mark_sent 예외 · insert_status 예외 → 원장 failed · 같은 예외.
           STARTED · 종료 · 권한 실패 주입 → PUSH 결과 같음 · 원장은 멈추거나 STARTED gap
AC 8       body SHA-256 = 분할 전 본문 · 비밀값이 든 본문은 본문만 보류
```

Telegram 은 대역(stub)만 — 실발송 0. 라이브 state · logs · 운영 DB 미접근(conftest).
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
import traceback
from pathlib import Path

import pytest

from app.three_push_runtime import ledger_context as lc
from app.three_push_runtime import ledger_store as ls
from app.three_push_runtime_message_builder import kst_today_date

RISK = "holdings_risk_alert"
# 실행마다 달라지는 값 — 비교에서 뺀다(시작 · 종료 시각 · 매번 새로 만든 PARAM id 와 그
# id 가 든 중복 키).
VOLATILE = {"started_at", "finished_at", "param_id", "duplicate_key"}


def _enable(monkeypatch):
    monkeypatch.setenv(lc.FLAG_ENV, "true")
    monkeypatch.setattr(lc, "_git_head", lambda: "f" * 40)


def _fresh_runtime(monkeypatch, root: Path) -> None:
    from app import runtime_state_db as rt

    root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(rt, "DEFAULT_DB_PATH", root / "runtime_state.sqlite")
    rt.reset_init_cache_for_testing()


def _ledger(sql: str, *args):
    db = ls.DEFAULT_DB_PATH
    if not db.exists():
        return None
    con = sqlite3.connect(db)
    try:
        return con.execute(sql, args).fetchall()
    finally:
        con.close()


def _strip(rec: dict) -> dict:
    return {k: v for k, v in rec.items() if k not in VOLATILE}


def _order(monkeypatch, runner) -> list[str]:
    calls: list[str] = []

    def _wrap(obj, name):
        orig = getattr(obj, name)

        def _w(*a, **k):
            calls.append(name)
            return orig(*a, **k)

        monkeypatch.setattr(obj, name, _w)

    for name in (
        "telegram_send",
        "mark_sent",
        "save_state",
        "save_risk_state",
        "insert_status_from_record",
    ):
        _wrap(runner, name)
    _wrap(runner._mb, "save_state_after_send")
    return calls


def _norm(value, root: Path):
    """실행 폴더(off · on) 경로를 같은 자리표시로 — rig 의 tmp 경로 차이는 비교 대상이 아니다."""
    text = json.dumps(value, ensure_ascii=False, default=str)
    for r in {str(root), str(root.resolve())}:
        text = text.replace(r, "<ROOT>")
    return json.loads(text)


def _capture(root: Path, rec: dict, bodies: list[str], order: list[str]) -> dict:
    hist = root / "history.jsonl"
    con = sqlite3.connect(root / "runtime_state.sqlite")
    try:
        rt_rows = con.execute(
            "SELECT push_kind, mode, status, reason, runtime_kst, runtime_date_kst,"
            " param_source, message_text_length, availability_available,"
            " availability_unavailable_or_other, telegram_attempted, telegram_sent, error"
            " FROM runtime_execution_status ORDER BY run_id"
        ).fetchall()
    finally:
        con.close()
    return _norm(
        {
            "record": _strip(rec),
            "keys": sorted(rec),
            "bodies": list(bodies),
            "history": [
                _strip(json.loads(line))
                for line in hist.read_text("utf-8").splitlines()
                if line.strip()
            ],
            "runtime_rows": rt_rows,
            # 러너가 쓰는 상태 파일만(배치 상태 fixture 는 생성 시각이 들어 있어 뺀다).
            "state_files": {
                p.name: p.read_text("utf-8")
                for p in sorted(root.rglob("*.json"))
                if "batch" not in p.name and "history" not in p.name
            },
            "order": list(order),
        },
        root,
    )


# ── 시나리오(기존 rig 재사용) ─────────────────────────────────────────────────


def _risk(monkeypatch, root, *, sender=None, hhmm="10:30"):
    from tests import test_holdings_risk_alert_runner as R

    _fresh_runtime(monkeypatch, root)
    R._seed_param()
    runner, send = R._install_runner(monkeypatch, root, sender=sender)
    today = kst_today_date()
    R._install_inputs(
        monkeypatch,
        runner,
        specs=[
            ("102110", "TIGER200", 10000.0, 9200.0),
            ("069500", "KODEX200", 10000.0, 9990.0),
        ],
        quotes_asof=R._asof(today),
    )
    R._tick(monkeypatch, runner, today, hhmm)
    order = _order(monkeypatch, runner)
    return runner, send.calls, order, lambda: runner.run(RISK, "send")


def _market(monkeypatch, root):
    from tests.test_market_briefing_flow_through import TODAY_TRADING, _install

    _fresh_runtime(monkeypatch, root)
    runner, sent, _ = _install(monkeypatch, root)
    # rig 의 오늘(TODAY_TRADING)과 같은 날 08:30 — 실행 날짜에 따라 달라지지 않는다.
    monkeypatch.setattr(
        runner, "kst_now_iso", lambda: f"{TODAY_TRADING}T08:30:02+09:00"
    )
    order = _order(monkeypatch, runner)
    return runner, sent, order, lambda: runner.run("market_briefing", "send")


def _holdings(monkeypatch, root):
    from tests.test_poc3_02d_ops02_regular_push_contract import (
        _holdings_rig,
        _holdings_slot,
    )

    _fresh_runtime(monkeypatch, root)
    runner, sent, _, today = _holdings_rig(monkeypatch, root)
    order = _order(monkeypatch, runner)
    return (
        runner,
        sent,
        order,
        lambda: _holdings_slot(monkeypatch, runner, today, "OPEN", "09:15"),
    )


def _intraday_db(root: Path) -> Path:
    from tests.test_intraday_alert_flow_through import FIXTURE_DAYS

    p = root / "m.sqlite"
    con = sqlite3.connect(p)
    con.execute(
        "CREATE TABLE krx_etf_daily_price_unadjusted(ticker TEXT,date TEXT,close REAL)"
    )
    rows = []
    for i in range(10):
        rows += [(f"T{i:05d}", d, 100.0 + n) for n, d in enumerate(FIXTURE_DAYS)]
    con.executemany("INSERT INTO krx_etf_daily_price_unadjusted VALUES(?,?,?)", rows)
    con.commit()
    con.close()
    return p


def _intraday(monkeypatch, root, *, hold=-6.0):
    from tests import test_intraday_alert_flow_through as ia

    import functools

    import app.runtime_evidence.intraday_alert_flow as iflow

    _fresh_runtime(monkeypatch, root)
    db = _intraday_db(root)
    rig = ia._build_rig(monkeypatch, root, db)
    # `db_path` 기본값은 정의 시점에 운영 경로로 묶여 있다 — 새 테스트는 라이브 DB 읽기
    # 허용 목록에 넣지 않고 tmp DB 를 직접 넘긴다.
    real = getattr(iflow.assemble_intraday_alert, "func", iflow.assemble_intraday_alert)
    monkeypatch.setattr(
        iflow, "assemble_intraday_alert", functools.partial(real, db_path=db)
    )
    ia._hold_and_sectors(rig, hold=hold)
    runner = rig["runner"]
    monkeypatch.setattr(runner, "kst_now_iso", lambda: ia._asof(ia.TODAY))
    order = _order(monkeypatch, runner)
    rig["order"] = order
    return runner, rig["sent"].calls, order, lambda: runner.run(RISK, "send"), rig


SCENARIOS = {"risk": _risk, "market": _market, "holdings": _holdings}


def _same(off: dict, on: dict) -> None:
    """항목별로 비교해 다른 키를 그대로 보여 준다."""
    for part in off:
        a, b = off[part], on[part]
        if isinstance(a, dict) and isinstance(b, dict):
            diff = {
                k: (a.get(k), b.get(k)) for k in set(a) | set(b) if a.get(k) != b.get(k)
            }
            assert not diff, (part, diff)
        else:
            assert a == b, (part, a, b)


def _off_on(monkeypatch, tmp_path, build):
    runner, bodies, order, go = build(monkeypatch, tmp_path / "off")[:4]
    off = _capture(tmp_path / "off", go(), bodies, order)
    assert _ledger("SELECT 1") is None  # 끄면 원장 파일 0
    _enable(monkeypatch)
    runner, bodies, order, go = build(monkeypatch, tmp_path / "on")[:4]
    on = _capture(tmp_path / "on", go(), bodies, order)
    return off, on


# ── AC 1 · 2 동등성 ───────────────────────────────────────────────────────────


@pytest.mark.parametrize("kind", sorted(SCENARIOS))
def test_ledger_on_off_keeps_body_record_history_db_state_and_order(
    monkeypatch, tmp_path, kind
):
    off, on = _off_on(monkeypatch, tmp_path, SCENARIOS[kind])
    _same(off, on)
    assert on["record"]["status"] == "sent" and len(on["bodies"]) == 1
    runs = _ledger("SELECT run_state, status, push_kind FROM evaluation_run")
    assert runs is not None and len(runs) == 1 and runs[0][:2] == ("FINALIZED", "sent")
    status, sha, body, chunks = _ledger(
        "SELECT delivery_status, body_sha256, body_text, planned_chunk_count FROM delivery"
    )[0]
    assert status == "sent" and chunks == 1
    assert body == on["bodies"][0]
    assert sha == hashlib.sha256(on["bodies"][0].encode("utf-8")).hexdigest()
    assert _ledger("SELECT COUNT(*) FROM signal_item")[0][0] >= 1


def test_intraday_sectors_same_lookups_and_items_recorded(monkeypatch, tmp_path):
    off_rig = _intraday(monkeypatch, tmp_path / "off")
    off = _capture(tmp_path / "off", off_rig[3](), off_rig[1], off_rig[2])
    off_calls = list(off_rig[4]["naver_calls"])
    _enable(monkeypatch)
    on_rig = _intraday(monkeypatch, tmp_path / "on")
    on = _capture(tmp_path / "on", on_rig[3](), on_rig[1], on_rig[2])
    assert off == on
    assert on_rig[4]["naver_calls"] == off_calls  # 시세 조회 수 · 순서 같음(재조회 0)
    rows = _ledger(
        "SELECT subject_kind, subject_id, state, disposition FROM signal_item"
        " ORDER BY item_seq"
    )
    kinds = {r[0] for r in rows}
    assert kinds == {"ticker", "sector"}
    assert len([r for r in rows if r[0] == "sector"]) == 10
    assert any(r[3] == "sent" for r in rows if r[0] == "sector")
    cfg = _ledger("SELECT config_version_id, tick FROM evaluation_run")[0]
    assert cfg == ("v1", "10:30")


def test_surge_selection_exception_is_unevaluable_and_keeps_records(
    monkeypatch, tmp_path
):
    """검증자 r1 A-1 — 급등 선정 예외 회차: 기존 기록은 끔 · 켬 같고, 원장 '상태 없음' 행은 평가 불가."""
    import app.runtime_evidence.intraday_alert_flow as iflow

    def _boom(**_kw):
        raise RuntimeError("surge bug")

    off_rig = _intraday(monkeypatch, tmp_path / "off", hold=6.0)  # 급등 구간 보유
    monkeypatch.setattr(iflow, "select_surge_holdings", _boom)
    off = _capture(tmp_path / "off", off_rig[3](), off_rig[1], off_rig[2])
    _enable(monkeypatch)
    on_rig = _intraday(monkeypatch, tmp_path / "on", hold=6.0)
    monkeypatch.setattr(iflow, "select_surge_holdings", _boom)
    on = _capture(tmp_path / "on", on_rig[3](), on_rig[1], on_rig[2])
    assert off == on  # surge_error 는 record · JSONL · 상태 파일에 들어가지 않는다
    rows = _ledger(
        "SELECT state, evaluable FROM signal_item WHERE subject_kind = 'ticker'"
    )
    assert any(st is None for st, _ in rows)
    assert all(ev == 0 for st, ev in rows if st is None)


def _ledger_frames(ei) -> int:
    return sum(
        1
        for f in traceback.extract_tb(ei.tb)
        if f.filename.endswith("ledger_context.py")
    )


@pytest.mark.parametrize(
    "enable, target, expected",
    [
        (False, "insert_status_from_record", 1),  # 경계만(비활성은 감싸지 않음)
        (True, "insert_status_from_record", 2),  # 경계 + wrap_insert_status
        (False, "assemble_push_kind", 1),
        (True, "assemble_push_kind", 1),
    ],
)
def test_traceback_frames_added_by_ledger(
    monkeypatch, tmp_path, enable, target, expected
):
    """검증자 r1 A-2 — run() 밖 예외의 traceback 에 원장 모듈 frame 이 몇 개 더해지는가."""
    if enable:
        _enable(monkeypatch)
    runner, _, _, go = _risk(monkeypatch, tmp_path)
    monkeypatch.setattr(
        runner, target, lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x"))
    )
    with pytest.raises(RuntimeError) as ei:
        go()
    assert _ledger_frames(ei) == expected


# ── AC 3 · 0행 ───────────────────────────────────────────────────────────────


def test_dry_run_pc_and_spike_write_nothing(monkeypatch, tmp_path):
    runner, _, _, _ = _risk(monkeypatch, tmp_path / "pc")
    assert runner.run(RISK, "send")["status"] == "sent"  # 플래그 없음(PC)
    assert _ledger("SELECT 1") is None
    _enable(monkeypatch)
    runner, _, _, _ = _risk(monkeypatch, tmp_path / "dry")
    assert runner.run(RISK, "dry-run")["status"] == "dry_run_success"
    runner.run("spike_or_falling_alert", "send")
    assert _ledger("SELECT 1") is None


# ── AC 4 · 종료 경로 ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "sender_kw, status, delivery",
    [
        ({"sent": False}, "failed", "failed"),
        ({"partial": True, "sent": False}, "failed", "partial"),
    ],
)
def test_send_failure_and_partial_are_finalized(
    monkeypatch, tmp_path, sender_kw, status, delivery
):
    from tests.test_holdings_risk_alert_runner import _Sender

    _enable(monkeypatch)
    runner, bodies, _, go = _risk(monkeypatch, tmp_path, sender=_Sender(**sender_kw))
    assert go()["status"] == status
    assert _ledger("SELECT run_state, status FROM evaluation_run") == [
        ("FINALIZED", status)
    ]
    assert _ledger("SELECT delivery_status FROM delivery") == [(delivery,)]


def test_skip_runs_are_finalized_with_items_and_skipped_delivery(monkeypatch, tmp_path):
    _enable(monkeypatch)
    runner, _, _, go = _risk(monkeypatch, tmp_path)
    monkeypatch.setenv("PUSH_AUTOSEND_ENABLED", "false")
    rec = go()
    assert (rec["status"], rec["reason"]) == ("skipped", "autosend_disabled")
    assert _ledger("SELECT run_state, reason FROM evaluation_run") == [
        ("FINALIZED", "autosend_disabled")
    ]
    assert _ledger("SELECT delivery_status, body_text FROM delivery") == [
        ("skipped", None)
    ]
    # 조립은 flag guard 앞이라 평가 항목은 남는다(관측 모집단).
    assert _ledger("SELECT COUNT(*) FROM signal_item")[0][0] == 2


# ── AC 5 · 6 · 예외 · 실패 주입 ───────────────────────────────────────────────


def _raises_same(monkeypatch, tmp_path, patch):
    """끔 · 켬에서 같은 예외(종류 · 메시지)가 그대로 올라오는지."""
    out = []
    for name, enable in (("off", False), ("on", True)):
        if enable:
            _enable(monkeypatch)
        runner, _, _, go = _risk(monkeypatch, tmp_path / name)
        patch(monkeypatch, runner)
        with pytest.raises(BaseException) as ei:
            go()
        out.append((type(ei.value), str(ei.value)))
    assert out[0] == out[1]
    return out[1]


def test_assembly_exception_is_finalized_failed_and_reraised(monkeypatch, tmp_path):
    def _patch(mp, runner):
        mp.setattr(
            runner,
            "assemble_push_kind",
            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("assemble bug")),
        )

    assert _raises_same(monkeypatch, tmp_path, _patch) == (RuntimeError, "assemble bug")
    assert _ledger("SELECT run_state, status, reason, error FROM evaluation_run") == [
        ("FINALIZED", "failed", "uncaught_exception", "RuntimeError")
    ]
    assert _ledger("SELECT delivery_status FROM delivery") == [("skipped",)]
    assert _ledger("SELECT COUNT(*) FROM signal_item") == [(0,)]


def test_mark_sent_exception_after_send_keeps_delivery_sent(monkeypatch, tmp_path):
    def _patch(mp, runner):
        mp.setattr(
            runner,
            "mark_sent",
            lambda *a, **k: (_ for _ in ()).throw(OSError("registry down")),
        )

    assert _raises_same(monkeypatch, tmp_path, _patch) == (OSError, "registry down")
    assert _ledger("SELECT run_state, status FROM evaluation_run") == [
        ("FINALIZED", "failed")
    ]
    assert _ledger("SELECT delivery_status FROM delivery") == [("sent",)]
    assert _ledger("SELECT COUNT(*) FROM signal_item")[0][0] == 2


def test_insert_status_exception_is_ledger_only_failed(monkeypatch, tmp_path):
    def _patch(mp, runner):
        mp.setattr(
            runner,
            "insert_status_from_record",
            lambda r: (_ for _ in ()).throw(sqlite3.OperationalError("locked")),
        )

    assert _raises_same(monkeypatch, tmp_path, _patch)[0] is sqlite3.OperationalError
    assert _ledger("SELECT status, run_id FROM evaluation_run") == [("failed", None)]


@pytest.mark.parametrize(
    "target, expected_runs",
    [
        ("insert_started", []),  # STARTED 를 못 쓰면 그 실행은 원장 쓰기 중단(고아 0)
        ("finalize", [("STARTED",)]),  # 종료를 못 쓰면 STARTED gap
    ],
)
def test_ledger_write_failure_does_not_change_push(
    monkeypatch, tmp_path, target, expected_runs
):
    runner, _, _, go = _risk(monkeypatch, tmp_path / "off")
    off = _capture(tmp_path / "off", go(), [], [])
    _enable(monkeypatch)
    monkeypatch.setattr(
        ls, target, lambda *a, **k: (_ for _ in ()).throw(sqlite3.OperationalError("x"))
    )
    runner, _, _, go = _risk(monkeypatch, tmp_path / "on")
    on = _capture(tmp_path / "on", go(), [], [])
    assert off == on
    assert _ledger("SELECT run_state FROM evaluation_run") == expected_runs


def test_permission_failure_stops_ledger_but_not_push(monkeypatch, tmp_path):
    """보정 1 — 0700/0600 을 확인하지 못하면 그 실행의 원장 쓰기를 멈춘다."""
    _enable(monkeypatch)

    def _deny(path, mode):
        raise ls.LedgerUnavailable("mode:0o755")

    monkeypatch.setattr(ls, "_secure", _deny)
    runner, bodies, _, go = _risk(monkeypatch, tmp_path)
    assert go()["status"] == "sent" and len(bodies) == 1
    assert not ls.DEFAULT_DB_PATH.exists()


def test_main_exit_code_same_with_ledger(monkeypatch, tmp_path):
    codes = []
    for name, enable in (("off", False), ("on", True)):
        if enable:
            _enable(monkeypatch)
        runner, _, _, _ = _risk(monkeypatch, tmp_path / name)
        monkeypatch.setattr(sys, "argv", ["run", "--push-kind", RISK, "--mode", "send"])
        with pytest.raises(SystemExit) as ei:
            runner.main()
        codes.append(ei.value.code)
    assert codes == [0, 0]


# ── AC 8 · 비밀값 ─────────────────────────────────────────────────────────────


def test_secret_in_body_withholds_body_but_keeps_sha(monkeypatch, tmp_path):
    _enable(monkeypatch)
    runner, bodies, _, go = _risk(monkeypatch, tmp_path)
    monkeypatch.setenv(
        "TELEGRAM_CHAT_ID", "TIGER200"
    )  # 본문에 든 문자열을 비밀값으로 둔다
    assert go()["status"] == "sent"
    body, sha, withheld = _ledger(
        "SELECT body_text, body_sha256, body_withheld FROM delivery"
    )[0]
    assert body is None and withheld == 1
    assert sha == hashlib.sha256(bodies[0].encode("utf-8")).hexdigest()


def test_run_row_carries_contract_schedule_and_cohort(monkeypatch, tmp_path):
    _enable(monkeypatch)
    runner, _, _, go = _risk(monkeypatch, tmp_path)
    rec = go()
    row = _ledger(
        "SELECT contract_version, tick, off_schedule, schedule_expected, cohort,"
        " input_basis_date, param_id, started_at FROM evaluation_run"
    )[0]
    off, expected = lc.schedule_for(RISK, rec["runtime_kst"], None)
    assert row[0] == "holdings_risk_alert.v1" and row[1] == "10:30"
    assert (row[2], row[3]) == (off, expected)
    assert row[4] in ("PRIMARY_LIVE", "LEGACY_DIAGNOSTIC")
    assert row[5] == rec["runtime_date_kst"] and row[6] == rec["param_id"]
    assert row[7] == rec["started_at"]  # 기존 기록과 대조하는 키
    assert _ledger("SELECT value FROM ledger_meta WHERE key='deploy_commit'") == [
        ("f" * 40,)
    ]


def test_market_run_carries_tags_and_primary_cohort(monkeypatch, tmp_path):
    """Q14 · Q-H 태그 키 · 평일 첫 예정 회차 = PRIMARY_LIVE 시작일(Q-D)."""
    from tests.test_market_briefing_flow_through import TODAY_TRADING

    _enable(monkeypatch)
    _, _, _, go = _market(monkeypatch, tmp_path)
    assert go()["status"] == "sent"
    tags, cohort, off, day = _ledger(
        "SELECT tags_json, cohort, off_schedule, runtime_date_kst FROM evaluation_run"
    )[0]
    assert json.loads(tags) == {
        "outlook_state": "UP",
        "flat_or_none": False,
        "input_delay": None,  # rig 의 미국 입력 대역은 점검 결과를 남기지 않는다
        "index_status": "ok",
        "batch_failure_reasons": [],
        "same_us_session": None,  # 첫 시장 run — 직전 없음
        "after_kr_market_closure": False,
    }
    assert (cohort, off, day) == ("PRIMARY_LIVE", 0, TODAY_TRADING)
    assert _ledger("SELECT value FROM ledger_meta WHERE key='primary_start_date'") == [
        (TODAY_TRADING,)
    ]


def test_market_preflight_failure_has_no_tags_or_items(monkeypatch, tmp_path):
    """조립 전에 끝난 run — 평가가 없으니 태그 · 항목을 만들지 않는다(logic-5)."""
    _enable(monkeypatch)
    runner, bodies, _, go = _market(monkeypatch, tmp_path)
    monkeypatch.setattr(
        runner,
        "load_param_and_check_slot",
        lambda record, **_kw: (None, ("failed", "active_param_missing", None)),
    )
    rec = go()
    assert (rec["status"], rec["reason"]) == ("failed", "active_param_missing")
    assert bodies == []
    assert _ledger(
        "SELECT run_state, status, reason, tags_json FROM evaluation_run"
    ) == [("FINALIZED", "failed", "active_param_missing", None)]
    assert _ledger("SELECT COUNT(*) FROM signal_item") == [(0,)]


def test_off_schedule_first_run_is_legacy_and_sets_no_primary_start(
    monkeypatch, tmp_path
):
    """수동(예정 밖) 실행은 PRIMARY 시작일을 정하지 않고 LEGACY_DIAGNOSTIC 이다(Q11 · Q28)."""
    _enable(monkeypatch)
    _, _, _, go = _risk(monkeypatch, tmp_path, hhmm="10:47")
    go()
    assert _ledger("SELECT off_schedule, cohort FROM evaluation_run") == [
        (1, "LEGACY_DIAGNOSTIC")
    ]
    assert _ledger("SELECT value FROM ledger_meta WHERE key='primary_start_date'") == []
