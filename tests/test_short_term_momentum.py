"""단기 흐름 + 일간 플래그 단위 테스트 (POC2 2026-06-01).

Market Discovery Evidence Closeout 1차 — 지시문 §5 / §6 / AC-1 ~ AC-7.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.short_term_momentum import (
    DAILY_DROP_THRESHOLD_PCT,
    DAILY_SURGE_THRESHOLD_PCT,
    KODEX200_TICKER,
    compute_daily_return_check,
    compute_short_term_momentum,
    compute_short_term_momentum_batch,
)


def _seed_price(
    db: Path,
    ticker: str,
    prices: list[tuple[str, float]],
) -> None:
    db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(db)) as con:
        con.execute(
            "CREATE TABLE IF NOT EXISTS etf_daily_price ("
            "ticker TEXT NOT NULL, date TEXT NOT NULL, close REAL, "
            "PRIMARY KEY (ticker, date))"
        )
        for d, c in prices:
            con.execute(
                "INSERT OR REPLACE INTO etf_daily_price (ticker, date, close) "
                "VALUES (?, ?, ?)",
                (ticker, d, c),
            )
        con.commit()


def _series_n(start: float, step: float, days: int) -> list[tuple[str, float]]:
    """간단한 (date, close) 시리즈 — date 는 YYYY-MM-DD 단조 증가."""
    return [(f"2026-04-{(i + 1):02d}", start + step * i) for i in range(days)]


def test_short_term_momentum_ok(tmp_path: Path):
    db = tmp_path / "m.sqlite"
    # 후보 — 30일 단조 증가 (마지막 30일째 close=129).
    _seed_price(db, "069500", _series_n(100.0, 1.0, 30))
    _seed_price(db, "111111", _series_n(50.0, 2.0, 30))

    r = compute_short_term_momentum("111111", db_path=db)
    assert r.status == "ok"
    # 5거래일 수익률 — (close[-1] - close[-6]) / close[-6] * 100.
    # series: 50 + 2*i, last index = 29 -> 50+58=108, idx[-6]=50+2*24=98.
    expected_r5 = (108.0 - 98.0) / 98.0 * 100.0
    assert r.return_5d_pct == pytest.approx(expected_r5, rel=1e-6)
    # KODEX200 마찬가지로 5거래일 (단조 증가) — 100 + 29=129, idx[-6]=100+24=124.
    expected_b5 = (129.0 - 124.0) / 124.0 * 100.0
    assert r.excess_vs_kodex200_5d_pctp == pytest.approx(
        expected_r5 - expected_b5, rel=1e-6
    )
    assert r.end_date == "2026-04-30"


def test_short_term_momentum_unavailable_when_short_history(tmp_path: Path):
    db = tmp_path / "m.sqlite"
    _seed_price(db, "111111", _series_n(50.0, 2.0, 3))  # 3일만.
    r = compute_short_term_momentum("111111", db_path=db)
    assert r.status == "unavailable"
    assert "insufficient" in (r.message or "")


def test_short_term_momentum_unavailable_when_only_10_days(tmp_path: Path):
    """2026-06-03 FIX (검증자 A-1 NOTE) — 6~20거래일 사이 데이터는 부분 ok 가
    아니라 status='unavailable'. 20거래일 수익률을 산출 불가하므로 응답 계약
    정합을 위해 ok 자체를 반환하지 않는다."""
    db = tmp_path / "m.sqlite"
    _seed_price(db, KODEX200_TICKER, _series_n(100.0, 1.0, 30))
    _seed_price(db, "111111", _series_n(50.0, 2.0, 10))  # 10일만 — 20일 부족.
    r = compute_short_term_momentum("111111", db_path=db)
    assert r.status == "unavailable"
    assert r.return_5d_pct is None
    assert r.return_10d_pct is None
    assert r.return_20d_pct is None


def test_short_term_momentum_unavailable_when_kodex_short(tmp_path: Path):
    """2026-06-03 FIX — KODEX200 benchmark 시계열이 짧으면 초과수익 산출 불가
    이므로 ticker 이력이 충분해도 status='unavailable'."""
    db = tmp_path / "m.sqlite"
    _seed_price(db, KODEX200_TICKER, _series_n(100.0, 1.0, 10))  # 10일만.
    _seed_price(db, "111111", _series_n(50.0, 2.0, 30))
    r = compute_short_term_momentum("111111", db_path=db)
    assert r.status == "unavailable"
    assert "KODEX200" in (r.message or "")


def test_short_term_momentum_batch_reuses_kodex_series(tmp_path: Path):
    db = tmp_path / "m.sqlite"
    _seed_price(db, KODEX200_TICKER, _series_n(100.0, 1.0, 30))
    _seed_price(db, "AAA", _series_n(50.0, 2.0, 30))
    _seed_price(db, "BBB", _series_n(80.0, 0.5, 30))
    out = compute_short_term_momentum_batch(["AAA", "BBB"], db_path=db)
    assert out["AAA"].status == "ok"
    assert out["BBB"].status == "ok"
    # 둘 다 KODEX200 대비 초과수익이 채워짐.
    assert out["AAA"].excess_vs_kodex200_5d_pctp is not None
    assert out["BBB"].excess_vs_kodex200_5d_pctp is not None


def test_daily_return_check_ok(tmp_path: Path):
    db = tmp_path / "m.sqlite"
    _seed_price(db, "111111", [("2026-04-29", 100.0), ("2026-04-30", 102.0)])
    r = compute_daily_return_check("111111", db_path=db)
    assert r.status == "ok"
    assert r.daily_return_pct == pytest.approx(2.0, rel=1e-6)
    assert r.flag is None


def test_daily_return_check_surge(tmp_path: Path):
    db = tmp_path / "m.sqlite"
    _seed_price(db, "111111", [("2026-04-29", 100.0), ("2026-04-30", 115.0)])
    r = compute_daily_return_check("111111", db_path=db)
    assert r.status == "warning"
    assert r.flag == "daily_surge_check_needed"
    assert r.threshold_pct == DAILY_SURGE_THRESHOLD_PCT
    assert r.daily_return_pct == pytest.approx(15.0, rel=1e-6)


def test_daily_return_check_drop(tmp_path: Path):
    db = tmp_path / "m.sqlite"
    _seed_price(db, "111111", [("2026-04-29", 100.0), ("2026-04-30", 85.0)])
    r = compute_daily_return_check("111111", db_path=db)
    assert r.status == "warning"
    assert r.flag == "daily_drop_check_needed"
    assert r.threshold_pct == DAILY_DROP_THRESHOLD_PCT
    assert r.daily_return_pct == pytest.approx(-15.0, rel=1e-6)


def test_daily_return_check_unavailable_when_single_row(tmp_path: Path):
    db = tmp_path / "m.sqlite"
    _seed_price(db, "111111", [("2026-04-30", 100.0)])
    r = compute_daily_return_check("111111", db_path=db)
    assert r.status == "unavailable"
