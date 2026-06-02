"""ETF NAV / 괴리율 fetcher + store + service 단위 테스트 (POC2 2026-06-01).

Market Discovery Evidence Closeout 1차 — 지시문 §7 / §8 / §9 / AC-8 ~ AC-13.
"""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from app.etf_nav_fetcher import (
    DISCOUNT_CHECK_THRESHOLD_PCT,
    DISCOUNT_WARNING_THRESHOLD_PCT,
    NavFetchResult,
    UNAVAILABLE_SOURCE,
    classify_discount_flag,
    compute_discount_rate_pct,
    default_nav_fetcher,
    unavailable_nav_fetcher,
)
from app.etf_nav_service import refresh_nav
from app.etf_nav_store import (
    NavDailyRow,
    fetch_latest_nav,
    fetch_nav_rows,
    init_nav_db,
    upsert_nav_rows,
)

# ─── fetcher ──────────────────────────────────────────────────────────


def test_unavailable_fetcher_returns_unavailable_status():
    r = unavailable_nav_fetcher("069500")
    assert r.status == "unavailable"
    assert r.source == UNAVAILABLE_SOURCE
    assert r.discount_rate_pct is None


def test_default_fetcher_is_unavailable_in_this_step():
    fetcher = default_nav_fetcher()
    r = fetcher("069500")
    assert r.status == "unavailable"


def test_compute_discount_rate_pct():
    assert compute_discount_rate_pct(100.0, 103.0) == pytest.approx(3.0)
    assert compute_discount_rate_pct(100.0, 97.0) == pytest.approx(-3.0)
    assert compute_discount_rate_pct(None, 100.0) is None
    assert compute_discount_rate_pct(100.0, None) is None
    assert compute_discount_rate_pct(0.0, 100.0) is None


def test_classify_discount_flag():
    assert classify_discount_flag(None) is None
    assert classify_discount_flag(0.5) is None
    assert (
        classify_discount_flag(DISCOUNT_CHECK_THRESHOLD_PCT) == "discount_check_needed"
    )
    assert (
        classify_discount_flag(-DISCOUNT_CHECK_THRESHOLD_PCT) == "discount_check_needed"
    )
    assert classify_discount_flag(DISCOUNT_WARNING_THRESHOLD_PCT) == "discount_warning"
    assert classify_discount_flag(-7.0) == "discount_warning"


# ─── store ────────────────────────────────────────────────────────────


def test_store_upsert_and_fetch_latest(tmp_path: Path):
    db = tmp_path / "n.sqlite"
    upsert_nav_rows(
        [
            NavDailyRow(
                etf_ticker="069500",
                asof="2026-05-30",
                nav=14000.0,
                market_price=14200.0,
                discount_rate_pct=1.43,
                source="naver_stock_etf_detail",
                status="ok",
                message=None,
            ),
            NavDailyRow(
                etf_ticker="069500",
                asof="2026-05-31",
                nav=14250.0,
                market_price=14800.0,
                discount_rate_pct=3.86,
                source="naver_stock_etf_detail",
                status="ok",
                message=None,
            ),
        ],
        db_path=db,
    )
    latest = fetch_latest_nav(etf_ticker="069500", db_path=db)
    assert latest is not None
    assert latest.asof == "2026-05-31"
    assert latest.discount_rate_pct == pytest.approx(3.86)


def test_store_returns_none_when_no_row(tmp_path: Path):
    db = tmp_path / "n.sqlite"
    init_nav_db(db)
    assert fetch_latest_nav(etf_ticker="069500", db_path=db) is None


def test_store_fetch_nav_rows_by_asof(tmp_path: Path):
    db = tmp_path / "n.sqlite"
    upsert_nav_rows(
        [
            NavDailyRow(
                etf_ticker="069500",
                asof="2026-05-31",
                nav=None,
                market_price=None,
                discount_rate_pct=None,
                source="unavailable",
                status="unavailable",
                message="not adopted",
            )
        ],
        db_path=db,
    )
    rows = fetch_nav_rows(etf_ticker="069500", asof="2026-05-31", db_path=db)
    assert len(rows) == 1
    assert rows[0].status == "unavailable"


def test_store_concurrent_init_does_not_raise(tmp_path: Path):
    db = tmp_path / "n.sqlite"
    errors: list[BaseException] = []

    def _worker():
        try:
            init_nav_db(db)
        except BaseException as e:  # noqa: BLE001
            errors.append(e)

    threads = [threading.Thread(target=_worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []


# ─── service ──────────────────────────────────────────────────────────


def test_refresh_nav_rejected_when_too_many(tmp_path: Path):
    db = tmp_path / "n.sqlite"
    out = refresh_nav(
        asof="2026-05-31",
        tickers=[f"T{i}" for i in range(11)],
        db_path=db,
    )
    assert out.status == "rejected"
    assert out.reason == "too_many_tickers"


def test_refresh_nav_default_writes_unavailable(tmp_path: Path):
    db = tmp_path / "n.sqlite"
    out = refresh_nav(
        asof="2026-05-31",
        tickers=["069500", "139260"],
        sleep_fn=lambda _s: None,
        db_path=db,
    )
    assert out.status == "partial"  # default fetcher 가 모두 unavailable.
    assert out.success_count == 0
    assert out.fail_count == 2
    assert all(item.status == "unavailable" for item in out.items)
    # store 에 unavailable row 가 실제로 기록됨.
    rows = fetch_nav_rows(etf_ticker="069500", asof="2026-05-31", db_path=db)
    assert len(rows) == 1
    assert rows[0].status == "unavailable"


def test_refresh_nav_uses_cache_on_second_call(tmp_path: Path):
    db = tmp_path / "n.sqlite"

    call_log: list[str] = []

    def _stub_ok(ticker: str) -> NavFetchResult:
        call_log.append(ticker)
        return NavFetchResult(
            status="ok",
            asof="2026-05-31",
            nav=14000.0,
            market_price=14210.0,
            source="naver_stock_etf_detail",
        )

    # 1차 — fetcher 호출.
    refresh_nav(
        asof="2026-05-31",
        tickers=["069500"],
        fetcher=_stub_ok,
        sleep_fn=lambda _s: None,
        db_path=db,
    )
    assert len(call_log) == 1

    # 2차 — 같은 asof / source 가 store 에 있으므로 cache 사용 (fetcher 호출 없음).
    out = refresh_nav(
        asof="2026-05-31",
        tickers=["069500"],
        fetcher=_stub_ok,
        sleep_fn=lambda _s: None,
        db_path=db,
    )
    assert len(call_log) == 1
    assert out.cached_count == 1
    assert out.items[0].from_cache is True
    # flag 도 계산됨 — 시장가격 14210 / NAV 14000 → 1.5%
    # discount_rate_pct 는 fetcher result 가 None 이므로 본 모듈이 계산해서 저장.
    assert out.items[0].discount_rate_pct == pytest.approx(1.5, rel=1e-3)


def test_refresh_nav_exception_isolated_per_ticker(tmp_path: Path):
    db = tmp_path / "n.sqlite"

    def _bad(ticker: str) -> NavFetchResult:
        if ticker == "069500":
            raise RuntimeError("boom")
        return NavFetchResult(
            status="ok",
            asof="2026-05-31",
            nav=14000.0,
            market_price=14210.0,
            source="naver_stock_etf_detail",
        )

    out = refresh_nav(
        asof="2026-05-31",
        tickers=["069500", "139260"],
        fetcher=_bad,
        sleep_fn=lambda _s: None,
        db_path=db,
    )
    # 첫 번째는 fail, 두 번째는 ok — 전체 status = partial.
    assert out.status == "partial"
    assert out.success_count == 1
    assert out.fail_count == 1
    # 첫 번째 row 도 store 에 unavailable 로 기록됨.
    rows_069 = fetch_nav_rows(etf_ticker="069500", asof="2026-05-31", db_path=db)
    assert rows_069[0].status == "unavailable"
    assert "boom" in (rows_069[0].message or "")
