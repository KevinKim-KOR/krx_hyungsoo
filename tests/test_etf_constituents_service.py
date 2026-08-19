"""etf_constituents_service refresh 흐름 테스트 (POC2 — 2026-05-27).

지시문 §4 의 K6 방어 정책 검증:
- 1회 10개 hard cap → rejected.
- 캐시 우선 (force=false 일 때).
- ticker 별 0.5초 delay (sleep_fn stub 으로 호출 검증).
- 30초 budget 초과 → skipped_timeout.
- 부분 실패 격리 → partial 응답.
- source 불명 → unavailable.
"""

from __future__ import annotations

from pathlib import Path

from app.etf_constituents_fetcher import FetchedConstituent, FetchResult
from app.etf_constituents_service import (
    DEFAULT_TOP_K,
    MAX_TICKERS_PER_REQUEST,
    MAX_TOP_K,
    PER_TICKER_DELAY_SECONDS,
    TIME_BUDGET_SECONDS,
    refresh_constituents,
)
from app.etf_constituents_store import fetch_constituents


def _ok_fetcher(*, source: str = "naver_stock_etf_component"):
    def fn(ticker, asof, top_k):  # noqa: ARG001
        return FetchResult(
            status="ok",
            source=source,
            constituents=[
                FetchedConstituent(
                    rank=1,
                    constituent_ticker="005930",
                    constituent_name="삼성전자",
                    weight_pct=25.1,
                ),
                FetchedConstituent(
                    rank=2,
                    constituent_ticker="000660",
                    constituent_name="SK하이닉스",
                    weight_pct=15.2,
                ),
            ],
        )

    return fn


def test_refresh_rejected_when_more_than_10_tickers(tmp_path: Path):
    db = tmp_path / "m.sqlite"
    tickers = [f"00{i:04d}" for i in range(MAX_TICKERS_PER_REQUEST + 1)]
    result = refresh_constituents(
        asof="2026-05-26", tickers=tickers, fetcher=_ok_fetcher(), db_path=db
    )
    assert result.status == "rejected"
    assert result.reason == "too_many_tickers"
    assert result.items == []


def test_refresh_cache_first_no_external_call_when_cached(tmp_path: Path):
    db = tmp_path / "m.sqlite"
    # 첫 호출 — fetch.
    sleeps: list[float] = []
    result1 = refresh_constituents(
        asof="2026-05-26",
        tickers=["139260"],
        fetcher=_ok_fetcher(),
        sleep_fn=sleeps.append,
        db_path=db,
    )
    assert result1.status == "ok"
    assert result1.cached_count == 0
    assert result1.fetched_count == 1

    # 두 번째 호출 — 캐시 히트, fetcher 호출 X.
    def _boom_fetcher(*args, **kwargs):  # noqa: ARG001
        raise AssertionError("cache hit 인데 fetcher 가 호출됨")

    result2 = refresh_constituents(
        asof="2026-05-26",
        tickers=["139260"],
        fetcher=_boom_fetcher,
        sleep_fn=sleeps.append,
        db_path=db,
    )
    assert result2.status == "ok"
    assert result2.cached_count == 1
    assert result2.fetched_count == 0
    assert result2.items[0].from_cache is True


def test_refresh_force_true_bypasses_cache(tmp_path: Path):
    db = tmp_path / "m.sqlite"
    refresh_constituents(
        asof="2026-05-26",
        tickers=["139260"],
        fetcher=_ok_fetcher(),
        db_path=db,
    )
    calls: list[str] = []

    def counting_fetcher(ticker, asof, top_k):  # noqa: ARG001
        calls.append(ticker)
        return _ok_fetcher()(ticker, asof, top_k)

    refresh_constituents(
        asof="2026-05-26",
        tickers=["139260"],
        force=True,
        fetcher=counting_fetcher,
        db_path=db,
    )
    assert calls == ["139260"]


def test_refresh_applies_per_ticker_delay(tmp_path: Path):
    db = tmp_path / "m.sqlite"
    sleeps: list[float] = []
    refresh_constituents(
        asof="2026-05-26",
        tickers=["A", "B", "C"],
        fetcher=_ok_fetcher(),
        sleep_fn=sleeps.append,
        db_path=db,
    )
    # 첫 ticker 는 delay 없음, 이후 매번 0.5s.
    assert sleeps == [PER_TICKER_DELAY_SECONDS, PER_TICKER_DELAY_SECONDS]


def test_refresh_time_budget_exceeded_skips_remaining(tmp_path: Path):
    db = tmp_path / "m.sqlite"
    # monotonic 을 가짜로 — t_start=0 + ticker A 검사=0 (정상 fetch) +
    # ticker B/C 검사=TIME_BUDGET+1 (timeout). default 도 TIME_BUDGET+1.
    times = iter([0.0, 0.0, TIME_BUDGET_SECONDS + 1.0, TIME_BUDGET_SECONDS + 1.0])

    def now_fn():
        try:
            return next(times)
        except StopIteration:
            return TIME_BUDGET_SECONDS + 1.0

    result = refresh_constituents(
        asof="2026-05-26",
        tickers=["A", "B", "C"],
        fetcher=_ok_fetcher(),
        sleep_fn=lambda _s: None,
        now_fn=now_fn,
        db_path=db,
    )
    # A 는 정상 fetch, B/C 는 budget 초과로 skipped_timeout.
    statuses = [i.status for i in result.items]
    assert statuses[0] == "ok"
    assert statuses[1] == "skipped_timeout"
    assert statuses[2] == "skipped_timeout"
    assert result.status == "partial"
    assert result.skipped_count == 2


def test_refresh_partial_when_some_fail(tmp_path: Path):
    db = tmp_path / "m.sqlite"
    ok_call = _ok_fetcher()

    def mixed_fetcher(ticker, asof, top_k):
        if ticker == "B":
            return FetchResult(
                status="unavailable",
                source="pykrx",
                constituents=[],
                message="no_data",
            )
        return ok_call(ticker, asof, top_k)

    result = refresh_constituents(
        asof="2026-05-26",
        tickers=["A", "B", "C"],
        fetcher=mixed_fetcher,
        sleep_fn=lambda _s: None,
        db_path=db,
    )
    assert result.status == "partial"
    assert result.success_count == 2
    assert result.fail_count == 1
    statuses = {i.ticker: i.status for i in result.items}
    assert statuses == {"A": "ok", "B": "unavailable", "C": "ok"}


def test_refresh_rejects_source_unknown_as_unavailable(tmp_path: Path):
    db = tmp_path / "m.sqlite"

    def unknown_source_fetcher(ticker, asof, top_k):  # noqa: ARG001
        return FetchResult(
            status="ok",
            source="unknown",  # 불명 → unavailable 처리.
            constituents=[
                FetchedConstituent(
                    rank=1,
                    constituent_ticker="005930",
                    constituent_name="삼성전자",
                    weight_pct=25.1,
                ),
            ],
        )

    result = refresh_constituents(
        asof="2026-05-26",
        tickers=["X"],
        fetcher=unknown_source_fetcher,
        sleep_fn=lambda _s: None,
        db_path=db,
    )
    assert result.items[0].status == "unavailable"
    assert result.fail_count == 1
    # 저장도 되면 안 됨 — source unclear 는 ok 처리 금지.
    stored = fetch_constituents(etf_ticker="X", asof="2026-05-26", db_path=db)
    assert stored == []


def test_refresh_rejected_missing_asof(tmp_path: Path):
    db = tmp_path / "m.sqlite"
    result = refresh_constituents(
        asof="", tickers=["A"], fetcher=_ok_fetcher(), db_path=db
    )
    assert result.status == "rejected"
    assert result.reason == "missing_asof"


# ── 2026-08-19 설계 확정: 깊이 30 · 레거시 10건 캐시는 완료로 보지 않음 ────


def _depth_fetcher(count: int, *, source: str = "naver_stock_etf_component"):
    """요청 깊이와 무관하게 `count` 건을 돌려주는 fetcher."""
    calls: list[int] = []

    def fn(ticker, asof, top_k):  # noqa: ARG001
        calls.append(top_k)
        return FetchResult(
            status="ok",
            source=source,
            constituents=[
                FetchedConstituent(
                    rank=i,
                    constituent_ticker=f"{i:06d}",
                    constituent_name=f"종목{i}",
                    weight_pct=float(30 - i),
                )
                for i in range(1, count + 1)
            ],
        )

    return fn, calls


def test_default_top_k_is_30_and_cap_allows_30(tmp_path: Path):
    """수집 깊이 상한이 30 이다 (외부 호출 수 상한 10 과 분리)."""
    assert DEFAULT_TOP_K == 30
    assert MAX_TOP_K == 30
    assert MAX_TICKERS_PER_REQUEST == 10, "ETF 1회 처리 상한은 그대로 10"

    db = tmp_path / "m.sqlite"
    fetcher, calls = _depth_fetcher(30)
    res = refresh_constituents(
        asof="2026-08-19", tickers=["A"], fetcher=fetcher, db_path=db
    )
    assert res.status == "ok"
    assert calls == [30], "fetcher 에 전달된 깊이"
    assert len(fetch_constituents(etf_ticker="A", asof="2026-08-19", db_path=db)) == 30


def test_legacy_10_row_cache_is_refetched_at_depth_30(tmp_path: Path):
    """구 정책으로 10건 잘려 저장된 캐시를 30건 요청 완료로 보지 않는다."""
    db = tmp_path / "m.sqlite"
    legacy, _ = _depth_fetcher(10)
    refresh_constituents(
        asof="2026-08-19", tickers=["A"], top_k=10, fetcher=legacy, db_path=db
    )
    assert len(fetch_constituents(etf_ticker="A", asof="2026-08-19", db_path=db)) == 10

    deep, calls = _depth_fetcher(30)
    res = refresh_constituents(
        asof="2026-08-19", tickers=["A"], fetcher=deep, db_path=db
    )
    assert calls == [30], "레거시 10건 캐시는 재수집 대상이어야 한다"
    assert res.items[0].from_cache is False
    assert len(fetch_constituents(etf_ticker="A", asof="2026-08-19", db_path=db)) == 30


def test_deep_cache_is_not_refetched(tmp_path: Path):
    """요청 깊이를 만족하는 캐시는 그대로 쓴다 (캐시 우선 정책 유지)."""
    db = tmp_path / "m.sqlite"
    deep, _ = _depth_fetcher(30)
    refresh_constituents(asof="2026-08-19", tickers=["A"], fetcher=deep, db_path=db)

    def boom(ticker, asof, top_k):  # noqa: ARG001
        raise AssertionError("캐시가 있는데 외부 호출이 일어났다")

    res = refresh_constituents(
        asof="2026-08-19", tickers=["A"], fetcher=boom, db_path=db
    )
    assert res.items[0].from_cache is True
    assert res.cached_count == 1


def test_exhausted_source_cache_is_not_refetched(tmp_path: Path):
    """총 구성종목이 30 미만인 ETF(=소스 고갈)는 재수집하지 않는다.

    10 건 정확히인 경우만 구 정책 잔재로 보고 재수집한다 — 그 외 건수는
    "source 가 그만큼밖에 없다" 는 뜻이라 다시 불러도 같은 결과다.
    """
    db = tmp_path / "m.sqlite"
    small, _ = _depth_fetcher(12)
    refresh_constituents(asof="2026-08-19", tickers=["A"], fetcher=small, db_path=db)

    def boom(ticker, asof, top_k):  # noqa: ARG001
        raise AssertionError("고갈된 source 인데 재수집이 일어났다")

    res = refresh_constituents(
        asof="2026-08-19", tickers=["A"], fetcher=boom, db_path=db
    )
    assert res.items[0].from_cache is True


def test_deep_snapshot_not_shrunk_by_shallow_refetch(tmp_path: Path):
    """30건 스냅샷이 이후 10건 수집으로 축소되지 않는다."""
    db = tmp_path / "m.sqlite"
    deep, _ = _depth_fetcher(30)
    refresh_constituents(asof="2026-08-19", tickers=["A"], fetcher=deep, db_path=db)

    shallow, _ = _depth_fetcher(10)
    refresh_constituents(
        asof="2026-08-19",
        tickers=["A"],
        top_k=10,
        force=True,
        fetcher=shallow,
        db_path=db,
    )
    rows = fetch_constituents(etf_ticker="A", asof="2026-08-19", db_path=db)
    assert len(rows) == 30, "얕은 재수집이 깊은 스냅샷을 지우면 안 된다"
    assert max(r.rank for r in rows) == 30
