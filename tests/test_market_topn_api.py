"""POC2 PC Market Discovery — GET /market/topn/latest read-only API 테스트.

검증 (지시문 §9 backend):
1. artifact 정상 → status=ok + TOP N 데이터
2. artifact 없음 → status=missing
3. artifact JSON 깨짐 → status=invalid
4. 필수 키 누락 → status=invalid
5. API 호출 중 FDR refresh 발생하지 않음
6. API 호출 중 SQLite 직접 조회 발생하지 않음
7. API 는 artifact 파일만 읽음
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import api as api_module
from app import api_market_topn
from app.market_topn import compute_and_save_topn
from app.market_data_store import (
    EtfDailyPriceRow,
    EtfMasterRow,
    upsert_daily_prices,
    upsert_etf_master,
)


@pytest.fixture
def artifact_dir(tmp_path: Path) -> Path:
    return tmp_path / "market"


def _seed_artifact(artifact_dir: Path) -> Path:
    """SQLite + artifact 를 tmp 경로에 모두 생성."""
    db_path = artifact_dir / "market_data.sqlite"
    artifact_path = artifact_dir / "etf_universe_topn_latest.json"
    from datetime import date, timedelta

    end = date(2024, 10, 31)
    d_minus_1 = (end - timedelta(days=1)).isoformat()
    d_minus_30 = (end - timedelta(days=30)).isoformat()
    d_minus_90 = (end - timedelta(days=90)).isoformat()

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
                (d_minus_90, 100.0),
                (d_minus_30, 105.0),
                (d_minus_1, 110.0),
                (end.isoformat(), 112.0),
            ],
        ),
        (
            "379800",
            [
                (d_minus_90, 100.0),
                (d_minus_30, 110.0),
                (d_minus_1, 119.0),
                (end.isoformat(), 120.0),
            ],
        ),
    ]:
        upsert_daily_prices(
            [EtfDailyPriceRow(tk, dt, c, c, c, c, 0, 0) for dt, c in closes],
            source="TestSource",
            db_path=db_path,
        )
    compute_and_save_topn(n=10, db_path=db_path, artifact_path=artifact_path)
    return artifact_path


# === Pure reader unit tests ===


def test_read_artifact_ok(artifact_dir: Path) -> None:
    path = _seed_artifact(artifact_dir)
    resp = api_market_topn.read_topn_artifact(path)
    assert resp.status == "ok"
    assert resp.asof == "2024-10-31"
    assert resp.source == "FinanceDataReader"
    assert resp.n == 10
    assert resp.universe_count == 2
    assert len(resp.daily_topn) == 2
    assert len(resp.one_month_topn) == 2
    assert len(resp.three_month_topn) == 2
    # 한 항목 형식 확인
    first = resp.daily_topn[0]
    assert first.rank == 1
    assert first.basis_end_date == "2024-10-31"


def test_read_artifact_missing(tmp_path: Path) -> None:
    path = tmp_path / "does_not_exist.json"
    resp = api_market_topn.read_topn_artifact(path)
    assert resp.status == "missing"
    assert resp.error is not None
    assert "artifact" in resp.error
    # missing 일 때도 정상 응답 구조 유지 (None 필드 + 빈 리스트)
    assert resp.daily_topn == []
    assert resp.one_month_topn == []
    assert resp.three_month_topn == []


def test_read_artifact_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "broken.json"
    path.write_text("{not-valid-json", encoding="utf-8")
    resp = api_market_topn.read_topn_artifact(path)
    assert resp.status == "invalid"
    assert resp.error is not None
    assert "JSON" in resp.error or "파싱" in resp.error


def test_entries_preserve_nulls_no_fabricated_defaults(tmp_path: Path) -> None:
    """지시문 §3.2 fallback 금지 — entry 필드 누락은 None 통과, 0/""/0.0 생성 금지.

    검증자 NOTE (A-1 / B-1) 반영: TOP N entry 의 rank/ticker/return_pct/name/basis_*
    필드 중 일부가 artifact 에서 누락되어도 백엔드가 0 / "" / 0.0 으로 채워넣지 않는다.
    """
    path = tmp_path / "partial_entries.json"
    path.write_text(
        json.dumps(
            {
                "asof": "2024-10-31",
                "source": "TestSource",
                "n": 10,
                "universe_count": 1,
                "daily_topn": [
                    # rank + ticker + return_pct 모두 있고 name 만 누락 — 통과
                    {
                        "rank": 1,
                        "ticker": "069500",
                        "return_pct": 1.23,
                    },
                    # return_pct 누락 — null 로 통과 (0.0 으로 생성 금지)
                    {
                        "rank": 2,
                        "ticker": "379800",
                    },
                    # rank 누락 — null 로 통과
                    {
                        "ticker": "133690",
                        "return_pct": -0.5,
                    },
                    # 3 필수 필드 모두 누락 — entry 자체 skip
                    {
                        "basis_start_date": "2024-10-01",
                    },
                ],
                "one_month_topn": [],
                "three_month_topn": [],
            }
        ),
        encoding="utf-8",
    )
    resp = api_market_topn.read_topn_artifact(path)
    assert resp.status == "ok"
    daily = resp.daily_topn
    # 마지막 entry (모든 필수 필드 누락) 만 skip — 3건 유지
    assert len(daily) == 3
    # row 0: name 만 누락 → name=None, 나머지는 그대로
    assert daily[0].rank == 1
    assert daily[0].ticker == "069500"
    assert daily[0].return_pct == 1.23
    assert daily[0].name is None  # 0 / "" 로 생성 금지
    # row 1: return_pct 누락 → None (0.0 생성 금지)
    assert daily[1].rank == 2
    assert daily[1].ticker == "379800"
    assert daily[1].return_pct is None
    # row 2: rank 누락 → None (0 생성 금지)
    assert daily[2].rank is None
    assert daily[2].ticker == "133690"
    assert daily[2].return_pct == -0.5


def test_read_artifact_invalid_missing_required_keys(tmp_path: Path) -> None:
    path = tmp_path / "partial.json"
    # 최상위는 객체지만 필수 키 (universe_count / daily_topn 등) 누락
    path.write_text(json.dumps({"asof": "2024-10-31"}), encoding="utf-8")
    resp = api_market_topn.read_topn_artifact(path)
    assert resp.status == "invalid"
    assert "필수 키" in resp.error


# === FastAPI endpoint tests (monkeypatch DEFAULT_TOPN_PATH) ===


@pytest.fixture
def api_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    """endpoint 가 사용하는 DEFAULT_TOPN_PATH 를 tmp 경로로 교체."""
    fake_path = tmp_path / "etf_universe_topn_latest.json"
    monkeypatch.setattr(api_market_topn, "DEFAULT_TOPN_PATH", fake_path)
    return TestClient(api_module.app)


def test_endpoint_returns_ok_when_artifact_present(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    # endpoint 가 가리키는 경로에 valid artifact 쓰기
    fake_path = api_market_topn.DEFAULT_TOPN_PATH
    fake_path.parent.mkdir(parents=True, exist_ok=True)
    fake_path.write_text(
        json.dumps(
            {
                "asof": "2024-10-31",
                "source": "FinanceDataReader",
                "n": 10,
                "universe_count": 1,
                "price_success_count": 1,
                "price_fail_count": 0,
                "runtime_seconds": 0.1,
                "daily_topn": [
                    {
                        "rank": 1,
                        "ticker": "069500",
                        "name": "KODEX 200",
                        "return_pct": 1.23,
                        "basis_start_date": "2024-10-30",
                        "basis_end_date": "2024-10-31",
                    }
                ],
                "one_month_topn": [],
                "three_month_topn": [],
                "topn_caveat": "TOP N 의 N 값은 고정값이 아니며 운영/테스트 중 변경 가능.",
            }
        ),
        encoding="utf-8",
    )
    res = api_client.get("/market/topn/latest")
    assert res.status_code == 200
    payload = res.json()
    assert payload["status"] == "ok"
    assert payload["asof"] == "2024-10-31"
    assert payload["universe_count"] == 1
    assert len(payload["daily_topn"]) == 1
    assert payload["daily_topn"][0]["ticker"] == "069500"


def test_endpoint_returns_missing_when_artifact_absent(
    api_client: TestClient,
) -> None:
    res = api_client.get("/market/topn/latest")
    assert res.status_code == 200
    payload = res.json()
    assert payload["status"] == "missing"
    assert payload["daily_topn"] == []


def test_endpoint_returns_invalid_when_json_broken(
    api_client: TestClient,
) -> None:
    fake_path = api_market_topn.DEFAULT_TOPN_PATH
    fake_path.parent.mkdir(parents=True, exist_ok=True)
    fake_path.write_text("{broken", encoding="utf-8")
    res = api_client.get("/market/topn/latest")
    assert res.status_code == 200
    payload = res.json()
    assert payload["status"] == "invalid"
    assert payload["error"] is not None


# === 금지 호출 가드 (지시문 AC-9 / §9 backend 4~6) ===


def test_endpoint_does_not_trigger_fdr_refresh(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """API 호출이 FDR refresh / SQLite 직접 조회를 발생시키지 않음."""
    # FDR refresh 함수가 호출되면 즉시 실패시키는 가드
    from app import market_data_fdr

    def boom(*args, **kwargs):
        raise AssertionError("FDR refresh 호출 발생 — 금지 (지시문 §3.1)")

    monkeypatch.setattr(market_data_fdr, "refresh_etf_universe", boom)
    monkeypatch.setattr(market_data_fdr, "refresh_price_history", boom)

    # SQLite 직접 조회 함수도 호출되면 실패
    from app import market_data_store

    def boom_sql(*args, **kwargs):
        raise AssertionError("SQLite 직접 조회 호출 발생 — 금지 (지시문 §3.1)")

    monkeypatch.setattr(market_data_store, "list_etf_tickers", boom_sql)
    monkeypatch.setattr(market_data_store, "fetch_price_history", boom_sql)

    res = api_client.get("/market/topn/latest")
    # artifact 없으니까 missing 응답이지만, 무엇보다 boom 들이 호출되지 않아야 함
    assert res.status_code == 200
    payload = res.json()
    assert payload["status"] in ("missing", "ok", "invalid")


def test_endpoint_reads_only_artifact_file_not_sqlite(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """artifact 파일만 읽고 SQLite 파일은 절대 열지 않는다."""
    import sqlite3

    original_connect = sqlite3.connect
    seen_connections: list[str] = []

    def tracking_connect(database, *args, **kwargs):
        seen_connections.append(str(database))
        return original_connect(database, *args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", tracking_connect)
    api_client.get("/market/topn/latest")
    assert seen_connections == []
