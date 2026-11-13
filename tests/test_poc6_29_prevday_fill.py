"""POC6-29 보완 2차 — ③ 전일 자료 보충(PLAN §10-4 · S 판정 Q-S2 · Q-S3).

전부 tmp 시장 DB · tmp 보관소 · 가짜 수집 함수(KRX · Yahoo · FDR · SSH 0 · 라이브 DB 0). 기준 시각 =
2026-10-30(금) 09:30 KST → 기준일 10/29.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app import market_refresh_service as svc
from app import oci_flow_import as ofi
from app import pc_prevday_fill as pf
from app import pc_refresh_all as ra
from app import supply_fx_oil_store as st
from app.market_benchmark_store import KOSPI_SOURCE
from app.market_data_store import latest_refresh_log
from app.market_refresh_state_store import (
    VIX_RETRY_SCOPE,
    MarketRefreshStateRow,
    read_state,
    write_state,
)
from app.market_refresh_vix_retry import start_vix_retry_job
from app.supply_fx_oil_basis import read_flow_link
from tests.test_poc6_17_flow_import import CLOSE, _run
from tests.test_poc6_29_morning_basis import EXPECTED, NOW, _seed
from tests.test_poc6_29_refresh_all import _market

LATE = "2026-10-28"


def _fill(db: Path, root: Path | None = None, **kw) -> dict:
    return pf.run_prevday_fill(
        db_path=db, now=NOW, evidence_root=root or db.parent / "evidence", **kw
    )


def _never(*_a, **_k):
    raise AssertionError("부르면 안 되는 수집")


# ── 묶음 작업: ② 가 대기일 때만 ③ ─────────────────────────────────────────


def _job(market_status: str, filler) -> dict:
    ra.reset_for_testing()
    ra.start_refresh_all(
        quick_refresher=lambda: {
            "status": "done",
            "fetched_at": "x",
            "items": {},
            "message": None,
        },
        holdings_refresher=lambda: (_ for _ in ()).throw(RuntimeError("보유 없음")),
        market_starter=_market(
            market_status, 600 if market_status == "skipped_cooldown" else 0
        ),
        prevday_filler=filler,
        thread_runner=lambda fn: fn(),
    )
    return ra.snapshot()


def test_prevday_runs_only_when_market_waits():
    calls = []
    snap = _job(
        "skipped_cooldown",
        lambda: calls.append(1) or {"status": "done", "id": "p", "items": {}},
    )
    assert calls == [1]
    assert snap["steps"]["prevday"] == {"status": "done", "id": "p", "items": {}}
    assert snap["state"] == "done"


@pytest.mark.parametrize(
    "status, reason",
    [
        ("accepted", "시장 전체 갱신을 시작했습니다 — 같은 수집에서 받습니다"),
        ("running", "시장 전체 갱신이 진행 중입니다 — 같은 수집에서 받습니다"),
        ("vix_retry_running", "VIX 다시 받기가 진행 중입니다"),
        ("prevday_running", "전일 자료 보충이 이미 진행 중입니다"),
        (
            "failed_to_start",
            "시장 갱신을 시작하지 못해 전일 자료 보충도 하지 않았습니다",
        ),
    ],
)
def test_prevday_shares_or_skips_when_market_not_waiting(status, reason):
    snap = _job(status, _never)
    assert snap["steps"]["prevday"]["status"] == "skipped"
    assert snap["steps"]["prevday"]["reason"] == reason


def test_prevday_exception_is_a_failed_step_and_job_finishes():
    def boom():
        raise RuntimeError("x")

    snap = _job("skipped_cooldown", boom)
    assert snap["steps"]["prevday"]["status"] == "failed"
    assert snap["steps"]["prevday"]["reason"] == ra.PREVDAY_ERROR_TEXT
    assert snap["state"] == "done"


# ── 잠금(기존 전체 갱신 잠금 · VIX 다시 받기와 같은 방식) ──────────────────


def test_skips_when_full_refresh_or_vix_retry_or_itself_running(tmp_path, monkeypatch):
    db = _seed(tmp_path)
    monkeypatch.setattr(svc._service.state, "status", "running")
    assert (
        _fill(db)["reason"] == "시장 전체 갱신이 진행 중입니다 — 같은 수집에서 받습니다"
    )
    monkeypatch.setattr(svc._service.state, "status", "completed")
    write_state(
        MarketRefreshStateRow(refresh_id="v", last_attempt_status="running"),
        db_path=db,
        scope=VIX_RETRY_SCOPE,
    )
    assert _fill(db)["reason"] == "VIX 다시 받기가 진행 중입니다"
    write_state(
        MarketRefreshStateRow(refresh_id="v", last_attempt_status="needed"),
        db_path=db,
        scope=VIX_RETRY_SCOPE,
    )
    monkeypatch.setattr(svc._service, "prevday_running", True)
    out = _fill(db)
    assert out["status"] == "skipped" and out["reason"] == svc.PREVDAY_RUNNING_TEXT
    assert not pf.PREVDAY_FILE.exists()  # 건너뜀은 결과 파일을 쓰지 않음


def test_full_refresh_and_vix_retry_refused_while_prevday_runs(tmp_path):
    db = _seed(tmp_path)
    write_state(
        MarketRefreshStateRow(refresh_id="v", last_attempt_status="needed"),
        db_path=db,
        scope=VIX_RETRY_SCOPE,
    )
    seen = {}

    def kospi():
        seen["full"] = svc.start_refresh_job(db_path=db, thread_runner=_never)
        seen["vix"] = start_vix_retry_job(db_path=db, thread_runner=_never)
        return {"status": "ok"}

    con = sqlite3.connect(db)
    con.execute(
        "DELETE FROM market_benchmark_daily_price WHERE benchmark_id='KOSPI' AND date=?",
        (EXPECTED,),
    )
    con.commit()
    con.close()
    _fill(
        db,
        kospi_refresher=kospi,
        vix_refresher=_never,
        fxwti_refresher=_never,
        flows_refresher=_never,
    )
    for k in ("full", "vix"):
        assert (
            seen[k].status == "prevday_running"
            and seen[k].message == svc.PREVDAY_RUNNING_TEXT
        )
    assert svc._service.prevday_running is False  # 끝나면 풀림
    assert (
        svc.start_refresh_job(db_path=db, thread_runner=lambda fn: None).status
        == "accepted"
    )
    svc.reset_state_for_testing(db)


def test_flag_released_even_when_fill_crashes(tmp_path, monkeypatch):
    db = _seed(tmp_path)

    def boom(_db):
        raise RuntimeError("x")

    monkeypatch.setattr(pf, "stored_dates", boom)
    with pytest.raises(RuntimeError):
        _fill(db)
    assert svc._service.prevday_running is False


# ── 모자란 것만 · 기존 경로 · 기록 구분 ────────────────────────────────────


def test_only_late_items_are_fetched(tmp_path):
    db = _seed(tmp_path, flows_last=LATE)
    seen = []
    out = _fill(
        db,
        kospi_refresher=_never,
        vix_refresher=_never,
        fxwti_refresher=_never,
        flows_refresher=lambda skip: seen.append(skip) or [],
    )
    assert out["status"] == "done" and out["expected_date"] == EXPECTED
    it = out["items"]
    assert [it[k]["status"] for k in ("kospi", "vix", "usdkrw", "wti")] == [
        "already",
        "already",
        "already",
        "skipped",
    ]
    assert seen == [False] and it["flows"]["via"] == "pull"
    # 가짜 반영이 날짜를 올리지 않았으니 '새 자료 없음'(확인된 사실만)
    assert it["flows"]["status"] == "unchanged"
    assert it["flows"]["reason"] == "OCI 수집본에 기준일 자료 없음"
    saved = json.loads(pf.PREVDAY_FILE.read_text(encoding="utf-8"))
    assert saved["id"] == out["id"] and saved["items"]["flows"]["before"] == LATE


def test_flows_copy_in_pc_store_is_applied_without_pull(tmp_path, monkeypatch):
    db = _seed(tmp_path, flows_last=LATE)
    root = tmp_path / "evidence"
    from app.market_benchmark_store import upsert_benchmark_prices

    upsert_benchmark_prices(  # 묶음의 지수값과 PC 코스피가 같아야 반영(기존 검사 그대로)
        benchmark_id="KOSPI",
        benchmark_name="KOSPI",
        rows=[(d, CLOSE[d]) for d in ("2026-10-28", EXPECTED)],
        source=KOSPI_SOURCE,
        db_path=db,
    )
    _run(
        root,
        datetime(2026, 10, 30, 0, 40, tzinfo=timezone.utc),
        ["2026-10-28", EXPECTED],
    )
    monkeypatch.setattr(ofi, "run_pull", _never)
    out = _fill(
        db, root, kospi_refresher=_never, vix_refresher=_never, fxwti_refresher=_never
    )
    f = out["items"]["flows"]
    assert (f["status"], f["via"], f["before"], f["after"]) == (
        "applied",
        "local",
        LATE,
        EXPECTED,
    )
    pull = latest_refresh_log(source=st.FLOW_PULL_LOG_SOURCE, db_path=db)
    assert (pull["attempted_count"], pull["success_count"], pull["fail_count"]) == (
        0,
        0,
        0,
    )
    assert out["id"] in pull["run_id"]
    link = read_flow_link(db, EXPECTED)
    assert link["state"] == "applied" and "가져오기 실패" not in link["text"]


def test_copy_short_of_basis_day_takes_pull_path(tmp_path):
    db = _seed(tmp_path, flows_last=LATE)
    root = tmp_path / "evidence"
    _run(root, datetime(2026, 10, 29, 0, 40, tzinfo=timezone.utc), ["2026-10-27", LATE])
    assert pf.local_flow_cover(root, db, EXPECTED) is None  # 기준일을 못 채운 묶음
    seen = []
    out = _fill(
        db,
        root,
        kospi_refresher=_never,
        vix_refresher=_never,
        fxwti_refresher=_never,
        flows_refresher=lambda skip: seen.append(skip) or [],
    )
    assert seen == [False]
    assert (
        out["items"]["flows"]["reason"]
        == "OCI 수집본에 기준일 자료 없음(마지막 수집본 10/28까지)"
    )


@pytest.mark.parametrize(
    "result, status, reason, after",
    [
        ({"status": "ok"}, "fetched", None, EXPECTED),
        (
            {"status": "failed", "error": "api_key_missing"},
            "failed",
            "설정 확인 필요(KRX 키 없음)",
            LATE,
        ),
        (
            {
                "status": "failed",
                "error": "source_stale:as_of=2026-10-28,expected=2026-10-29,lag=1",
            },
            "unchanged",
            "KRX 에 아직 기준일 자료가 없음",
            LATE,
        ),
        (
            {"status": "failed", "error": "fetch_failed:Timeout"},
            "failed",
            "KRX 받기 실패",
            LATE,
        ),
        (
            {"status": "failed", "error": "evidence_write_failed:x"},
            "failed",
            "KRX 자료 확인 필요",
            LATE,
        ),
    ],
)
def test_kospi_result_maps_to_confirmed_reason_and_no_kospi_log_row(
    tmp_path, result, status, reason, after
):
    db = _seed(tmp_path, kospi_last=LATE)

    def kospi():
        if result["status"] == "ok":
            from app.market_benchmark_store import upsert_benchmark_prices

            upsert_benchmark_prices(
                benchmark_id="KOSPI",
                benchmark_name="KOSPI",
                rows=[(EXPECTED, 5001.0)],
                source=KOSPI_SOURCE,
                db_path=db,
            )
        return result

    state_before = read_state(db_path=db)
    out = _fill(
        db,
        kospi_refresher=kospi,
        vix_refresher=_never,
        fxwti_refresher=_never,
        flows_refresher=_never,
    )
    k = out["items"]["kospi"]
    assert (k["status"], k["reason"], k["after"]) == (status, reason, after)
    assert (
        latest_refresh_log(source=KOSPI_SOURCE, db_path=db) is None
    )  # '마지막 전체 갱신' 행 없음
    assert read_state(db_path=db) == state_before  # 전체 갱신 상태 · 마지막 성공 그대로


def test_vix_and_fx_wti_use_source_rules_and_fx_log_is_market_flow_source(tmp_path):
    db = _seed(tmp_path, vix_last="2026-10-27", fx_last=LATE)
    calls = []
    out = _fill(
        db,
        kospi_refresher=_never,
        flows_refresher=_never,
        vix_refresher=lambda: calls.append("vix")
        or "시장 불안 지표(VIX)를 갱신하지 못했습니다",
        fxwti_refresher=lambda: calls.append("fx") or ["WTI"],
    )
    assert calls == ["vix", "fx"]
    it = out["items"]
    assert (it["vix"]["status"], it["vix"]["reason"]) == (
        "failed",
        "시장 불안 지표(VIX)를 갱신하지 못했습니다",
    )
    assert it["usdkrw"]["status"] == "failed" and it["wti"]["reason"] == "WTI"
    row = latest_refresh_log(source=st.FX_WTI_LOG_SOURCE, db_path=db)
    assert row["run_id"] == f"market-flow-fxwti-{out['id']}" and row["fail_count"] == 1
    # '마지막 전체 갱신'(시장 흐름 출처 제외 계산)에 ③ 행이 잡히지 않는다
    assert st.FX_WTI_LOG_SOURCE in st.MARKET_FLOW_LOG_SOURCES


def test_one_item_crash_does_not_stop_others(tmp_path):
    db = _seed(tmp_path, kospi_last=LATE, flows_last=LATE)

    def boom():
        raise RuntimeError("x")

    seen = []
    out = _fill(
        db,
        kospi_refresher=boom,
        flows_refresher=lambda skip: seen.append(skip)
        or ["투자자 수급(OCI 연결 실패)"],
        vix_refresher=_never,
        fxwti_refresher=_never,
    )
    assert (out["items"]["kospi"]["status"], out["items"]["kospi"]["reason"]) == (
        "failed",
        pf.ERROR_TEXT,
    )
    assert seen == [False]
    assert (out["items"]["flows"]["status"], out["items"]["flows"]["reason"]) == (
        "failed",
        "OCI 연결 실패",
    )
