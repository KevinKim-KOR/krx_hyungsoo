"""POC5-18 — PC 시장 갱신의 예상 밖 오류 상태 정정(`DEF-PC-REFRESH-UNEXPECTED-COMPLETED`).

설계 docs/ai_design/POC5/POC5-18_PC_MARKET_REFRESH_UNEXPECTED_FAILURE_STATUS_DESIGN_V1.md §3 · §6
PLAN docs/ai_plan/POC5/POC5-18_PC_MARKET_REFRESH_UNEXPECTED_FAILURE_STATUS_PLAN_V1.md §2 · §3
tmp DB · 기존 시험 주입 지점(svc fixture · SQLite 시험용 트리거). 외부 조회 · 라이브 DB 0.
"""

from __future__ import annotations

import sqlite3
from datetime import timedelta

import pytest

from app import market_refresh_service
from app.market_refresh_service import get_state_snapshot, start_refresh_job
from app.market_refresh_state_store import read_state
from app.market_refresh_vix_retry import get_vix_retry_snapshot
from app.pc_vix_refresh import VIX_STEP_FAILED_TEXT
from tests.test_market_vix_retry import MORNING_KST_UTC, svc  # noqa: F401
from tests.test_pc_refresh_stall_protection import (
    END,
    TICKERS,
    _block_price_log,
    _ok,
    _run,
)


def _boom(*a, **kw):
    raise RuntimeError("list read failed")


def _saved_dates(db, ticker: str) -> list[str]:
    con = sqlite3.connect(str(db))
    try:
        return [
            d
            for (d,) in con.execute(
                "SELECT date FROM etf_daily_price WHERE ticker = ? ORDER BY date",
                (ticker,),
            )
        ]
    finally:
        con.close()


# ── 종목 목록 읽기 오류 ──────────────────────────────────────────────────────────
def test_list_read_error_is_failed_in_memory_and_store_and_rerun_accepted(
    svc: dict, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    monkeypatch.setattr(market_refresh_service, "list_etf_tickers", _boom)
    _run(svc, _ok)
    snap = get_state_snapshot(db_path=svc["db"])
    assert snap.status == "failed"
    assert snap.error_summary.startswith("refresh_unexpected: RuntimeError")
    assert snap.cooldown_remaining_seconds == 0  # 새 성공 시각 · 대기 없음
    row = read_state(db_path=svc["db"])
    assert (row.last_attempt_status, row.last_success_at) == ("failed", None)
    assert "kospi" in svc["calls"] and "nav" in svc["calls"]  # 뒤 단계는 기존 흐름대로
    assert _run(svc, _ok).status == "accepted"


def test_failed_run_keeps_the_previous_success_record(
    svc: dict, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    earlier = MORNING_KST_UTC - timedelta(hours=7)  # 대기가 끝난 이전 성공
    monkeypatch.setattr(market_refresh_service, "_utcnow", lambda: earlier)
    _run(svc, _ok)
    before = read_state(db_path=svc["db"])
    assert before.last_attempt_status == "completed"

    monkeypatch.setattr(market_refresh_service, "_utcnow", lambda: MORNING_KST_UTC)
    monkeypatch.setattr(market_refresh_service, "list_etf_tickers", _boom)
    assert _run(svc, _ok).status == "accepted"
    after = read_state(db_path=svc["db"])
    assert after.last_attempt_status == "failed"
    # 이전 정상 성공을 오류 시각으로 덮거나 지우지 않는다.
    assert (after.last_success_at, after.last_success_asof_date) == (
        before.last_success_at,
        before.last_success_asof_date,
    )
    assert get_state_snapshot(db_path=svc["db"]).cooldown_remaining_seconds == 0


# ── 중단 없는 가격 기록 오류 ─────────────────────────────────────────────────────
def test_price_log_error_without_stop_is_failed_and_saved_prices_kept(
    svc: dict,  # noqa: F811
) -> None:
    _block_price_log(svc["db"])
    _run(svc, _ok)
    snap = get_state_snapshot(db_path=svc["db"])
    assert snap.status == "failed"
    assert snap.error_summary.startswith("refresh_unexpected: ")
    assert "price log blocked" in snap.error_summary
    assert snap.cooldown_remaining_seconds == 0
    for t in TICKERS[:8]:  # 받은 가격은 그대로(롤백 · 삭제 없음)
        assert END.isoformat() in _saved_dates(svc["db"], t)
    assert read_state(db_path=svc["db"]).last_attempt_status == "failed"
    assert _run(svc, _ok).status == "accepted"


# ── 실행 간 분리 · 대조 ─────────────────────────────────────────────────────────
def test_error_run_then_normal_rerun_then_existing_cooldown(
    svc: dict, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    real = market_refresh_service.list_etf_tickers
    monkeypatch.setattr(market_refresh_service, "list_etf_tickers", _boom)
    _run(svc, _ok)
    assert get_state_snapshot(db_path=svc["db"]).status == "failed"
    # 오류 원인을 걷어낸 새 실행 — 이전 실행의 표식을 물려받지 않는다.
    monkeypatch.setattr(market_refresh_service, "list_etf_tickers", real)
    assert _run(svc, _ok).status == "accepted"
    snap = get_state_snapshot(db_path=svc["db"])
    assert (snap.status, snap.error_summary) == ("completed", None)
    assert snap.cooldown_remaining_seconds > 0
    assert _run(svc, _ok).status == "skipped_cooldown"


def test_normal_run_still_completes_with_cooldown(svc: dict) -> None:  # noqa: F811
    _run(svc, _ok)
    snap = get_state_snapshot(db_path=svc["db"])
    assert (snap.status, snap.error_summary) == ("completed", None)
    assert snap.cooldown_remaining_seconds > 0


# ── VIX 다시 받기 ──────────────────────────────────────────────────────────────
def test_unexpected_error_with_vix_failure_sets_no_vix_marker(
    svc: dict, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    svc["vix"] = VIX_STEP_FAILED_TEXT
    monkeypatch.setattr(market_refresh_service, "list_etf_tickers", _boom)
    _run(svc, _ok)
    assert get_state_snapshot(db_path=svc["db"]).status == "failed"
    marker = get_vix_retry_snapshot(svc["db"])  # 표식 행이 없으면 None
    assert marker is None or marker["needed"] is False


def test_vix_only_failure_marker_unchanged(svc: dict) -> None:  # noqa: F811
    svc["vix"] = VIX_STEP_FAILED_TEXT
    _run(svc, _ok)
    assert get_state_snapshot(db_path=svc["db"]).status == "completed"
    assert get_vix_retry_snapshot(svc["db"])["needed"] is True


# ── 실제 서비스 실행 경로로 한 번 더(백그라운드 실행기 대신 동기 실행) ──────────────────
def test_start_refresh_job_records_failed_when_list_read_fails(
    svc: dict, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    monkeypatch.setattr(market_refresh_service, "list_etf_tickers", _boom)
    res = start_refresh_job(
        db_path=svc["db"],
        cooldown_hours=6,
        universe_fetcher=svc["universe"],
        price_fetcher=_ok,
        end_date_for_prices=END,
        thread_runner=lambda runner: runner(),
    )
    assert res.status == "accepted"
    assert read_state(db_path=svc["db"]).last_attempt_status == "failed"
