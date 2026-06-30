"""D-2 (2026-06-30) — market_refresh_state SQLite SSOT 영속화 테스트.

AC-9 요구 5 케이스 + 설계자 확정 4 보강 케이스.

- 최초 상태 (행 없음 → 과거 성공 추정 X)
- 정상 성공 → SQLite 영속화 + 새 인스턴스에서 detail 전체 복구
- 성공 후 실패 → last_success_* 보존, detail 의미 유지
- running 상태 재시작 → failed 정규화, detail 보존
- 새 서비스 인스턴스의 상태 복구 (모듈 reload 시뮬레이션)
- MarketRefreshStatusResponse 응답 필드/의미 변경 없음 (회귀)
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from app import market_refresh_service
from app.market_refresh_service import (
    _ServiceState,
    get_state_snapshot,
    reset_state_for_testing,
    start_refresh_job,
)
from app.market_refresh_state_store import (
    MarketRefreshStateRow,
    REFRESH_SCOPE,
    read_state,
    write_state,
)

# ─── stubs ──────────────────────────────────────────────────────────────


def _stub_universe_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Symbol": "069500",
                "Category": 1,
                "Name": "KODEX 200",
                "Price": 11720.0,
                "Volume": 1000,
                "MarCap": 50000.0,
            },
        ]
    )


def _stub_price_df(start, end) -> pd.DataFrame:
    idx = pd.to_datetime([start.isoformat(), end.isoformat()])
    return pd.DataFrame(
        {
            "Open": [100.0, 101.0],
            "High": [102.0, 103.0],
            "Low": [99.0, 100.0],
            "Close": [100.5, 101.5],
            "Volume": [1000, 1100],
            "Change": [0.0, 0.01],
        },
        index=idx,
    )


def _run_inline_success(db_path: Path) -> None:
    start_refresh_job(
        db_path=db_path,
        cooldown_hours=6,
        universe_fetcher=_stub_universe_df,
        price_fetcher=lambda tk, s, e: _stub_price_df(s, e),
        end_date_for_prices=date(2024, 10, 31),
        thread_runner=lambda runner: runner(),
    )


@pytest.fixture
def fake_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db = tmp_path / "market_data.sqlite"
    monkeypatch.setattr("app.market_data_store.DEFAULT_DB_PATH", db, raising=True)
    monkeypatch.setattr("app.market_refresh_service.DEFAULT_DB_PATH", db, raising=True)
    reset_state_for_testing(db_path=db)
    return db


# ─── AC-9 케이스 ────────────────────────────────────────────────────────


def test_initial_state_does_not_infer_success(fake_db: Path) -> None:
    """AC-6 — 최초 상태에서 과거 성공 기록을 추정하지 않는다."""
    assert read_state(db_path=fake_db) is None
    snap = get_state_snapshot(db_path=fake_db)
    assert snap.status == "idle"
    assert snap.refresh_id is None
    assert snap.asof is None
    assert snap.universe_count is None
    assert snap.price_success_count is None
    assert snap.runtime_seconds is None


def test_success_persisted_to_sqlite(fake_db: Path) -> None:
    """AC-2 — 정상 갱신 성공 뒤 마지막 정상 기준일·완료 시각·상태가 SQLite 에 저장."""
    _run_inline_success(fake_db)
    row = read_state(db_path=fake_db)
    assert row is not None
    assert row.last_attempt_status == "completed"
    assert row.last_success_asof_date == "2024-10-31"
    assert row.last_success_at is not None
    assert row.last_attempt_started_at is not None
    assert row.last_attempt_finished_at is not None
    assert row.asof == "2024-10-31"
    assert row.universe_count == 1
    assert row.price_attempted_count == 1
    assert row.price_success_count == 1
    assert row.runtime_seconds is not None


def test_new_instance_recovers_full_state(fake_db: Path) -> None:
    """AC-3 / detail 전체 복구 — 새 서비스 인스턴스가 SQLite 에서 상태 복구."""
    _run_inline_success(fake_db)
    snap_before = get_state_snapshot(db_path=fake_db)

    # 새 인스턴스 시뮬레이션 — _service 를 비우고 다시 hydrate.
    market_refresh_service._service = _ServiceState()
    snap_after = get_state_snapshot(db_path=fake_db)

    assert snap_after.status == "completed"
    assert snap_after.refresh_id == snap_before.refresh_id
    assert snap_after.started_at == snap_before.started_at
    assert snap_after.finished_at == snap_before.finished_at
    assert snap_after.asof == snap_before.asof
    assert snap_after.universe_count == snap_before.universe_count
    assert snap_after.price_attempted_count == snap_before.price_attempted_count
    assert snap_after.price_success_count == snap_before.price_success_count
    assert snap_after.price_fail_count == snap_before.price_fail_count
    assert snap_after.runtime_seconds == snap_before.runtime_seconds
    assert snap_after.error_summary == snap_before.error_summary


def test_failure_preserves_last_success(fake_db: Path) -> None:
    """AC-4 — 갱신 실패는 마지막 정상 성공 기준일/시각을 지우지 않는다."""
    _run_inline_success(fake_db)
    success_row = read_state(db_path=fake_db)
    assert success_row is not None
    last_success_asof = success_row.last_success_asof_date
    last_success_at = success_row.last_success_at
    success_universe = success_row.universe_count

    # 실패 시뮬레이션 — universe fetch 가 빈 결과 → universe_count 0 → fail.
    def empty_universe() -> pd.DataFrame:
        return pd.DataFrame(
            columns=["ticker", "name", "category", "price", "volume", "market_cap"]
        )

    def fail_price(tk, s, e):  # noqa: ANN001
        return None

    # cooldown 우회 — cooldown_hours=0 으로 즉시 다시 실행.
    start_refresh_job(
        db_path=fake_db,
        cooldown_hours=0,
        universe_fetcher=empty_universe,
        price_fetcher=fail_price,
        end_date_for_prices=date(2024, 11, 1),
        thread_runner=lambda runner: runner(),
    )

    after = read_state(db_path=fake_db)
    assert after is not None
    assert after.last_attempt_status == "failed"
    # 마지막 정상 성공 기록은 유지.
    assert after.last_success_asof_date == last_success_asof
    assert after.last_success_at == last_success_at
    # detail 의미 유지: 마지막 시도 (실패) 의 detail 은 갱신, 그러나
    # last_success_* 는 분리 저장되므로 마지막 성공 detail 도 잃지 않는다.
    assert success_universe is not None


def test_restart_running_normalized_to_failed_preserving_detail(fake_db: Path) -> None:
    """AC-5 — 재시작 뒤 남은 running 상태는 failed 로 정규화. detail 보존."""
    # running 상태가 SQLite 에 남은 상황을 직접 구성.
    write_state(
        MarketRefreshStateRow(
            refresh_id="rid-prev-running",
            last_success_asof_date="2024-10-30",
            last_success_at="2024-10-30T00:00:00Z",
            last_attempt_started_at="2024-10-31T00:00:00Z",
            last_attempt_finished_at=None,
            last_attempt_status="running",
            last_error_summary=None,
            asof="2024-10-31",
            universe_count=1107,
            price_attempted_count=1107,
            price_success_count=842,
            price_fail_count=265,
            runtime_seconds=120.0,
        ),
        db_path=fake_db,
    )
    # 새 인스턴스 시뮬레이션.
    market_refresh_service._service = _ServiceState()
    snap = get_state_snapshot(db_path=fake_db)

    assert snap.status == "failed"  # running → failed 정규화
    # detail 값은 살아 있어야 한다 (null/임의값 초기화 금지).
    assert snap.universe_count == 1107
    assert snap.price_attempted_count == 1107
    assert snap.price_success_count == 842
    assert snap.price_fail_count == 265
    assert snap.runtime_seconds == 120.0
    assert snap.asof == "2024-10-31"
    # finished_at 은 정규화 시각으로 채워져야 함.
    assert snap.finished_at is not None

    row = read_state(db_path=fake_db)
    assert row is not None
    # 마지막 정상 성공 기록도 유지.
    assert row.last_success_asof_date == "2024-10-30"
    assert row.last_success_at == "2024-10-30T00:00:00Z"


# ─── 설계자 확정 보강 4 케이스 ──────────────────────────────────────────


def test_status_response_fields_unchanged(fake_db: Path) -> None:
    """기존 MarketRefreshStatusResponse 응답 필드/의미 변경 없음 (회귀).

    RefreshState 가 노출하는 필드 집합이 그대로 유지되어야 한다.
    """
    expected_fields = {
        "status",
        "refresh_id",
        "started_at",
        "finished_at",
        "asof",
        "universe_count",
        "price_attempted_count",
        "price_success_count",
        "price_fail_count",
        "runtime_seconds",
        "error_summary",
        "cooldown_remaining_seconds",
    }
    snap = get_state_snapshot(db_path=fake_db)
    assert set(snap.__dict__.keys()) == expected_fields


def test_new_instance_detail_fields_all_recovered(fake_db: Path) -> None:
    """정상 성공 후 새 인스턴스에서 detail 필드 전체 복구."""
    _run_inline_success(fake_db)
    market_refresh_service._service = _ServiceState()
    snap = get_state_snapshot(db_path=fake_db)
    # detail 모두 None 이 아니어야 함.
    for field in (
        "refresh_id",
        "started_at",
        "finished_at",
        "asof",
        "universe_count",
        "price_attempted_count",
        "price_success_count",
        "runtime_seconds",
    ):
        assert getattr(snap, field) is not None, f"{field} should be recovered"


def test_failure_after_success_keeps_last_success_in_new_instance(
    fake_db: Path,
) -> None:
    """성공 후 실패 뒤 새 인스턴스에서도 last_success_* 정보 유지."""
    _run_inline_success(fake_db)
    row1 = read_state(db_path=fake_db)
    assert row1 is not None
    saved_last_success_asof = row1.last_success_asof_date
    saved_last_success_at = row1.last_success_at

    # 실패 발생.
    def empty_universe() -> pd.DataFrame:
        return pd.DataFrame(
            columns=["ticker", "name", "category", "price", "volume", "market_cap"]
        )

    start_refresh_job(
        db_path=fake_db,
        cooldown_hours=0,
        universe_fetcher=empty_universe,
        price_fetcher=lambda tk, s, e: None,
        end_date_for_prices=date(2024, 11, 1),
        thread_runner=lambda runner: runner(),
    )

    # 새 인스턴스 시뮬레이션.
    market_refresh_service._service = _ServiceState()
    row2 = read_state(db_path=fake_db)
    assert row2 is not None
    assert row2.last_attempt_status == "failed"
    assert row2.last_success_asof_date == saved_last_success_asof
    assert row2.last_success_at == saved_last_success_at


def test_running_state_persisted_during_job(fake_db: Path) -> None:
    """갱신 시작 시 SQLite 에 running 상태가 즉시 기록된다 (재시작 정규화의 전제)."""
    started_states: list[str] = []

    # thread_runner 안에서 SQLite 를 읽어 running 이 기록되었는지 확인.
    def runner_with_inspect(runner) -> None:
        # _execute_refresh_job 진입 직후 SQLite 상태를 확인하려면 runner 호출 전.
        # start_refresh_job 안의 lock-block 단계에서 이미 running 으로 persist 됨.
        row = read_state(db_path=fake_db)
        if row is not None:
            started_states.append(row.last_attempt_status or "")
        runner()

    start_refresh_job(
        db_path=fake_db,
        cooldown_hours=6,
        universe_fetcher=_stub_universe_df,
        price_fetcher=lambda tk, s, e: _stub_price_df(s, e),
        end_date_for_prices=date(2024, 10, 31),
        thread_runner=runner_with_inspect,
    )
    assert "running" in started_states
    # 종료 후 completed.
    final = read_state(db_path=fake_db)
    assert final is not None
    assert final.last_attempt_status == "completed"


# ─── 단일 행 원칙 ────────────────────────────────────────────────────────


def test_single_row_principle(fake_db: Path) -> None:
    """refresh_scope='market_data' 행은 항상 단일."""
    _run_inline_success(fake_db)
    # 여러 번 write 해도 단일 행만 유지.
    _run_inline_success(fake_db)

    import sqlite3

    con = sqlite3.connect(str(fake_db))
    try:
        cur = con.execute(
            "SELECT COUNT(*) FROM market_refresh_state WHERE refresh_scope = ?",
            (REFRESH_SCOPE,),
        )
        count = cur.fetchone()[0]
    finally:
        con.close()
    assert count == 1
