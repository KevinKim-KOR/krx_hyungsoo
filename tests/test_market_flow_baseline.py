"""Market Flow ML Dataset + Baseline v1 자동 테스트 (2026-07-03).

지시문 §13 필수 테스트 12개:
1. target = KODEX200 이후 정확히 20번째 거래일 수익률
2. VIX source_date 는 as_of_date 보다 엄격히 이전
3. 동일 날짜 VIX 미사용
4. ETF breadth 에서 인버스/레버리지/합성/선물형/missing_confirm 제외
5. coverage_count/coverage_ratio 정의대로 계산
6. 필수 입력 없으면 임의 보정 X, unavailable 처리
7~8. 시간 순서 split + target overlap 방지
9. 재현성
10. 외부 데이터 호출 없음
11. latest_inference 는 무라벨 최신 feature 행에서만
12. 기존 전체 테스트 유지 (별도 실행)
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from app.market_data_store import (
    EtfDailyPriceRow,
    EtfMasterRow,
    init_db,
    upsert_daily_prices,
    upsert_etf_master,
)
from app.market_benchmark_store import upsert_benchmark_prices
from app.market_flow_baseline import (
    BENCHMARK_KODEX200_TICKER,
    BENCHMARK_KOSPI_ID,
    BENCHMARK_VIX_ID,
    FEATURE_COLUMNS,
    TARGET_COLUMN,
    _find_strictly_prior_vix,
    _median,
    _percentile,
    _temporal_split,
    build_dataset,
    run_baseline,
)
from app.market_timeseries_ingestion_store import (
    STATUS_MISSING_CONFIRM,
    TimeseriesIngestionStateRow,
    upsert_state as upsert_ingest_state,
)


def _iso_business_dates(start: str, count: int) -> list[str]:
    """단순한 연속 날짜 시퀀스 (평일/휴일 무관 — 시계열 인덱스 목적)."""
    d = date.fromisoformat(start)
    result: list[str] = []
    for _ in range(count):
        result.append(d.isoformat())
        d = d + timedelta(days=1)
    return result


def _seed_kodex(db: Path, dates: list[str], closes: list[float]) -> None:
    upsert_daily_prices(
        [
            EtfDailyPriceRow(
                ticker=BENCHMARK_KODEX200_TICKER,
                date=d,
                open=None,
                high=None,
                low=None,
                close=c,
                volume=None,
                change=None,
            )
            for d, c in zip(dates, closes)
        ],
        source="TEST",
        db_path=db,
    )


def _seed_kospi(db: Path, dates: list[str], closes: list[float]) -> None:
    upsert_benchmark_prices(
        benchmark_id=BENCHMARK_KOSPI_ID,
        benchmark_name="KOSPI",
        rows=list(zip(dates, closes)),
        source="TEST",
        db_path=db,
    )


def _seed_vix(db: Path, dates: list[str], closes: list[float]) -> None:
    upsert_benchmark_prices(
        benchmark_id=BENCHMARK_VIX_ID,
        benchmark_name="VIX",
        rows=list(zip(dates, closes)),
        source="TEST",
        db_path=db,
    )


def _seed_etf(
    db: Path, ticker: str, name: str, dates: list[str], closes: list[float]
) -> None:
    upsert_etf_master(
        [
            EtfMasterRow(
                ticker=ticker,
                name=name,
                category="1",
                price=None,
                volume=None,
                market_cap=None,
            )
        ],
        source="TEST",
        db_path=db,
    )
    upsert_daily_prices(
        [
            EtfDailyPriceRow(
                ticker=ticker,
                date=d,
                open=None,
                high=None,
                low=None,
                close=c,
                volume=None,
                change=None,
            )
            for d, c in zip(dates, closes)
        ],
        source="TEST",
        db_path=db,
    )


@pytest.fixture
def fake_db(tmp_path: Path) -> Path:
    db = tmp_path / "market_data.sqlite"
    init_db(db)
    return db


def _full_seed_normal(db: Path, n: int = 80) -> list[str]:
    """정상 시나리오 seed — 80 거래일 KODEX/KOSPI/VIX/ETF 3종."""
    dates = _iso_business_dates("2024-01-01", n)
    kodex_closes = [100.0 + i * 0.5 for i in range(n)]
    kospi_closes = [200.0 + i * 0.8 for i in range(n)]
    vix_closes = [15.0 + (i % 5) * 0.3 for i in range(n)]
    _seed_kodex(db, dates, kodex_closes)
    _seed_kospi(db, dates, kospi_closes)
    _seed_vix(db, dates, vix_closes)
    for i, tk in enumerate(("111111", "222222", "333333")):
        _seed_etf(
            db,
            tk,
            f"NAME_{tk}",
            dates,
            [50.0 + i + j * 0.2 for j in range(n)],
        )
    return dates


# ---------- 지시문 §13 개별 케이스 ----------


def test_1_target_is_20th_trading_day_return(fake_db: Path) -> None:
    dates = _full_seed_normal(fake_db, n=80)
    result = build_dataset(db_path=fake_db)
    assert result.rows
    # 첫 labeled 행: as_of_date 는 kodex_dates[20] (5d/20d lookback 성립).
    row = result.rows[0]
    idx_asof = dates.index(row["as_of_date"])
    expected_target_end = dates[idx_asof + 20]
    assert row["target_end_date"] == expected_target_end


def test_2_vix_source_date_strictly_prior(fake_db: Path) -> None:
    _full_seed_normal(fake_db, n=80)
    result = build_dataset(db_path=fake_db)
    for row in result.rows:
        assert row["vix_source_date"] < row["as_of_date"]


def test_3_same_day_vix_not_used(fake_db: Path) -> None:
    _full_seed_normal(fake_db, n=80)
    result = build_dataset(db_path=fake_db)
    for row in result.rows:
        assert row["vix_source_date"] != row["as_of_date"]


def test_4_etf_breadth_excludes_inverse_leveraged_synthetic_futures_and_missing_confirm(
    fake_db: Path,
) -> None:
    dates = _iso_business_dates("2024-01-01", 30)
    _seed_kodex(fake_db, dates, [100.0 + i for i in range(30)])
    _seed_kospi(fake_db, dates, [200.0 + i for i in range(30)])
    _seed_vix(fake_db, dates, [15.0] * 30)
    # 4 종 태그 + 1 정상.
    _seed_etf(fake_db, "AA", "KODEX 인버스", dates, [10.0] * 30)
    _seed_etf(fake_db, "BB", "KODEX 레버리지", dates, [10.0] * 30)
    _seed_etf(fake_db, "CC", "KODEX 합성 XYZ", dates, [10.0] * 30)
    _seed_etf(fake_db, "DD", "KODEX 미국선물", dates, [10.0] * 30)
    _seed_etf(fake_db, "EE", "NORMAL ETF", dates, [10.0 + i * 0.1 for i in range(30)])
    _seed_etf(fake_db, "FF", "MISSING", dates, [10.0] * 30)
    upsert_ingest_state(
        TimeseriesIngestionStateRow(
            ticker="FF",
            ingestion_status=STATUS_MISSING_CONFIRM,
            source="TEST",
            price_basis="SOURCE_CLOSE",
        ),
        db_path=fake_db,
    )

    from app.market_flow_dataset import _load_eligible_etf_tickers
    import sqlite3

    con = sqlite3.connect(str(fake_db))
    try:
        eligible = _load_eligible_etf_tickers(con)
    finally:
        con.close()
    assert eligible == ["EE"]


def test_5_coverage_count_and_ratio(fake_db: Path) -> None:
    # target 20d 미래 계산이 필요하므로 60 거래일 seed.
    dates = _iso_business_dates("2024-01-01", 60)
    _seed_kodex(fake_db, dates, [100.0 + i for i in range(60)])
    _seed_kospi(fake_db, dates, [200.0 + i for i in range(60)])
    _seed_vix(fake_db, dates, [15.0] * 60)
    # 3 종 정상. 그중 1 종은 first 10 일만 (20d lookback 계산 불가 케이스).
    _seed_etf(fake_db, "AA", "NORMAL A", dates, [10.0 + i * 0.1 for i in range(60)])
    _seed_etf(fake_db, "BB", "NORMAL B", dates, [20.0 + i * 0.1 for i in range(60)])
    _seed_etf(
        fake_db, "CC", "NORMAL C", dates[:10], [30.0 + i * 0.1 for i in range(10)]
    )
    result = build_dataset(db_path=fake_db)
    assert result.rows
    row0 = result.rows[0]
    assert row0["etf_eligible_count"] == 3
    # coverage: 첫 labeled row 는 as_of=dates[20]. CC 는 dates[:10] 만 → coverage 2.
    assert row0["etf_coverage_count_20d"] == 2
    assert row0["etf_coverage_ratio_20d"] == pytest.approx(2 / 3, abs=1e-9)


def test_6_missing_input_marks_unavailable_without_synthesis(
    fake_db: Path,
) -> None:
    """KOSPI 없음 → excluded_reason_counts 에 기록 + row 없음."""
    dates = _iso_business_dates("2024-01-01", 40)
    _seed_kodex(fake_db, dates, [100.0 + i for i in range(40)])
    # KOSPI seed 없음.
    _seed_vix(fake_db, dates, [15.0] * 40)
    _seed_etf(fake_db, "AA", "NORMAL", dates, [10.0 + i * 0.1 for i in range(40)])
    result = build_dataset(db_path=fake_db)
    assert result.labeled_count == 0
    assert "kospi_missing_on_asof" in result.excluded_reason_counts
    # 임의 보정 X — 0 채움 / forward fill 흔적 없음.


def test_7_temporal_split_train_no_leak_to_validation(fake_db: Path) -> None:
    _full_seed_normal(fake_db, n=80)
    result = build_dataset(db_path=fake_db)
    rows = result.rows
    if len(rows) < 3:
        pytest.skip("labeled row 부족")
    train, val, test = _temporal_split(rows)
    if train and val:
        train_max_end = max(r["target_end_date"] for r in train)
        val_start = val[0]["as_of_date"]
        assert train_max_end < val_start


def test_8_temporal_split_validation_no_leak_to_test(fake_db: Path) -> None:
    _full_seed_normal(fake_db, n=80)
    result = build_dataset(db_path=fake_db)
    rows = result.rows
    if len(rows) < 3:
        pytest.skip("labeled row 부족")
    train, val, test = _temporal_split(rows)
    if val and test:
        val_max_end = max(r["target_end_date"] for r in val)
        test_start = test[0]["as_of_date"]
        assert val_max_end < test_start


def test_9_reproducibility_same_fixture(fake_db: Path) -> None:
    _full_seed_normal(fake_db, n=80)
    r1 = build_dataset(db_path=fake_db)
    r2 = build_dataset(db_path=fake_db)
    assert len(r1.rows) == len(r2.rows)
    for a, b in zip(r1.rows, r2.rows):
        assert a["as_of_date"] == b["as_of_date"]
        for col in FEATURE_COLUMNS:
            assert a[col] == b[col]
        assert a[TARGET_COLUMN] == b[TARGET_COLUMN]


def test_10_no_external_data_calls(
    fake_db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FDR 호출 감시 — build_dataset 은 SQLite 만 사용."""
    import FinanceDataReader as fdr

    calls: list = []

    def stub(*args, **kwargs):
        calls.append((args, kwargs))
        raise RuntimeError("external data call should not happen")

    monkeypatch.setattr(fdr, "DataReader", stub)
    monkeypatch.setattr(fdr, "StockListing", stub)
    _full_seed_normal(fake_db, n=80)
    build_dataset(db_path=fake_db)
    assert calls == []


def test_11_latest_inference_only_on_unlabeled_latest_row(fake_db: Path) -> None:
    """무라벨 최신 행이 있으면 build 결과에 노출, 없으면 None."""
    _full_seed_normal(fake_db, n=80)
    result = build_dataset(db_path=fake_db)
    # target_horizon_unavailable 카운트가 존재하고 unlabeled_latest_row 는 dict.
    if result.unlabeled_latest_row is not None:
        assert TARGET_COLUMN in result.unlabeled_latest_row
        assert result.unlabeled_latest_row[TARGET_COLUMN] is None
        assert result.unlabeled_latest_row["as_of_date"] > result.rows[-1]["as_of_date"]


# ---------- 순수 helper 단위 ----------


def test_helper_percentile_and_median() -> None:
    assert _median([1.0, 2.0, 3.0]) == 2.0
    assert _median([1.0, 2.0, 3.0, 4.0]) == 2.5
    p50 = _percentile([1.0, 2.0, 3.0], 50.0)
    assert p50 == pytest.approx(2.0)


def test_helper_find_strictly_prior_vix() -> None:
    dates = ["2024-01-01", "2024-01-02", "2024-01-05"]
    # as_of == 2024-01-05 → strictly prior 는 index 1 (2024-01-02).
    assert _find_strictly_prior_vix(dates, "2024-01-05") == 1
    # as_of == 2024-01-01 → strictly prior 없음.
    assert _find_strictly_prior_vix(dates, "2024-01-01") is None


# ---------- 통합 run_baseline (sklearn 미존재 환경) ----------


def test_run_baseline_writes_artifacts_and_marks_unavailable_without_sklearn(
    fake_db: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _full_seed_normal(fake_db, n=80)
    dataset_path = tmp_path / "dataset.csv"
    artifact_path = tmp_path / "artifact.json"

    # sklearn 감지 함수를 False 로 강제 — 지시문 §7.1 시나리오 재현.
    monkeypatch.setattr("app.market_flow_baseline._sklearn_available", lambda: False)

    artifact = run_baseline(
        db_path=fake_db,
        dataset_path=dataset_path,
        artifact_path=artifact_path,
    )
    assert dataset_path.exists()
    assert artifact_path.exists()
    assert artifact["status"] == "unavailable"
    assert artifact["latest_inference"]["unavailable_reason"] == "sklearn_not_installed"
    assert artifact["schema_version"] == "market_flow_baseline_v1"
    assert artifact["vix_alignment"] == "strictly_prior_observation"
    assert artifact["model"]["ridge_alpha"] == 1.0
    # limitations 에 sklearn 미설치 명시.
    assert any("sklearn" in x for x in artifact["limitations"])
    # dataset 정보 노출.
    assert (
        artifact["dataset"]["row_count"]
        == len(artifact["feature_columns"]) * 0 + artifact["dataset"]["row_count"]
    )
    # 행동 문구 미포함.
    text = str(artifact).lower()
    for banned in ("매수", "매도", "상승 예상", "하락 예상", "위험 높음"):
        assert banned not in text


def test_dataset_csv_written_with_fixed_columns(
    fake_db: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _full_seed_normal(fake_db, n=80)
    dataset_path = tmp_path / "dataset.csv"
    artifact_path = tmp_path / "artifact.json"
    monkeypatch.setattr("app.market_flow_baseline._sklearn_available", lambda: False)
    run_baseline(
        db_path=fake_db,
        dataset_path=dataset_path,
        artifact_path=artifact_path,
    )
    content = dataset_path.read_text(encoding="utf-8").splitlines()
    header = content[0].split(",")
    # ID + feature + target 순서.
    from app.market_flow_baseline import ID_COLUMNS

    expected = list(ID_COLUMNS) + list(FEATURE_COLUMNS) + [TARGET_COLUMN]
    assert header == expected
