"""POC6-17 — OCI 수급 보관본의 PC 반영 · pull 동시 실행 잠금 · 기간 비교 기준일 설명(설계 V1 · PLAN 판정).

전부 tmp 보관소 · tmp 시장 DB · 가짜 가져오기 결과로 본다(실제 SSH · 키움 · 라이브 DB 0 · conftest 가드).
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import api_supply_fx_oil
from app import oci_flow_import as ofi
from app import supply_fx_oil_refresh as rf
from app import supply_fx_oil_store as st
from app.api import app
from app.forward_auto.runner import Child, run_child
from app.market_benchmark_store import upsert_benchmark_prices
from app.market_data_store import log_refresh
from app.ml_evidence import store, transfer
from app.oci_flow_import import PullOutcome
from app.supply_fx_oil_basis import end_basis, read_flow_link
from app.supply_fx_oil_context import build_market_flow_context
from tests.test_poc6_05_evidence_store import FakeRemote, daily_run, win

REAL_RUN_PULL = ofi.run_pull  # conftest 가 실제 pull 을 막기 전(수집 시점) 원본

DAYS = [
    "2026-10-20",
    "2026-10-21",
    "2026-10-22",
    "2026-10-23",
    "2026-10-26",
    "2026-10-27",
    "2026-10-28",
    "2026-10-29",
    "2026-10-30",
]
CLOSE = {d: 5000.0 + i for i, d in enumerate(DAYS)}
T0 = datetime(2026, 10, 23, 0, 40, tzinfo=timezone.utc)
PC_AT = "2026-10-23T10:31:30Z"  # PC 직접 조회 저장 형식(초 Z)


def nets(v: int = 1) -> dict[str, int]:
    return {inv: v * 100_000_000 * (i + 1) for i, inv in enumerate(st.INVESTORS)}


def _db(tmp: Path, kospi_days=DAYS) -> Path:
    db = tmp / "market_data.sqlite"
    upsert_benchmark_prices(
        benchmark_id="KOSPI",
        benchmark_name="코스피",
        rows=[(d, CLOSE[d]) for d in kospi_days],
        source="TEST",
        db_path=db,
    )
    st.init_market_flow_tables(db)
    con = sqlite3.connect(db)
    for sid in (st.USDKRW, st.WTI):
        u, p, b = st.MACRO_SERIES[sid]
        con.executemany(
            "INSERT INTO market_macro_daily VALUES (?, ?, ?, ?, ?, ?, ?)",
            [(sid, d, 1000.0, u, p, b, "2026-11-02T01:00:00Z") for d in DAYS],
        )
    con.commit()
    con.close()
    return db


def _pc_rows(db: Path, days, v: int = 1, at: str = PC_AT) -> None:
    con = sqlite3.connect(db)
    con.executemany(
        "INSERT INTO market_investor_flow_daily VALUES (?, ?, ?, NULL, NULL, ?, ?, ?)",
        [
            ("KOSPI", d, inv, net, st.FLOW_SOURCE, at)
            for d in days
            for inv, net in nets(v).items()
        ],
    )
    con.commit()
    con.close()


def _run(
    root: Path,
    started: datetime,
    days,
    *,
    v: int = 1,
    observed: datetime | None = None,
    flow_status: str = "OK",
    status: str = "OK",
    edit=None,
    received=None,
) -> dict:
    """일일 수집 묶음 하나(수급 object = OCI daily_flow 와 같은 모양)."""
    observed = observed or started
    objs, shas = {}, []
    for d in days:
        payload = {
            "date": d,
            "observed_at": store.iso(observed),
            "index_close": CLOSE[d],
            "nets": nets(v),
        }
        if edit:
            edit(payload)
        info = store.put_bytes(root, store.canonical(payload))
        objs[info["sha256"]] = {
            "sha256": info["sha256"],
            "bytes": info["bytes"],
            "role": "investor_flow_received",
            "format": "json",
        }
        shas.append(info["sha256"])
    if flow_status == "FAILED":
        f = {
            "status": "FAILED",
            "reason": "투자자 수급(키움 인증 정보 없음)",
            "planned": 0,
            "not_attempted_extra": [],
            "objects": [],
        }
    else:
        f = {
            "status": flow_status,
            "planned": len(days),
            "received": list(days if received is None else received),
            "failed": {},
            "not_attempted": [],
            "not_attempted_extra": [],
            "objects": shas,
            "db_upsert": "OK",
            "mismatch": False,
            "message": None,
            "error": None,
        }
    m = {
        "schema": store.SCHEMA,
        "run_id": store.new_run_id(started),
        "kind": "DAILY_COLLECTION",
        "site": "TEST",
        "status": status,
        "sources": {"investor_flow": f, "fx_wti": {"status": "OK"}},
        "objects": [objs[k] for k in sorted(objs)],
    }
    return store.publish_run(root, m, clock=lambda: started + timedelta(seconds=9))[1]


def _flows(db: Path) -> dict:
    con = sqlite3.connect(db)
    rows = con.execute(
        "SELECT market, trade_date, investor, net_value, source, collected_at "
        "FROM market_investor_flow_daily"
    ).fetchall()
    con.close()
    return {(m, d, i): (n, s, c) for m, d, i, n, s, c in rows}


def _imports(db: Path) -> list:
    con = sqlite3.connect(db)
    try:
        return con.execute(
            "SELECT evidence_run_id, flow_status, result, new_rows, corrected_rows, "
            "refreshed_rows, same_rows, kept_newer_rows FROM market_investor_flow_import "
            "ORDER BY evidence_run_id"
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    finally:
        con.close()


def _apply(db: Path, root: Path, rid: str = "r1") -> ofi.ApplyResult:
    return ofi.apply_evidence_flows(root=root, db_path=db, refresh_id=rid)


def _tree_hash(root: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(root.rglob("*")):
        if p.is_file():
            h.update(str(p.relative_to(root)).encode() + p.read_bytes())
    return h.hexdigest()


# ── 반영: 회신과 같은 입력 · D · 비대상 표 ─────────────────────────────────────


def test_reply_input_fills_flows_and_moves_D_without_touching_other_tables(tmp_path):
    db, ev = _db(tmp_path), tmp_path / "ev"
    _pc_rows(db, DAYS[:3])  # PC 수급 10-22 까지(회신 상황)
    con = sqlite3.connect(db)
    con.execute(  # 다른 market 행(대상 밖)
        "INSERT INTO market_investor_flow_daily VALUES ('KOSDAQ', '2026-10-22', 'foreign', "
        "NULL, NULL, 7, 'X', '2026-10-23T00:00:00Z')"
    )
    con.commit()
    other = {
        t: con.execute(f"SELECT * FROM {t} ORDER BY 1, 2").fetchall()
        for t in ("market_benchmark_daily_price", "market_macro_daily")
    }
    con.close()
    before = build_market_flow_context(db_path=db)
    assert before["D"] == "2026-10-22"
    assert before["end_basis"]["limited_by"] == "flows"
    _run(ev, datetime(2026, 11, 2, 0, 40, tzinfo=timezone.utc), DAYS)
    ev_hash = _tree_hash(ev)
    probs = ofi.refresh_flows_from_oci(
        db_path=db,
        refresh_id="r1",
        asof="2026-11-02",
        root=ev,
        pull=lambda: PullOutcome("ok"),
    )
    assert probs == []
    f = _flows(db)
    assert max(d for m, d, _ in f if m == "KOSPI") == "2026-10-30"
    assert f[("KOSDAQ", "2026-10-22", "foreign")] == (7, "X", "2026-10-23T00:00:00Z")
    con = sqlite3.connect(db)
    assert {
        t: con.execute(f"SELECT * FROM {t} ORDER BY 1, 2").fetchall()
        for t in ("market_benchmark_daily_price", "market_macro_daily")
    } == other
    con.close()
    assert _tree_hash(ev) == ev_hash  # 보관 원본 불변
    after = build_market_flow_context(db_path=db)
    assert after["D"] == "2026-10-30" and after["end_basis"]["limited_by"] is None
    assert after["series"]["usdkrw"]["E"] == "2026-10-30"  # 다른 원천 날짜 그대로
    assert after["flow_link"]["state"] == "applied"
    assert after["flow_link"]["retry_helps"] is False


def test_same_run_reapply_is_noop(tmp_path):
    db, ev = _db(tmp_path), tmp_path / "ev"
    _run(ev, T0, DAYS[:4])
    assert len(_apply(db, ev).applied) == 1
    snap = _flows(db)
    again = _apply(db, ev, "r2")
    assert again.applied == [] and again.failed_run is None
    assert _flows(db) == snap and len(_imports(db)) == 1


# ── 정정 순서(판정 §4-1 · §4-3) ──────────────────────────────────────────────


def test_same_value_newer_observation_then_older_different_value_keeps_latest(
    tmp_path,
):
    db, ev = _db(tmp_path), tmp_path / "ev"
    d = DAYS[3]
    _pc_rows(db, [d], v=1, at=PC_AT)  # 10/23 관측
    late = datetime(2026, 11, 2, 0, 40, tzinfo=timezone.utc)
    mid = datetime(2026, 10, 25, 0, 40, tzinfo=timezone.utc)
    _run(ev, T0, [d], v=1, observed=late)  # 같은 값 · 11/02 관측
    _run(
        ev, T0 + timedelta(hours=1), [d], v=9, observed=mid
    )  # 뒤에 도착한 10/25 의 다른 값
    res = _apply(db, ev)
    assert res.failed_run is None and len(res.applied) == 2
    row = _flows(db)[("KOSPI", d, "foreign")]
    assert row == (nets(1)["foreign"], st.FLOW_OCI_SOURCE, store.iso(late))
    assert res.counts["refreshed"] == 13 and res.counts["kept_newer"] == 13
    assert res.counts["corrected"] == 0


def test_overlap_correction_newer_observation_wins(tmp_path):
    db, ev = _db(tmp_path), tmp_path / "ev"
    _run(ev, T0, DAYS[:2], v=1)
    _run(ev, T0 + timedelta(days=1), DAYS[1:3], v=2)
    res = _apply(db, ev)
    f = _flows(db)
    assert f[("KOSPI", DAYS[0], "foreign")][0] == nets(1)["foreign"]
    assert f[("KOSPI", DAYS[1], "foreign")][0] == nets(2)["foreign"]  # 정정
    assert res.counts["corrected"] == 13 and res.counts["new"] == 13 * 3


@pytest.mark.parametrize(
    "pc_at, v, obs, expect",
    [
        (
            PC_AT,
            1,
            T0 + timedelta(days=5),
            "refreshed",
        ),  # 같은 값 · 늦은 관측 → 시각만 올림
        (PC_AT, 2, T0 + timedelta(days=5), "corrected"),  # 다른 값 · 늦은 관측 → 정정
        (PC_AT, 2, T0, "kept_newer"),  # 다른 값 · 이른 관측 → PC 최신 값 유지
        (PC_AT, 1, T0, "same"),  # 같은 값 · 이른 관측 → 그대로(시각 내리지 않음)
    ],
)
def test_first_transition_from_pc_direct_rows(tmp_path, pc_at, v, obs, expect):
    db, ev = _db(tmp_path), tmp_path / "ev"
    d = DAYS[2]
    _pc_rows(db, [d], v=1, at=pc_at)
    _run(ev, T0, [d], v=v, observed=obs)
    res = _apply(db, ev)
    assert res.failed_run is None and res.counts[expect] == 13
    row = _flows(db)[("KOSPI", d, "foreign")]
    if expect in ("refreshed", "corrected"):
        assert row == (nets(v)["foreign"], st.FLOW_OCI_SOURCE, store.iso(obs))
    else:
        assert row == (nets(1)["foreign"], st.FLOW_SOURCE, pc_at)


@pytest.mark.parametrize("pc_at", [store.iso(T0), "시각 아님"])
def test_conflict_same_time_or_unknown_time_rolls_back_and_stops(tmp_path, pc_at):
    db, ev = _db(tmp_path), tmp_path / "ev"
    _pc_rows(db, [DAYS[1]], v=1, at=pc_at)
    bad = _run(ev, T0, DAYS[:2], v=2, observed=T0)  # DAYS[0] 은 새 행 · DAYS[1] 충돌
    _run(ev, T0 + timedelta(days=1), DAYS[5:6], v=3)
    snap = _flows(db)
    res = _apply(db, ev)
    assert res.failed_run == bad["run_id"] and "충돌" in res.fail_reason
    assert res.applied == [] and _flows(db) == snap  # 앞 행도 rollback · 뒤 묶음 미처리
    assert _imports(db) == []


def test_unknown_time_same_value_is_left_as_is(tmp_path):
    db, ev = _db(tmp_path), tmp_path / "ev"
    _pc_rows(db, [DAYS[1]], v=1, at="시각 아님")
    _run(ev, T0, [DAYS[1]], v=1)
    res = _apply(db, ev)
    assert res.failed_run is None and res.counts["same"] == 13
    assert _flows(db)[("KOSPI", DAYS[1], "foreign")][2] == "시각 아님"


# ── 묶음 상태 · 검사(판정 §4-2 · §4-3) ───────────────────────────────────────


def test_failed_flow_runs_are_excluded_and_do_not_block_later_runs(tmp_path):
    db, ev = _db(tmp_path), tmp_path / "ev"
    a = _run(ev, T0, [], flow_status="FAILED", status="PARTIAL")
    b = _run(ev, T0 + timedelta(seconds=30), [], flow_status="FAILED", status="PARTIAL")
    c = _run(
        ev, T0 + timedelta(hours=2), DAYS[:3], status="PARTIAL"
    )  # 다른 자료 때문에 PARTIAL
    res = _apply(db, ev)
    assert res.excluded == [a["run_id"], b["run_id"]] and res.applied == [c["run_id"]]
    assert [r[2] for r in _imports(db)] == ["EXCLUDED_NO_FLOW"] * 2 + ["APPLIED"]
    assert _apply(db, ev).excluded == []  # 한 번 기록하면 다시 보지 않음


def test_partial_flow_applies_only_returned_objects(tmp_path):
    db, ev = _db(tmp_path), tmp_path / "ev"
    _run(ev, T0, DAYS[:2], flow_status="PARTIAL")  # 3번째 날은 실패(object 없음)
    res = _apply(db, ev)
    assert res.failed_run is None
    assert {d for _, d, _ in _flows(db)} == set(DAYS[:2])  # 빠진 날을 채우지 않음
    assert _imports(db)[0][1] == "PARTIAL"


def test_damaged_object_stops_and_keeps_earlier_runs(tmp_path):
    db, ev = _db(tmp_path), tmp_path / "ev"
    ok = _run(ev, T0, DAYS[:2])
    bad = _run(ev, T0 + timedelta(days=1), DAYS[2:4])
    later = _run(ev, T0 + timedelta(days=2), DAYS[4:5])
    victim = store.object_path(ev, bad["sources"]["investor_flow"]["objects"][0])
    victim.chmod(0o644)
    victim.write_bytes(b"{}")
    probs = ofi.refresh_flows_from_oci(
        db_path=db,
        refresh_id="r1",
        asof="2026-11-02",
        root=ev,
        pull=lambda: PullOutcome("ok"),
    )
    assert probs == ["투자자 수급(보관본 손상(수급 object))"]
    assert {d for _, d, _ in _flows(db)} == set(DAYS[:2])
    assert [r[0] for r in _imports(db)] == [ok["run_id"]]
    assert later["run_id"] not in [r[0] for r in _imports(db)]
    link = build_market_flow_context(db_path=db)["flow_link"]
    assert link["state"] == "apply_failed" and link["retry_helps"] is True
    assert "보관본 손상" in link["text"] and "10/21까지 사용 중" in link["text"]


def _set(key, value):
    def edit(p):
        p[key] = value

    return edit


@pytest.mark.parametrize(
    "edit, reason",
    [
        (lambda p: p["nets"].pop("foreign"), "투자자 분류"),
        (lambda p: p["nets"].update(foreign=True), "정수 원"),
        (lambda p: p["nets"].update(foreign=1.5), "정수 원"),
        (_set("index_close", float("nan")), "지수값"),
        (_set("index_close", float("inf")), "지수값"),
        (_set("index_close", 0), "지수값"),
        (_set("index_close", True), "지수값"),
        (_set("index_close", CLOSE[DAYS[0]] + 1), "PC 코스피와 다름"),
        (_set("observed_at", "2026-11-02T00:40:09"), "관측 시각"),  # 시간대 미상
        (_set("date", DAYS[1]), "날짜"),
        (lambda p: p["nets"].update(foreign=2**63), "순매수 범위"),  # 검토 지적 2
        (lambda p: p["nets"].update(foreign=-(2**63)), "순매수 범위"),
    ],
)
def test_object_checks_reject_whole_run(tmp_path, edit, reason):
    db, ev = _db(tmp_path), tmp_path / "ev"
    _run(ev, T0, DAYS[:1], edit=edit)
    res = _apply(db, ev)
    assert res.applied == [] and reason in res.fail_reason
    assert _flows(db) == {} and _imports(db) == []


def test_same_run_id_with_changed_manifest_is_conflict(tmp_path):
    db, ev = _db(tmp_path), tmp_path / "ev"
    r = _run(ev, T0, DAYS[:1])
    _apply(db, ev)
    con = sqlite3.connect(db)
    con.execute("UPDATE market_investor_flow_import SET manifest_sha256 = 'x'")
    con.commit()
    con.close()
    res = _apply(db, ev)
    assert res.failed_run == r["run_id"] and "같은 묶음 다른 내용" in res.fail_reason


def test_db_error_rolls_back_rows_and_record_together(tmp_path):
    db, ev = _db(tmp_path), tmp_path / "ev"
    _run(ev, T0, DAYS[:2])
    con = sqlite3.connect(db)
    con.execute(ofi.IMPORT_DDL)
    con.execute(
        "CREATE TRIGGER boom BEFORE INSERT ON market_investor_flow_import "
        "BEGIN SELECT RAISE(ABORT, 'x'); END"
    )
    con.commit()
    con.close()
    res = _apply(db, ev)
    assert res.fail_reason == "PC 표 반영 실패"
    assert _flows(db) == {} and _imports(db) == []  # 행 반영도 함께 되돌림


# ── 가져오기 실패 · 경합(판정 §3) ─────────────────────────────────────────────


@pytest.mark.parametrize(
    "outcome, head",
    [
        (PullOutcome("unreachable", "OCI 연결 실패"), "가져오기 실패(OCI 연결 실패)"),
        (PullOutcome("busy", "다른 가져오기 진행 중"), "다른 가져오기 진행 중"),
        (
            PullOutcome("timeout", "가져오기 시간 제한(150초)"),
            "가져오기 실패(가져오기 시간 제한(150초))",
        ),
    ],
)
def test_pull_failure_applies_verified_local_copies_and_says_so(
    tmp_path, outcome, head
):
    db, ev = _db(tmp_path), tmp_path / "ev"
    _pc_rows(db, DAYS[:3])
    _run(ev, datetime(2026, 11, 2, 0, 40, tzinfo=timezone.utc), DAYS)
    probs = ofi.refresh_flows_from_oci(
        db_path=db, refresh_id="r1", asof="2026-11-02", root=ev, pull=lambda: outcome
    )
    assert probs == [f"투자자 수급({outcome.reason})"]
    out = build_market_flow_context(db_path=db)
    assert out["D"] == "2026-10-30"
    link = out["flow_link"]
    assert link["state"] == "applied_local" and link["retry_helps"] is True
    assert link["text"] == (
        f"{head} · PC에 이미 받은 10/30까지의 수급 반영 완료 · 새 OCI 자료는 확인하지 못했습니다"
    )
    # 같은 사본뿐인 다음 실행 = '기존 PC 수급 유지'(새 자료 반영이라 쓰지 않음)
    ofi.refresh_flows_from_oci(
        db_path=db, refresh_id="r2", asof="2026-11-02", root=ev, pull=lambda: outcome
    )
    link = build_market_flow_context(db_path=db)["flow_link"]
    assert (
        link["state"] == "kept_local" and "기존 PC 수급(10/30까지) 유지" in link["text"]
    )


def test_pc_market_flow_step_never_builds_kiwoom_client(tmp_path, monkeypatch):
    db = _db(tmp_path)

    def no_client(*a, **k):
        raise AssertionError("PC 수급 단계가 키움을 불렀다")

    monkeypatch.setattr(rf, "KiwoomClient", no_client)
    monkeypatch.setattr(rf, "refresh_investor_flows", no_client)
    monkeypatch.setattr(rf, "refresh_fx_wti", lambda **k: [])
    _run(tmp_path / "ev", T0, DAYS[:3])
    msg = rf.refresh_market_flow(
        db_path=db,
        now_utc=T0,
        refresh_id="r1",
        asof="2026-10-23",
        evidence_root=tmp_path / "ev",
        flow_pull=lambda: PullOutcome("ok"),
    )
    assert msg is None and len(_flows(db)) == 39


@pytest.mark.parametrize(
    "child_out, state",
    [
        (Child(0, {"status": "OK"}, False, "", ""), "ok"),
        (Child(2, {"status": "REPAIRED"}, False, "", ""), "ok"),
        (Child(3, {"status": "BUSY", "reason": "PULL_BUSY"}, False, "", ""), "busy"),
        (
            Child(
                2,
                {"status": "CHECK_REQUIRED", "error": "OCI 목록 조회 실패(rc 255)"},
                False,
                "",
                "",
            ),
            "unreachable",
        ),
        (
            Child(2, {"status": "CHECK_REQUIRED", "problems": ["x"]}, False, "", ""),
            "check",
        ),
        (Child(1, {"status": "FAILED"}, False, "", ""), "failed"),
        (Child(None, None, True, "", ""), "timeout"),
        (Child(1, None, False, "", ""), "failed"),
        (
            Child(
                1, {"status": "FAILED", "error": "TimeoutExpired: ssh"}, False, "", ""
            ),
            "unreachable",
        ),
    ],
)
def test_run_pull_maps_cli_result(tmp_path, child_out, state):
    seen = {}

    def child(argv, **kw):
        seen.update(argv=argv, **kw)
        return child_out

    po = REAL_RUN_PULL(root=tmp_path / "ev", child=child)
    assert po.state == state
    assert seen["argv"][-3:] == ["--root", str((tmp_path / "ev").resolve()), "pull"]
    assert seen["timeout_s"] == ofi.PULL_TIMEOUT_S == 150
    assert (po.reason is None) == (state == "ok")


def test_run_pull_child_exception_is_failed(tmp_path):
    def child(argv, **kw):
        raise OSError("x")

    assert REAL_RUN_PULL(root=tmp_path, child=child).state == "failed"


# ── 05 pull 동시 실행 잠금(판정 §2) ────────────────────────────────────────────


def test_pull_busy_does_not_touch_other_pull_workspace(tmp_path):
    pc, oci = tmp_path / "pc", tmp_path / "oci"
    daily_run(oci, T0, T0, [win("A", 1, "x")])
    other = pc / ".incoming" / "pull_other"
    other.mkdir(parents=True)
    (other / "f").write_text("x")
    remote = FakeRemote(oci)
    with store.file_lock(pc / transfer.PULL_LOCK) as ok:
        assert ok
        r = transfer.pull(root=pc, remote=remote, now=T0)
    assert r["status"] == "BUSY" and r["reason"] == "PULL_BUSY"
    assert r["problems"] == ["다른 가져오기 진행 중"] and r["pulled"] == []
    assert remote.calls == [] and (other / "f").exists()  # 원격 0 · 남의 임시 칸 그대로
    r2 = transfer.pull(root=pc, remote=remote, now=T0)  # 풀린 뒤 = 정상
    assert r2["status"] == "OK" and len(r2["pulled"]) == 1 and not other.exists()


def test_timed_out_pull_child_group_is_reaped_and_lock_released(tmp_path):
    ev = tmp_path / "ev"
    ev.mkdir()
    pidf = tmp_path / "grand.pid"
    code = (
        "import subprocess, sys, time\n"
        "from pathlib import Path\n"
        "from app.ml_evidence import store\n"
        f"with store.file_lock(Path({str(ev)!r}) / '.pull.lock') as ok:\n"
        "    g = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
        f"    Path({str(pidf)!r}).write_text(str(g.pid))\n"
        "    time.sleep(60)\n"
    )
    repo = Path(__file__).resolve().parents[1]
    env = dict(os.environ, PYTHONPATH=str(repo))
    t = time.monotonic()
    c = run_child(
        [sys.executable, "-c", code], cwd=repo, timeout_s=3, env=env, grace_s=1
    )
    assert c.timed_out and time.monotonic() - t < 20
    grand = int(pidf.read_text())
    for _ in range(50):
        try:
            os.kill(grand, 0)
        except ProcessLookupError:
            break
        time.sleep(0.1)
    else:
        pytest.fail("손자 프로세스(전송 흉내)가 남았다")
    with store.file_lock(ev / transfer.PULL_LOCK) as ok:
        assert ok  # 잠금이 영구로 남지 않음


def test_06_run_pull_records_busy_without_turning_it_into_success(
    tmp_path, monkeypatch, capsys
):
    from app.forward_compare import archive, forward
    from app.ml_evidence import daily
    from scripts import run_forward_compare as rfc

    busy = {
        "status": "BUSY",
        "reason": "PULL_BUSY",
        "problems": ["다른 가져오기 진행 중"],
    }
    monkeypatch.setattr(transfer, "pull", lambda **k: busy)
    monkeypatch.setattr(transfer, "default_remote", lambda: None)
    monkeypatch.setattr(forward, "run", lambda *a, **k: {"status": "NO_EVIDENCE"})
    monkeypatch.setattr(archive, "local_state", lambda *a: {})
    monkeypatch.setattr(daily, "git_head", lambda: "x")
    rc = rfc.main(
        [
            "--root",
            str(tmp_path / "r"),
            "--evidence",
            str(tmp_path / "e"),
            "run",
            "--pull",
        ]
    )
    line = [x for x in capsys.readouterr().out.splitlines() if x.startswith("RESULT ")][
        -1
    ]
    res = json.loads(line[7:])
    assert (
        res["pull"] == "BUSY" and res["status"] == "NO_EVIDENCE"
    )  # 주 기록 판정은 06 본래 결과
    assert isinstance(rc, int)


# ── 기준일 설명(판정 §4-4 · 설계 §5) ──────────────────────────────────────────


@pytest.mark.parametrize(
    "D, k, f, common, limited",
    [
        ("2026-10-30", "2026-10-30", "2026-10-30", True, None),
        ("2026-10-22", "2026-10-30", "2026-10-22", True, "flows"),
        ("2026-10-29", "2026-10-29", "2026-10-30", True, "kospi"),
        (
            "2026-10-27",
            "2026-10-30",
            "2026-10-29",
            True,
            "gap",
        ),  # 최신일이 달라도 중간 결측
        ("2026-10-27", "2026-10-30", "2026-10-30", True, "gap"),
        ("2026-10-30", "2026-10-30", "2026-10-29", False, "unknown"),
    ],
)
def test_end_basis_names_the_actual_limit(D, k, f, common, limited):
    b = end_basis(D=D, kospi_E=k, flows_E=f, common_ok=common, others=[])
    assert b["limited_by"] == limited


def test_end_basis_texts_and_later_short_series():
    b = end_basis(
        D="2026-10-22",
        kospi_E="2026-10-30",
        flows_E="2026-10-22",
        common_ok=True,
        others=[("원/달러", "2026-10-30"), ("WTI", "2026-10-22")],
    )
    assert b["text"] == (
        "코스피는 10/30, 수급은 10/22까지 있어 기간 비교는 10/22까지입니다 · "
        "원/달러 10/30 최근 값은 '최근 큰 변화'에 따로 보입니다"
    )
    assert (
        end_basis(
            D="2026-10-30",
            kospi_E="2026-10-30",
            flows_E=None,
            common_ok=False,
            others=[],
        )["text"]
        == "수급 자료가 없어 기간 비교는 코스피 10/30까지입니다"
    )


def _log(db, rid, source, fail, success=1, error=None):
    log_refresh(
        run_id=rid,
        source=source,
        asof="2026-11-02",
        attempted=1,
        success=success,
        fail=fail,
        runtime_seconds=0.0,
        error_summary=error,
        db_path=db,
    )


def test_flow_link_states_from_records(tmp_path):
    db = _db(tmp_path)
    assert read_flow_link(db, "2026-10-22")["state"] == "no_record"
    _log(
        db,
        "market-flow-flow-a",
        st.FLOW_LOG_SOURCE,
        1,
        0,
        "투자자 수급(키움 인증 실패 — 등록 IP · 앱키 확인)",
    )
    link = read_flow_link(db, "2026-10-22")
    assert link["state"] == "legacy_direct_failed" and link["retry_helps"] is True
    assert "키움 인증 실패" in link["text"] and "등록 IP" not in link["text"]
    _log(db, "market-flow-flowpull-b", st.FLOW_PULL_LOG_SOURCE, 0)
    _log(db, "market-flow-flowoci-b", st.FLOW_IMPORT_LOG_SOURCE, 0, 0)
    link = read_flow_link(db, "2026-10-30")
    # 가져오기 정상 · 반영한 OCI 묶음 없음 = 'OCI 수집본 기준'이라 쓰지 않음(검토 지적 7) · 다시 누르기 아님
    assert link["state"] == "no_record" and link["retry_helps"] is False
    assert "반영한 OCI 수급 묶음이 없습니다" in link["text"]
    assert (
        "키움" not in link["text"]
    )  # 뒤에 기록이 있으면 옛 실패를 현재 상태로 쓰지 않음
    con = sqlite3.connect(db)
    con.execute(ofi.IMPORT_DDL)
    con.execute(
        "INSERT INTO market_investor_flow_import VALUES ('r', 's', '2026-11-02T00:40:09.000000Z', "
        "'OK', 'APPLIED', '2026-10-01', '2026-10-30', 20, 0, 0, 0, 260, 0, NULL, 'x', 'b')"
    )
    con.commit()
    con.close()
    link = read_flow_link(db, "2026-10-30")
    assert link["state"] == "applied" and "새 자료 없음" in link["text"]


def test_flow_link_oci_collect_failed_blocks_retry_task(tmp_path):
    db, ev = _db(tmp_path), tmp_path / "ev"
    _run(ev, T0, DAYS[:3])
    _run(ev, T0 + timedelta(days=1), [], flow_status="FAILED", status="PARTIAL")
    ofi.refresh_flows_from_oci(
        db_path=db,
        refresh_id="r1",
        asof="2026-11-02",
        root=ev,
        pull=lambda: PullOutcome("ok"),
    )
    out = build_market_flow_context(db_path=db)
    assert out["end_basis"]["limited_by"] == "flows"  # 코스피 10/30 · 수급 10/22
    link = out["flow_link"]
    assert link["state"] == "oci_collect_failed" and link["retry_helps"] is False
    assert "다시 갱신해도 바뀌지 않을 수 있습니다" in link["text"]


def test_flow_link_apply_conflict_does_not_ask_to_press_again(tmp_path):
    db = _db(tmp_path)
    _log(db, "market-flow-flowpull-c", st.FLOW_PULL_LOG_SOURCE, 0)
    _log(
        db,
        "market-flow-flowoci-c",
        st.FLOW_IMPORT_LOG_SOURCE,
        1,
        0,
        "수급 값 충돌(2026-10-22 · 같은 관측 시각 또는 기존 시각 불명)",
    )
    link = read_flow_link(db, "2026-10-22")
    assert link["state"] == "apply_failed" and link["retry_helps"] is False


def test_flow_link_unreadable_db_is_unknown(tmp_path):
    bad = tmp_path / "m.sqlite"
    bad.write_bytes(b"not a database" * 100)
    link = read_flow_link(bad, None)
    assert link["state"] == "unknown" and link["retry_helps"] is False


def test_get_flow_context_writes_nothing_and_carries_new_fields(tmp_path, monkeypatch):
    db = _db(tmp_path)
    _pc_rows(db, DAYS[:3])
    _log(
        db,
        "market-flow-flow-a",
        st.FLOW_LOG_SOURCE,
        1,
        0,
        "투자자 수급(키움 인증 실패)",
    )
    before = (db.read_bytes(), db.stat().st_mtime_ns)
    monkeypatch.setattr(api_supply_fx_oil, "_DB_PATH", db)
    body = TestClient(app).get("/market/flow-context").json()
    assert (db.read_bytes(), db.stat().st_mtime_ns) == before
    assert body["end_basis"]["limited_by"] == "flows"
    assert body["flow_link"]["state"] == "legacy_direct_failed"
    six = body["ai_text"]["6M"].splitlines()
    assert six[1].startswith("- [기간 비교 기준일] 코스피는 10/30, 수급은 10/22까지")
    assert "수급 연결: 아직 OCI 수급을 반영한 기록 없음" in six[1]


def test_standalone_entry_runs_same_step_only(tmp_path, monkeypatch, capsys):
    db, ev = _db(tmp_path), tmp_path / "ev"
    _run(ev, T0, DAYS[:3])
    monkeypatch.setattr(ofi, "run_pull", lambda **k: PullOutcome("ok"))
    rc = ofi.main(["--db", str(db), "--root", str(ev)])
    out = [x for x in capsys.readouterr().out.splitlines() if x.startswith("RESULT ")]
    res = json.loads(out[-1][7:])
    assert rc == 0 and res["problems"] == [] and res["refresh_id"].startswith("manual-")
    assert len(_flows(db)) == 39
    con = sqlite3.connect(db)
    srcs = [
        r[0]
        for r in con.execute("SELECT source FROM market_refresh_log ORDER BY rowid")
    ]
    con.close()
    assert srcs[-2:] == [st.FLOW_PULL_LOG_SOURCE, st.FLOW_IMPORT_LOG_SOURCE]
    assert st.FX_WTI_LOG_SOURCE not in srcs  # 다른 공급자 단계 없음


# ── 독립 검토 지적 반영(2026-11-02) ─────────────────────────────────────────────


def test_unknown_flow_status_is_a_problem_not_silent_exclusion(tmp_path):
    db, ev = _db(tmp_path), tmp_path / "ev"
    r = _run(ev, T0, DAYS[:3], flow_status="ok")  # 오타 · 모르는 상태 + object 있음
    res = _apply(db, ev)
    assert res.excluded == [] and res.applied == []
    assert res.failed_run == r["run_id"] and "수급 상태" in res.fail_reason
    assert _imports(db) == [] and _flows(db) == {}


def test_unexpected_error_rolls_back_that_run_and_keeps_earlier_range(
    tmp_path, monkeypatch
):
    db, ev = _db(tmp_path), tmp_path / "ev"
    first = _run(ev, T0, DAYS[:2], v=1)
    second = _run(
        ev, T0 + timedelta(days=1), DAYS[1:3], v=2
    )  # 겹친 날 = 기존 행 시각 해석

    def boom(_text):
        raise RuntimeError("예상 밖")

    monkeypatch.setattr(ofi, "_row_time", boom)
    probs = ofi.refresh_flows_from_oci(
        db_path=db,
        refresh_id="r1",
        asof="2026-11-02",
        root=ev,
        pull=lambda: PullOutcome("ok"),
    )
    assert probs == ["투자자 수급(PC 표 반영 확인 필요(예상 밖 오류))"]
    f = _flows(db)
    assert {d for _, d, _ in f} == set(
        DAYS[:2]
    )  # 두 번째 묶음의 새 날(DAYS[2])도 되돌림
    assert f[("KOSPI", DAYS[1], "foreign")][0] == nets(1)["foreign"]
    assert [r[0] for r in _imports(db)] == [first["run_id"]]
    con = sqlite3.connect(db)
    row = con.execute(
        "SELECT success_count, fail_count FROM market_refresh_log WHERE source = ?",
        (st.FLOW_IMPORT_LOG_SOURCE,),
    ).fetchone()
    con.close()
    assert row == (1, 1)  # 앞서 끝난 범위(1 묶음)를 지우지 않음
    link = build_market_flow_context(db_path=db)["flow_link"]
    assert link["state"] == "apply_failed" and link["retry_helps"] is False
    assert second["run_id"] not in [r[0] for r in _imports(db)]


def test_oci_collect_failure_outranks_pull_failure(tmp_path):
    db, ev = _db(tmp_path), tmp_path / "ev"
    _run(ev, T0, DAYS[:3])
    ofi.refresh_flows_from_oci(
        db_path=db,
        refresh_id="r1",
        asof="2026-11-02",
        root=ev,
        pull=lambda: PullOutcome("ok"),
    )
    _run(
        ev, T0 + timedelta(days=1), [], flow_status="FAILED", status="PARTIAL"
    )  # 06 이 받아 둔 실패 묶음
    ofi.refresh_flows_from_oci(
        db_path=db,
        refresh_id="r2",
        asof="2026-11-02",
        root=ev,
        pull=lambda: PullOutcome("busy", "다른 가져오기 진행 중"),
    )
    out = build_market_flow_context(db_path=db)
    link = out["flow_link"]
    assert out["end_basis"]["limited_by"] == "flows"
    assert link["state"] == "oci_collect_failed" and link["retry_helps"] is False
    # 두 사실을 함께: 확인된 OCI 수집 실패 + 이번 가져오기 경합 · 새 자료 미확인(검증자 r1 F1 정정 뒤 형식)
    assert link["text"].startswith("OCI의 최근 수급 수집이 실패했습니다")
    assert "다른 가져오기 진행 중" in link["text"]
    assert "새 OCI 자료는 확인하지 못했습니다" in link["text"]


def test_unreadable_manifest_dir_stops_without_asking_to_press_again(tmp_path):
    db, ev = _db(tmp_path), tmp_path / "ev"
    ok = _run(ev, T0, DAYS[:2])
    later = _run(ev, T0 + timedelta(days=2), DAYS[2:4])
    bad = ev / "runs" / store.new_run_id(T0 + timedelta(days=1))
    bad.mkdir()
    (bad / "manifest.json").write_text("{깨짐")
    ofi.refresh_flows_from_oci(
        db_path=db,
        refresh_id="r1",
        asof="2026-11-02",
        root=ev,
        pull=lambda: PullOutcome("ok"),
    )
    assert [r[0] for r in _imports(db)] == [ok["run_id"]]
    assert later["run_id"] not in [r[0] for r in _imports(db)]
    link = build_market_flow_context(db_path=db)["flow_link"]
    assert (
        link["state"] == "apply_failed" and "묶음 목록을 읽을 수 없음" in link["text"]
    )
    assert link["retry_helps"] is False  # 다시 가져와도 되살아나지 않는 사유


def test_unknown_pull_failure_does_not_use_pc_copies(tmp_path):
    db, ev = _db(tmp_path), tmp_path / "ev"
    _pc_rows(db, DAYS[:3])
    _run(ev, datetime(2026, 11, 2, 0, 40, tzinfo=timezone.utc), DAYS)
    snap = _flows(db)
    probs = ofi.refresh_flows_from_oci(
        db_path=db,
        refresh_id="r1",
        asof="2026-11-02",
        root=ev,
        pull=lambda: PullOutcome("failed", "가져오기 실행 실패"),
    )
    assert probs == ["투자자 수급(가져오기 실행 실패)"]
    assert (
        _flows(db) == snap and _imports(db) == []
    )  # 판정 §3 — 알 수 없는 실패는 PC 사본 사용으로 넘기지 않음
    link = build_market_flow_context(db_path=db)["flow_link"]
    assert link["state"] == "kept_local"
    assert link["text"].startswith(
        "가져오기 실패(가져오기 실행 실패) · 기존 PC 수급(10/22까지) 유지"
    )


# ── 검증자 r1 F1 — 확인된 OCI 수집 실패가 다른 모든 상태보다 우선(판정 §4-4) ─────────────

BASES = {
    # 이름: (기록 준비, OCI 실패가 없을 때 기대 상태, 기대 retry, 문장에 남아야 할 조각)
    "legacy_fail": ("legacy", "legacy_direct_failed", True, "마지막 PC 직접 조회 실패"),
    "none": ("none", "no_record", True, "아직 OCI 수급을 반영한 기록 없음"),
    "applied": ("pull_ok:1", "applied", False, "수급은 OCI 수집본을 PC에 반영"),
    "applied_zero": ("pull_ok:0", "applied", False, "새 자료 없음"),
    "apply_fail_retry": (
        "fail:보관본 손상(수급 object)",
        "apply_failed",
        True,
        "보관본 손상",
    ),
    "apply_fail_noretry": (
        "fail:수급 값 충돌(x)",
        "apply_failed",
        False,
        "수급 값 충돌",
    ),
    "apply_fail_db": ("fail:PC 표 반영 실패", "apply_failed", True, "PC 표 반영 실패"),
    "busy_applied": ("busy:1", "applied_local", True, "PC에 이미 받은"),
    "busy_kept": ("busy:0", "kept_local", True, "기존 PC 수급"),
}


def _seed(db: Path, setup: str, oci: str | None, applied: bool) -> None:
    if setup == "legacy":
        _log(
            db,
            "market-flow-flow-a",
            st.FLOW_LOG_SOURCE,
            1,
            0,
            "투자자 수급(키움 인증 실패)",
        )
    elif setup != "none":
        kind, val = setup.split(":", 1)
        pull_fail = 1 if kind == "busy" else 0
        _log(
            db,
            "market-flow-flowpull-z",
            st.FLOW_PULL_LOG_SOURCE,
            pull_fail,
            1 - pull_fail,
            "다른 가져오기 진행 중" if pull_fail else None,
        )
        if kind == "fail":
            _log(db, "market-flow-flowoci-z", st.FLOW_IMPORT_LOG_SOURCE, 1, 0, val)
        else:
            _log(db, "market-flow-flowoci-z", st.FLOW_IMPORT_LOG_SOURCE, 0, int(val))
    con = sqlite3.connect(db)
    con.execute(ofi.IMPORT_DDL)
    rows = []
    if applied:
        rows.append(("a", "OK", "APPLIED", "2026-10-30T00:40:09.000000Z"))
    if oci is not None:
        res = "EXCLUDED_NO_FLOW" if oci == "FAILED" else "APPLIED"
        rows.append(("b", oci, res, "2026-11-02T00:40:09.000000Z"))
    for rid, status, res, pub in rows:
        con.execute(
            "INSERT INTO market_investor_flow_import VALUES (?, 's', ?, ?, ?, NULL, NULL, "
            "0, 0, 0, 0, 0, 0, NULL, 'x', 'z')",
            (rid, pub, status, res),
        )
    con.commit()
    con.close()


@pytest.mark.parametrize("oci", [None, "OK", "PARTIAL", "FAILED"])
@pytest.mark.parametrize("base", sorted(BASES))
def test_flow_link_precedence_table(tmp_path, base, oci):
    db = _db(tmp_path)
    setup, state, retry, frag = BASES[base]
    _seed(db, setup, oci, applied=True)
    link = read_flow_link(db, "2026-10-22")
    assert frag in link["text"]  # 다른 상태의 사실은 어느 경우에도 문장에 남는다
    if oci == "FAILED":
        assert link["state"] == "oci_collect_failed" and link["retry_helps"] is False
        assert link["text"].startswith("OCI의 최근 수급 수집이 실패했습니다")
        assert "다시 갱신해도 바뀌지 않을 수 있습니다" in link["text"]
    else:
        assert (link["state"], link["retry_helps"]) == (state, retry)
    # 가장 최근 공개 묶음의 수급 상태(OCI 상태 행이 없으면 앞서 반영한 OK 묶음)
    assert link["oci_flow_status"] == (oci or "OK")


def test_flow_link_precedence_pull_ok_without_applied_runs(tmp_path):
    db = _db(tmp_path)
    _seed(db, "pull_ok:0", None, applied=False)
    link = read_flow_link(db, "2026-10-22")
    assert (link["state"], link["retry_helps"]) == ("no_record", False)
    db2 = _db(tmp_path / "b")
    _seed(db2, "pull_ok:0", "FAILED", applied=False)
    link = read_flow_link(db2, "2026-10-22")
    assert (link["state"], link["retry_helps"]) == ("oci_collect_failed", False)
    assert "반영한 OCI 수급 묶음이 없습니다" in link["text"]


def test_verifier_repro_a_apply_start_error_after_oci_collect_failure(
    tmp_path, monkeypatch
):
    db, ev = _db(tmp_path), tmp_path / "ev"
    _run(ev, T0, DAYS[:3])
    _run(ev, T0 + timedelta(days=1), [], flow_status="FAILED", status="PARTIAL")
    ok = lambda: PullOutcome("ok")  # noqa: E731
    ofi.refresh_flows_from_oci(db_path=db, refresh_id="r1", asof="d", root=ev, pull=ok)
    first = build_market_flow_context(db_path=db)["flow_link"]
    assert (first["state"], first["retry_helps"]) == ("oci_collect_failed", False)

    def broken(_db):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(
        ofi, "init_market_flow_tables", broken
    )  # 다음 실행의 반영 시작 오류
    probs = ofi.refresh_flows_from_oci(
        db_path=db, refresh_id="r2", asof="d", root=ev, pull=ok
    )
    assert probs == ["투자자 수급(PC 표 반영 실패)"]
    out = build_market_flow_context(db_path=db)
    link = out["flow_link"]
    assert (link["state"], link["retry_helps"], link["oci_flow_status"]) == (
        "oci_collect_failed",
        False,
        "FAILED",
    )
    assert "OCI의 최근 수급 수집이 실패했습니다" in link["text"]
    assert "수급 자료 반영 실패(" in link["text"] and "PC 표 반영 실패" in link["text"]


def test_verifier_repro_b_late_older_damaged_run_after_oci_collect_failure(tmp_path):
    db, ev = _db(tmp_path), tmp_path / "ev"
    _run(ev, T0, DAYS[:3])
    _run(ev, T0 + timedelta(days=2), [], flow_status="FAILED", status="PARTIAL")
    ok = lambda: PullOutcome("ok")  # noqa: E731
    ofi.refresh_flows_from_oci(db_path=db, refresh_id="r1", asof="d", root=ev, pull=ok)
    late = _run(
        ev, T0 + timedelta(days=1), DAYS[3:5]
    )  # 최신 FAILED 보다 오래된 묶음이 늦게 도착
    victim = store.object_path(ev, late["sources"]["investor_flow"]["objects"][0])
    victim.chmod(0o644)
    victim.write_bytes(b"{}")
    ofi.refresh_flows_from_oci(db_path=db, refresh_id="r2", asof="d", root=ev, pull=ok)
    link = build_market_flow_context(db_path=db)["flow_link"]
    assert (link["state"], link["retry_helps"]) == ("oci_collect_failed", False)
    assert (
        "보관본 손상" in link["text"]
        and "OCI의 최근 수급 수집이 실패했습니다" in link["text"]
    )
