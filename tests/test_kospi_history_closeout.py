"""KOSPI history closeout 자동 테스트 (2026-07-05).

지시문 §10 필수 테스트:
1. run_kospi_closeout 이 SQLite 만 read + 결정된 source 만 write.
2. NAVER 후보만 split 충분 → NAVER 선택 + YAHOO 미조회.
3. NAVER 불충족 + YAHOO 충족 → YAHOO 선택 + NAVER 신규 행 미기록.
4. NAVER 도 YAHOO 도 불충족 → SQLite 미변경 + status=unavailable.
5. 기존 KOSPI 행 overwrite 금지 (동일 date 재기록 시 원본 close 유지).
6. NAVER 와 YAHOO 신규 행 혼합 금지 (선택된 한 source 만 저장).
7. artifact JSON 이 §8.1 형태 필드를 모두 포함.
8. kospi 실행이 외부 조회(fdr.DataReader) 를 하지만, benchmark/incremental 은
   KOSPI DataReader 를 호출하지 않는다 (경계 분리).
9. 외부 FDR 특정 반환치나 특정 source 의 성공 자체를 assertion 하지 않는다
   (테스트는 fixture 로 stubbed source 만 검증).

기본 원칙: 실제 FDR 호출은 stub 처리. 실제 KOSPI/KODEX/VIX/ETF 시계열은
fixture 로 SQLite 에 seed.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Callable

import pytest

from app import kospi_history_closeout
from app.kospi_history_closeout import (
    KOSPI_CLOSEOUT_ARTIFACT_PATH,
    KospiCloseoutResult,
    run_kospi_closeout,
)
from app.market_benchmark_store import (
    fetch_existing_benchmark_close_map,
    upsert_benchmark_prices,
)
from app.market_data_store import (
    EtfDailyPriceRow,
    EtfMasterRow,
    init_db,
    upsert_daily_prices,
    upsert_etf_master,
)
from app.market_flow_baseline import (
    BENCHMARK_KODEX200_TICKER,
    BENCHMARK_KOSPI_ID,
    BENCHMARK_VIX_ID,
)


def _iso_dates(start: str, count: int) -> list[str]:
    d = date.fromisoformat(start)
    out: list[str] = []
    for _ in range(count):
        out.append(d.isoformat())
        d = d + timedelta(days=1)
    return out


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


def _seed_vix(db: Path, dates: list[str], closes: list[float]) -> None:
    upsert_benchmark_prices(
        benchmark_id=BENCHMARK_VIX_ID,
        benchmark_name="VIX",
        rows=list(zip(dates, closes)),
        source="TEST",
        db_path=db,
    )


def _seed_kospi(
    db: Path, dates: list[str], closes: list[float], source: str = "TEST"
) -> None:
    upsert_benchmark_prices(
        benchmark_id=BENCHMARK_KOSPI_ID,
        benchmark_name="KOSPI",
        rows=list(zip(dates, closes)),
        source=source,
        db_path=db,
    )


def _seed_normal_etf(db: Path, ticker: str, dates: list[str]) -> None:
    upsert_etf_master(
        [
            EtfMasterRow(
                ticker=ticker,
                name=f"NORMAL_{ticker}",
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
                close=10.0 + i * 0.1,
                volume=None,
                change=None,
            )
            for i, d in enumerate(dates)
        ],
        source="TEST",
        db_path=db,
    )


@pytest.fixture
def fake_db(tmp_path: Path) -> Path:
    db = tmp_path / "market_data.sqlite"
    init_db(db)
    return db


def _seed_full_market(db: Path, n: int = 100) -> list[str]:
    """KODEX + VIX + ETF 3종 seed. KOSPI 는 테스트별로 조절."""
    dates = _iso_dates("2024-01-01", n)
    _seed_kodex(db, dates, [100.0 + i * 0.5 for i in range(n)])
    _seed_vix(db, dates, [15.0 + (i % 5) * 0.3 for i in range(n)])
    for tk in ("111111", "222222", "333333"):
        _seed_normal_etf(db, tk, dates)
    return dates


def _make_fdr_stub(
    per_symbol_rows: dict[str, list[tuple[str, float]]],
    call_log: list[dict],
) -> Callable:
    """FDR DataReader stub — symbol 별로 정해진 rows 를 pandas-like 로 반환."""
    import pandas as pd

    def stub(symbol, start=None, end=None):
        call_log.append({"symbol": symbol, "start": start, "end": end})
        rows = per_symbol_rows.get(symbol, [])
        if not rows:
            return pd.DataFrame(columns=["Close"])
        idx = pd.to_datetime([r[0] for r in rows])
        return pd.DataFrame({"Close": [r[1] for r in rows]}, index=idx)

    return stub


# ---------- 지시문 §10 테스트 케이스 ----------


def test_1_naver_sufficient_selects_naver_and_skips_yahoo(
    fake_db: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """NAVER 후보만으로 split 충분 → NAVER 선택 + YAHOO 미조회."""
    dates = _seed_full_market(fake_db, n=200)
    # KOSPI 는 seed 안 함 → NAVER stub 가 전체 100 일 반환.
    call_log: list[dict] = []
    stub = _make_fdr_stub(
        {
            kospi_history_closeout.NAVER_SYMBOL: [
                (d, 200.0 + i * 0.6) for i, d in enumerate(dates)
            ],
            # YAHOO 는 등록 안 함 — 호출 시 감지 목적.
        },
        call_log,
    )
    import FinanceDataReader as fdr

    monkeypatch.setattr(fdr, "DataReader", stub)

    artifact_path = tmp_path / "kospi_closeout.json"
    result: KospiCloseoutResult = run_kospi_closeout(
        db_path=fake_db, artifact_path=artifact_path
    )

    assert result.status == "ok"
    assert result.selected_source == "NAVER_FDR"
    assert result.naver.selected is True
    assert result.yahoo.selected is False
    # YAHOO 은 조회조차 안 됨.
    symbols_called = [c["symbol"] for c in call_log]
    assert kospi_history_closeout.NAVER_SYMBOL in symbols_called
    assert kospi_history_closeout.YAHOO_SYMBOL not in symbols_called
    # SQLite 에 KOSPI 저장됨.
    kospi_map = fetch_existing_benchmark_close_map(BENCHMARK_KOSPI_ID, db_path=fake_db)
    assert len(kospi_map) == 200


def test_2_naver_insufficient_yahoo_sufficient_selects_yahoo(
    fake_db: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """NAVER 반환 부족 → YAHOO fallback 성공 시 YAHOO 만 저장."""
    dates = _seed_full_market(fake_db, n=200)
    call_log: list[dict] = []
    stub = _make_fdr_stub(
        {
            # NAVER 은 아주 짧은 구간만 → labeled 행이 나올 수 없어 split 불충분.
            kospi_history_closeout.NAVER_SYMBOL: [(dates[0], 200.0)],
            kospi_history_closeout.YAHOO_SYMBOL: [
                (d, 210.0 + i * 0.6) for i, d in enumerate(dates)
            ],
        },
        call_log,
    )
    import FinanceDataReader as fdr

    monkeypatch.setattr(fdr, "DataReader", stub)

    result = run_kospi_closeout(
        db_path=fake_db, artifact_path=tmp_path / "kospi_closeout.json"
    )

    assert result.status == "ok"
    assert result.selected_source == "YAHOO_FDR"
    assert result.yahoo.selected is True
    assert result.naver.selected is False
    # SQLite 에 KOSPI 저장은 YAHOO 값 기반.
    kospi_map = fetch_existing_benchmark_close_map(BENCHMARK_KOSPI_ID, db_path=fake_db)
    # YAHOO 신규 100 행 저장 (NAVER 1 행은 미기록).
    assert len(kospi_map) == 200
    # 저장된 값은 YAHOO 계열 (200.0 시작 아님).
    assert kospi_map[dates[0]] == pytest.approx(210.0)


def test_3_both_insufficient_leaves_sqlite_untouched(
    fake_db: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """NAVER + YAHOO 모두 split 불충족 → SQLite 미변경 + status=unavailable."""
    dates = _seed_full_market(fake_db, n=200)
    _seed_kospi(fake_db, dates[:5], [200.0, 200.5, 201.0, 201.5, 202.0])
    kospi_before = fetch_existing_benchmark_close_map(
        BENCHMARK_KOSPI_ID, db_path=fake_db
    )

    call_log: list[dict] = []
    stub = _make_fdr_stub(
        {
            kospi_history_closeout.NAVER_SYMBOL: [(dates[0], 200.0)],
            kospi_history_closeout.YAHOO_SYMBOL: [(dates[0], 210.0)],
        },
        call_log,
    )
    import FinanceDataReader as fdr

    monkeypatch.setattr(fdr, "DataReader", stub)

    result = run_kospi_closeout(
        db_path=fake_db, artifact_path=tmp_path / "kospi_closeout.json"
    )

    assert result.status == "unavailable"
    assert result.selected_source is None
    assert result.inserted_row_count == 0
    kospi_after = fetch_existing_benchmark_close_map(
        BENCHMARK_KOSPI_ID, db_path=fake_db
    )
    assert kospi_after == kospi_before


def test_4_existing_kospi_rows_not_overwritten(
    fake_db: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """기존 KOSPI 행 overwrite 금지."""
    dates = _seed_full_market(fake_db, n=200)
    # 기존 5 개 KOSPI 행 seed (특수한 표식 close).
    existing_dates = dates[:5]
    existing_closes = [999.1, 999.2, 999.3, 999.4, 999.5]
    _seed_kospi(fake_db, existing_dates, existing_closes, source="EXISTING")

    call_log: list[dict] = []
    stub = _make_fdr_stub(
        {
            kospi_history_closeout.NAVER_SYMBOL: [
                (d, 200.0 + i * 0.6) for i, d in enumerate(dates)
            ],
        },
        call_log,
    )
    import FinanceDataReader as fdr

    monkeypatch.setattr(fdr, "DataReader", stub)

    result = run_kospi_closeout(
        db_path=fake_db, artifact_path=tmp_path / "kospi_closeout.json"
    )

    assert result.status == "ok"
    assert result.overwrite_performed is False
    kospi_after = fetch_existing_benchmark_close_map(
        BENCHMARK_KOSPI_ID, db_path=fake_db
    )
    for d, c in zip(existing_dates, existing_closes):
        assert kospi_after[d] == pytest.approx(c), f"기존 KOSPI {d} 값이 overwrite 됨"
    # 신규 date 는 NAVER 값으로 저장.
    for i in range(5, 200):
        assert kospi_after[dates[i]] == pytest.approx(200.0 + i * 0.6)


def test_5_no_source_mixing(
    fake_db: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """NAVER + YAHOO 신규 행 혼합 금지 — 선택된 한 source 만 저장."""
    dates = _seed_full_market(fake_db, n=200)
    call_log: list[dict] = []
    # NAVER 로 성공 → YAHOO 신규 행이 저장되면 안 됨.
    stub = _make_fdr_stub(
        {
            kospi_history_closeout.NAVER_SYMBOL: [
                (d, 200.0 + i * 0.6) for i, d in enumerate(dates)
            ],
            kospi_history_closeout.YAHOO_SYMBOL: [
                (d, 999.0 + i) for i, d in enumerate(dates)  # 만약 저장되면 표식.
            ],
        },
        call_log,
    )
    import FinanceDataReader as fdr

    monkeypatch.setattr(fdr, "DataReader", stub)

    result = run_kospi_closeout(
        db_path=fake_db, artifact_path=tmp_path / "kospi_closeout.json"
    )
    assert result.selected_source == "NAVER_FDR"
    kospi_after = fetch_existing_benchmark_close_map(
        BENCHMARK_KOSPI_ID, db_path=fake_db
    )
    # YAHOO 표식 999.x 는 어떤 date 에도 저장되면 안 됨.
    for d, c in kospi_after.items():
        assert c < 500.0, f"YAHOO 값 {c} 이 NAVER 성공 상황에서 저장됨 ({d})"


def test_6_artifact_contains_required_fields(
    fake_db: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """artifact §8.1 필수 필드 존재 확인."""
    dates = _seed_full_market(fake_db, n=200)
    call_log: list[dict] = []
    stub = _make_fdr_stub(
        {
            kospi_history_closeout.NAVER_SYMBOL: [
                (d, 200.0 + i * 0.6) for i, d in enumerate(dates)
            ],
        },
        call_log,
    )
    import FinanceDataReader as fdr

    monkeypatch.setattr(fdr, "DataReader", stub)

    artifact_path = tmp_path / "kospi_closeout.json"
    run_kospi_closeout(db_path=fake_db, artifact_path=artifact_path)
    import json

    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    for key in (
        "status",
        "generated_at",
        "requested_range",
        "existing_kospi",
        "source_candidates",
        "selected_source",
        "inserted_row_count",
        "overwrite_performed",
        "source_application_ranges",
    ):
        assert key in payload, f"missing key: {key}"
    assert "naver_fdr" in payload["source_candidates"]
    assert "yahoo_fdr" in payload["source_candidates"]
    assert "projected_split_rows" in payload["source_candidates"]["naver_fdr"]


def test_7_kodex_range_missing_returns_unavailable(
    fake_db: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """KODEX200 시계열 없음 → SQLite 변경 X, status=unavailable."""
    # KODEX 를 seed 하지 않음.
    call_log: list[dict] = []

    def stub(*a, **kw):  # 호출되어서는 안 됨.
        call_log.append((a, kw))
        import pandas as pd

        return pd.DataFrame(columns=["Close"])

    import FinanceDataReader as fdr

    monkeypatch.setattr(fdr, "DataReader", stub)

    result = run_kospi_closeout(
        db_path=fake_db, artifact_path=tmp_path / "kospi_closeout.json"
    )
    assert result.status == "unavailable"
    assert result.unavailable_reason == "kodex_range_missing"
    assert call_log == []


def test_8_benchmark_incremental_do_not_call_kospi_datareader(
    fake_db: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """경계 분리: kospi 명령 외 경로 (benchmark/incremental) 는 KOSPI symbol 을
    DataReader 로 호출하지 않는다.
    """
    from scripts import refresh_market_timeseries as script

    # main() 을 호출하지 않고 인자 파서로 직접 kospi 이외 서브커맨드 목록 확인.
    parser = (
        script._parse_args.__wrapped__
        if hasattr(script._parse_args, "__wrapped__")
        else None
    )
    _ = parser  # not required — 우리는 소스 정적으로만 검사.
    import inspect

    # kospi 서브커맨드 dispatch 외의 함수들 (_cmd_benchmark, _cmd_incremental,
    # _cmd_initial, _cmd_vix, _cmd_status) 이 KOSPI symbol 상수를 사용하지 않음.
    for fn_name in (
        "_cmd_benchmark",
        "_cmd_incremental",
        "_cmd_initial",
        "_cmd_vix",
        "_cmd_status",
    ):
        fn = getattr(script, fn_name, None)
        if fn is None:
            continue
        fn_src = inspect.getsource(fn)
        assert "NAVER:KOSPI" not in fn_src
        assert "^KS11" not in fn_src
        assert "run_kospi_closeout" not in fn_src


def test_9_default_artifact_path_constant() -> None:
    """§8.1 artifact 경로 상수 존재 확인."""
    assert str(KOSPI_CLOSEOUT_ARTIFACT_PATH).endswith(
        "kospi_history_closeout_latest.json"
    )
