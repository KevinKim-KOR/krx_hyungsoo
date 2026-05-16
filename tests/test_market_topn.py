"""POC2 — SQLite 기반 일간 / 1개월 / 3개월 TOP N 산출 테스트.

검증:
- daily / 1m / 3m 모두 계산.
- N 값 변경 시 결과 개수 변화.
- artifact JSON 생성.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from app.market_data_store import (
    EtfDailyPriceRow,
    EtfMasterRow,
    upsert_daily_prices,
    upsert_etf_master,
)
from app.market_topn import (
    compute_and_save_topn,
    compute_topn,
)


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "market_data.sqlite"


def _seed_universe(db_path: Path, ticker_names: list[tuple[str, str]]) -> None:
    rows = [
        EtfMasterRow(
            ticker=tk, name=nm, category="X", price=None, volume=None, market_cap=None
        )
        for tk, nm in ticker_names
    ]
    upsert_etf_master(rows, source="TestSource", db_path=db_path)


def _seed_price_series(
    db_path: Path,
    ticker: str,
    closes: list[tuple[str, float]],
) -> None:
    rows = [
        EtfDailyPriceRow(
            ticker=ticker, date=d, open=c, high=c, low=c, close=c, volume=0, change=0
        )
        for d, c in closes
    ]
    upsert_daily_prices(rows, source="TestSource", db_path=db_path)


def _dates_around(end: date) -> dict[str, str]:
    return {
        "end": end.isoformat(),
        "minus_1": (end - timedelta(days=1)).isoformat(),
        "minus_30": (end - timedelta(days=30)).isoformat(),
        "minus_90": (end - timedelta(days=90)).isoformat(),
    }


def _seed_three_etfs(db_path: Path, end: date) -> None:
    d = _dates_around(end)
    _seed_universe(
        db_path,
        [("AAA001", "ETF A"), ("BBB002", "ETF B"), ("CCC003", "ETF C")],
    )
    # AAA001: 1m 대박, 3m 대박, daily 보통
    _seed_price_series(
        db_path,
        "AAA001",
        [
            (d["minus_90"], 100.0),
            (d["minus_30"], 110.0),
            (d["minus_1"], 119.0),
            (d["end"], 120.0),
        ],
    )
    # BBB002: 1m 평범, 3m 평범, daily 1위
    _seed_price_series(
        db_path,
        "BBB002",
        [
            (d["minus_90"], 100.0),
            (d["minus_30"], 102.0),
            (d["minus_1"], 100.0),
            (d["end"], 105.0),
        ],
    )
    # CCC003: 1m 마이너스, 3m 마이너스, daily 최하
    _seed_price_series(
        db_path,
        "CCC003",
        [
            (d["minus_90"], 100.0),
            (d["minus_30"], 99.0),
            (d["minus_1"], 95.0),
            (d["end"], 94.0),
        ],
    )


def test_compute_topn_daily(db_path: Path) -> None:
    end = date(2024, 10, 31)
    _seed_three_etfs(db_path, end)

    payload = compute_topn(n=3, db_path=db_path)
    assert payload["asof"] == end.isoformat()
    assert payload["universe_count"] == 3

    daily = payload["daily_topn"]
    assert [r["ticker"] for r in daily] == ["BBB002", "AAA001", "CCC003"]
    assert daily[0]["rank"] == 1
    assert daily[0]["return_pct"] == pytest.approx(5.0, abs=0.01)
    # ETF 이름 매핑 살아 있어야 함
    assert daily[0]["name"] == "ETF B"
    # basis_start/end_date 가 일관됨
    assert daily[0]["basis_end_date"] == end.isoformat()


def test_compute_topn_one_month(db_path: Path) -> None:
    end = date(2024, 10, 31)
    _seed_three_etfs(db_path, end)
    payload = compute_topn(n=3, db_path=db_path)
    one_m = payload["one_month_topn"]
    assert [r["ticker"] for r in one_m] == ["AAA001", "BBB002", "CCC003"]
    assert one_m[0]["return_pct"] == pytest.approx(
        (120.0 / 110.0 - 1) * 100.0, abs=0.01
    )


def test_compute_topn_three_month(db_path: Path) -> None:
    end = date(2024, 10, 31)
    _seed_three_etfs(db_path, end)
    payload = compute_topn(n=3, db_path=db_path)
    three_m = payload["three_month_topn"]
    assert [r["ticker"] for r in three_m] == ["AAA001", "BBB002", "CCC003"]
    assert three_m[0]["return_pct"] == pytest.approx(20.0, abs=0.01)


def test_compute_topn_respects_n_parameter(db_path: Path) -> None:
    end = date(2024, 10, 31)
    _seed_three_etfs(db_path, end)

    payload_n1 = compute_topn(n=1, db_path=db_path)
    assert len(payload_n1["daily_topn"]) == 1
    assert len(payload_n1["one_month_topn"]) == 1
    assert len(payload_n1["three_month_topn"]) == 1

    payload_n2 = compute_topn(n=2, db_path=db_path)
    assert len(payload_n2["daily_topn"]) == 2
    assert len(payload_n2["one_month_topn"]) == 2
    assert len(payload_n2["three_month_topn"]) == 2

    payload_n10 = compute_topn(n=10, db_path=db_path)
    # universe 가 3개뿐 — TOP 10 요청해도 최대 3개
    assert len(payload_n10["daily_topn"]) == 3
    assert payload_n10["n"] == 10


def test_compute_and_save_artifact_writes_json(tmp_path: Path) -> None:
    db_path = tmp_path / "market_data.sqlite"
    artifact = tmp_path / "etf_universe_topn_latest.json"
    end = date(2024, 10, 31)
    _seed_three_etfs(db_path, end)

    payload, written_path = compute_and_save_topn(
        n=10, db_path=db_path, artifact_path=artifact
    )
    assert written_path == artifact
    assert artifact.exists()

    loaded = json.loads(artifact.read_text(encoding="utf-8"))
    assert loaded["asof"] == end.isoformat()
    assert loaded["source"] == "FinanceDataReader"
    assert loaded["n"] == 10
    assert loaded["universe_count"] == 3
    assert len(loaded["daily_topn"]) == 3
    assert loaded["topn_caveat"].startswith("TOP N 의 N 값은 고정값이 아니며")


def test_compute_topn_empty_db_returns_safe_payload(db_path: Path) -> None:
    payload = compute_topn(n=10, db_path=db_path)
    assert payload["universe_count"] == 0
    assert payload["asof"] is None
    assert payload["daily_topn"] == []
    assert payload["one_month_topn"] == []
    assert payload["three_month_topn"] == []
