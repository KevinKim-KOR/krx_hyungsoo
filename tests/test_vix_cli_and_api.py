"""VIX CLI 서브커맨드 + /market/topn/latest 응답 확장 테스트 (2026-07-03)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app import api as api_module
from app import api_market_topn, market_data_store
from app.market_benchmark_store import upsert_benchmark_prices
from app.market_data_store import (
    EtfDailyPriceRow,
    EtfMasterRow,
    init_db,
    upsert_daily_prices,
    upsert_etf_master,
)


@pytest.fixture
def fake_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db = tmp_path / "market_data.sqlite"
    init_db(db)
    monkeypatch.setattr(api_market_topn, "DEFAULT_DB_PATH", db)
    monkeypatch.setattr(market_data_store, "DEFAULT_DB_PATH", db)
    return db


def _seed_topn_universe(db: Path) -> None:
    """/market/topn/latest 가 status=ok 응답할 최소 데이터."""
    upsert_etf_master(
        [EtfMasterRow("069500", "KODEX 200", "1", 100.0, 1000, 5000.0)],
        source="TEST",
        db_path=db,
    )
    upsert_daily_prices(
        [
            EtfDailyPriceRow(
                ticker="069500",
                date=dt,
                open=None,
                high=None,
                low=None,
                close=c,
                volume=None,
                change=None,
            )
            for dt, c in [
                ("2026-06-30", 34000.0),
                ("2026-07-01", 34500.0),
                ("2026-07-02", 34845.0),
            ]
        ],
        source="TEST",
        db_path=db,
    )


# ---------- /market/topn/latest 응답 확장 (지시문 §7) ----------


def test_topn_response_includes_market_risk_reference_when_data(
    fake_db: Path,
) -> None:
    _seed_topn_universe(fake_db)
    upsert_benchmark_prices(
        benchmark_id="VIX",
        benchmark_name="VIX",
        rows=[
            ("2026-06-24", 10.0),
            ("2026-06-25", 10.5),
            ("2026-06-26", 11.0),
            ("2026-06-27", 11.5),
            ("2026-06-28", 12.0),
            ("2026-06-29", 15.0),
        ],
        source="FDR_VIX",
        db_path=fake_db,
    )
    client = TestClient(api_module.app)
    resp = client.get("/market/topn/latest")
    assert resp.status_code == 200
    body = resp.json()
    assert "market_risk_reference" in body
    mrr = body["market_risk_reference"]
    assert mrr["kodex200"]["availability"] == "available"
    assert mrr["kodex200"]["as_of_date"] == "2026-07-02"
    assert mrr["vix"]["availability"] == "available"
    assert mrr["vix"]["as_of_date"] == "2026-06-29"
    assert len(mrr["kodex200"]["recent_20d_series"]) == 3
    assert len(mrr["vix"]["recent_20d_series"]) == 6


def test_topn_response_market_risk_reference_unavailable_without_data(
    fake_db: Path,
) -> None:
    _seed_topn_universe(fake_db)
    client = TestClient(api_module.app)
    body = client.get("/market/topn/latest").json()
    assert "market_risk_reference" in body
    mrr = body["market_risk_reference"]
    # KODEX200 은 있음, VIX 는 없음.
    assert mrr["kodex200"]["availability"] == "available"
    assert mrr["vix"]["availability"] == "unavailable"
    assert mrr["vix"]["recent_20d_series"] == []


# ---------- vix CLI (지시문 §5) ----------


def test_vix_cli_writes_to_benchmark_table(
    fake_db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def stub_fdr(symbol, start, end):
        idx = pd.to_datetime(["2026-06-28", "2026-06-29"])
        return pd.DataFrame({"Close": [12.0, 15.0]}, index=idx)

    import FinanceDataReader as fdr

    monkeypatch.setattr(fdr, "DataReader", stub_fdr)
    from scripts.refresh_market_timeseries import main as cli

    rc = cli(["vix", "--db-path", str(fake_db)])
    assert rc == 0

    from app.market_benchmark_store import fetch_benchmark_history

    series = fetch_benchmark_history("VIX", db_path=fake_db)
    assert len(series) == 2
    assert series[-1] == ("2026-06-29", 15.0)


def test_vix_cli_conflict_does_not_overwrite(
    fake_db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # 기존 값.
    upsert_benchmark_prices(
        benchmark_id="VIX",
        benchmark_name="VIX",
        rows=[("2026-06-29", 15.0)],
        source="TEST",
        db_path=fake_db,
    )

    def stub_fdr_conflict(symbol, start, end):
        idx = pd.to_datetime(["2026-06-29"])
        return pd.DataFrame({"Close": [999.0]}, index=idx)

    import FinanceDataReader as fdr

    monkeypatch.setattr(fdr, "DataReader", stub_fdr_conflict)
    from scripts.refresh_market_timeseries import main as cli

    rc = cli(["vix", "--db-path", str(fake_db)])
    assert rc == 2
    # 기존 값 그대로.
    from app.market_benchmark_store import fetch_benchmark_history

    series = fetch_benchmark_history("VIX", db_path=fake_db)
    assert series == [("2026-06-29", 15.0)]


def test_vix_cli_up_to_date_returns_ok(
    fake_db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """이후 실행 — 마지막 저장일보다 새 데이터 없으면 rc=0."""
    upsert_benchmark_prices(
        benchmark_id="VIX",
        benchmark_name="VIX",
        rows=[("2050-01-01", 15.0)],
        source="TEST",
        db_path=fake_db,
    )
    from scripts.refresh_market_timeseries import main as cli

    # start > end → early return
    rc = cli(["vix", "--db-path", str(fake_db)])
    assert rc == 0


def test_vix_cli_does_not_call_kodex_or_etf(
    fake_db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC-3 — vix 는 KODEX200 / ETF universe 호출 X.

    스크립트의 다른 서브커맨드용 함수가 호출되지 않는지 sentinel 로 검증.
    """
    calls: list[str] = []
    from scripts import refresh_market_timeseries as rm

    orig_bench = rm._cmd_benchmark
    orig_initial = rm._cmd_initial
    orig_inc = rm._cmd_incremental

    def guard_bench(args):
        calls.append("benchmark")
        return orig_bench(args)

    def guard_initial(args):
        calls.append("initial")
        return orig_initial(args)

    def guard_inc(args):
        calls.append("incremental")
        return orig_inc(args)

    monkeypatch.setattr(rm, "_cmd_benchmark", guard_bench)
    monkeypatch.setattr(rm, "_cmd_initial", guard_initial)
    monkeypatch.setattr(rm, "_cmd_incremental", guard_inc)

    def stub_fdr(symbol, start, end):
        idx = pd.to_datetime(["2026-06-29"])
        return pd.DataFrame({"Close": [15.0]}, index=idx)

    import FinanceDataReader as fdr

    monkeypatch.setattr(fdr, "DataReader", stub_fdr)

    rc = rm.main(["vix", "--db-path", str(fake_db)])
    assert rc == 0
    assert calls == []  # 다른 서브커맨드 호출 안 됨.


def test_vix_cli_unparseable_latest_aborts(
    fake_db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FIX r1 (B-1) — 기존 latest VIX 날짜가 파싱 불가하면 명확한 실패로 종료."""
    import sqlite3

    from app.market_benchmark_store import init_benchmark_db

    init_benchmark_db(fake_db)
    con = sqlite3.connect(str(fake_db))
    try:
        con.execute(
            "INSERT INTO market_benchmark_daily_price "
            "(benchmark_id, benchmark_name, date, close, source, created_at) "
            "VALUES ('VIX', 'VIX', 'not-a-date', 10.0, 'TEST', '2026-01-01T00:00:00Z')"
        )
        con.commit()
    finally:
        con.close()

    # 실측 FDR 호출이 일어나면 안 된다 — 파싱 단계에서 즉시 실패.
    called = {"n": 0}

    def stub_fdr(symbol, start, end):
        called["n"] += 1
        return pd.DataFrame({"Close": [10.0]}, index=pd.to_datetime(["2026-06-29"]))

    import FinanceDataReader as fdr

    monkeypatch.setattr(fdr, "DataReader", stub_fdr)
    from scripts.refresh_market_timeseries import main as cli

    rc = cli(["vix", "--db-path", str(fake_db)])
    assert rc == 2
    assert called["n"] == 0  # FDR 호출 자체가 없어야 함.


def test_incremental_does_not_call_vix(
    fake_db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC-3 — incremental 이 vix 를 자동 호출하지 않는다.

    _cmd_vix 를 guard 로 감시.
    """
    from scripts import refresh_market_timeseries as rm

    upsert_etf_master(
        [EtfMasterRow("069500", "KODEX 200", "1", None, None, None)],
        source="TEST",
        db_path=fake_db,
    )

    calls: list[str] = []
    orig = rm._cmd_vix
    monkeypatch.setattr(
        rm,
        "_cmd_vix",
        lambda args: (calls.append("vix"), orig(args))[1],
    )

    def stub_fdr(symbol, start, end):
        idx = pd.to_datetime(["2026-06-30", "2026-07-01", "2026-07-02"])
        return pd.DataFrame({"Close": [34000.0, 34500.0, 34800.0]}, index=idx)

    # naver/yahoo adapter 는 별개 fetcher — vix 처럼 fdr.DataReader 를 직접
    # patch 하면 안 되므로 여기서는 adapter fetcher 만 stub.
    from app import market_timeseries_naver_yahoo_adapter as adapter

    def adapter_fetcher(symbol, start, end):
        return stub_fdr(symbol, start, end)

    monkeypatch.setattr(adapter, "_default_price_fetcher", adapter_fetcher)

    rm.main(["incremental", "--db-path", str(fake_db)])
    # incremental 내부 로직 상 rc 는 여러 케이스 가능 — 여기서는 vix 미호출 확인.
    assert "vix" not in calls
