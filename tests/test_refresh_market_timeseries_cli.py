"""scripts/refresh_market_timeseries.py CLI 자동 테스트.

외부 네트워크 없이 stub fetcher (adapter._default_price_fetcher patch) 로 검증.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Iterable

import pandas as pd
import pytest

from app.market_data_store import (
    EtfMasterRow,
    fetch_price_history,
    init_db,
    upsert_etf_master,
)
from app.market_timeseries_ingestion_store import STATUS_NORMAL, read_state
from app.market_timeseries_refresh_state_store import (
    STATUS_OK,
    read_state as read_refresh_state,
)


def _df(rows: Iterable[tuple[str, float]]) -> pd.DataFrame:
    idx = pd.to_datetime([r[0] for r in rows])
    return pd.DataFrame({"Close": [r[1] for r in rows]}, index=idx)


@pytest.fixture
def fake_db(tmp_path: Path) -> Path:
    db = tmp_path / "market_data.sqlite"
    init_db(db)
    return db


@pytest.fixture
def stub_fetcher(monkeypatch: pytest.MonkeyPatch):
    """네이버 primary + Yahoo fallback stub 을 등록한 상태로 반환."""

    prices: dict[str, list[tuple[str, float]]] = {
        "069500": [
            ("2024-10-29", 100.0),
            ("2024-10-30", 101.0),
            ("2024-10-31", 102.0),
        ],
    }

    def fetcher(symbol: str, start: date, end: date):
        # FIX r1 — CLI 는 이제 NAVER:<ticker> / YAHOO:<ticker>.KS 로 호출.
        raw = symbol
        if raw.startswith("NAVER:"):
            raw = raw.split(":", 1)[1]
        elif raw.startswith("YAHOO:"):
            raw = raw.split(":", 1)[1]
            if raw.endswith(".KS"):
                raw = raw.rsplit(".KS", 1)[0]
        rows = prices.get(raw, [])
        return _df(rows)

    from app import market_timeseries_naver_yahoo_adapter as adapter

    monkeypatch.setattr(adapter, "_default_price_fetcher", fetcher)
    return prices


def _seed_universe(db: Path, tickers: list[str]) -> None:
    upsert_etf_master(
        [
            EtfMasterRow(
                ticker=tk,
                name=f"N_{tk}",
                category="1",
                price=None,
                volume=None,
                market_cap=None,
            )
            for tk in tickers
        ],
        source="TEST",
        db_path=db,
    )


# ---------- benchmark ----------


def test_cli_benchmark_writes_refresh_state(fake_db: Path, stub_fetcher) -> None:
    from scripts.refresh_market_timeseries import main as cli

    rc = cli(["benchmark", "--db-path", str(fake_db)])
    assert rc == 0
    refresh = read_refresh_state(db_path=fake_db)
    assert refresh is not None
    assert refresh.last_attempt_status == STATUS_OK
    assert refresh.benchmark_asof_date == "2024-10-31"
    series = fetch_price_history("069500", db_path=fake_db)
    assert len(series) == 3


def test_cli_benchmark_failure_marks_failed(
    fake_db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """네이버·Yahoo 모두 빈 응답 → refresh_state.status=failed."""
    from app import market_timeseries_naver_yahoo_adapter as adapter

    def empty(symbol: str, start: date, end: date):
        return _df([])

    monkeypatch.setattr(adapter, "_default_price_fetcher", empty)
    from scripts.refresh_market_timeseries import main as cli

    rc = cli(["benchmark", "--db-path", str(fake_db)])
    assert rc == 2
    refresh = read_refresh_state(db_path=fake_db)
    assert refresh is not None
    assert refresh.last_attempt_status == "failed"


# ---------- initial / incremental / status ----------


def test_cli_initial_requires_benchmark_first(fake_db: Path, stub_fetcher) -> None:
    _seed_universe(fake_db, ["069500", "379800"])
    from scripts.refresh_market_timeseries import main as cli

    rc = cli(["initial", "--max-tickers", "1", "--db-path", str(fake_db)])
    # benchmark 안 돌린 상태 → rc=2
    assert rc == 2


def test_cli_initial_processes_pending_tickers(
    fake_db: Path, stub_fetcher, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_universe(fake_db, ["069500", "379800"])
    # 379800 도 fetcher stub 에 등록.
    stub_fetcher["379800"] = [
        ("2024-10-29", 200.0),
        ("2024-10-30", 201.0),
        ("2024-10-31", 202.0),
    ]

    from scripts.refresh_market_timeseries import main as cli

    assert cli(["benchmark", "--db-path", str(fake_db)]) == 0
    rc = cli(["initial", "--all", "--db-path", str(fake_db)])
    assert rc == 0
    st = read_state("379800", db_path=fake_db)
    assert st is not None
    assert st.ingestion_status == STATUS_NORMAL


def test_cli_incremental_processes_normal_tickers(fake_db: Path, stub_fetcher) -> None:
    _seed_universe(fake_db, ["069500", "379800"])
    stub_fetcher["379800"] = [
        ("2024-10-29", 200.0),
        ("2024-10-30", 201.0),
        ("2024-10-31", 202.0),
    ]
    from scripts.refresh_market_timeseries import main as cli

    assert cli(["benchmark", "--db-path", str(fake_db)]) == 0
    assert cli(["initial", "--all", "--db-path", str(fake_db)]) == 0

    # 다음 실행에서 새 거래일 추가.
    stub_fetcher["069500"].append(("2024-11-01", 103.0))
    stub_fetcher["379800"].append(("2024-11-01", 203.0))
    rc = cli(["incremental", "--db-path", str(fake_db)])
    assert rc == 0
    series = dict(fetch_price_history("379800", db_path=fake_db))
    assert "2024-11-01" in series


def test_cli_status_command(fake_db: Path, stub_fetcher, capsys) -> None:
    from scripts.refresh_market_timeseries import main as cli

    cli(["benchmark", "--db-path", str(fake_db)])
    rc = cli(["status", "--db-path", str(fake_db)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "benchmark_asof_date" in out
    assert "ingestion counts" in out


def test_cli_output_is_ascii_safe(fake_db: Path, stub_fetcher, capsys) -> None:
    """Windows cp949 안전 (ASCII 만 출력)."""
    _seed_universe(fake_db, ["069500"])
    from scripts.refresh_market_timeseries import main as cli

    cli(["benchmark", "--db-path", str(fake_db)])
    cli(["status", "--db-path", str(fake_db)])
    captured = capsys.readouterr()
    captured.out.encode("ascii")
    captured.err.encode("ascii")
