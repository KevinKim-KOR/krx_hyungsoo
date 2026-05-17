"""POC2 Market Discovery — SQLite 직접 + refresh + status API 테스트.

2026-05-18 변경:
- artifact 기반 테스트 폐기 (JSON 파일 없음).
- GET /market/topn/latest 가 SQLite 에서 직접 계산함을 검증.
- POST /market/refresh single-flight + cooldown.
- GET /market/refresh/status 상태 노출.
- 결측 0% 보정 금지 (지시문 §6).
- JSON artifact 절대 생성 안 함 (AC-8).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app import api as api_module
from app import api_market_topn, market_data_store, market_refresh_service
from app.market_data_store import (
    EtfDailyPriceRow,
    EtfMasterRow,
    upsert_daily_prices,
    upsert_etf_master,
)
from app.market_refresh_service import RefreshState

# ─── helpers ──────────────────────────────────────────────────────


def _seed_two_etfs_with_prices(db_path: Path, end: date) -> None:
    d = {
        "end": end.isoformat(),
        "minus_1": (end - timedelta(days=1)).isoformat(),
        "minus_30": (end - timedelta(days=30)).isoformat(),
        "minus_90": (end - timedelta(days=90)).isoformat(),
    }
    upsert_etf_master(
        [
            EtfMasterRow("069500", "KODEX 200", "1", 100.0, 1000, 5000.0),
            EtfMasterRow("379800", "KODEX 미국S&P500", "4", 200.0, 2000, 6000.0),
        ],
        source="TestSource",
        db_path=db_path,
    )
    for tk, closes in [
        (
            "069500",
            [
                (d["minus_90"], 100.0),
                (d["minus_30"], 105.0),
                (d["minus_1"], 110.0),
                (d["end"], 112.0),
            ],
        ),
        (
            "379800",
            [
                (d["minus_90"], 100.0),
                (d["minus_30"], 110.0),
                (d["minus_1"], 119.0),
                (d["end"], 120.0),
            ],
        ),
    ]:
        upsert_daily_prices(
            [EtfDailyPriceRow(tk, dt, c, c, c, c, 0, 0) for dt, c in closes],
            source="TestSource",
            db_path=db_path,
        )


@pytest.fixture
def api_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    """endpoint 가 사용하는 DB 경로를 tmp 로 교체 + refresh service state 초기화."""
    fake_db = tmp_path / "market_data.sqlite"
    # 양쪽 모듈의 DEFAULT_DB_PATH 를 모두 patch — compute_topn / api / refresh_service
    monkeypatch.setattr(api_market_topn, "DEFAULT_DB_PATH", fake_db)
    monkeypatch.setattr(market_data_store, "DEFAULT_DB_PATH", fake_db)
    market_refresh_service.reset_state_for_testing()
    return TestClient(api_module.app)


# ─── GET /market/topn/latest ──────────────────────────────────────


def test_topn_latest_sqlite_direct_ok(api_client: TestClient) -> None:
    db = api_market_topn.DEFAULT_DB_PATH
    _seed_two_etfs_with_prices(db, date(2024, 10, 31))
    res = api_client.get("/market/topn/latest")
    assert res.status_code == 200
    payload = res.json()
    assert payload["status"] == "ok"
    assert payload["asof"] == "2024-10-31"
    assert payload["universe_count"] == 2
    # source 라벨에 SQLite 명시
    assert "SQLite" in (payload["source"] or "")
    assert len(payload["daily_topn"]) == 2


def test_topn_latest_status_missing_when_db_absent(api_client: TestClient) -> None:
    res = api_client.get("/market/topn/latest")
    payload = res.json()
    assert payload["status"] == "missing"
    assert payload["daily_topn"] == []


def test_topn_latest_status_empty_when_universe_without_prices(
    api_client: TestClient,
) -> None:
    db = api_market_topn.DEFAULT_DB_PATH
    upsert_etf_master(
        [EtfMasterRow("069500", "KODEX 200", "1", 100.0, 1000, 5000.0)],
        source="TestSource",
        db_path=db,
    )
    res = api_client.get("/market/topn/latest")
    payload = res.json()
    assert payload["status"] == "empty"
    assert payload["universe_count"] == 1
    assert payload["daily_topn"] == []


def test_topn_latest_supports_n_query_param(api_client: TestClient) -> None:
    db = api_market_topn.DEFAULT_DB_PATH
    _seed_two_etfs_with_prices(db, date(2024, 10, 31))
    res5 = api_client.get("/market/topn/latest?n=5")
    payload5 = res5.json()
    assert payload5["n"] == 5
    assert len(payload5["daily_topn"]) <= 5
    res1 = api_client.get("/market/topn/latest?n=1")
    payload1 = res1.json()
    assert payload1["n"] == 1
    assert len(payload1["daily_topn"]) == 1


def test_topn_latest_does_not_call_fdr(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GET endpoint 가 FDR refresh 함수를 호출하면 fail."""
    from app import market_data_fdr

    def boom(*args, **kwargs):
        raise AssertionError("GET /market/topn/latest 가 FDR 호출 — 금지")

    monkeypatch.setattr(market_data_fdr, "refresh_etf_universe", boom)
    monkeypatch.setattr(market_data_fdr, "refresh_price_history", boom)
    res = api_client.get("/market/topn/latest")
    assert res.status_code == 200


def test_topn_latest_missing_data_not_filled_with_zero(api_client: TestClient) -> None:
    """결측 0% 보정 금지 — period_exclusions 에 집계.

    TINY 신규 상장 ETF (history 1건) 는 어떤 기간 TOP N 에도 포함되면 안 된다.
    """
    db = api_market_topn.DEFAULT_DB_PATH
    end = date(2024, 10, 31)
    upsert_etf_master(
        [
            EtfMasterRow("FULL", "Full History", "1", None, None, None),
            EtfMasterRow("TINY", "New Listing", "1", None, None, None),
        ],
        source="TestSource",
        db_path=db,
    )
    # FULL: 정상 history
    upsert_daily_prices(
        [
            EtfDailyPriceRow(
                "FULL",
                (end - timedelta(days=90)).isoformat(),
                100.0,
                100.0,
                100.0,
                100.0,
                0,
                0,
            ),
            EtfDailyPriceRow(
                "FULL",
                (end - timedelta(days=1)).isoformat(),
                110.0,
                110.0,
                110.0,
                110.0,
                0,
                0,
            ),
            EtfDailyPriceRow("FULL", end.isoformat(), 112.0, 112.0, 112.0, 112.0, 0, 0),
        ],
        source="TestSource",
        db_path=db,
    )
    # TINY: latest 1건만 → 모든 기간 insufficient_history
    upsert_daily_prices(
        [EtfDailyPriceRow("TINY", end.isoformat(), 105.0, 105.0, 105.0, 105.0, 0, 0)],
        source="TestSource",
        db_path=db,
    )
    res = api_client.get("/market/topn/latest")
    payload = res.json()
    assert payload["status"] == "ok"
    # TINY 는 어디에도 포함 안 됨 (0% 보정 금지)
    for label in ("daily_topn", "one_month_topn", "three_month_topn"):
        assert all(r["ticker"] != "TINY" for r in payload[label])
    excl = payload["period_exclusions"]
    assert excl["daily"]["insufficient_history"] >= 1
    assert excl["one_month"]["insufficient_history"] >= 1


# ─── POST /market/refresh ─────────────────────────────────────────


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
            {
                "Symbol": "379800",
                "Category": 4,
                "Name": "KODEX 미국S&P500",
                "Price": 27765.0,
                "Volume": 2000,
                "MarCap": 60000.0,
            },
        ]
    )


def _stub_price_df(start: date, end: date) -> pd.DataFrame:
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


def test_post_refresh_accepted_and_runs_inline_for_test(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """POST /market/refresh 가 accepted 응답 + background job 시작.

    테스트에서는 threading 대신 inline 실행으로 강제하기 위해 start_refresh_job 의
    thread_runner 를 직접 호출하는 형태로 monkeypatch.
    """
    captured_calls = {"universe": 0, "prices": 0}

    def stub_uni():
        captured_calls["universe"] += 1
        return _stub_universe_df()

    def stub_price(ticker, start, end):
        captured_calls["prices"] += 1
        return _stub_price_df(start, end)

    # API 엔드포인트 내부의 start_refresh_job 호출을 inline + stub 으로 가로채기
    original = market_refresh_service.start_refresh_job

    def inline_start(**kwargs):
        kwargs.setdefault("universe_fetcher", stub_uni)
        kwargs.setdefault("price_fetcher", stub_price)
        kwargs.setdefault("end_date_for_prices", date(2024, 10, 31))
        kwargs["thread_runner"] = lambda runner: runner()
        return original(**kwargs)

    monkeypatch.setattr(api_market_topn, "start_refresh_job", inline_start)

    res = api_client.post("/market/refresh")
    assert res.status_code == 200
    payload = res.json()
    assert payload["status"] == "accepted"
    assert payload["refresh_id"] is not None
    # background runner 가 inline 으로 실행됐으므로 FDR + 가격 수집이 호출돼야 함
    assert captured_calls["universe"] == 1
    assert captured_calls["prices"] >= 1


def test_post_refresh_running_when_already_in_progress(
    api_client: TestClient,
) -> None:
    """이미 running 상태일 때 추가 POST 는 running 응답 + 새 job 생성 안 함."""
    # 현재 state 를 running 으로 직접 설정
    market_refresh_service._service.state.status = "running"
    market_refresh_service._service.state.refresh_id = "ongoing-001"
    res = api_client.post("/market/refresh")
    payload = res.json()
    assert payload["status"] == "running"
    assert payload["refresh_id"] == "ongoing-001"


def test_post_refresh_skipped_within_cooldown(api_client: TestClient) -> None:
    """6h cooldown 안 — skipped_cooldown 응답."""
    market_refresh_service._service.last_success_at = datetime.now(timezone.utc)
    market_refresh_service._service.state.status = "idle"
    res = api_client.post("/market/refresh")
    payload = res.json()
    assert payload["status"] == "skipped_cooldown"
    assert payload["cooldown_remaining_seconds"] > 0


def test_post_refresh_does_not_create_json_artifact(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """AC-8 — POST /market/refresh 가 어떤 JSON artifact 도 생성하지 않는다."""
    # state/market 디렉토리 (tmp_path 의 부모) 안에서 어떤 파일이 새로 생기는지 추적
    market_dir = api_market_topn.DEFAULT_DB_PATH.parent
    market_dir.mkdir(parents=True, exist_ok=True)
    before = set(market_dir.iterdir())

    original = market_refresh_service.start_refresh_job

    def inline_start(**kwargs):
        kwargs["universe_fetcher"] = _stub_universe_df
        kwargs["price_fetcher"] = lambda tk, s, e: _stub_price_df(s, e)
        kwargs["end_date_for_prices"] = date(2024, 10, 31)
        kwargs["thread_runner"] = lambda runner: runner()
        return original(**kwargs)

    monkeypatch.setattr(api_market_topn, "start_refresh_job", inline_start)

    res = api_client.post("/market/refresh")
    assert res.status_code == 200
    after = set(market_dir.iterdir())
    new_files = after - before
    # SQLite 파일은 생기지만 JSON artifact 는 절대 안 생긴다
    json_files = [p for p in new_files if p.suffix == ".json"]
    assert json_files == []


# ─── GET /market/refresh/status ───────────────────────────────────


def test_status_idle_initially(api_client: TestClient) -> None:
    res = api_client.get("/market/refresh/status")
    payload = res.json()
    assert payload["status"] == "idle"
    assert payload["refresh_id"] is None


def test_status_running_after_state_set(api_client: TestClient) -> None:
    market_refresh_service._service.state = RefreshState(
        status="running",
        refresh_id="rid-running",
        started_at="2024-10-31T00:00:00Z",
    )
    res = api_client.get("/market/refresh/status")
    payload = res.json()
    assert payload["status"] == "running"
    assert payload["refresh_id"] == "rid-running"


def test_status_completed_with_counts(api_client: TestClient) -> None:
    market_refresh_service._service.state = RefreshState(
        status="completed",
        refresh_id="rid-completed",
        started_at="2024-10-31T00:00:00Z",
        finished_at="2024-10-31T00:05:00Z",
        asof="2024-10-31",
        universe_count=1107,
        price_attempted_count=1107,
        price_success_count=842,
        price_fail_count=265,
        runtime_seconds=234.0,
    )
    res = api_client.get("/market/refresh/status")
    payload = res.json()
    assert payload["status"] == "completed"
    assert payload["universe_count"] == 1107
    assert payload["price_success_count"] == 842


# ─── 회귀 / 통합 ──────────────────────────────────────────────────


def test_market_refresh_log_is_recorded_by_refresh_job(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """POST /market/refresh 의 background job 이 market_refresh_log 를 기록."""
    original = market_refresh_service.start_refresh_job

    def inline_start(**kwargs):
        kwargs["universe_fetcher"] = _stub_universe_df
        kwargs["price_fetcher"] = lambda tk, s, e: _stub_price_df(s, e)
        kwargs["end_date_for_prices"] = date(2024, 10, 31)
        kwargs["thread_runner"] = lambda runner: runner()
        return original(**kwargs)

    monkeypatch.setattr(api_market_topn, "start_refresh_job", inline_start)

    api_client.post("/market/refresh")
    from app.market_data_store import latest_refresh_log

    log = latest_refresh_log(db_path=api_market_topn.DEFAULT_DB_PATH)
    assert log is not None
    assert log["source"].startswith("FinanceDataReader")


def test_no_etf_universe_topn_latest_json_path_in_code() -> None:
    """AC-1/AC-14 — 코드에 etf_universe_topn_latest.json 참조가 남지 않는다.

    app/ 내부 코드에서 grep 한 결과가 0건이어야 한다 (테스트 / 문서 / handoff 는 제외).
    """
    import re
    from pathlib import Path as _P

    app_dir = _P(__file__).resolve().parent.parent / "app"
    bad_files: list[str] = []
    for py in app_dir.glob("*.py"):
        text = py.read_text(encoding="utf-8")
        if re.search(r"etf_universe_topn_latest\.json", text):
            bad_files.append(str(py))
    assert (
        bad_files == []
    ), f"etf_universe_topn_latest.json 참조가 코드에 남아 있다: {bad_files}"
