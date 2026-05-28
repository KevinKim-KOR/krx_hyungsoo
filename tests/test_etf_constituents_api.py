"""ETF constituents API (POST refresh + GET analysis) 통합 테스트
(POC2 — 2026-05-27)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import api as api_module
from app import api_etf_constituents  # noqa: F401
from app.etf_constituents_store import (
    ConstituentRow,
    upsert_constituents,
)


@pytest.fixture
def api_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    fake_db = tmp_path / "market_data.sqlite"
    # store / service 모두 DEFAULT_DB_PATH 를 모듈 attr 로 참조하므로 둘 다 patch.
    from app import etf_constituents_store as store
    from app import etf_constituents_service as service
    from app import etf_constituents_analysis as analysis

    monkeypatch.setattr(store, "DEFAULT_DB_PATH", fake_db)
    monkeypatch.setattr(service, "DEFAULT_DB_PATH", fake_db)
    monkeypatch.setattr(analysis, "DEFAULT_DB_PATH", fake_db)
    # service 의 default_fetcher 는 pykrx 호출 — 통합 테스트에서는 stub fetcher 주입.

    return TestClient(api_module.app)


def _seed_two_etfs_in_db(db: Path):
    # 2026-05-27 FIX (검증자 B-6 NOTE 후속) — cache hit 검증을 위해 PYKRX_SOURCE
    # 와 일치하는 source 로 시드. service 의 cache check 가 PYKRX_SOURCE 매칭.
    from app.etf_constituents_fetcher import PYKRX_SOURCE

    upsert_constituents(
        [
            ConstituentRow(
                "139260", "2026-05-26", PYKRX_SOURCE, 1, "005930", "삼성전자", 25.0
            ),
            ConstituentRow(
                "139260",
                "2026-05-26",
                PYKRX_SOURCE,
                2,
                "000660",
                "SK하이닉스",
                20.0,
            ),
        ],
        db_path=db,
    )
    upsert_constituents(
        [
            ConstituentRow(
                "363580", "2026-05-26", PYKRX_SOURCE, 1, "005930", "삼성전자", 30.0
            ),
            ConstituentRow(
                "363580", "2026-05-26", PYKRX_SOURCE, 2, "035420", "NAVER", 12.0
            ),
        ],
        db_path=db,
    )


def test_post_refresh_rejects_more_than_10_tickers(api_client):
    res = api_client.post(
        "/market/constituents/refresh",
        json={
            "asof": "2026-05-26",
            "tickers": [f"00{i:04d}" for i in range(11)],
        },
    )
    body = res.json()
    assert res.status_code == 200
    assert body["status"] == "rejected"
    assert body["reason"] == "too_many_tickers"


def test_post_refresh_cache_only_when_data_exists(
    api_client, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    # 캐시 데이터 미리 시드.
    from app import etf_constituents_store as store

    _seed_two_etfs_in_db(store.DEFAULT_DB_PATH)

    # fetcher 가 호출되면 fail (캐시 우선 검증).
    def boom(ticker, asof, top_k):  # noqa: ARG001
        raise AssertionError("cache hit 인데 fetcher 가 호출됨")

    from app import etf_constituents_service as service

    monkeypatch.setattr(service, "default_fetcher", lambda: boom)

    res = api_client.post(
        "/market/constituents/refresh",
        json={
            "asof": "2026-05-26",
            "tickers": ["139260", "363580"],
        },
    )
    body = res.json()
    assert body["status"] == "ok"
    assert body["cached_count"] == 2
    assert body["fetched_count"] == 0


def test_get_analysis_returns_concentration_and_overlap(api_client):
    from app import etf_constituents_store as store

    _seed_two_etfs_in_db(store.DEFAULT_DB_PATH)

    res = api_client.get(
        "/market/constituents/analysis?tickers=139260,363580&asof=2026-05-26"
    )
    body = res.json()
    assert res.status_code == 200
    assert body["status"] == "ok"
    assert body["coverage"]["available_count"] == 2

    by_ticker = {c["etf_ticker"]: c for c in body["constituents"]}
    assert by_ticker["139260"]["status"] == "ok"
    assert by_ticker["139260"]["concentration"]["top1_weight_pct"] == 25.0
    assert by_ticker["139260"]["concentration"]["top3_weight_pct"] == 45.0

    assert len(body["overlap_matrix"]) == 1
    pair = body["overlap_matrix"][0]
    assert pair["common_count_top10"] == 1
    assert pair["weighted_overlap_pct"] == 25.0
    # repeated_core: 삼성전자가 2 ETF 에서 등장.
    assert len(body["repeated_core_holdings"]) == 1
    assert body["repeated_core_holdings"][0]["ticker"] == "005930"
    assert body["repeated_core_holdings"][0]["appears_in_etf_count"] == 2


def test_get_analysis_rejects_too_many_tickers(api_client):
    csv = ",".join(f"00{i:04d}" for i in range(11))
    res = api_client.get(f"/market/constituents/analysis?tickers={csv}&asof=2026-05-26")
    assert res.status_code == 422


def test_get_analysis_marks_unavailable_for_missing_ticker(api_client):
    res = api_client.get(
        "/market/constituents/analysis?tickers=UNKNOWN&asof=2026-05-26"
    )
    body = res.json()
    assert body["status"] == "ok"
    assert body["coverage"]["unavailable_count"] == 1
    assert body["constituents"][0]["status"] == "unavailable"


def test_get_analysis_asof_optional_uses_latest_when_missing(api_client):
    """2026-05-27 FIX (검증자 B-6 NOTE) — asof 미지정 시 latest_constituent_asof
    중 MAX 를 사용."""
    from app import etf_constituents_store as store

    # 두 ETF 를 서로 다른 asof 로 시드.
    upsert_constituents(
        [ConstituentRow("139260", "2026-05-25", "src", 1, "005930", "삼성전자", 25.0)],
        db_path=store.DEFAULT_DB_PATH,
    )
    upsert_constituents(
        [ConstituentRow("363580", "2026-05-26", "src", 1, "035420", "NAVER", 12.0)],
        db_path=store.DEFAULT_DB_PATH,
    )
    # asof 없이 호출 — MAX (2026-05-26) 가 effective asof. 139260 의 25일자
    # 데이터는 다른 asof 라 unavailable 처리.
    res = api_client.get("/market/constituents/analysis?tickers=139260,363580")
    body = res.json()
    assert res.status_code == 200
    assert body["asof"] == "2026-05-26"
    by_ticker = {c["etf_ticker"]: c for c in body["constituents"]}
    assert by_ticker["363580"]["status"] == "ok"
    assert by_ticker["139260"]["status"] == "unavailable"


def test_get_analysis_asof_optional_falls_back_to_today_when_no_data(api_client):
    """ticker 가 DB 에 1건도 없으면 today 로 fallback (모두 unavailable)."""
    res = api_client.get("/market/constituents/analysis?tickers=NEVER1,NEVER2")
    body = res.json()
    assert res.status_code == 200
    # today 의 ISO date — 형식만 확인.
    assert len(body["asof"]) == 10
    assert body["asof"][4] == "-" and body["asof"][7] == "-"
    assert body["coverage"]["available_count"] == 0
    assert body["coverage"]["unavailable_count"] == 2


def test_refresh_cache_first_matches_pykrx_source(
    api_client, monkeypatch: pytest.MonkeyPatch
):
    """2026-05-27 FIX (검증자 B-6 NOTE) — cache key 가 ticker+asof+source 일치
    매칭. PYKRX_SOURCE 와 다른 source 의 캐시는 hit 처리되지 않는다.
    """
    from app import etf_constituents_store as store

    # 다른 source 로 시드 (예: "src" — pykrx 와 다름).
    upsert_constituents(
        [ConstituentRow("139260", "2026-05-26", "src", 1, "005930", "삼성전자", 25.0)],
        db_path=store.DEFAULT_DB_PATH,
    )

    called: list[str] = []

    def stub_fetcher(ticker, asof, top_k):  # noqa: ARG001
        from app.etf_constituents_fetcher import (
            FetchedConstituent,
            FetchResult,
            PYKRX_SOURCE,
        )

        called.append(ticker)
        return FetchResult(
            status="ok",
            source=PYKRX_SOURCE,
            constituents=[
                FetchedConstituent(
                    rank=1,
                    constituent_ticker="005930",
                    constituent_name="삼성전자",
                    weight_pct=25.0,
                )
            ],
        )

    from app import etf_constituents_service as service

    monkeypatch.setattr(service, "default_fetcher", lambda: stub_fetcher)

    res = api_client.post(
        "/market/constituents/refresh",
        json={"asof": "2026-05-26", "tickers": ["139260"]},
    )
    body = res.json()
    # 기존 캐시는 다른 source 라 hit 안 됨 → fetcher 호출됨.
    assert called == ["139260"]
    assert body["fetched_count"] == 1
    assert body["cached_count"] == 0
