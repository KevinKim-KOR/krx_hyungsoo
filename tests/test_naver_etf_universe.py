"""Naver ETF Universe NAV / 괴리율 연동 테스트 (2026-06-08).

지시문 §4 / §5 / AC-1 ~ AC-12 — 외부 네트워크 의존 없는 fixture 기반.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.etf_nav_service import refresh_nav_universe
from app.etf_nav_store import fetch_latest_nav, fetch_nav_rows
from app.naver_etf_universe_fetcher import (
    NaverUniverseSnapshot,
    SOURCE_LABEL,
    TTL_SECONDS,
    _build_snapshot_from_payload,
    fetch_universe_snapshot,
    reset_cache_for_tests,
)

# ─── fixture payload ──────────────────────────────────────────────────


def _make_payload(items=None):
    items = (
        items
        if items is not None
        else [
            {
                "itemcode": "069500",
                "itemname": "KODEX 200",
                "nav": "33,520",
                "nowVal": "33,535",
                "changeRate": "0.04",
                "threeMonthEarnRate": "5.12",
            },
            {
                "itemcode": "360750",
                "itemname": "TIGER 미국S&P500",
                "nav": "28,663",
                "nowVal": "28,845",
                "changeRate": "0.10",
                "threeMonthEarnRate": "8.40",
            },
            {
                "itemcode": "BROKEN",
                "itemname": "broken",
                "nav": "-",
                "nowVal": "-",
                "changeRate": "-",
            },
        ]
    )
    return {"result": {"etfItemList": items}}


# ─── snapshot builder ─────────────────────────────────────────────────


def test_build_snapshot_parses_numbers_and_computes_discount_rate():
    now = datetime(2026, 6, 8, 0, 0, tzinfo=timezone.utc)
    snap = _build_snapshot_from_payload(_make_payload(), now)
    assert snap.status == "ok"
    assert "069500" in snap.items
    k200 = snap.items["069500"]
    assert k200.nav == pytest.approx(33520.0)
    assert k200.market_price == pytest.approx(33535.0)
    assert k200.discount_rate_pct == pytest.approx(
        ((33535.0 / 33520.0) - 1.0) * 100.0, rel=1e-6
    )
    # 시장가/NAV 누락 항목은 unavailable.
    broken = snap.items["BROKEN"]
    assert broken.status == "unavailable"


def test_build_snapshot_empty_payload_returns_unavailable():
    now = datetime(2026, 6, 8, 0, 0, tzinfo=timezone.utc)
    snap = _build_snapshot_from_payload({"result": {"etfItemList": []}}, now)
    assert snap.status == "unavailable"


# ─── fetch_universe_snapshot (TTL + stale) ────────────────────────────


def _stub_http(payload):
    calls = {"count": 0}

    def _getter(_url):
        calls["count"] += 1
        return (200, payload, None)

    return calls, _getter


def _failing_http():
    calls = {"count": 0}

    def _getter(_url):
        calls["count"] += 1
        return (None, None, "URLError: network down")

    return calls, _getter


def test_fetch_universe_snapshot_uses_ttl_cache():
    reset_cache_for_tests()
    calls, getter = _stub_http(_make_payload())
    snap1 = fetch_universe_snapshot(http_getter=getter)
    snap2 = fetch_universe_snapshot(http_getter=getter)
    assert calls["count"] == 1
    assert snap1.cache_hit is False
    assert snap2.cache_hit is True
    assert snap2.items.keys() == snap1.items.keys()


def test_fetch_universe_snapshot_force_bypasses_cache():
    reset_cache_for_tests()
    calls, getter = _stub_http(_make_payload())
    fetch_universe_snapshot(http_getter=getter)
    fetch_universe_snapshot(http_getter=getter, force=True)
    assert calls["count"] == 2


def test_fetch_universe_snapshot_stale_reused_on_failure():
    reset_cache_for_tests()
    _, ok_getter = _stub_http(_make_payload())
    fetch_universe_snapshot(http_getter=ok_getter)
    # TTL 만료 시뮬레이션 — cache 의 expires_at 을 과거로.
    from app.naver_etf_universe_fetcher import _UNIVERSE_CACHE

    _UNIVERSE_CACHE["expires_at"] = datetime.now(timezone.utc) - timedelta(
        seconds=TTL_SECONDS + 1
    )
    _, fail_getter = _failing_http()
    stale = fetch_universe_snapshot(http_getter=fail_getter)
    assert stale.stale_cache_used is True
    assert stale.status == "partial"
    assert "069500" in stale.items


def test_fetch_universe_snapshot_unavailable_when_no_cache_and_failure():
    reset_cache_for_tests()
    _, fail_getter = _failing_http()
    snap = fetch_universe_snapshot(http_getter=fail_getter)
    assert snap.status == "unavailable"
    assert snap.items == {}


# ─── refresh_nav_universe (service + store integration) ───────────────


@pytest.fixture
def tmp_db(tmp_path: Path) -> Path:
    return tmp_path / "market_data.sqlite"


def _fake_fetcher_ok():
    def _fn(force=False):  # noqa: ARG001
        return NaverUniverseSnapshot(
            status="ok",
            fetched_at="2026-06-08T00:00:00Z",
            items={
                "069500": _make_item("069500", 33520.0, 33535.0),
                "360750": _make_item("360750", 28663.0, 28845.0),
            },
        )

    return _fn


def _make_item(ticker, nav, price):
    from app.naver_etf_universe_fetcher import NaverUniverseItem

    return NaverUniverseItem(
        ticker=ticker,
        name=f"NAME_{ticker}",
        nav=nav,
        market_price=price,
        discount_rate_pct=((price / nav) - 1.0) * 100.0,
        change_rate_pct=0.0,
        three_month_return_pct=0.0,
        status="ok",
    )


def test_refresh_nav_universe_upserts_all_items(tmp_db: Path):
    summary = refresh_nav_universe(
        asof="2026-06-05",
        db_path=tmp_db,
        fetcher=_fake_fetcher_ok(),
    )
    assert summary.status == "ok"
    assert summary.total_count == 2
    assert summary.success_count == 2
    assert summary.unavailable_count == 0
    assert summary.upserted_count == 2
    # store 에 ok row 가 있어야 한다.
    row = fetch_latest_nav(etf_ticker="069500", db_path=tmp_db)
    assert row is not None
    assert row.status == "ok"
    assert row.source == SOURCE_LABEL
    assert row.discount_rate_pct == pytest.approx(
        ((33535.0 / 33520.0) - 1.0) * 100.0, rel=1e-6
    )


def test_refresh_nav_universe_records_unavailable_for_broken_items(tmp_db: Path):
    def _fetcher(force=False):  # noqa: ARG001
        return NaverUniverseSnapshot(
            status="ok",
            fetched_at="2026-06-08T00:00:00Z",
            items={
                "069500": _make_item("069500", 33520.0, 33535.0),
                "BAD": _make_broken_item("BAD"),
            },
        )

    summary = refresh_nav_universe(asof="2026-06-05", db_path=tmp_db, fetcher=_fetcher)
    assert summary.success_count == 1
    assert summary.unavailable_count == 1
    # BAD 도 row 로 기록되어 있어야 한다 (status=unavailable).
    rows = fetch_nav_rows(etf_ticker="BAD", asof="2026-06-05", db_path=tmp_db)
    assert len(rows) == 1
    assert rows[0].status == "unavailable"


def _make_broken_item(ticker):
    from app.naver_etf_universe_fetcher import NaverUniverseItem

    return NaverUniverseItem(
        ticker=ticker,
        name=None,
        nav=None,
        market_price=None,
        discount_rate_pct=None,
        change_rate_pct=None,
        three_month_return_pct=None,
        status="unavailable",
        message="missing",
    )


def test_refresh_nav_universe_rejects_missing_asof(tmp_db: Path):
    summary = refresh_nav_universe(asof="", db_path=tmp_db, fetcher=_fake_fetcher_ok())
    assert summary.status == "unavailable"
    assert summary.message == "missing_asof"


def test_refresh_nav_universe_unavailable_when_snapshot_unavailable(tmp_db: Path):
    def _fetcher(force=False):  # noqa: ARG001
        return NaverUniverseSnapshot(
            status="unavailable",
            fetched_at="2026-06-08T00:00:00Z",
            items={},
            message="empty",
        )

    summary = refresh_nav_universe(asof="2026-06-05", db_path=tmp_db, fetcher=_fetcher)
    assert summary.status == "unavailable"
    assert summary.success_count == 0


def test_refresh_nav_universe_stale_marks_partial(tmp_db: Path):
    def _fetcher(force=False):  # noqa: ARG001
        return NaverUniverseSnapshot(
            status="partial",
            fetched_at="2026-06-08T00:00:00Z",
            items={"069500": _make_item("069500", 33520.0, 33535.0)},
            cache_hit=False,
            stale_cache_used=True,
            message="stale cache reused",
        )

    summary = refresh_nav_universe(asof="2026-06-05", db_path=tmp_db, fetcher=_fetcher)
    assert summary.status == "partial"
    assert summary.stale_cache_used is True
    row = fetch_latest_nav(etf_ticker="069500", db_path=tmp_db)
    assert row.status == "partial"
    assert row.message == "stale cache reused"


def test_refresh_nav_universe_no_external_network_used(tmp_db: Path):
    """fixture fetcher 만 사용 — 실제 외부 호출 0 보장.

    fetcher 인자를 주입하면 fetch_universe_snapshot 은 호출되지 않는다.
    """
    flag = {"called": False}

    def _spy_fetcher(force=False):  # noqa: ARG001
        flag["called"] = True
        return NaverUniverseSnapshot(
            status="ok",
            fetched_at="2026-06-08T00:00:00Z",
            items={"069500": _make_item("069500", 33520.0, 33535.0)},
        )

    refresh_nav_universe(
        asof="2026-06-05",
        db_path=tmp_db,
        fetcher=_spy_fetcher,
    )
    assert flag["called"] is True
