"""POC5-09 — 저장 거래량 확인 근거 계산 · 읽기 · topn 응답 (설계서 §3 · §9-2).

라이브 DB 를 열지 않는다(순수 계산 · tmp DB · 기존 격리 fixture).
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import (
    api as api_module,
    api_market_topn,
    etf_constituents_store,
    etf_nav_store,
    market_data_store,
    market_refresh_service,
)
from app.market_data_store import (
    EtfDailyPriceRow,
    fetch_recent_price_rows,
    upsert_daily_prices,
)
from app.stored_volume_evidence import (
    build_stored_volume_evidence,
    compute_stored_volume_evidence,
)

D = "2026-10-08"


def _rows(d_volume, prev_volumes, *, src="FinanceDataReader"):
    """최신순 행: 기준일 D 다음에 앞 저장일(가까운 날부터)."""
    out = [(D, 100.0, d_volume, src)]
    for i, v in enumerate(prev_volumes):
        out.append((f"2026-09-{30 - i:02d}", 100.0, v, src))
    return out


def test_normal_ratio_is_volume_over_previous_20_average() -> None:
    ev = compute_stored_volume_evidence("069500", _rows(1_500_000, [1_000_000] * 20))
    assert ev.status == "ok"
    assert ev.asof_date == D and ev.source == "FinanceDataReader"
    assert ev.volume == 1_500_000
    assert ev.avg_prev20 == 1_000_000
    assert ev.ratio == pytest.approx(1.5)
    assert (ev.avg_status, ev.ratio_status) == ("ok", "ok")
    assert (ev.window_date_count, ev.valid_count) == (20, 20)
    assert ev.window_end_date == "2026-09-30" and ev.window_start_date == "2026-09-11"


def test_reference_day_is_excluded_from_average() -> None:
    ev = compute_stored_volume_evidence("X", _rows(99_000_000, [10] * 20))
    assert ev.avg_prev20 == 10
    assert ev.ratio == pytest.approx(9_900_000)


def test_window_is_only_the_20_rows_before_reference_day() -> None:
    # 21번째 앞 행(값 1e9)은 창 밖이라 평균에 들어가지 않는다.
    rows = _rows(50, [100] * 20)
    rows.append(("2026-09-01", 100.0, 1_000_000_000, "FinanceDataReader"))
    ev = compute_stored_volume_evidence("X", rows)
    assert ev.avg_prev20 == 100
    assert ev.window_date_count == 20


def test_missing_value_in_window_is_not_filled_from_older_rows() -> None:
    prev = [100] * 19 + [None]
    rows = _rows(50, prev)
    rows.append(("2026-09-01", 100.0, 100, "FinanceDataReader"))  # 창 밖 유효값
    ev = compute_stored_volume_evidence("X", rows)
    assert ev.valid_count == 19
    assert ev.avg_prev20 is None and ev.avg_status == "insufficient"
    assert ev.ratio is None and ev.ratio_status == "avg_insufficient"
    assert ev.volume == 50  # 기준일 거래량은 그대로 보인다


def test_short_history_counts_available_rows() -> None:
    ev = compute_stored_volume_evidence("X", _rows(50, [100] * 12))
    assert (ev.window_date_count, ev.valid_count) == (12, 12)
    assert ev.avg_status == "insufficient" and ev.ratio_status == "avg_insufficient"


@pytest.mark.parametrize("bad", [None, -1, float("nan"), float("inf")])
def test_invalid_window_values_are_not_counted(bad) -> None:
    ev = compute_stored_volume_evidence("X", _rows(50, [100] * 19 + [bad]))
    assert ev.valid_count == 19
    assert ev.avg_prev20 is None


def test_zero_is_valid_volume() -> None:
    ev = compute_stored_volume_evidence("X", _rows(0, [0] * 10 + [100] * 10))
    assert ev.volume == 0
    assert ev.valid_count == 20
    assert ev.avg_prev20 == 50
    assert ev.ratio == 0 and ev.ratio_status == "ok"


def test_zero_average_cannot_divide() -> None:
    ev = compute_stored_volume_evidence("X", _rows(10, [0] * 20))
    assert ev.avg_prev20 == 0 and ev.avg_status == "ok"
    assert ev.ratio is None and ev.ratio_status == "avg_zero"


def test_missing_reference_volume_keeps_average() -> None:
    ev = compute_stored_volume_evidence("X", _rows(None, [100] * 20))
    assert ev.volume is None
    assert ev.avg_prev20 == 100
    assert ev.ratio is None and ev.ratio_status == "volume_missing"


def test_ratio_reason_priority_missing_volume_before_insufficient() -> None:
    # 판정 §9-2: 기준일 거래량 없음 → 자료 부족 → 평균 0 순서로 하나만.
    ev = compute_stored_volume_evidence("X", _rows(-5, [100] * 3))
    assert ev.volume is None
    assert ev.ratio_status == "volume_missing"


def test_no_price_rows() -> None:
    ev = compute_stored_volume_evidence("X", [])
    assert ev.status == "no_price_data"
    assert ev.asof_date is None and ev.volume is None and ev.avg_prev20 is None


# ── 읽기 (tmp DB) ────────────────────────────────────────────────────────────


def _seed(db: Path, ticker: str, end: date, n: int, volumes, *, source="SrcA"):
    rows = []
    for i in range(n):
        d = (end - timedelta(days=n - 1 - i)).isoformat()
        rows.append(EtfDailyPriceRow(ticker, d, 1, 1, 1, 100.0, volumes(i), 0))
    upsert_daily_prices(rows, source=source, db_path=db)


def test_reader_skips_rows_without_close_and_reads_source(tmp_path: Path) -> None:
    db = tmp_path / "m.sqlite"
    end = date(2026, 10, 8)
    _seed(db, "069500", end, 25, lambda i: 1000 + i, source="FinanceDataReader")
    # 가격이 없는 최신 행 — 저장 가격 날짜가 아니므로 기준일이 되지 않는다.
    upsert_daily_prices(
        [EtfDailyPriceRow("069500", "2026-10-09", None, None, None, None, 5, None)],
        source="Other",
        db_path=db,
    )
    _seed(
        db, "OTHER1", date(2026, 10, 9), 25, lambda i: 7
    )  # 다른 종목 날짜는 안 섞인다
    rows = fetch_recent_price_rows("069500", limit=21, db_path=db)
    assert len(rows) == 21 and rows[0][0] == "2026-10-08"
    assert rows[0][3] == "FinanceDataReader"
    ev = build_stored_volume_evidence("069500", db_path=db)
    assert ev.asof_date == "2026-10-08"
    assert ev.source == "FinanceDataReader"
    assert ev.volume == 1024
    assert ev.avg_prev20 == pytest.approx(sum(1004 + k for k in range(20)) / 20)


# ── topn 응답 선택 필드 ───────────────────────────────────────────────────────


@pytest.fixture
def api_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    fake_db = tmp_path / "market_data.sqlite"
    monkeypatch.setattr(api_market_topn, "DEFAULT_DB_PATH", fake_db)
    monkeypatch.setattr(market_data_store, "DEFAULT_DB_PATH", fake_db)
    monkeypatch.setattr(etf_constituents_store, "DEFAULT_DB_PATH", fake_db)
    monkeypatch.setattr(etf_nav_store, "DEFAULT_DB_PATH", fake_db)
    market_refresh_service.reset_state_for_testing(db_path=fake_db)
    return TestClient(api_module.app)


def test_topn_response_carries_kodex200_stored_volume(api_client: TestClient) -> None:
    db = api_market_topn.DEFAULT_DB_PATH
    _seed(db, "069500", date(2026, 10, 8), 30, lambda i: 100 if i < 29 else 150)
    body = api_client.get("/market/topn/latest").json()
    vol = body["kodex200_stored_volume"]
    assert vol["ticker"] == "069500"
    assert vol["asof_date"] == "2026-10-08"
    assert vol["volume"] == 150 and vol["avg_prev20"] == 100
    assert vol["ratio"] == pytest.approx(1.5)
    assert vol["source"] == "SrcA"


def test_topn_response_without_kodex200_rows(api_client: TestClient) -> None:
    body = api_client.get("/market/topn/latest").json()
    assert body["kodex200_stored_volume"]["status"] == "no_price_data"


def test_reader_infinite_volume_is_invalid_not_error(tmp_path: Path) -> None:
    # REAL 무한대가 저장돼 있어도 읽기 · 계산이 오류를 내지 않고 유효하지 않은 값으로 센다.
    db = tmp_path / "m.sqlite"
    _seed(
        db, "069500", date(2026, 10, 8), 25, lambda i: float("inf") if i == 24 else 100
    )
    ev = build_stored_volume_evidence("069500", db_path=db)
    assert ev.volume is None and ev.ratio_status == "volume_missing"
    assert ev.avg_prev20 == 100
