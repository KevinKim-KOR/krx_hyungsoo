"""POC2 — FDR wrapper 테스트 (stub 기반).

검증:
- universe fetch stub → etf_master 저장.
- etf_master 저장 시 ticker 별 추가 호출 0건 (AC-4).
- price fetch stub → etf_daily_price 저장.
- market_refresh_log 기록.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from app.market_data_store import (
    fetch_price_history,
    latest_refresh_log,
    list_etf_tickers,
)
from app.market_data_fdr import (
    refresh_etf_universe,
    refresh_price_history,
)


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "market_data.sqlite"


def _stub_universe_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Symbol": "069500",
                "Category": 1,
                "Name": "KODEX 200",
                "Price": 11720.0,
                "Change": -765,
                "ChangeRate": -6.13,
                "NAV": 11691.0,
                "EarningRate": 43.8,
                "Volume": 27724693,
                "Amount": 3333867,
                "MarCap": 249988.0,
                "RiseFall": 5,
            },
            {
                "Symbol": "379800",
                "Category": 4,
                "Name": "KODEX 미국S&P500",
                "Price": 27765.0,
                "Change": 170,
                "ChangeRate": 0.62,
                "NAV": 27919.0,
                "EarningRate": 13.88,
                "Volume": 19449232,
                "Amount": 540600,
                "MarCap": 179445.0,
                "RiseFall": 2,
            },
            {
                "Symbol": "69500",
                "Category": 1,
                "Name": "(short-form duplicate)",
                "Price": None,
                "Volume": None,
                "MarCap": None,
            },
        ]
    )


def _stub_price_df(start: date, end: date) -> pd.DataFrame:
    # 최소 일별 3행 — daily / 1m / 3m base 모두 산정 가능 시계열은 별도 테스트에서 다룸
    idx = pd.to_datetime([f"{start.isoformat()}", f"{end.isoformat()}"])
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


def test_refresh_etf_universe_uses_single_listing_call_no_n_plus_one(
    db_path: Path,
) -> None:
    """AC-4: universe 저장 시 ticker 별 fdr.DataReader 호출이 발생하면 안 된다."""
    call_count = {"universe": 0, "price_per_ticker": 0}

    def stub_universe_fetcher():
        call_count["universe"] += 1
        return _stub_universe_df()

    def banned_price_fetcher(*_args, **_kwargs):
        # 본 테스트에서 price fetcher 가 호출되면 N+1 위반.
        call_count["price_per_ticker"] += 1
        raise AssertionError(
            "etf_master 채우기 단계에서 가격 호출 발생 — N+1 금지 위반"
        )

    result = refresh_etf_universe(fetcher=stub_universe_fetcher, db_path=db_path)

    assert result.success is True
    assert result.universe_count == 3
    assert call_count["universe"] == 1
    assert call_count["price_per_ticker"] == 0

    tickers = list_etf_tickers(db_path)
    # zero-pad 6자리 정규화 — "69500" 도 "069500" 으로 합쳐져 결국 2개 distinct ticker
    assert "069500" in tickers
    assert "379800" in tickers


def test_refresh_etf_universe_logs_refresh_summary(db_path: Path) -> None:
    refresh_etf_universe(fetcher=_stub_universe_df, db_path=db_path)
    log = latest_refresh_log(source="FinanceDataReader/universe", db_path=db_path)
    assert log is not None
    assert log["attempted_count"] == 3  # stub 3 rows
    assert log["success_count"] == 3
    assert log["fail_count"] == 0


def test_refresh_etf_universe_handles_empty_dataframe(db_path: Path) -> None:
    def empty_fetcher():
        return pd.DataFrame(columns=["Symbol", "Name"])

    result = refresh_etf_universe(fetcher=empty_fetcher, db_path=db_path)
    assert result.success is False
    assert result.universe_count == 0
    log = latest_refresh_log(source="FinanceDataReader/universe", db_path=db_path)
    assert log is not None
    assert log["fail_count"] == 1
    assert log["error_summary"] == "empty_universe"


def test_refresh_price_history_stores_rows_and_logs(db_path: Path) -> None:
    captured_calls: list[tuple[str, date, date]] = []

    def stub_price_fetcher(ticker, start, end):
        captured_calls.append((ticker, start, end))
        return _stub_price_df(start, end)

    end_d = date(2024, 10, 31)
    result = refresh_price_history(
        ["069500", "379800"],
        end_date=end_d,
        lookback_days=120,
        price_fetcher=stub_price_fetcher,
        db_path=db_path,
    )

    assert result.attempted == 2
    assert result.success == 2
    assert result.fail == 0
    assert len(captured_calls) == 2

    hist_069 = fetch_price_history("069500", db_path=db_path)
    assert len(hist_069) == 2
    assert hist_069[-1][1] == 101.5

    log = latest_refresh_log(source="FinanceDataReader/prices", db_path=db_path)
    assert log is not None
    assert log["success_count"] == 2
    assert log["fail_count"] == 0


def test_refresh_price_history_isolates_per_ticker_failure(db_path: Path) -> None:
    def mixed_fetcher(ticker, start, end):
        if ticker == "BAD001":
            raise RuntimeError("simulated fetch error")
        return _stub_price_df(start, end)

    result = refresh_price_history(
        ["069500", "BAD001", "379800"],
        end_date=date(2024, 10, 31),
        lookback_days=120,
        price_fetcher=mixed_fetcher,
        db_path=db_path,
    )
    assert result.attempted == 3
    assert result.success == 2
    assert result.fail == 1
    assert any(f["ticker"] == "BAD001" for f in result.failure_examples)

    log = latest_refresh_log(source="FinanceDataReader/prices", db_path=db_path)
    assert log["fail_count"] == 1
    assert log["error_summary"] is not None
    assert "BAD001" in log["error_summary"]


def test_refresh_price_history_no_data_recorded_as_failure(db_path: Path) -> None:
    def no_data_fetcher(_ticker, _start, _end):
        return pd.DataFrame()

    result = refresh_price_history(
        ["498400"],
        end_date=date(2024, 10, 31),
        lookback_days=120,
        price_fetcher=no_data_fetcher,
        db_path=db_path,
    )
    assert result.attempted == 1
    assert result.success == 0
    assert result.fail == 1
    assert result.failure_examples[0]["error"] == "no_data"
