"""ML Baseline v0 룩백 검증 — builder + API 테스트 (POC2 2026-06-11).

지시문 §17 / §18 — 외부 source 호출 0, baseline 재계산 X (API), leakage check,
조정장 label 미생성, 위험 threshold 미확정.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api import app
from app.market_benchmark_store import (
    MARKET_BENCHMARK_DAILY_PRICE_DDL,
    upsert_benchmark_prices,
)
from app.market_data_store import (
    ETF_DAILY_PRICE_DDL,
    ETF_MASTER_DDL,
    MARKET_REFRESH_LOG_DDL,
)
from app.market_regime import KODEX200_TICKER, KOSPI_ID
from app.ml_baseline_targets import (
    MAX_HORIZON,
    build_candidate_targets,
    build_risk_targets,
    evaluate_leakage,
)
from app.ml_baseline_v0 import build_baseline_report
from app.ml_feature_builder import build_features
from app.ml_feature_store import (
    ETF_ML_FEATURE_DAILY_DDL,
    MARKET_RISK_FEATURE_DAILY_DDL,
    upsert_etf_features,
    upsert_market_risk_features,
)


def _create_schema(db: Path) -> None:
    with sqlite3.connect(str(db)) as con:
        con.execute(ETF_MASTER_DDL)
        con.execute(ETF_DAILY_PRICE_DDL)
        con.execute(MARKET_REFRESH_LOG_DDL)
        con.execute(MARKET_BENCHMARK_DAILY_PRICE_DDL)
        con.execute(ETF_ML_FEATURE_DAILY_DDL)
        con.execute(MARKET_RISK_FEATURE_DAILY_DDL)
        con.commit()


def _insert_master(db: Path, ticker: str, name: str) -> None:
    with sqlite3.connect(str(db)) as con:
        con.execute(
            "INSERT OR REPLACE INTO etf_master(ticker, name, source, last_seen_at) "
            "VALUES (?, ?, 'test', '2026-06-08T00:00:00Z')",
            (ticker, name),
        )
        con.commit()


def _insert_price_series(
    db: Path, ticker: str, rows: list[tuple[str, float, int]]
) -> None:
    with sqlite3.connect(str(db)) as con:
        for d, c, v in rows:
            con.execute(
                "INSERT OR REPLACE INTO etf_daily_price"
                "(ticker, date, close, volume, source, fetched_at) "
                "VALUES (?, ?, ?, ?, 'test', '2026-06-08T00:00:00Z')",
                (ticker, d, c, v),
            )
        con.commit()


def _make_series(
    days: int, base_close: float, daily_change_pct: float
) -> list[tuple[str, float, int]]:
    out: list[tuple[str, float, int]] = []
    cur = date(2026, 3, 2)
    close = base_close
    for _ in range(days):
        while cur.weekday() >= 5:
            cur += timedelta(days=1)
        out.append((cur.isoformat(), round(close, 4), 10000))
        close *= 1.0 + (daily_change_pct / 100.0)
        cur += timedelta(days=1)
    return out


@pytest.fixture
def tmp_db_with_features(tmp_path: Path) -> Path:
    """50 거래일 (MAX_HORIZON=20 보다 충분히 큼) + 4 ETF + KOSPI."""
    db = tmp_path / "market_data.sqlite"
    _create_schema(db)
    _insert_master(db, KODEX200_TICKER, "KODEX 200")
    _insert_master(db, "360750", "TIGER 미국S&P500")
    _insert_master(db, "133690", "TIGER 미국나스닥100")
    _insert_master(db, "229200", "KODEX 코스닥150")
    _insert_price_series(db, KODEX200_TICKER, _make_series(50, 100.0, 0.5))
    _insert_price_series(db, "360750", _make_series(50, 50.0, 1.0))
    _insert_price_series(db, "133690", _make_series(50, 75.0, 0.3))
    _insert_price_series(db, "229200", _make_series(50, 30.0, -0.2))
    kospi_rows = [(d, c) for d, c, _ in _make_series(50, 2500.0, 0.4)]
    upsert_benchmark_prices(
        benchmark_id=KOSPI_ID,
        benchmark_name="KOSPI",
        rows=kospi_rows,
        source="test",
        db_path=db,
    )
    result = build_features(db_path=db, default_lookback_days=30)
    upsert_etf_features(result.etf_rows, db_path=db)
    upsert_market_risk_features(result.market_rows, db_path=db)
    return db


# ─── targets / leakage ──────────────────────────────────────────────


def test_candidate_targets_no_future_data_in_last_horizon(tmp_db_with_features: Path):
    rows, errs = build_candidate_targets(tmp_db_with_features, KODEX200_TICKER)
    assert errs == []
    # ticker 별 마지막 row 의 future_return_20d 는 반드시 None (tail 제외 보장).
    by_tk: dict[str, list] = {}
    for r in rows:
        by_tk.setdefault(r.ticker, []).append(r)
    for tk, lst in by_tk.items():
        lst.sort(key=lambda r: r.asof)
        assert (
            lst[-1].future_return_20d is None
        ), f"ticker={tk} 마지막 asof 의 future_return_20d 가 None 아님 — leakage 의심"


def test_risk_targets_no_future_data_in_last_horizon(tmp_db_with_features: Path):
    rows, errs = build_risk_targets(tmp_db_with_features, KODEX200_TICKER)
    assert errs == []
    rows.sort(key=lambda r: r.asof)
    assert rows[-1].future_kodex200_return_10d is None
    assert rows[-1].future_market_drawdown_10d is None


def test_leakage_check_passes_on_clean_data(tmp_db_with_features: Path):
    cand, _ = build_candidate_targets(tmp_db_with_features, KODEX200_TICKER)
    risk, _ = build_risk_targets(tmp_db_with_features, KODEX200_TICKER)
    leak = evaluate_leakage(tmp_db_with_features, cand, risk)
    assert leak.feature_future_data_leakage_detected is False
    assert leak.target_horizon_short_tail_excluded is True
    assert leak.time_order_preserved is True


def test_max_horizon_constant_is_20():
    """지시문 §7.2 / §8.2 의 horizon 중 max=20 (사용자 결정: max horizon tail 제외)."""
    assert MAX_HORIZON == 20


# ─── baseline report ────────────────────────────────────────────────


def test_build_baseline_report_returns_known_status(tmp_db_with_features: Path):
    report = build_baseline_report(db_path=tmp_db_with_features)
    assert report.status in ("ok", "warn", "insufficient_history")
    assert report.feature_asof_range["trading_days"] > 0
    assert report.candidate_baseline["target_horizons"] == [5, 10, 20]
    assert "high_risk_group_future_return" in report.risk_baseline
    # 조정장 label / 위험 threshold 가 report 어디에도 나타나지 않아야 함.
    serial = json.dumps(report.candidate_baseline) + json.dumps(report.risk_baseline)
    assert "regime_label" not in serial
    assert "risk_threshold" not in serial


def test_baseline_report_no_leakage(tmp_db_with_features: Path):
    report = build_baseline_report(db_path=tmp_db_with_features)
    leak = report.leakage_checks
    assert leak["feature_future_data_leakage_detected"] is False
    assert leak["target_horizon_short_tail_excluded"] is True


def test_baseline_report_evaluated_days_excludes_tail(tmp_db_with_features: Path):
    report = build_baseline_report(db_path=tmp_db_with_features)
    trading_days = report.feature_asof_range["trading_days"]
    # 평가 거래일 ≤ trading_days - MAX_HORIZON 이어야 함.
    assert report.evaluated_asof_range["evaluated_days"] <= trading_days - MAX_HORIZON


def test_baseline_report_evaluated_range_has_end(tmp_db_with_features: Path):
    """지시문 §6 / §11.1 — evaluated_asof_range.end 가 반드시 기록되어야 한다."""
    report = build_baseline_report(db_path=tmp_db_with_features)
    rng = report.evaluated_asof_range
    assert rng["start"] is not None
    assert rng["end"] is not None
    assert rng["end"] <= report.feature_asof_range["end"]


def test_candidate_baseline_includes_simple_comparisons(tmp_db_with_features: Path):
    """지시문 §7.4 — composite 외 단순 return_20d / excess_20d top quintile baseline 노출."""
    report = build_baseline_report(db_path=tmp_db_with_features)
    sb = report.candidate_baseline.get("simple_baselines")
    assert sb is not None
    assert "simple_return_20d_top_quintile_avg_future_return" in sb
    assert "simple_excess_20d_vs_kodex200_top_quintile_avg_future_return" in sb
    assert "universe_median_future_return" in sb


def test_risk_baseline_includes_simple_comparisons(tmp_db_with_features: Path):
    """지시문 §8.4 — composite 외 단순 5d 시장 수익률 / 20d drawdown / 시장폭 baseline 노출."""
    report = build_baseline_report(db_path=tmp_db_with_features)
    sb = report.risk_baseline.get("simple_baselines")
    assert sb is not None
    assert "kodex200_return_5d" in sb
    assert "drawdown_20d_market_proxy" in sb
    assert "etf_universe_down_ratio" in sb


def test_baseline_report_insufficient_history_on_empty_db(tmp_path: Path):
    db = tmp_path / "empty.sqlite"
    _create_schema(db)
    report = build_baseline_report(db_path=db)
    # 빈 DB → coverage error 가 곧 insufficient_history 또는 error.
    assert report.status in ("insufficient_history", "error")


# ─── API ────────────────────────────────────────────────────────────


def test_baseline_api_empty_when_no_report(tmp_path: Path, monkeypatch):
    fake = tmp_path / "missing.json"
    monkeypatch.setattr("app.api_ml_baseline.BASELINE_REPORT_PATH", fake, raising=False)
    client = TestClient(app)
    resp = client.get("/ml/baseline-v0/latest")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "empty"
    assert body["report"] is None
    assert body["message"] is not None


def test_baseline_api_returns_report_when_present(tmp_path: Path, monkeypatch):
    snap = tmp_path / "report.json"
    payload = {
        "status": "ok",
        "generated_at": "2026-06-11T00:00:00Z",
        "feature_asof_range": {"start": "2026-04-01", "end": "2026-06-08"},
        "candidate_baseline": {"status": "ok"},
        "risk_baseline": {"status": "ok"},
    }
    snap.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr("app.api_ml_baseline.BASELINE_REPORT_PATH", snap, raising=False)
    client = TestClient(app)
    resp = client.get("/ml/baseline-v0/latest")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["report"]["status"] == "ok"


def test_baseline_api_corrupted_report_returns_error(tmp_path: Path, monkeypatch):
    snap = tmp_path / "broken.json"
    snap.write_text("{invalid json", encoding="utf-8")
    monkeypatch.setattr("app.api_ml_baseline.BASELINE_REPORT_PATH", snap, raising=False)
    client = TestClient(app)
    resp = client.get("/ml/baseline-v0/latest")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "error"
    assert "손상" in body["message"]


def test_baseline_api_does_not_recompute(tmp_path: Path, monkeypatch):
    """read-only API 가 build_baseline_report 를 호출하지 않음을 보장."""
    snap = tmp_path / "report.json"
    snap.write_text('{"status": "ok"}', encoding="utf-8")
    monkeypatch.setattr("app.api_ml_baseline.BASELINE_REPORT_PATH", snap, raising=False)

    def _boom(*args, **kwargs):
        raise AssertionError("build_baseline_report called from API")

    monkeypatch.setattr(
        "app.ml_baseline_v0.build_baseline_report", _boom, raising=False
    )

    client = TestClient(app)
    resp = client.get("/ml/baseline-v0/latest")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
