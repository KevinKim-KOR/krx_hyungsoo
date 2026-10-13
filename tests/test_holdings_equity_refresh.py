"""POC5-10 — PC 수동 갱신의 보유 개별주 가격 단계 (PLAN §2 · §6 · 설계 POC5-09 §10-4 · §10-5).

격리 DB(tmp) · 가짜 수집기만 쓴다. 보유 파일은 conftest 격리 경로(tmp)에만 쓴다. 외부 호출 0.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest

from app import holdings as holdings_module
from app import market_refresh_service
from app.holdings_equity_refresh import (
    HOLDINGS_EQUITY_LOG_SOURCE,
    HOLDINGS_EQUITY_STEP_FAILED_TEXT,
    HOLDINGS_READ_FAILED_TEXT,
)
from app.market_data_store import (
    EtfDailyPriceRow,
    fetch_price_history,
    get_last_price_date,
    latest_refresh_log,
    list_etf_tickers,
    upsert_daily_prices,
)
from app.market_refresh_service import (
    get_state_snapshot,
    reset_state_for_testing,
    start_refresh_job,
)
from app.pc_price_basis import apply_pc_price_basis, load_recent_price_rows

END = date(2026, 10, 12)


def _universe_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Symbol": t,
                "Category": 1,
                "Name": n,
                "Price": 100.0,
                "Volume": 10,
                "MarCap": 1.0,
            }
            for t, n in (("069500", "KODEX 200"), ("111111", "ETF A"))
        ]
    )


class FakeFetcher:
    """가짜 FDR: 요청 구간의 평일 행을 돌려준다. fail 에 든 종목은 예외."""

    def __init__(self, fail: tuple[str, ...] = ()):
        self.fail = set(fail)
        self.calls: list[tuple[str, date, date]] = []

    def __call__(self, ticker: str, start: date, end: date):
        self.calls.append((ticker, start, end))
        if ticker in self.fail:
            raise RuntimeError(f"boom {ticker}")
        days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
        days = [d for d in days if d.weekday() < 5]
        idx = pd.to_datetime([d.isoformat() for d in days])
        n = len(days)
        return pd.DataFrame(
            {
                "Open": [100.0] * n,
                "High": [100.0] * n,
                "Low": [100.0] * n,
                "Close": [100.0 + i for i in range(n)],
                "Volume": [1000] * n,
                "Change": [0.0] * n,
            },
            index=idx,
        )


@pytest.fixture
def fake_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db = tmp_path / "market_data.sqlite"
    monkeypatch.setattr("app.market_data_store.DEFAULT_DB_PATH", db, raising=True)
    monkeypatch.setattr("app.market_refresh_service.DEFAULT_DB_PATH", db, raising=True)
    monkeypatch.setattr(
        "app.market_briefing.calendar.CALENDAR_DIR", tmp_path / "no_calendar"
    )
    monkeypatch.setattr(
        market_refresh_service, "_regenerate_intraday_config", lambda db_path: None
    )
    # KOSPI 단계는 이 시험 대상이 아니다 — 외부 호출 없이 성공으로 둔다(기록 행은 그대로 남음).
    monkeypatch.setattr(
        market_refresh_service,
        "refresh_kospi_benchmark",
        lambda **kw: {"status": "ok", "error": None},
    )
    reset_state_for_testing(db_path=db)
    return db


def _seed_stock_until(db: Path, ticker: str, last: date, n: int = 30) -> None:
    rows = []
    d = last
    while len(rows) < n:
        if d.weekday() < 5:
            rows.append(EtfDailyPriceRow(ticker, d.isoformat(), 1, 1, 1, 50.0, 5, 0))
        d -= timedelta(days=1)
    upsert_daily_prices(rows, source="FinanceDataReader", db_path=db)


def _hold(*tickers: str, accounts: tuple[str, ...] = ()) -> None:
    rows = [holdings_module.Holding(t, 1.0, 100.0) for t in tickers]
    rows += [
        holdings_module.Holding(t, 1.0, 100.0, account_group=a) for t, a in accounts
    ]
    holdings_module.save(rows)


def _run(db: Path, fetcher: FakeFetcher) -> None:
    start_refresh_job(
        db_path=db,
        cooldown_hours=6,
        universe_fetcher=_universe_df,
        price_fetcher=fetcher,
        end_date_for_prices=END,
        thread_runner=lambda runner: runner(),
    )


def _log_rows(db: Path) -> list[tuple]:
    import sqlite3

    con = sqlite3.connect(str(db))
    try:
        return con.execute(
            "SELECT run_id, source, attempted_count, success_count, fail_count, error_summary "
            "FROM market_refresh_log ORDER BY rowid"
        ).fetchall()
    finally:
        con.close()


def _equity_row(db: Path) -> tuple:
    rows = [r for r in _log_rows(db) if r[1] == HOLDINGS_EQUITY_LOG_SOURCE]
    assert len(rows) == 1
    return rows[0]


def test_targets_are_holdings_minus_etf_master_and_fill_gap(fake_db: Path) -> None:
    _seed_stock_until(fake_db, "000660", date(2026, 8, 12))
    _hold(
        "069500", "000660", "111111", accounts=(("000660", "연금"),)
    )  # ETF 2 · 개별주 1(두 계좌)
    f = FakeFetcher()
    _run(fake_db, f)

    # 개별주는 ETF 목록에 들어가지 않는다.
    assert "000660" not in list_etf_tickers(fake_db)
    # 증분: 마지막 저장일(08-12)부터 같은 갱신의 끝 날짜까지 한 번만 받는다.
    stock_calls = [c for c in f.calls if c[0] == "000660"]
    assert stock_calls == [("000660", date(2026, 8, 12), END)]
    assert get_last_price_date("000660", db_path=fake_db) == "2026-10-12"
    dates = {d for d, _ in fetch_price_history("000660", db_path=fake_db)}
    assert "2026-09-15" in dates and "2026-08-13" in dates  # 누락 구간이 채워짐
    run_id, _src, att, ok, fail, err = _equity_row(fake_db)
    assert run_id.startswith("holdings-equity-prices-")
    assert (att, ok, fail, err) == (1, 1, 0, None)
    snap = get_state_snapshot(cooldown_hours=6, db_path=fake_db)
    assert snap.status == "completed"
    assert snap.error_summary is None
    # ETF 단계 건수에 개별주를 합치지 않는다.
    assert snap.price_attempted_count == 2


def test_latest_refresh_is_still_the_kospi_row(fake_db: Path) -> None:
    """별도 행이 '마지막 refresh'(latest_refresh_log() · 화면 · 연결 ID)를 대신하지 않는다."""
    _hold("000660")
    _run(fake_db, FakeFetcher())
    latest = latest_refresh_log(db_path=fake_db)
    assert latest["run_id"].startswith("kospi-benchmark-")
    etf_price_rows = [
        r
        for r in _log_rows(fake_db)
        if r[1] == "FinanceDataReader/prices" and r[2] == 2
    ]
    assert len(etf_price_rows) == 1  # ETF 단계 행(2종목)은 그대로 1개


def test_one_stock_fails_others_still_saved(fake_db: Path) -> None:
    _seed_stock_until(fake_db, "000660", date(2026, 8, 12))
    _seed_stock_until(fake_db, "005930", date(2026, 8, 12))
    _hold("000660", "005930")
    _run(fake_db, FakeFetcher(fail=("005930",)))
    assert get_last_price_date("000660", db_path=fake_db) == "2026-10-12"
    assert (
        get_last_price_date("005930", db_path=fake_db) == "2026-08-12"
    )  # 옛 자료 그대로
    _r, _s, att, ok, fail, err = _equity_row(fake_db)
    assert (att, ok, fail) == (2, 1, 1)
    assert "005930" in (err or "")
    snap = get_state_snapshot(cooldown_hours=6, db_path=fake_db)
    assert snap.status == "completed"  # 전체 갱신 판정은 ETF 결과대로
    assert snap.error_summary.endswith("보유 개별주 가격 갱신 일부 실패(1종목)")


def test_all_stocks_fail_message(fake_db: Path) -> None:
    # 저장 행이 없는 종목의 수집 실패 — 공유 함수가 두 번 세도 문구 · 기록은 1종목.
    _hold("000660")
    _run(fake_db, FakeFetcher(fail=("000660",)))
    _r, _s, att, ok, fail, _err = _equity_row(fake_db)
    assert (att, ok, fail) == (1, 0, 1)
    snap = get_state_snapshot(cooldown_hours=6, db_path=fake_db)
    assert snap.error_summary == "보유 개별주 가격 갱신 실패(1종목)"


def test_holdings_read_failure_is_not_treated_as_empty(fake_db: Path) -> None:
    holdings_module.HOLDINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    holdings_module.HOLDINGS_FILE.write_text("{ broken", encoding="utf-8")
    f = FakeFetcher()
    _run(fake_db, f)
    assert {c[0] for c in f.calls} == {"069500", "111111"}  # ETF 갱신은 그대로
    _r, _s, att, ok, fail, err = _equity_row(fake_db)
    assert (att, ok, fail) == (0, 0, 0)
    assert err.startswith("holdings_read_failed:")
    snap = get_state_snapshot(cooldown_hours=6, db_path=fake_db)
    assert snap.status == "completed"
    assert snap.error_summary.endswith(HOLDINGS_READ_FAILED_TEXT)


@pytest.mark.parametrize("held", [(), ("069500", "111111")])
def test_no_targets_is_normal(fake_db: Path, held: tuple) -> None:
    # 유효한 빈 보유(파일 있음 · 0행) · ETF 만 보유 = 정상 '대상 없음'.
    _hold(*held)
    f = FakeFetcher()
    _run(fake_db, f)
    _r, _s, att, ok, fail, err = _equity_row(fake_db)
    assert (att, ok, fail, err) == (0, 0, 0, None)
    snap = get_state_snapshot(cooldown_hours=6, db_path=fake_db)
    assert snap.error_summary is None


def test_existing_etf_summary_is_kept_first(fake_db: Path) -> None:
    # ETF 단계 일부 실패 문구 뒤에 개별주 문구가 붙는다(기존 판정 · 문구 불변).
    _hold("000660")
    _run(fake_db, FakeFetcher(fail=("111111", "000660")))
    snap = get_state_snapshot(cooldown_hours=6, db_path=fake_db)
    assert snap.error_summary == (
        "price_partial_failure: fail=1 · 보유 개별주 가격 갱신 실패(1종목)"
    )


def _evidence_for(ticker: str) -> dict:
    stm = {
        "status": "ok",
        **{
            k: 0.0
            for k in (
                "return_5d_pct",
                "return_10d_pct",
                "return_20d_pct",
                "excess_vs_kodex200_5d_pctp",
                "excess_vs_kodex200_10d_pctp",
                "excess_vs_kodex200_20d_pctp",
            )
        },
    }
    return {
        "summary": {},
        "holdings": [
            {
                "ticker": ticker,
                "name": ticker,
                "holding": {"evaluation_amount": 1.0, "pnl_rate_pct": 0.0},
                "returns": {"status": "unavailable"},
                "short_term_momentum": stm,
                "evidence_notes": [],
            }
        ],
        "judgment_summary": None,
    }


def test_poc5_09_date_check_returns_stock_after_refresh(fake_db: Path) -> None:
    """수집 뒤 기준일이 KODEX200 과 같아지면 현재 비교로 돌아오고, 실패해 옛 자료가 남으면 계속 빠진다."""
    _seed_stock_until(fake_db, "000660", date(2026, 8, 12))
    _seed_stock_until(fake_db, "005930", date(2026, 8, 12))
    _hold("000660", "005930")
    _run(fake_db, FakeFetcher(fail=("005930",)))
    rows = load_recent_price_rows(["000660", "005930"], db_path=fake_db)
    ev = _evidence_for("000660")
    ev["holdings"] += _evidence_for("005930")["holdings"]
    ev["judgment_summary"] = {"holdings": {}}
    out = apply_pc_price_basis(ev, rows)
    ok, stale = out["holdings"]
    assert ok["price_dates"]["end_date"] == "2026-10-12"
    assert ok["price_dates"]["comparison"] == "ok"
    top = [t["ticker"] for t in out["judgment_summary"]["holdings"]["top_holdings"]]
    assert top == [
        "000660"
    ]  # 수집된 종목은 최대 3개 후보로 돌아오고 옛 자료 종목은 빠진다
    assert stale["price_dates"]["end_date"] == "2026-08-12"
    assert stale["price_dates"]["comparison"] == "date_mismatch"


def test_missing_holdings_file_is_read_failure(fake_db: Path) -> None:
    """보유 파일 없음은 '유효한 빈 보유'가 아니다 — 빈 보유로 바꾸지 않고 읽기 실패로 기록."""
    assert not holdings_module.HOLDINGS_FILE.exists()
    f = FakeFetcher()
    _run(fake_db, f)
    assert {c[0] for c in f.calls} == {"069500", "111111"}  # ETF 갱신은 그대로
    _r, _s, att, ok, fail, err = _equity_row(fake_db)
    assert (att, ok, fail) == (0, 0, 0)
    assert err.startswith("holdings_read_failed: FileNotFoundError")
    snap = get_state_snapshot(cooldown_hours=6, db_path=fake_db)
    assert snap.status == "completed"
    assert snap.error_summary == HOLDINGS_READ_FAILED_TEXT


def test_mixed_new_failed_and_old_succeeded_counts_each_stock(fake_db: Path) -> None:
    """공유 함수 이중 집계와 무관하게 종목마다 센다 — 새 종목(저장 행 없음) 실패 · 기존 종목 성공."""
    _seed_stock_until(fake_db, "000660", date(2026, 8, 12))
    _hold("999999", "000660")
    _run(fake_db, FakeFetcher(fail=("999999",)))
    assert get_last_price_date("000660", db_path=fake_db) == "2026-10-12"
    _r, _s, att, ok, fail, _err = _equity_row(fake_db)
    assert (att, ok, fail) == (2, 1, 1)
    snap = get_state_snapshot(cooldown_hours=6, db_path=fake_db)
    assert snap.error_summary == "보유 개별주 가격 갱신 일부 실패(1종목)"


def test_kospi_and_stock_failures_keep_order(
    fake_db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        market_refresh_service,
        "refresh_kospi_benchmark",
        lambda **kw: {"status": "failed", "error": "test_kospi"},
    )
    _hold("000660")
    _run(fake_db, FakeFetcher(fail=("000660",)))
    snap = get_state_snapshot(cooldown_hours=6, db_path=fake_db)
    assert snap.error_summary == (
        "kospi_benchmark_unavailable: test_kospi · 보유 개별주 가격 갱신 실패(1종목)"
    )
    assert latest_refresh_log(db_path=fake_db)["run_id"].startswith("kospi-benchmark-")


def test_universe_failure_still_refreshes_stocks(fake_db: Path) -> None:
    _seed_stock_until(fake_db, "000660", date(2026, 8, 12))
    _hold("000660")
    f = FakeFetcher()
    start_refresh_job(
        db_path=fake_db,
        cooldown_hours=6,
        universe_fetcher=lambda: pd.DataFrame([]),
        price_fetcher=f,
        end_date_for_prices=END,
        thread_runner=lambda runner: runner(),
    )
    assert [c[0] for c in f.calls] == [
        "000660"
    ]  # ETF 가격은 건너뛰고 개별주 단계는 돈다
    snap = get_state_snapshot(cooldown_hours=6, db_path=fake_db)
    assert snap.status == "failed"  # 전체 판정은 ETF(universe) 결과대로
    assert snap.error_summary.startswith("universe_fetch_failed")
    assert "보유 개별주" not in snap.error_summary


def test_step_exception_is_isolated(
    fake_db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(**kw):
        raise RuntimeError("db gone")

    monkeypatch.setattr(market_refresh_service, "refresh_holdings_equity_prices", boom)
    _hold("000660")
    _run(fake_db, FakeFetcher())
    snap = get_state_snapshot(cooldown_hours=6, db_path=fake_db)
    assert snap.status == "completed"
    assert snap.error_summary == HOLDINGS_EQUITY_STEP_FAILED_TEXT


def test_log_write_failure_does_not_change_result(
    fake_db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app import holdings_equity_refresh as mod

    _seed_stock_until(fake_db, "000660", date(2026, 8, 12))
    _hold("000660")

    def bad_log(**kw):
        raise RuntimeError("log fail")

    monkeypatch.setattr(mod, "log_refresh", bad_log)
    msg = mod.refresh_holdings_equity_prices(
        refresh_id="r1", end_date=END, db_path=fake_db, price_fetcher=FakeFetcher()
    )
    assert msg is None
    assert get_last_price_date("000660", db_path=fake_db) == "2026-10-12"


def _latest_payload(db: Path) -> dict:
    from app.market_topn_helpers import _latest_refresh_payload

    return _latest_refresh_payload(db)


def _run_with_kospi_log_failing(
    db: Path, monkeypatch: pytest.MonkeyPatch, *, with_step: bool
) -> dict:
    from app.market_benchmark_store import KOSPI_SOURCE

    real = market_refresh_service.log_refresh

    def flaky_log(**kw):
        if kw.get("source") == KOSPI_SOURCE:
            raise RuntimeError("kospi log write failed")
        return real(**kw)

    monkeypatch.setattr(market_refresh_service, "log_refresh", flaky_log)
    if not with_step:
        monkeypatch.setattr(
            market_refresh_service, "refresh_holdings_equity_prices", lambda **kw: None
        )
    _seed_stock_until(db, "000660", date(2026, 8, 12))
    _hold("000660")
    _run(db, FakeFetcher())
    return _latest_payload(db)


@pytest.mark.parametrize("with_step", [False, True])
def test_last_full_refresh_kept_even_if_kospi_log_fails(
    fake_db: Path, monkeypatch: pytest.MonkeyPatch, with_step: bool
) -> None:
    """검증자 r1 재현 — KOSPI 기록이 두 번 다 실패해도 '마지막 전체 갱신' = ETF 가격 행(단계 유무 같음)."""
    p = _run_with_kospi_log_failing(fake_db, monkeypatch, with_step=with_step)
    assert p["source"] == "FinanceDataReader/prices"
    assert p["refresh_id"].startswith("fdr-prices-")
    assert (p["attempted_count"], p["success_count"], p["fail_count"]) == (2, 2, 0)
    if with_step:
        # 단계는 실제로 돌았다(개별주 저장 · 요약 행 1).
        assert get_last_price_date("000660", db_path=fake_db) == "2026-10-12"
        assert _equity_row(fake_db)[2:5] == (1, 1, 0)


def test_step_writes_only_its_summary_row(fake_db: Path) -> None:
    """개별주 단계는 종목별 'FinanceDataReader/prices' 행을 남기지 않는다(ETF 가격 행은 1개)."""
    _seed_stock_until(fake_db, "000660", date(2026, 8, 12))
    _hold("000660")
    _run(fake_db, FakeFetcher())
    price_rows = [r for r in _log_rows(fake_db) if r[1] == "FinanceDataReader/prices"]
    assert [r[2] for r in price_rows] == [2]  # ETF 2종목 한 번
    assert get_last_price_date("000660", db_path=fake_db) == "2026-10-12"


def test_latest_refresh_log_exclude_source(fake_db: Path) -> None:
    from app.market_data_store import HOLDINGS_EQUITY_PRICE_LOG_SOURCE, log_refresh

    log_refresh(
        run_id="a",
        source="X",
        asof="2026-10-12",
        attempted=1,
        success=1,
        fail=0,
        runtime_seconds=0.0,
        db_path=fake_db,
    )
    log_refresh(
        run_id="b",
        source=HOLDINGS_EQUITY_PRICE_LOG_SOURCE,
        asof="2026-10-12",
        attempted=1,
        success=1,
        fail=0,
        runtime_seconds=0.0,
        db_path=fake_db,
    )
    assert latest_refresh_log(db_path=fake_db)["run_id"] == "b"  # 기본 동작 그대로
    assert (
        latest_refresh_log(
            db_path=fake_db, exclude_source=HOLDINGS_EQUITY_PRICE_LOG_SOURCE
        )["run_id"]
        == "a"
    )
    assert _latest_payload(fake_db)["refresh_id"] == "a"
