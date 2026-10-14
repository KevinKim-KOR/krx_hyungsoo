"""POC5-12 — VIX 최신성 판정 · 'VIX 다시 받기'(설계 §2 · §3 · PLAN §1 · §2 · §7 판정 Q1~Q3 · §3).

격리 DB(tmp) · 가짜 수집기 · 고정 시각만 쓴다. 외부 호출 0 · 라이브 DB 0.
"""

from __future__ import annotations

import sqlite3
import types
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app import (
    api_market_topn,
    api_market_topn_service,
    market_refresh_service,
    market_refresh_vix_retry,
)
from app.market_benchmark_store import latest_benchmark_date, upsert_benchmark_prices
from app.market_data_store import init_db
from app.market_refresh_service import (
    get_state_snapshot,
    reset_state_for_testing,
    start_refresh_job,
)
from app.market_refresh_state_store import (
    VIX_RETRY_SCOPE,
    MarketRefreshStateRow,
    read_state,
    write_state,
)
from app.market_refresh_vix_retry import get_vix_retry_snapshot, start_vix_retry_job
from app.pc_vix_refresh import VIX_STEP_FAILED_TEXT, vix_freshness

# 한국 시각 2026-10-14(수) 15:41 = 미국 동부 10-14 02:41 — 첨부 사례(E = 10-13).
CASE_UTC = datetime(2026, 10, 14, 6, 41, tzinfo=timezone.utc)
# 한국 시각 2026-10-14(수) 07:00 = 미국 동부 10-13(화) 18:00 — 10-13 마감 뒤.
MORNING_KST_UTC = datetime(2026, 10, 13, 22, 0, tzinfo=timezone.utc)


# ── 최신성 판정(PLAN §1) ──────────────────────────────────────────────────────
@pytest.mark.parametrize(
    ("as_of", "now_utc", "state", "compare", "behind"),
    [
        # 첨부 사례 — 10-14 15:41 KST · D = 10-13 → 경고 없음
        ("2026-10-13", CASE_UTC, "fresh", "2026-10-13", 0),
        ("2026-10-12", CASE_UTC, "one_weekday_behind", "2026-10-13", 1),
        ("2026-10-09", CASE_UTC, "update_check", "2026-10-13", 2),  # 금 → 월 · 화
        ("2026-10-01", CASE_UTC, "update_check", "2026-10-13", 8),
        # 미국 마감 전 · 후(서머타임 EDT 16:30 = 20:30Z)
        (
            "2026-10-12",
            datetime(2026, 10, 13, 20, 29, tzinfo=timezone.utc),
            "fresh",
            "2026-10-12",
            0,
        ),
        (
            "2026-10-12",
            datetime(2026, 10, 13, 20, 30, tzinfo=timezone.utc),
            "one_weekday_behind",
            "2026-10-13",
            1,
        ),
        # 표준시(EST 16:30 = 21:30Z)
        (
            "2026-12-14",
            datetime(2026, 12, 15, 21, 29, tzinfo=timezone.utc),
            "fresh",
            "2026-12-14",
            0,
        ),
        (
            "2026-12-14",
            datetime(2026, 12, 15, 21, 30, tzinfo=timezone.utc),
            "one_weekday_behind",
            "2026-12-15",
            1,
        ),
        # 토 · 일 · 월요일 아침(한국) — 주말은 지연을 늘리지 않는다(E = 금)
        (
            "2026-10-09",
            datetime(2026, 10, 10, 15, 0, tzinfo=timezone.utc),
            "fresh",
            "2026-10-09",
            0,
        ),  # 미국 토 11:00
        (
            "2026-10-09",
            datetime(2026, 10, 11, 15, 0, tzinfo=timezone.utc),
            "fresh",
            "2026-10-09",
            0,
        ),  # 미국 일 11:00
        (
            "2026-10-09",
            datetime(2026, 10, 11, 22, 0, tzinfo=timezone.utc),
            "fresh",
            "2026-10-09",
            0,
        ),  # 한국 월 07:00 = 미국 일 18:00
        (
            "2026-10-08",
            datetime(2026, 10, 11, 22, 0, tzinfo=timezone.utc),
            "one_weekday_behind",
            "2026-10-09",
            1,
        ),
        # 날짜 없음 · 해석 불가 · D > E
        (None, CASE_UTC, "date_check", "2026-10-13", None),
        ("", CASE_UTC, "date_check", "2026-10-13", None),
        ("2026-13-01", CASE_UTC, "date_check", "2026-10-13", None),
        ("2026-10-14", CASE_UTC, "date_check", "2026-10-13", None),
    ],
)
def test_vix_freshness(as_of, now_utc, state, compare, behind) -> None:
    assert vix_freshness(as_of, now_utc) == {
        "state": state,
        "compare_date": compare,
        "weekdays_behind": behind,
    }


def _seed_vix(db: Path, rows: list[tuple[str, float]]) -> None:
    upsert_benchmark_prices(
        benchmark_id="VIX",
        benchmark_name="VIX",
        rows=rows,
        source="FDR_VIX",
        db_path=db,
    )


def test_pc_payload_adds_freshness_and_keeps_original_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """PC 응답 조립만 선택 필드를 붙인다. 기준일 · 종가는 공유 builder 값 그대로."""
    from app.market_risk_reference_service import build_market_risk_reference

    db = tmp_path / "market_data.sqlite"
    init_db(db)
    _seed_vix(db, [("2026-10-12", 19.5), ("2026-10-13", 20.25)])
    monkeypatch.setattr(api_market_topn_service, "_now_utc", lambda: CASE_UTC)
    payload = api_market_topn_service.build_market_risk_reference_payload(db)
    shared = build_market_risk_reference(db_path=db)
    assert payload.vix.as_of_date == shared.vix.as_of_date == "2026-10-13"
    assert payload.vix.close == shared.vix.close == 20.25
    assert payload.vix.freshness.model_dump() == {
        "state": "fresh",
        "compare_date": "2026-10-13",
        "weekdays_behind": 0,
    }
    # 공유 builder(결정 초안 미리보기도 사용)에는 판정이 없다.
    assert not hasattr(shared.vix, "freshness")

    monkeypatch.setattr(
        api_market_topn_service,
        "_now_utc",
        lambda: datetime(2026, 10, 15, 22, 0, tzinfo=timezone.utc),
    )  # E = 10-15 → 10-14 · 10-15 두 평일
    late = api_market_topn_service.build_market_risk_reference_payload(db)
    assert late.vix.freshness.state == "update_check"
    assert late.vix.freshness.weekdays_behind == 2
    assert late.vix.as_of_date == "2026-10-13"  # 기준일을 오늘로 고쳐 쓰지 않음


def test_pc_payload_without_vix_keeps_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = tmp_path / "market_data.sqlite"
    init_db(db)
    monkeypatch.setattr(api_market_topn_service, "_now_utc", lambda: CASE_UTC)
    payload = api_market_topn_service.build_market_risk_reference_payload(db)
    assert payload.vix.availability == "unavailable"
    assert payload.vix.as_of_date is None
    assert payload.vix.freshness.state == "date_check"


# ── 'VIX 다시 받기' 표식 · 실행(PLAN §2 · §7) ─────────────────────────────────
def _universe_df(tickers=("069500",)) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Symbol": t,
                "Category": 1,
                "Name": t,
                "Price": 1.0,
                "Volume": 1,
                "MarCap": 1.0,
            }
            for t in tickers
        ]
    )


def _price_fetcher(ticker, start, end):
    idx = pd.to_datetime(["2026-10-12", "2026-10-13"])
    return pd.DataFrame(
        {
            "Open": [1.0, 1.0],
            "High": [1.0, 1.0],
            "Low": [1.0, 1.0],
            "Close": [1.0, 1.0],
            "Volume": [1, 1],
            "Change": [0.0, 0.0],
        },
        index=idx,
    )


NAV_OK = types.SimpleNamespace(status="ok")


@pytest.fixture
def svc(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    """격리 DB · 다른 단계 성공 stub · VIX 단계 결과는 시험마다 `rig['vix']` 로 정한다."""
    db = tmp_path / "market_data.sqlite"
    monkeypatch.setattr("app.market_data_store.DEFAULT_DB_PATH", db, raising=True)
    monkeypatch.setattr("app.market_refresh_service.DEFAULT_DB_PATH", db, raising=True)
    monkeypatch.setattr(
        "app.market_briefing.calendar.CALENDAR_DIR", tmp_path / "no_cal"
    )
    rig: dict = {"db": db, "calls": [], "vix": None, "nav": NAV_OK}

    def rec(name, ret):
        def f(**kw):
            rig["calls"].append(name)
            return ret() if callable(ret) else ret

        return f

    def vix(**kw):
        rig["calls"].append("vix")
        out = rig["vix"]
        if isinstance(out, Exception):
            raise out
        if out is None:
            _seed_vix(db, [("2026-10-13", 20.0)])
        return out

    def nav(**kw):
        rig["calls"].append("nav")
        if isinstance(rig["nav"], Exception):
            raise rig["nav"]
        return rig["nav"]

    monkeypatch.setattr(
        market_refresh_service, "_regenerate_intraday_config", lambda db_path: None
    )
    monkeypatch.setattr(
        market_refresh_service,
        "refresh_kospi_benchmark",
        rec("kospi", {"status": "ok", "error": None}),
    )
    monkeypatch.setattr(
        market_refresh_service, "refresh_holdings_equity_prices", rec("equity", None)
    )
    monkeypatch.setattr(market_refresh_service, "refresh_nav_universe", nav)
    monkeypatch.setattr(
        market_refresh_service, "_write_nav_refresh_summary", lambda s: None
    )
    monkeypatch.setattr(market_refresh_service, "refresh_pc_vix", vix)
    monkeypatch.setattr(market_refresh_service, "_utcnow", lambda: MORNING_KST_UTC)
    reset_state_for_testing(db_path=db)
    rig["universe"] = _universe_df
    return rig


def _full(rig: dict, *, cooldown: int = 6, universe=None, prices=None):
    return start_refresh_job(
        db_path=rig["db"],
        cooldown_hours=cooldown,
        universe_fetcher=universe or rig["universe"],
        price_fetcher=prices or _price_fetcher,
        end_date_for_prices=date(2026, 10, 13),
        thread_runner=lambda runner: runner(),
    )


def _retry(rig: dict, runner=None):
    return start_vix_retry_job(
        db_path=rig["db"],
        cooldown_hours=6,
        thread_runner=runner or (lambda r: r()),
    )


def _log_rows(db: Path) -> list[tuple]:
    con = sqlite3.connect(str(db))
    try:
        return con.execute(
            "SELECT run_id, source, error_summary FROM market_refresh_log ORDER BY rowid"
        ).fetchall()
    finally:
        con.close()


def test_vix_only_failure_sets_marker(svc: dict) -> None:
    svc["vix"] = VIX_STEP_FAILED_TEXT
    _full(svc)
    assert get_state_snapshot(db_path=svc["db"]).status == "completed"
    snap = get_vix_retry_snapshot(svc["db"])
    assert snap["needed"] is True
    assert snap["status"] == "needed"
    assert snap["error_summary"] == VIX_STEP_FAILED_TEXT


def test_vix_step_exception_also_sets_marker(svc: dict) -> None:
    svc["vix"] = RuntimeError("boom")
    _full(svc)
    assert get_vix_retry_snapshot(svc["db"])["needed"] is True


def test_success_or_freshness_only_leaves_no_marker(svc: dict) -> None:
    """VIX 단계 성공(이미 최신 · 오래된 날짜 그대로 포함)이면 표식 행을 만들지 않는다."""
    _full(svc)
    assert get_vix_retry_snapshot(svc["db"]) is None


def _kospi_failed(rig, monkeypatch):
    monkeypatch.setattr(
        market_refresh_service,
        "refresh_kospi_benchmark",
        lambda **kw: {"status": "failed", "error": "down"},
    )


def _kospi_raises(rig, monkeypatch):
    def boom(**kw):
        raise RuntimeError("kospi boom")

    monkeypatch.setattr(market_refresh_service, "refresh_kospi_benchmark", boom)


def _equity_failed(rig, monkeypatch):
    monkeypatch.setattr(
        market_refresh_service,
        "refresh_holdings_equity_prices",
        lambda **kw: "보유 개별주 가격을 갱신하지 못했습니다",
    )


def _etf_partial(rig, monkeypatch):
    def prices(ticker, start, end):
        if ticker == "111111":
            raise RuntimeError("boom")
        return _price_fetcher(ticker, start, end)

    rig["universe"] = lambda: _universe_df(("069500", "111111"))
    rig["prices"] = prices


def _nav(value):
    def apply(rig, monkeypatch):
        rig["nav"] = value

    return apply


OTHER_STEP_FAILURES = {
    "etf_price_partial": _etf_partial,
    "kospi_failed": _kospi_failed,
    "kospi_exception": _kospi_raises,
    "holdings_equity": _equity_failed,
    "nav_partial": _nav(types.SimpleNamespace(status="partial")),
    "nav_unavailable": _nav(types.SimpleNamespace(status="unavailable")),
    "nav_exception": _nav(RuntimeError("nav boom")),
    "nav_none": _nav(None),
}


@pytest.mark.parametrize("case", sorted(OTHER_STEP_FAILURES))
def test_other_step_failure_does_not_set_marker(
    svc: dict, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    OTHER_STEP_FAILURES[case](svc, monkeypatch)
    svc["vix"] = VIX_STEP_FAILED_TEXT
    _full(svc, prices=svc.get("prices"))
    assert get_vix_retry_snapshot(svc["db"]) is None


@pytest.mark.parametrize("case", sorted(OTHER_STEP_FAILURES))
def test_other_step_failure_after_prior_marker_clears_it(
    svc: dict, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    svc["vix"] = VIX_STEP_FAILED_TEXT
    _full(svc)
    assert get_vix_retry_snapshot(svc["db"])["needed"] is True
    OTHER_STEP_FAILURES[case](svc, monkeypatch)
    _full(svc, cooldown=0, prices=svc.get("prices"))
    snap = get_vix_retry_snapshot(svc["db"])
    assert snap["needed"] is False
    assert snap["status"] == "cleared"
    assert _retry(svc).status == "not_needed"


def test_next_full_refresh_with_vix_success_clears_marker(svc: dict) -> None:
    svc["vix"] = VIX_STEP_FAILED_TEXT
    _full(svc)
    svc["vix"] = None
    _full(svc, cooldown=0)
    assert get_vix_retry_snapshot(svc["db"])["status"] == "cleared"


def test_retry_runs_only_vix_and_keeps_full_refresh_records(svc: dict) -> None:
    svc["vix"] = VIX_STEP_FAILED_TEXT
    _full(svc)
    before = get_state_snapshot(db_path=svc["db"])
    full_row_before = read_state(db_path=svc["db"])
    logs_before = _log_rows(svc["db"])
    svc["calls"].clear()
    svc["vix"] = None
    res = _retry(svc)
    assert res.status == "accepted"
    assert res.refresh_id.startswith("vix_retry_")
    assert svc["calls"] == ["vix"]  # ETF · 보유 · KOSPI · NAV 호출 0
    after = get_state_snapshot(db_path=svc["db"])
    assert after == before
    full_row_after = read_state(db_path=svc["db"])
    assert full_row_after.last_success_at == full_row_before.last_success_at
    assert full_row_after.refresh_id == full_row_before.refresh_id
    assert full_row_after.price_success_count == full_row_before.price_success_count
    assert _log_rows(svc["db"]) == logs_before
    # 끝난 결과는 POST 가 준 id 로 바로 읽힌다(첫 상태 조회 전에 끝나도 보임).
    snap = get_vix_retry_snapshot(svc["db"])
    assert snap["refresh_id"] == res.refresh_id
    assert snap["status"] == "completed"
    assert snap["needed"] is False
    assert snap["vix_as_of_date"] == "2026-10-13"
    assert snap["error_summary"] is None
    assert snap["finished_at"] is not None
    # 성공 뒤에는 대상이 없다.
    assert _retry(svc).status == "not_needed"


def test_retry_ignores_six_hour_cooldown(svc: dict) -> None:
    svc["vix"] = VIX_STEP_FAILED_TEXT
    _full(svc)
    assert _full(svc).status == "skipped_cooldown"
    svc["vix"] = None
    assert _retry(svc).status == "accepted"


def test_retry_failure_keeps_marker_with_reason_and_can_retry_again(svc: dict) -> None:
    svc["vix"] = VIX_STEP_FAILED_TEXT
    _full(svc)
    first = _retry(svc)
    snap = get_vix_retry_snapshot(svc["db"])
    assert snap["refresh_id"] == first.refresh_id
    assert snap["status"] == "failed"
    assert snap["needed"] is True
    assert snap["error_summary"] == VIX_STEP_FAILED_TEXT
    svc["vix"] = RuntimeError("boom")
    second = _retry(svc)
    assert second.status == "accepted"
    assert get_vix_retry_snapshot(svc["db"])["status"] == "failed"
    svc["vix"] = None
    assert _retry(svc).status == "accepted"
    assert get_vix_retry_snapshot(svc["db"])["status"] == "completed"


def test_retry_without_marker_is_not_needed_and_runs_nothing(svc: dict) -> None:
    res = _retry(svc)
    assert res.status == "not_needed"
    assert res.refresh_id is None
    assert svc["calls"] == []
    assert get_vix_retry_snapshot(svc["db"]) is None


def test_duplicate_and_overlap_are_refused(svc: dict) -> None:
    svc["vix"] = VIX_STEP_FAILED_TEXT
    _full(svc)
    held: list = []
    first = _retry(svc, runner=held.append)  # 시작만 하고 아직 돌지 않음
    assert first.status == "accepted"
    assert get_vix_retry_snapshot(svc["db"])["status"] == "running"
    dup = _retry(svc)
    assert dup.status == "vix_retry_running"
    assert dup.refresh_id == first.refresh_id
    full = _full(svc, cooldown=0)
    # 전체 갱신 진행('running')과 구분한다 — 화면이 '갱신 완료'로 읽지 않게.
    assert full.status == "vix_retry_running"
    assert full.refresh_id == first.refresh_id
    assert svc["calls"].count("vix") == 1  # 첫 전체 갱신의 VIX 단계만
    svc["vix"] = None
    held[0]()
    assert get_vix_retry_snapshot(svc["db"])["status"] == "completed"


def test_full_refresh_running_refuses_retry(svc: dict) -> None:
    write_state(
        MarketRefreshStateRow(
            refresh_id="vix_old",
            last_attempt_status="needed",
            last_error_summary=VIX_STEP_FAILED_TEXT,
        ),
        db_path=svc["db"],
        scope=VIX_RETRY_SCOPE,
    )
    held: list = []
    start_refresh_job(
        db_path=svc["db"],
        cooldown_hours=0,
        universe_fetcher=_universe_df,
        price_fetcher=_price_fetcher,
        end_date_for_prices=date(2026, 10, 13),
        thread_runner=held.append,
    )
    res = _retry(svc)
    assert res.status == "running"
    assert svc["calls"] == []
    assert get_vix_retry_snapshot(svc["db"])["status"] == "needed"


def test_restart_turns_running_retry_into_failed(svc: dict) -> None:
    svc["vix"] = VIX_STEP_FAILED_TEXT
    _full(svc)
    held: list = []
    _retry(svc, runner=held.append)
    assert get_vix_retry_snapshot(svc["db"])["status"] == "running"
    market_refresh_service._service.loaded_for_db = (
        None  # 서버 다시 켜기와 같은 복구 경로
    )
    snap = get_vix_retry_snapshot(svc["db"])
    assert snap["status"] == "failed"
    assert snap["needed"] is True
    assert snap["error_summary"] == VIX_STEP_FAILED_TEXT
    # 전체 갱신 상태는 그대로 completed.
    assert get_state_snapshot(db_path=svc["db"]).status == "completed"


def test_retry_calls_service_module_vix_step(svc: dict) -> None:
    """다시 받기는 서비스 모듈의 `refresh_pc_vix` 를 부른다(conftest stub · 시험 교체가 같은 통로)."""
    assert market_refresh_vix_retry.__name__ == "app.market_refresh_vix_retry"
    svc["vix"] = VIX_STEP_FAILED_TEXT
    _full(svc)
    svc["vix"] = None
    _retry(svc)
    assert latest_benchmark_date("VIX", db_path=svc["db"]) == "2026-10-13"


# ── API(같은 경로 · scope · 상태 필드) ────────────────────────────────────────
@pytest.fixture
def client(svc: dict, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(api_market_topn, "DEFAULT_DB_PATH", svc["db"])
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(api_market_topn.router)
    return TestClient(app)


def test_api_unknown_scope_is_422_and_starts_nothing(
    client: TestClient, svc: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    started: list = []
    monkeypatch.setattr(
        api_market_topn, "start_refresh_job", lambda **kw: started.append("full")
    )
    monkeypatch.setattr(
        api_market_topn, "start_vix_retry_job", lambda **kw: started.append("vix")
    )
    for bad in ("all", "VIX", ""):
        r = client.post(f"/market/refresh?scope={bad}")
        assert r.status_code == 422, bad
    assert started == []


def test_api_scope_vix_routes_to_retry_and_status_shows_it(
    client: TestClient, svc: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    r = client.get("/market/refresh/status")
    assert r.status_code == 200
    assert r.json()["vix_retry"] is None
    r = client.post("/market/refresh?scope=vix")
    assert r.json()["status"] == "not_needed"
    write_state(
        MarketRefreshStateRow(
            refresh_id="full_1",
            last_attempt_status="needed",
            last_error_summary=VIX_STEP_FAILED_TEXT,
        ),
        db_path=svc["db"],
        scope=VIX_RETRY_SCOPE,
    )
    monkeypatch.setattr(
        market_refresh_vix_retry.threading,
        "Thread",
        lambda target, name, daemon: types.SimpleNamespace(start=target),
    )
    r = client.post("/market/refresh?scope=vix")
    body = r.json()
    assert body["status"] == "accepted"
    assert svc["calls"] == ["vix"]
    status = client.get("/market/refresh/status").json()
    assert status["vix_retry"] == {
        "needed": False,
        "status": "completed",
        "refresh_id": body["refresh_id"],
        "started_at": "2026-10-13T22:00:00Z",
        "finished_at": "2026-10-13T22:00:00Z",
        "error_summary": None,
        "vix_as_of_date": "2026-10-13",
    }
    # 전체 갱신 필드는 그대로(idle).
    assert status["status"] == "idle"


def test_api_without_scope_is_full_refresh(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    called: list = []

    def fake_full(**kw):
        called.append(kw)
        return market_refresh_service.StartResult(
            status="skipped_cooldown",
            refresh_id=None,
            message="x",
            cooldown_remaining_seconds=1,
        )

    monkeypatch.setattr(api_market_topn, "start_refresh_job", fake_full)
    r = client.post("/market/refresh")
    assert r.json()["status"] == "skipped_cooldown"
    assert len(called) == 1
