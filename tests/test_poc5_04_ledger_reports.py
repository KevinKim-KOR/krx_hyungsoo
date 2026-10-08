"""POC5-04 — R0 수집 점검 · R1 원시 결과 리포트(tmp 원장 · tmp 캘린더 · 고정 fixture · 라이브 DB 0).

설계 개정 1 §8 수용 기준 · PLAN §3.
"""

from __future__ import annotations

import ast
import hashlib
import json
import sqlite3
from datetime import date, timedelta
from pathlib import Path

import pytest

from app.ledger_copy import store as pc_store
from app.ledger_reports import bootstrap, dates, evidence, r0, r1, render
from app.ledger_reports.source import load_snapshot
from app.three_push_runtime import ledger_outcome as lo
from app.three_push_runtime import ledger_store as ls

START = "2026-10-08"
FIRST = "2026-10-07T23:30:02.273319+00:00"
SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_ledger_report.py"


# ── fixture ──────────────────────────────────────────────────────────────────


@pytest.fixture
def cal(tmp_path):
    d = tmp_path / "market_meta"
    d.mkdir()
    days, x = [], date(2026, 1, 1)
    while x.year == 2026:
        if x.weekday() < 5 and x.isoformat() != "2026-10-09":
            days.append(x.isoformat())
        x += timedelta(days=1)
    (d / "krx_trading_days_2026.csv").write_text(
        "date,source\n" + "\n".join(f"{v},TEST" for v in days) + "\n", encoding="utf-8"
    )
    return dates.calendar(d)


@pytest.fixture
def ledger(tmp_path):
    p = tmp_path / "pc" / "decision_evidence.sqlite"
    con = ls.connect(p)
    ls.meta_put_once(con, "primary_start_date", START)
    ls.meta_put_once(con, "first_active_at", FIRST)
    for stmt in lo.DDL:
        con.execute(stmt)
    con.commit()
    pc_store.connect(p).close()  # PC 전용 표(user_feedback · ledger_sync_attempt)
    yield p, con
    con.close()


def _item(
    kind="ticker",
    sid="005930",
    *,
    disp="sent",
    exposure="PRIMARY",
    state="D5_8",
    values=None,
    evaluable=1,
):
    return {
        "subject_kind": kind,
        "subject_id": sid,
        "held": 1,
        "state": state,
        "prev_state": None,
        "disposition": disp,
        "event_type": None,
        "exposure": exposure,
        "values_json": json.dumps(values or {}),
        "t0_price": 100.0,
        "t0_price_asof": "x",
        "evaluable": evaluable,
    }


def _run(
    con,
    eid,
    day,
    kind,
    hhmm,
    items=(),
    *,
    status="sent",
    delivery="sent",
    cohort="PRIMARY_LIVE",
    off=0,
    finalize=True,
):
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
    if not finalize:
        return
    ls.finalize(
        con,
        eid,
        {"status": status, "cohort": cohort, "contract_version": f"{kind}.v1"},
        lambda _c: [dict(i) for i in items],
        {
            "delivery_status": delivery,
            "telegram_sent": 1,
            "body_text": "b",
            "body_sha256": "h",
        },
    )


def _outcome(
    con,
    eid,
    seq,
    series,
    h,
    status="MATURED",
    ret=None,
    up=None,
    down=None,
    basis="KRX_ETF_UNADJUSTED|X",
):
    con.execute(
        "INSERT INTO price_outcome (event_id, item_seq, series_id, horizon, status, return_raw,"
        " max_up_raw, max_down_raw, price_basis, computed_at) VALUES (?,?,?,?,?,?,?,?,?, 'c')",
        (eid, seq, series, h, status, ret, up, down, basis),
    )
    con.commit()


def _sync(path, at):
    c = sqlite3.connect(str(path))
    with c:
        c.execute(
            "INSERT INTO ledger_sync_attempt (attempted_at, ok) VALUES (?, 1)", (at,)
        )
    c.close()


def _full_days(con, cal, n):
    """n 거래일 × 11 예정 슬롯 실행(item 없음)."""
    days = cal.days_from(START, n)
    for d in days:
        for kind, hhmm in r0.expected_slots():
            _run(con, f"{d}-{kind}-{hhmm}", d, kind, hhmm)
    return days


RECON_OK = (
    "captured_at=2026-10-23T09:35:00+09:00\nstatus=OK floor="
    + FIRST
    + "\nok=110 missing_in_ledger=0 started_gap=0 ledger_only=0\n"
)
OPS_OK = (
    "price_batch_price_date=2026-10-22\n"
    "price_batch_status=success\n"
    "price_batch_completed_at=2026-10-23T09:20:05+09:00\n"
    "ops_error_count=0\n"
    "메모: 원장 오류 0\n"
)


def _r0(path, cal, end, recon=RECON_OK, ops=OPS_OK):
    return r0.build(
        load_snapshot(path),
        cal,
        end=end,
        reconcile_text=recon,
        ops_text=ops,
        generated_at="t",
    )


def _sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


# ── R0 ───────────────────────────────────────────────────────────────────────


def test_r0_collection_ok_after_ten_days(ledger, cal):
    path, con = ledger
    days = _full_days(con, cal, 10)
    assert days[-1] == "2026-10-22"
    _sync(path, "2026-10-23T09:31:00+09:00")
    rep = _r0(path, cal, "2026-10-22")
    assert rep["verdict"] == "COLLECTION_OK", (
        rep["not_ready_reasons"],
        rep["problems"],
    )
    assert rep["window"]["d10"] == "2026-10-22" and rep["window"]["trading_days"] == 10
    assert (
        rep["schedule"]["expected"] == 110 and rep["schedule"]["missing"]["count"] == 0
    )
    assert rep["reconciliation"]["state"] == "OK"


def test_r0_not_ready_before_ten_days(ledger, cal):
    path, con = ledger
    _full_days(con, cal, 3)
    _sync(path, "2026-10-14T09:31:00+09:00")
    ops = OPS_OK.replace("2026-10-22", "2026-10-13").replace(
        "2026-10-23T09:20", "2026-10-14T09:20"
    )
    rep = _r0(path, cal, "2026-10-13", ops=ops)
    assert rep["verdict"] == "NOT_READY"
    assert any("10일 미만" in x for x in rep["not_ready_reasons"])


def test_r0_time_passing_alone_is_not_batch_completion(ledger, cal):
    path, con = ledger
    _full_days(con, cal, 10)
    _sync(path, "2026-10-23T11:00:00+09:00")  # 09:30 은 지났지만 배치 완료 근거가 없다
    assert _r0(path, cal, "2026-10-22", ops=None)["verdict"] == "NOT_READY"
    early = _r0(path, cal, "2026-10-22", ops=OPS_OK.replace("09:20:05", "11:30:00"))
    assert early["verdict"] == "NOT_READY"  # 사본이 배치 완료 전에 동기화됐다
    assert early["ops"]["reason"] == "PC 사본이 배치 완료 뒤에 동기화되지 않음"
    failed = _r0(path, cal, "2026-10-22", ops=OPS_OK.replace("success", "failed"))
    assert failed["verdict"] == "NOT_READY"


def test_r0_reconcile_errors_are_check_required_even_if_status_not_ok(ledger, cal):
    path, con = ledger
    _full_days(con, cal, 10)
    _sync(path, "2026-10-23T09:31:00+09:00")
    bad = (
        RECON_OK.replace("missing_in_ledger=0", "missing_in_ledger=2")
        + "missing_in_ledger_ids=41,42\n"
    )
    rep = _r0(path, cal, "2026-10-22", recon=bad.replace("status=OK", "status=FAILED"))
    assert rep["verdict"] == "CHECK_REQUIRED"
    assert rep["reconciliation"]["state"] == "ERRORS"
    assert rep["reconciliation"]["ids"]["missing_in_ledger"] == ["41", "42"]


@pytest.mark.parametrize(
    "recon, reason",
    [
        (None, "대조 근거 없음"),
        (
            "captured_at=2026-10-23T09:35:00+09:00\nstatus=FAILED error_class=OperationalError\n",
            "분류 건수 줄을 읽을 수 없음",
        ),
        (
            RECON_OK.replace(FIRST, "2026-10-01T00:00:00+00:00"),
            "floor 가 원장 first_active_at 과 다름",
        ),
        (
            RECON_OK.replace("2026-10-23T09:35", "2026-10-22T15:00"),
            "기간이 종료일을 덮지 못함",
        ),
    ],
)
def test_r0_unusable_reconcile_is_not_checked(ledger, cal, recon, reason):
    path, con = ledger
    _full_days(con, cal, 10)
    _sync(path, "2026-10-23T09:31:00+09:00")
    rep = _r0(path, cal, "2026-10-22", recon=recon)
    assert rep["verdict"] == "NOT_READY"
    assert rep["reconciliation"]["state"] == "NOT_CHECKED"
    assert reason in rep["reconciliation"]["reason"]


def test_r0_wider_cumulative_period_is_accepted(ledger, cal):
    path, con = ledger
    _full_days(con, cal, 10)
    _sync(path, "2026-10-23T09:31:00+09:00")
    wide = RECON_OK.replace("2026-10-23T09:35", "2026-10-27T10:00")
    rep = _r0(path, cal, "2026-10-22", recon=wide)
    assert (
        rep["verdict"] == "COLLECTION_OK"
        and rep["reconciliation"]["includes_after_end"] is True
    )


def test_r0_missing_slot_started_and_orphans_are_check_required(ledger, cal):
    path, con = ledger
    _full_days(con, cal, 10)
    con.execute(
        "DELETE FROM delivery WHERE event_id = ?", ("2026-10-12-market_briefing-08:30",)
    )
    con.execute(
        "DELETE FROM evaluation_run WHERE event_id = ?",
        ("2026-10-13-holdings_briefing-12:30",),
    )
    con.execute(
        "INSERT INTO price_outcome (event_id, item_seq, series_id, horizon, status, computed_at)"
        " VALUES ('ghost', 1, 's', 1, 'MATURED', 'c')"
    )
    con.commit()
    _run(
        con,
        "stuck",
        "2026-10-15",
        "holdings_risk_alert",
        "13:31",
        off=1,
        finalize=False,
    )
    _sync(path, "2026-10-23T09:31:00+09:00")
    rep = _r0(path, cal, "2026-10-22")
    assert rep["verdict"] == "CHECK_REQUIRED"
    assert rep["schedule"]["missing"]["keys"] == ["2026-10-13 holdings_briefing 12:30"]
    assert rep["integrity"]["finalized_without_delivery"]["keys"] == [
        "2026-10-12-market_briefing-08:30"
    ]
    assert rep["integrity"]["orphan_outcomes"]["keys"] == ["ghost#1"]
    assert rep["integrity"]["started_in_window"]["keys"] == ["stuck"]
    assert rep["schedule"]["off_schedule_runs"] == 1


def test_r0_skipped_and_non_trading_runs_are_records_not_errors(ledger, cal):
    path, con = ledger
    _full_days(con, cal, 10)
    con.execute(
        "UPDATE evaluation_run SET status = 'skipped' WHERE event_id = ?",
        ("2026-10-14-holdings_risk_alert-15:20",),
    )
    con.commit()
    _run(
        con,
        "holiday",
        "2026-10-09",
        "market_briefing",
        "08:30",
        status="skipped",
        delivery="skipped",
    )
    _sync(path, "2026-10-23T09:31:00+09:00")
    rep = _r0(path, cal, "2026-10-22")
    assert rep["verdict"] == "COLLECTION_OK"
    assert rep["schedule"]["non_trading_day_runs"] == 1
    assert rep["schedule"]["status_by_kind"]["holdings_risk_alert"]["skipped"] == 1


def test_r0_pending_split_not_due_and_due(ledger, cal):
    path, con = ledger
    grp = _item(
        "index_group",
        "KODEX|반도체",
        exposure=None,
        state=None,
        values={"tickers": ["A", "B"]},
    )
    _run(
        con,
        "M",
        START,
        "market_briefing",
        "08:30",
        [_item("market", "SP500", exposure=None, state="DOWN"), grp],
    )
    _outcome(con, "M", 1, "benchmark:KOSPI", 1, ret=0.01)
    _sync(path, "2026-10-13T09:31:00+09:00")
    out = _r0(path, cal, "2026-10-12")["outcomes"]
    assert (
        out["expected_slots"] == 3 + 3 * 2
    )  # index_group = ticker 마다 · item × 3 아님
    assert out["by_status"] == {"MATURED": 1}
    # +1 평가일 10-08 · 10-08 ≤ 종료일 → 도래 · +5(10-15) · +20(11-05) → 미도래
    assert out["pending_due"] == 2 and out["pending_not_due"] == 6
    assert "원인 미확인" in out["pending_due_note"]


# ── R1 ───────────────────────────────────────────────────────────────────────


def _r1(path, cal, end="2026-10-30", **kw):
    return r1.build(load_snapshot(path), cal, end=end, generated_at="t", **kw)


def _groups(rep, **match):
    return [g for g in rep["groups"] if all(g[k] == v for k, v in match.items())]


def test_r1_three_exposure_tables_and_none_kept(ledger, cal):
    path, con = ledger
    _run(
        con,
        "M",
        START,
        "market_briefing",
        "08:30",
        [_item("market", "SP500", exposure=None, state="DOWN")],
    )
    _run(
        con,
        "H",
        START,
        "holdings_briefing",
        "09:15",
        [
            _item(exposure="PRIMARY"),
            _item(sid="069500", disp="not_selected", exposure=None, state=None),
        ],
    )
    _run(
        con,
        "R",
        START,
        "holdings_risk_alert",
        "10:30",
        [_item(exposure="SECONDARY", state="D5_7")],
    )
    rep = _r1(path, cal)
    assert {g["exposure"] for g in rep["groups"]} == {"PRIMARY", "SECONDARY", "NONE"}
    none = _groups(rep, exposure="NONE", view="observed", horizon=1)
    assert {(g["subject_kind"], g["state"]) for g in none} == {
        ("market", "DOWN"),
        ("ticker", "—"),
    }
    assert all(
        g["exposure_label"] == "노출 분류 없음" for g in _groups(rep, exposure="NONE")
    )
    assert rep["population"]["items"] == 4


def test_r1_denominators_delivered_partial_and_exclusions(ledger, cal):
    path, con = ledger
    _run(
        con,
        "S",
        START,
        "holdings_briefing",
        "09:15",
        [_item(), _item(sid="A", disp="suppressed", exposure="SECONDARY")],
    )
    _run(
        con,
        "P",
        START,
        "holdings_risk_alert",
        "09:30",
        [_item(sid="B")],
        delivery="partial",
    )
    _run(
        con,
        "L",
        "2026-10-07",  # LEGACY = 시작일 전 실행(01B 규칙 · 실제로 생기는 모양)
        "holdings_briefing",
        "12:30",
        [_item(sid="C")],
        cohort="LEGACY_DIAGNOSTIC",
    )
    _run(con, "O", START, "holdings_risk_alert", "13:05", [_item(sid="D")], off=1)
    _run(
        con,
        "E",
        START,
        "holdings_risk_alert",
        "13:30",
        [_item(sid="F", evaluable=0), _item("sector_block", "BLOCK")],
    )
    _run(
        con,
        "N",
        START,
        "market_briefing",
        "08:30",
        [_item("market", "NASDAQ", exposure=None)],
    )
    rep = _r1(path, cal)
    pop = rep["population"]
    assert pop["items"] == 3 and pop["partial_sent_items"] == 1
    assert pop["exclusions"] == {
        "before_primary_start": 1,
        "evaluable_0": 1,
        "market_not_sp500": 1,
        "off_schedule": 1,
        "subject_not_outcome_target": 1,
    }
    delivered = _groups(rep, view="delivered", horizon=1)
    # S 의 sent item 만 '전달' · suppressed 와 partial(P) 은 관측에만
    assert sum(g["pending_due"] + g["pending_not_due"] for g in delivered) == 1
    observed = _groups(rep, view="observed", horizon=1)
    assert sum(g["pending_due"] + g["pending_not_due"] for g in observed) == 3


def test_r1_known_values_and_multi_ticker_counts(ledger, cal):
    path, con = ledger
    grp = _item(
        "index_group",
        "G",
        exposure=None,
        state=None,
        values={"tickers": ["A", "B", "C"]},
    )
    _run(con, "M", START, "market_briefing", "08:30", [grp])
    for t, ret, up, down in (
        ("A", 0.01, 0.02, -0.01),
        ("B", 0.03, 0.05, -0.02),
        ("C", -0.02, 0.01, -0.04),
    ):
        _outcome(con, "M", 1, f"krx_etf:{t}", 1, ret=ret, up=up, down=down)
    rep = _r1(path, cal)
    (g,) = _groups(rep, view="observed", horizon=1, price_basis="KRX_ETF_UNADJUSTED|X")
    assert g["n_matured"] == 3 and g["n_price_observation"] == 3
    assert (g["n_event"], g["n_item"], g["n_signal_date"]) == (
        1,
        1,
        1,
    )  # ticker 3개 ≠ 알림 3개
    assert g["mean"] == pytest.approx(0.02 / 3)
    assert g["median"] == pytest.approx(0.01)
    assert g["q25"] == pytest.approx(-0.005) and g["q75"] == pytest.approx(0.02)
    assert (g["min"], g["max"]) == (pytest.approx(-0.02), pytest.approx(0.03))
    assert g["max_up_median"] == pytest.approx(0.02) and g[
        "max_down_median"
    ] == pytest.approx(-0.02)
    assert (
        g["bootstrap"]["status"] == "INSUFFICIENT_SAMPLE"
        and g["bootstrap"]["low"] is None
    )


def test_r1_zero_and_single_observation(ledger, cal):
    path, con = ledger
    _run(con, "H", START, "holdings_briefing", "09:15", [_item()])
    rep = _r1(path, cal)
    (pend,) = _groups(rep, view="observed", horizon=1)
    assert pend["n_matured"] == 0 and pend["mean"] is None and pend["median"] is None
    _outcome(con, "H", 1, "krx_etf:005930", 1, ret=0.042)
    (one,) = _groups(
        _r1(path, cal), view="observed", horizon=1, price_basis="KRX_ETF_UNADJUSTED|X"
    )
    assert (
        one["mean"] == one["median"] == one["q25"] == one["min"] == pytest.approx(0.042)
    )


def test_r1_feedback_changes_digest_not_statistics(ledger, cal):
    path, con = ledger
    days = cal.days_from(START, 12)
    for n, d in enumerate(days):
        _run(con, f"H{n}", d, "holdings_briefing", "09:15", [_item()])
        _outcome(con, f"H{n}", 1, "krx_etf:005930", 1, ret=0.001 * (n - 5))
    before = _r1(path, cal, iterations=200)
    pc_store.add_feedback("H3", helpfulness="UNHELPFUL_CONFUSING", path=path)
    pc_store.add_feedback("H3", helpfulness="HELPFUL", path=path)
    rows_before = (
        sqlite3.connect(str(path))
        .execute("SELECT COUNT(*) FROM user_feedback")
        .fetchone()[0]
    )
    after = _r1(path, cal, iterations=200)
    assert after["input"]["digest"] != before["input"]["digest"]
    assert after["groups"] == before["groups"]  # 표본 · 통계 · bootstrap 동일
    assert after["feedback"]["events_with_feedback"] == 1
    assert after["feedback"]["latest_helpfulness"] == {
        "HELPFUL": 1
    }  # 같은 event 반복 평가 = 1
    assert (
        sqlite3.connect(str(path))
        .execute("SELECT COUNT(*) FROM user_feedback")
        .fetchone()[0]
        == rows_before
    )


def test_r1_same_input_same_seed_is_identical(ledger, cal):
    path, con = ledger
    for n, d in enumerate(cal.days_from(START, 12)):
        _run(con, f"H{n}", d, "holdings_briefing", "09:15", [_item()])
        _outcome(con, f"H{n}", 1, "krx_etf:005930", 1, ret=0.002 * (n % 4) - 0.003)
    a = _r1(path, cal, iterations=300, seed=0)
    b = _r1(path, cal, iterations=300, seed=0)
    assert a["groups"] == b["groups"]
    (g,) = _groups(a, view="observed", horizon=1, price_basis="KRX_ETF_UNADJUSTED|X")
    assert (
        g["bootstrap"]["status"] == "OK"
        and g["bootstrap"]["low"] <= g["mean"] <= g["bootstrap"]["high"]
    )


# ── bootstrap ────────────────────────────────────────────────────────────────


class _FixedRng:
    bounds: list[int] = []

    def __init__(self, seed):
        pass

    def randrange(self, upper):
        _FixedRng.bounds.append(upper)
        return 0


def test_bootstrap_non_circular_contiguous_date_bundles(monkeypatch):
    days = [f"d{i:02d}" for i in range(20)]
    obs = {d: [float(i)] * (2 if i % 2 else 1) for i, d in enumerate(days)}
    _FixedRng.bounds = []
    monkeypatch.setattr(bootstrap.random, "Random", _FixedRng)
    out = bootstrap.date_block_ci(days, obs, block=5, iterations=3)
    assert set(_FixedRng.bounds) == {
        20 - 5 + 1
    }  # 시작은 [0, N-b] — 끝과 처음을 잇지 않는다
    first = [
        v for d in days[:5] for v in obs[d]
    ]  # 매 블록이 d00 ~ d04 · 같은 날 관측 함께
    assert out["low"] == out["high"] == pytest.approx(sum(first) / len(first))


def test_bootstrap_insufficient_and_undefined_resamples():
    days = [f"d{i:02d}" for i in range(20)]
    few = {d: [0.01] for d in days[:9]}  # 성숙 날짜 9 < 2 × 5
    assert (
        bootstrap.date_block_ci(days, few, block=5)["status"] == "INSUFFICIENT_SAMPLE"
    )
    half = {d: [0.01] for d in days[:10]}  # 뒤쪽 블록만 뽑히면 관측 0
    out = bootstrap.date_block_ci(days, half, block=5, iterations=1000, seed=0)
    assert out["status"] == "RESAMPLE_UNDEFINED" and out["undefined_resamples"] > 0
    assert out["low"] is None and out["high"] is None  # 정상 구간으로 위장하지 않는다


def test_eval_dates_follow_02_rule(cal):
    assert dates.eval_dates(cal, "2026-10-08", "09:15") == {
        1: "2026-10-08",
        5: "2026-10-15",
        20: "2026-11-05",
    }
    assert (
        dates.eval_dates(cal, "2026-10-08", "15:40")[1] == "2026-10-12"
    )  # 15:30 뒤 = 다음 거래일부터 · 10-09 휴장
    assert dates.default_end(cal, "2026-10-12") == "2026-10-08"


# ── 읽기 전용 · CLI · 경계 ─────────────────────────────────────────────────────


def test_cli_writes_new_folder_and_never_touches_db(ledger, cal, tmp_path, monkeypatch):
    from scripts import run_ledger_report as cli

    monkeypatch.setattr(dates, "today_kst", lambda: "2026-10-12")
    path, con = ledger
    _run(con, "H", START, "holdings_briefing", "09:15", [_item()])
    con.close()
    before = _sha(path)
    out = tmp_path / "out"
    cal_dir = str(tmp_path / "market_meta")
    assert (
        cli.main(
            [
                "r0",
                "--db",
                str(path),
                "--end",
                "2026-10-08",
                "--calendar-dir",
                cal_dir,
                "--out-dir",
                str(out),
            ]
        )
        == 0
    )
    assert (
        cli.main(
            [
                "r1",
                "--db",
                str(path),
                "--end",
                "2026-10-08",
                "--calendar-dir",
                cal_dir,
                "--out-dir",
                str(out),
                "--iterations",
                "20",
            ]
        )
        == 0
    )
    folders = sorted(p.name for p in out.iterdir())
    assert [f[:3] for f in folders] == ["r0_", "r1_"]
    for f in out.iterdir():
        assert sorted(x.name for x in f.iterdir()) == ["report.json", "report.md"]
    assert _sha(path) == before
    rep = json.loads(next(out.glob("r0_*/report.json")).read_text(encoding="utf-8"))
    with pytest.raises(FileExistsError):
        render.write(rep, out, next(out.glob("r0_*")).name.split("_")[-1])


def test_new_modules_have_no_network_ssh_or_telegram():
    root = Path(__file__).resolve().parents[1]
    files = [*sorted((root / "app" / "ledger_reports").glob("*.py")), SCRIPT]
    banned = (
        "requests",
        "httpx",
        "urllib",
        "telegram",
        "aiohttp",
        "socket",
        "subprocess",
        "paramiko",
    )
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


def test_evidence_ops_notes_are_bounded():
    text = "price_batch_price_date=2026-10-22\n" + "\n".join(
        "가 " * 300 for _ in range(60)
    )
    out = evidence.parse_ops(text, end="2026-10-22", last_sync_success=None)
    assert len(out["notes"]) == evidence.NOTE_LINES and all(
        len(n) == evidence.NOTE_WIDTH for n in out["notes"]
    )


# ── 검토 반영(2026-10-08) ─────────────────────────────────────────────────────


def _clean_ten_days(ledger, cal):
    path, con = ledger
    _full_days(con, cal, 10)
    _sync(path, "2026-10-23T09:31:00+09:00")
    return path, con


def test_long_period_axis_is_not_cut_at_120_days(ledger, cal):
    path, con = ledger
    axis = dates.trading_days(cal, START, "2027-03-31")
    assert (
        axis[-1] == "2027-03-31" and len(axis) > 100
    )  # 2027 은 평일 기본(한국 거래일 계약)
    late = "2027-03-02"
    _run(con, "A", START, "holdings_briefing", "09:15", [_item()])
    _run(con, "B", late, "holdings_briefing", "09:15", [_item()])
    rep = _r1(path, cal, end="2027-03-31", iterations=20)
    assert rep["window"]["trading_days"] == len(axis)
    g = _groups(rep, view="observed", horizon=1)[0]
    assert g["bootstrap"]["n_days"] == len(axis)
    r0rep = _r0(path, cal, "2027-03-31")
    # 축이 120 달력일에서 잘리면 2027-02 뒤 날짜의 누락이 사라진다 — 전 기간 × 11 슬롯 − 기록 2
    assert r0rep["schedule"]["expected"] == len(axis) * 11
    assert r0rep["schedule"]["missing"]["count"] == len(axis) * 11 - 2


@pytest.mark.parametrize(
    "value", ["unknown", "today", "2026-10-3", "20261022", "2026-10-21"]
)
def test_ops_batch_date_must_be_strict_and_cover_end(value):
    text = OPS_OK.replace("2026-10-22", value)
    out = evidence.parse_ops(
        text, end="2026-10-22", last_sync_success="2026-10-23T10:00:00+09:00"
    )
    assert out["batch_confirmed"] is False and out["reason"]


@pytest.mark.parametrize(
    "line, verdict",
    [
        ("ops_error_count=3", "CHECK_REQUIRED"),
        ("", "NOT_READY"),
        ("ops_error_count=x", "NOT_READY"),
    ],
)
def test_ops_error_count_drives_verdict(ledger, cal, line, verdict):
    path, _ = _clean_ten_days(ledger, cal)
    ops = OPS_OK.replace("ops_error_count=0\n", line + ("\n" if line else ""))
    rep = _r0(path, cal, "2026-10-22", ops=ops)
    assert rep["verdict"] == verdict


@pytest.mark.parametrize("what", ["run_failed", "delivery_failed", "delivery_partial"])
def test_operational_failures_are_not_collection_ok(ledger, cal, what):
    path, con = _clean_ten_days(ledger, cal)
    eid = "2026-10-14-holdings_risk_alert-11:30"
    if what == "run_failed":
        con.execute(
            "UPDATE evaluation_run SET status = 'failed' WHERE event_id = ?", (eid,)
        )
    else:
        status = what.split("_")[1]
        con.execute(
            "UPDATE delivery SET delivery_status = ? WHERE event_id = ?", (status, eid)
        )
    con.commit()
    rep = _r0(path, cal, "2026-10-22")
    assert rep["verdict"] == "CHECK_REQUIRED"
    assert rep["operations"][what]["keys"] == [eid]


@pytest.mark.parametrize("kind", ["started_gap", "ledger_only", "missing_in_ledger"])
def test_each_reconcile_error_kind_is_check_required(ledger, cal, kind):
    path, _ = _clean_ten_days(ledger, cal)
    bad = RECON_OK.replace(f"{kind}=0", f"{kind}=1")
    rep = _r0(path, cal, "2026-10-22", recon=bad)
    assert (
        rep["verdict"] == "CHECK_REQUIRED"
        and rep["reconciliation"]["state"] == "ERRORS"
    )
    assert any("근거 기간" in p for p in rep["problems"])


def test_reconcile_errors_from_another_ledger_are_not_checked(ledger, cal):
    path, _ = _clean_ten_days(ledger, cal)
    other = RECON_OK.replace(FIRST, "2025-01-01T00:00:00+00:00").replace(
        "missing_in_ledger=0", "missing_in_ledger=3"
    )
    no_time = "\n".join(
        x
        for x in RECON_OK.replace(
            "missing_in_ledger=0", "missing_in_ledger=3"
        ).splitlines()
        if not x.startswith("captured_at=")
    )
    for text in (other, no_time):
        rep = _r0(path, cal, "2026-10-22", recon=text)
        assert rep["reconciliation"]["state"] == "NOT_CHECKED"
        assert rep["verdict"] == "NOT_READY"


@pytest.mark.parametrize(
    "case",
    [
        "orphan_items",
        "orphan_deliveries",
        "started_with_rows",
        "duplicates",
        "outcome_on_non_target",
        "finalized_without_delivery",
        "started_in_window",
    ],
)
def test_each_integrity_problem_alone_is_check_required(ledger, cal, case):
    path, con = _clean_ten_days(ledger, cal)
    if case == "orphan_items":
        con.execute(
            "INSERT INTO signal_item (event_id, item_seq, subject_kind, subject_id, disposition)"
            " VALUES ('ghost', 1, 'ticker', 'X', 'sent')"
        )
    elif case == "orphan_deliveries":
        con.execute(
            "INSERT INTO delivery (event_id, delivery_status) VALUES ('ghost', 'sent')"
        )
    elif case == "started_with_rows":
        _run(con, "S", "2026-10-07", "holdings_briefing", "09:15", finalize=False)
        con.execute(
            "INSERT INTO delivery (event_id, delivery_status) VALUES ('S', 'sent')"
        )
    elif case == "duplicates":
        _run(con, "dup", "2026-10-13", "market_briefing", "08:30")
    elif case == "outcome_on_non_target":
        _run(
            con,
            "NT",
            "2026-10-13",
            "holdings_briefing",
            "13:00",
            [_item(evaluable=0)],
            off=1,
        )
        _outcome(con, "NT", 1, "krx_etf:005930", 1, ret=0.01)
    elif case == "finalized_without_delivery":
        con.execute(
            "DELETE FROM delivery WHERE event_id = '2026-10-15-market_briefing-08:30'"
        )
    else:
        _run(
            con,
            "S2",
            "2026-10-15",
            "holdings_risk_alert",
            "13:31",
            off=1,
            finalize=False,
        )
    con.commit()
    rep = _r0(path, cal, "2026-10-22")
    assert rep["verdict"] == "CHECK_REQUIRED", rep["problems"]
    key = "schedule" if case == "duplicates" else "integrity"
    assert rep[key][case]["count"] == 1


def test_pending_alone_keeps_collection_ok(ledger, cal):
    path, con = _clean_ten_days(ledger, cal)
    con.execute(
        "INSERT INTO signal_item (event_id, item_seq, subject_kind, subject_id,"
        " disposition, evaluable, exposure, values_json)"
        " VALUES ('2026-10-22-holdings_briefing-09:15', 1, 'ticker', 'A',"
        " 'sent', 1, 'PRIMARY', '{}')"
    )
    con.commit()
    rep = _r0(path, cal, "2026-10-22")
    assert rep["verdict"] == "COLLECTION_OK", rep["problems"]
    # 대상 item 1개 · 결과 0 → +1(평가일 10-22) 도래 · +5 · +20 미도래 — 대기만으로는 점검 필요 아님
    assert (rep["outcomes"]["pending_due"], rep["outcomes"]["pending_not_due"]) == (
        1,
        2,
    )


def test_matured_after_end_is_not_due_not_statistic(ledger, cal):
    path, con = ledger
    _run(con, "H", START, "holdings_briefing", "09:15", [_item()])
    con.execute(
        "INSERT INTO price_outcome (event_id, item_seq, series_id, horizon, status, return_raw,"
        " eval_date, price_basis, computed_at) VALUES ('H', 1, 'krx_etf:005930', 20, 'MATURED',"
        " 0.05, '2026-11-05', 'KRX_ETF_UNADJUSTED|X', 'c')"
    )
    con.commit()
    rep = _r1(path, cal, end="2026-10-15")
    assert all(g["n_matured"] == 0 for g in _groups(rep, horizon=20))
    assert (
        sum(g["pending_not_due"] for g in _groups(rep, view="observed", horizon=20))
        == 1
    )
    _sync(path, "2026-10-16T10:00:00+09:00")
    assert _r0(path, cal, "2026-10-15")["outcomes"]["by_status"] == {}


def test_validate_end(cal):
    assert dates.validate_end(cal, "2026-10-08", "2026-10-12") == "2026-10-08"
    for bad, today in (
        ("20261008", "2026-10-12"),
        ("2026-10-12", "2026-10-12"),
        ("2026-10-09", "2026-10-12"),
    ):
        with pytest.raises(ValueError):
            dates.validate_end(cal, bad, today)


def test_r1_block_and_empty_days_on_axis(ledger, cal):
    path, con = ledger
    days = cal.days_from(START, 30)
    for n, d in enumerate(days[::2]):  # 하루 걸러 사건 — 빈 날도 축에 남는다
        _run(con, f"H{n}", d, "holdings_briefing", "09:15", [_item()])
        _outcome(con, f"H{n}", 1, "krx_etf:005930", 20, ret=0.01, basis="B")
    rep = _r1(path, cal, end=days[-1], iterations=30)
    (g,) = _groups(rep, view="observed", horizon=20, price_basis="B")
    assert g["bootstrap"]["block_days"] == 20 and g["bootstrap"]["n_days"] == 30
    assert g["bootstrap"]["status"] == "INSUFFICIENT_SAMPLE"  # 사건 날짜 15 < 2 × 20


def test_markdown_table_rows_keep_column_count(ledger, cal):
    path, con = ledger
    _run(con, "H", START, "holdings_briefing", "09:15", [_item()])
    _outcome(
        con, "H", 1, "krx_etf:005930", 1, ret=0.01, basis="KRX_ETF_UNADJUSTED|ETF_KODEX"
    )
    md = render.r1_markdown(_r1(path, cal))
    rows = [ln for ln in md.splitlines() if ln.startswith("| ")]
    widths = {len(ln.replace("\\|", "").split("|")) for ln in rows}
    assert len(widths) == 1


def test_ops_notes_hide_secrets():
    text = OPS_OK + "TELEGRAM_BOT_TOKEN=123\nnote " + "a" * 40 + " ok\n"
    notes = evidence.parse_ops(text, end="2026-10-22", last_sync_success=None)["notes"]
    assert "[가림 — 비밀값 단어가 든 줄]" in notes
    assert any("[가림]" in n for n in notes) and not any("a" * 40 in n for n in notes)


def test_unknown_exposure_value_does_not_crash(ledger, cal):
    path, con = ledger
    _run(con, "H", START, "holdings_briefing", "09:15", [_item(exposure="TERTIARY")])
    rep = _r1(path, cal)
    assert {g["exposure"] for g in rep["groups"]} == {"TERTIARY"}
    assert "알 수 없는 노출값(TERTIARY)" in render.r1_markdown(rep)


# ── 검증자 r1 정정(2026-10-08) ────────────────────────────────────────────────


@pytest.mark.parametrize(
    "table",
    [
        "evaluation_run",
        "signal_item",
        "delivery",
        "ledger_meta",
        "user_feedback",
        "ledger_sync_attempt",
    ],
)
def test_missing_required_table_is_never_collection_ok(ledger, cal, table):
    path, con = _clean_ten_days(ledger, cal)
    _run(con, "T", "2026-10-13", "holdings_briefing", "13:00", [_item()], off=1)
    con.execute(f"DROP TABLE {table}")
    con.commit()
    rep = _r0(path, cal, "2026-10-22")
    assert rep["verdict"] == "CHECK_REQUIRED"
    assert f"입력 사본 손상 — 사본 필수 표 없음: {table}" in rep["problems"]
    assert rep["input"]["problems"] == [f"사본 필수 표 없음: {table}"]
    with pytest.raises(r1.InvalidInput):
        _r1(path, cal)


def test_outcome_table_dropped_after_it_was_created(ledger, cal):
    path, con = _clean_ten_days(ledger, cal)
    ls.meta_put_once(con, lo.META_KEY, lo.SCHEMA_VERSION)
    con.execute("DROP TABLE price_outcome")
    con.commit()
    rep = _r0(path, cal, "2026-10-22")
    assert rep["verdict"] == "CHECK_REQUIRED"
    assert any("price_outcome 표 없음" in p for p in rep["problems"])
    with pytest.raises(r1.InvalidInput):
        _r1(path, cal)


def test_outcome_table_absent_before_maturity_is_normal(ledger, cal):
    path, con = _clean_ten_days(ledger, cal)
    con.execute(
        "DROP TABLE price_outcome"
    )  # 성숙 단계가 아직 한 번도 돌지 않은 원장(기록 없음)
    con.commit()
    rep = _r0(path, cal, "2026-10-22")
    assert rep["verdict"] == "COLLECTION_OK" and rep["input"]["problems"] == []


@pytest.mark.parametrize("iterations", [0, -1])
def test_bootstrap_needs_at_least_one_iteration(iterations):
    days = [f"d{i:02d}" for i in range(20)]
    with pytest.raises(ValueError):
        bootstrap.date_block_ci(
            days, {d: [0.01] for d in days}, block=5, iterations=iterations
        )


@pytest.mark.parametrize("value", ["0", "-1"])
def test_cli_rejects_non_positive_iterations(ledger, cal, tmp_path, monkeypatch, value):
    from scripts import run_ledger_report as cli

    path, con = ledger
    con.close()
    monkeypatch.setattr(dates, "today_kst", lambda: "2026-10-12")
    cal_dir = str(tmp_path / "market_meta")
    args = ["r1", "--db", str(path), "--end", "2026-10-08", "--calendar-dir", cal_dir]
    with pytest.raises(SystemExit) as e:
        cli.main([*args, "--out-dir", str(tmp_path / "o"), "--iterations", value])
    assert e.value.code == 2
    assert not (tmp_path / "o").exists()


def test_cli_r1_fails_on_damaged_input(ledger, cal, tmp_path, monkeypatch, capsys):
    from scripts import run_ledger_report as cli

    path, con = ledger
    con.execute("DROP TABLE signal_item")
    con.commit()
    con.close()
    monkeypatch.setattr(dates, "today_kst", lambda: "2026-10-12")
    out = tmp_path / "o"
    code = cli.main(
        [
            "r1",
            "--db",
            str(path),
            "--end",
            "2026-10-08",
            "--calendar-dir",
            str(tmp_path / "market_meta"),
            "--out-dir",
            str(out),
        ]
    )
    assert code == 3 and "invalid_input" in capsys.readouterr().out
    assert not out.exists()  # 손상된 입력으로는 리포트를 만들지 않는다
