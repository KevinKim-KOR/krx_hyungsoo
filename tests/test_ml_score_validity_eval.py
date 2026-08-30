"""POC3-ML-02 — 평가 계약 테스트 (PLAN §7).

T-2 진입일 분리 / T-3 E2 무추가규칙 / T-4 target 종료일 / T-6 상장 PIT /
T-7 3M 비중첩 / T-9 산식 동결 / T-10 U2 순서 재현 / T-11 결측 미보간 /
T-12 E1 게이트 / T-13 커버리지 분모 / T-14 결정성 / T-15 경로 격리.

라이브 `state/` 경로에 쓰지 않는다 — 전부 합성 fixture + tmp_path.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.ml_relative_upside_features import (
    KODEX200_TICKER,
    build_feature_rows_for_ticker,
    build_kodex200_series,
)
from app.ml_score_validity_eval import (
    E1_MAX_SCORE_ABS_ERROR,
    E1_MIN_SPEARMAN,
    E1_MIN_TOP_K_OVERLAP,
    MIN_OBSERVATIONS,
    build_calendar,
    build_close_maps,
    evaluate_e1_gates,
    forward_excess,
    is_filter_universe,
    month_end_days,
    observations_upto,
    reproduce_scores_at,
    truncate_history,
)
from app.ml_score_validity_metrics import quantile_means, top_fraction
from app.ml_score_validity_screen import _read_only_connect, replay_screen_slates

# --- fixture 생성 ------------------------------------------------------------


def _business_days(start_year: int, months: int) -> list[str]:
    """월별 20 거래일을 갖는 합성 달력 (YYYY-MM-DD, 일자 01~20)."""
    days: list[str] = []
    year, month = start_year, 1
    for _ in range(months):
        for d in range(1, 21):
            days.append(f"{year:04d}-{month:02d}-{d:02d}")
        month += 1
        if month > 12:
            month = 1
            year += 1
    return days


def _series(days: list[str], start: float, step: float) -> list[tuple[str, float]]:
    return [(d, start + step * i) for i, d in enumerate(days)]


# --- T-2 진입일 분리 ---------------------------------------------------------


def test_t2_entry_date_is_the_day_after_signal_date():
    days = _business_days(2020, 6)
    points = build_calendar(days, months_ahead=1)
    assert points, "기준일이 하나도 없으면 안 된다"
    for p in points:
        assert p.entry_date > p.signal_date, "진입일은 판단일 이후여야 한다"
        assert days[days.index(p.signal_date) + 1] == p.entry_date
        assert p.exit_date > p.next_signal_date


def test_t2_exit_date_is_day_after_next_signal_date():
    days = _business_days(2020, 6)
    p = build_calendar(days, months_ahead=1)[0]
    assert days[days.index(p.next_signal_date) + 1] == p.exit_date


def test_t2_label_uses_entry_and_exit_not_signal_close():
    """판단일 종가로 라벨을 만들면 값이 달라진다 — 그것을 고정한다."""
    days = _business_days(2020, 3)
    prices = {
        "AAA": _series(days, 100.0, 1.0),
        KODEX200_TICKER: _series(days, 100.0, 0.0),
    }
    maps = build_close_maps(prices)
    p = build_calendar(days, months_ahead=1)[0]
    label = forward_excess(maps, "AAA", p.entry_date, p.exit_date)
    wrong = forward_excess(maps, "AAA", p.signal_date, p.next_signal_date)
    assert label is not None and wrong is not None
    assert label != pytest.approx(wrong)


def test_t2_one_month_windows_do_not_overlap():
    days = _business_days(2020, 8)
    points = build_calendar(days, months_ahead=1)
    for a, b in zip(points, points[1:]):
        assert a.exit_date <= b.exit_date
        assert a.entry_date < b.entry_date
        # a 의 청산일이 b 의 진입일이다 (= 겹치지 않는다).
        assert a.exit_date == b.entry_date


def test_t2_missing_entry_or_exit_price_returns_none():
    days = _business_days(2020, 3)
    prices = {
        "AAA": [(d, 100.0) for d in days if d != days[21]],
        KODEX200_TICKER: _series(days, 100.0, 0.0),
    }
    maps = build_close_maps(prices)
    assert forward_excess(maps, "AAA", days[21], days[25]) is None


# --- T-4 / T-3 절단만으로 target_end <= t --------------------------------


def test_t4_truncation_bounds_target_end_at_signal_date():
    days = _business_days(2020, 6)
    hist = _series(days, 100.0, 0.5)
    cut = days[70]
    truncated = truncate_history(hist, cut)
    assert truncated[-1][0] == cut
    kodex = build_kodex200_series({KODEX200_TICKER: truncated})
    rows = build_feature_rows_for_ticker(
        "AAA", truncated, kodex, include_future_target=True
    )
    with_target = [r for r in rows if r.future_excess_return_20d is not None]
    assert with_target, "target 이 있는 행이 있어야 검사가 의미 있다"
    # target 종료 index = asof_index + 20 이고, 그 날짜는 절단 이력 안에 있다.
    for row in with_target:
        end_date = truncated[row.asof_index + 20][0]
        assert end_date <= cut


def test_t4_truncate_history_is_inclusive_of_cut_date():
    hist = [("2020-01-01", 1.0), ("2020-01-02", 2.0), ("2020-01-03", 3.0)]
    assert truncate_history(hist, "2020-01-02") == hist[:2]
    assert truncate_history(hist, "2019-12-31") == []


def test_t3_reproduce_uses_default_recipe_arguments(monkeypatch):
    """E2 는 embargo/purge 인자를 주입하지 않고 v0 기본값으로 학습해야 한다."""
    import app.ml_score_validity_eval as mod

    seen = {}
    real = mod.train_walk_forward

    def spy(rows, **kwargs):
        seen["kwargs"] = kwargs
        return real(rows, **kwargs)

    monkeypatch.setattr(mod, "train_walk_forward", spy)

    days = _business_days(2020, 8)
    prices = {
        "AAA": _series(days, 100.0, 0.7),
        "BBB": _series(days, 100.0, -0.3),
        KODEX200_TICKER: _series(days, 100.0, 0.1),
    }
    mod.reproduce_scores_at(prices, days[120])
    assert seen["kwargs"] == {}, "기본 인자 외 어떤 학습 정책도 주입하면 안 된다"


def test_t3_reproduce_never_sees_prices_after_signal_date():
    days = _business_days(2020, 8)
    prices = {
        "AAA": _series(days, 100.0, 0.7),
        "BBB": _series(days, 100.0, -0.3),
        KODEX200_TICKER: _series(days, 100.0, 0.1),
    }
    cut = days[120]
    run = reproduce_scores_at(prices, cut)
    assert run.max_input_date is not None
    assert run.max_input_date <= cut
    assert run.max_target_end_date is None or run.max_target_end_date <= cut


# --- T-9 산식 동결 -----------------------------------------------------------


def test_t9_eval_features_match_operational_builder_exactly():
    """평가 경로가 산식을 재구현하지 않았음을 고정한다."""
    days = _business_days(2020, 6)
    hist = _series(days, 100.0, 0.4)
    kodex_hist = _series(days, 200.0, 0.2)
    cut = days[90]

    truncated = truncate_history(hist, cut)
    kodex_map = build_kodex200_series(
        {KODEX200_TICKER: truncate_history(kodex_hist, cut)}
    )
    expected = build_feature_rows_for_ticker(
        "AAA", truncated, kodex_map, include_future_target=False
    )
    # 평가 모듈은 동일 함수를 호출하므로 값이 완전히 같아야 한다.
    again = build_feature_rows_for_ticker(
        "AAA", truncate_history(hist, cut), kodex_map, include_future_target=False
    )
    assert [r.__dict__ for r in expected] == [r.__dict__ for r in again]


# --- T-6 상장 PIT ------------------------------------------------------------


def test_t6_observations_upto_counts_only_past_closes():
    days = _business_days(2020, 3)
    hist = _series(days[30:], 100.0, 1.0)  # 31번째 거래일에 상장
    assert observations_upto(hist, days[10]) == 0
    assert observations_upto(hist, days[30]) == 1
    assert observations_upto(hist, days[59]) == 30


def test_t6_ticker_below_min_observations_cannot_produce_features():
    days = _business_days(2020, 2)
    short = _series(days[: MIN_OBSERVATIONS - 1], 100.0, 1.0)
    kodex = build_kodex200_series({KODEX200_TICKER: _series(days, 100.0, 0.1)})
    rows = build_feature_rows_for_ticker(
        "NEW", short, kodex, include_future_target=False
    )
    assert rows == []


# --- T-7 3M 비중첩 -----------------------------------------------------------


def test_t7_three_month_calendar_spans_three_months():
    days = _business_days(2020, 12)
    points = build_calendar(days, months_ahead=3)
    ends = month_end_days(days)
    for p in points:
        i = ends.index(p.signal_date)
        assert ends[i + 3] == p.next_signal_date


def test_t7_quarter_end_subset_is_non_overlapping():
    days = _business_days(2020, 24)
    points = build_calendar(days, months_ahead=3)
    quarter = [p for p in points if p.signal_date[5:7] in ("03", "06", "09", "12")]
    assert quarter
    for a, b in zip(quarter, quarter[1:]):
        assert a.exit_date <= b.entry_date, "분기말 표본은 겹치면 안 된다"


# --- T-11 결측 미보간 --------------------------------------------------------


def test_t11_missing_price_is_excluded_not_filled_with_zero():
    days = _business_days(2020, 3)
    prices = {
        "GAP": [(d, 100.0) for d in days[:30]],  # 이후 데이터 없음
        KODEX200_TICKER: _series(days, 100.0, 0.1),
    }
    maps = build_close_maps(prices)
    assert forward_excess(maps, "GAP", days[40], days[50]) is None


def test_t11_quantile_means_ignore_absent_tickers():
    scored = [("A", 10.0, 0.05), ("B", 20.0, -0.02)]
    # 점수 오름차순 분위 — bucket 0 = 최하위 점수(A=10), bucket 1 = 최상위(B=20).
    result = quantile_means(scored, buckets=2)
    assert result[0] == pytest.approx(0.05)
    assert result[1] == pytest.approx(-0.02)


def test_top_fraction_takes_highest_scores():
    scored = [(f"T{i}", float(i), float(i)) for i in range(10)]
    top = top_fraction(scored, 0.2)
    assert [t[0] for t in top] == ["T9", "T8"]


# --- T-12 E1 게이트 ----------------------------------------------------------


def _perfect_scores(n: int = 120) -> dict[str, float]:
    return {f"T{i:04d}": float(i) for i in range(n)}


def test_t12_gate_passes_when_reproduction_is_exact():
    scores = _perfect_scores()
    gate = evaluate_e1_gates(scores, dict(scores))
    assert gate["status"] == "E1_RECONSTRUCTED"
    assert all(g["passed"] for g in gate["gates"].values())


def test_t12_gate_fails_on_candidate_set_mismatch():
    scores = _perfect_scores()
    repro = dict(scores)
    repro.pop("T0000")
    gate = evaluate_e1_gates(scores, repro)
    assert gate["status"] == "E1_UNAVAILABLE"
    assert gate["gates"]["G1_candidate_set_identical"]["passed"] is False


def test_t12_gate_fails_when_max_abs_score_error_exceeds_threshold():
    scores = _perfect_scores()
    repro = dict(scores)
    repro["T0050"] = scores["T0050"] + E1_MAX_SCORE_ABS_ERROR + 0.5
    gate = evaluate_e1_gates(scores, repro)
    assert gate["status"] == "E1_UNAVAILABLE"
    assert gate["gates"]["G3_max_abs_score_error"]["passed"] is False
    assert gate["gates"]["G3_max_abs_score_error"]["value"] > E1_MAX_SCORE_ABS_ERROR


def test_t12_gate_thresholds_are_the_approved_values():
    assert E1_MAX_SCORE_ABS_ERROR == 1.0
    assert E1_MIN_SPEARMAN == 0.999
    assert E1_MIN_TOP_K_OVERLAP == 0.95


def test_t12_gate_fails_when_ranks_disagree():
    scores = _perfect_scores()
    repro = {k: -v for k, v in scores.items()}  # 순위 완전 역전
    gate = evaluate_e1_gates(scores, repro)
    assert gate["status"] == "E1_UNAVAILABLE"
    assert gate["gates"]["G4_rank_agreement"]["passed"] is False


# --- T-13 커버리지 분모 = 필터 universe --------------------------------------


def test_t13_filter_universe_excludes_product_tags():
    assert is_filter_universe([]) is True
    assert is_filter_universe(["inverse"]) is False
    assert is_filter_universe(["leveraged"]) is False
    assert is_filter_universe(["synthetic"]) is False
    assert is_filter_universe(["futures"]) is False
    assert is_filter_universe(["leveraged", "futures"]) is False


# --- T-10 U2 화면 순서 재현 / T-15 경로 격리 ---------------------------------


def _build_market_db(
    path: Path, days: list[str], series: dict[str, list[float]]
) -> None:
    con = sqlite3.connect(str(path))
    con.execute(
        "CREATE TABLE etf_master (ticker TEXT PRIMARY KEY, name TEXT, category TEXT,"
        " price REAL, volume INTEGER, market_cap REAL, source TEXT NOT NULL,"
        " last_seen_at TEXT NOT NULL)"
    )
    con.execute(
        "CREATE TABLE etf_daily_price (ticker TEXT NOT NULL, date TEXT NOT NULL,"
        " open REAL, high REAL, low REAL, close REAL, volume INTEGER, change REAL,"
        " source TEXT NOT NULL, fetched_at TEXT NOT NULL, PRIMARY KEY (ticker, date))"
    )
    con.execute(
        "CREATE TABLE market_refresh_log (run_id TEXT PRIMARY KEY, source TEXT NOT NULL,"
        " asof TEXT NOT NULL, attempted_count INTEGER NOT NULL DEFAULT 0,"
        " success_count INTEGER NOT NULL DEFAULT 0, fail_count INTEGER NOT NULL DEFAULT 0,"
        " runtime_seconds REAL NOT NULL DEFAULT 0, error_summary TEXT,"
        " created_at TEXT NOT NULL)"
    )
    for ticker in series:
        name = "KODEX 레버리지" if ticker == "LEV" else f"TIGER {ticker}"
        con.execute(
            "INSERT INTO etf_master VALUES (?,?,?,?,?,?,?,?)",
            (ticker, name, None, None, None, None, "TEST", "2020-01-01"),
        )
    for ticker, closes in series.items():
        for d, c in zip(days, closes):
            con.execute(
                "INSERT INTO etf_daily_price VALUES (?,?,?,?,?,?,?,?,?,?)",
                (ticker, d, None, None, None, c, None, None, "TEST", "2020-01-01"),
            )
    con.commit()
    con.close()


def test_t10_screen_slate_is_one_month_return_order_not_score_order(tmp_path):
    days = _business_days(2020, 4)
    n = len(days)
    series = {
        # SLOW 가 최근 1개월 수익률이 가장 높도록 구성.
        "FAST": [100.0 + 0.1 * i for i in range(n)],
        "SLOW": [100.0] * (n - 25) + [100.0 + 3.0 * i for i in range(25)],
        "LEV": [100.0 + 5.0 * i for i in range(n)],  # 레버리지 → 제외되어야 함
        KODEX200_TICKER: [100.0 + 0.05 * i for i in range(n)],
    }
    db = tmp_path / "market.sqlite"
    _build_market_db(db, days, series)

    signal = days[-1]
    slates = replay_screen_slates(
        [signal], live_db_path=db, temp_db_path=tmp_path / "pit.sqlite", n=10
    )
    slate = slates[signal]
    tickers = [row["ticker"] for row in slate]
    assert "LEV" not in tickers, "레버리지는 화면 필터로 제외되어야 한다"
    assert tickers[0] == "SLOW", "1개월 수익률 desc 가 선정 기준이어야 한다"
    returns = [row["one_month_return_pct"] for row in slate]
    assert returns == sorted(returns, reverse=True)


def test_t10_pit_replay_ignores_prices_after_signal_date(tmp_path):
    """절단 임시 DB 를 쓰므로 미래 급등이 과거 슬레이트에 영향을 주면 안 된다."""
    days = _business_days(2020, 6)
    n = len(days)
    calm = [100.0 + 0.1 * i for i in range(n)]
    spike = [100.0 + 0.1 * i for i in range(n)]
    # 마지막 5거래일에만 폭등 → 1개월 window 안에서 급등으로 보인다.
    for i in range(n - 5, n):
        spike[i] = 100000.0
    series = {"AAA": calm, "SPIKE": spike, KODEX200_TICKER: calm}
    db = tmp_path / "market.sqlite"
    _build_market_db(db, days, series)

    # 과거 기준일과 최신 기준일을 함께 요청한다 — 증분 절단이 실제로
    # 동작해야만 과거 슬레이트가 미래 폭등을 못 본다.
    past_signal, last_signal = days[60], days[-1]
    slates = replay_screen_slates(
        [past_signal, last_signal],
        live_db_path=db,
        temp_db_path=tmp_path / "pit.sqlite",
        n=10,
    )
    for row in slates[past_signal]:
        assert (
            row["one_month_return_pct"] < 100.0
        ), "미래 폭등이 과거 기준일 수익률에 반영되면 PIT 재현이 아니다"
    # 반면 최신 기준일에서는 폭등이 보여야 한다 (테스트가 무의미하지 않음을 고정).
    assert any(
        row["one_month_return_pct"] > 100.0 for row in slates[last_signal]
    ), "최신 기준일에서는 폭등이 반영되어야 한다"


def test_t15_live_db_is_opened_read_only(tmp_path):
    days = _business_days(2020, 2)
    db = tmp_path / "market.sqlite"
    _build_market_db(db, days, {KODEX200_TICKER: [100.0] * len(days)})
    con = _read_only_connect(db)
    try:
        with pytest.raises(sqlite3.OperationalError):
            con.execute("DELETE FROM etf_daily_price")
    finally:
        con.close()


def test_t15_replay_does_not_modify_source_database(tmp_path):
    days = _business_days(2020, 3)
    n = len(days)
    db = tmp_path / "market.sqlite"
    _build_market_db(
        db,
        days,
        {"AAA": [100.0 + i for i in range(n)], KODEX200_TICKER: [100.0] * n},
    )
    before = db.read_bytes()
    replay_screen_slates(
        [days[40]], live_db_path=db, temp_db_path=tmp_path / "pit.sqlite", n=5
    )
    assert db.read_bytes() == before, "라이브 DB 가 변경되면 안 된다"


# --- T-14 결정성 -------------------------------------------------------------


def test_t14_reproduce_scores_is_deterministic():
    """T-14 (1/2) — PIT 재현 원시 단계의 결정성.

    전체 결과 객체 단위 결정성은 `test_ml_score_validity_contracts.py` 의
    `test_l4_full_payload_is_deterministic_across_two_builds` 가 담당한다
    (설계자 보완 §5 — 한 기준일 비교로 끝내지 않는다).
    """
    days = _business_days(2020, 8)
    prices = {
        "AAA": _series(days, 100.0, 0.7),
        "BBB": _series(days, 100.0, -0.3),
        "CCC": _series(days, 100.0, 0.2),
        KODEX200_TICKER: _series(days, 100.0, 0.1),
    }
    cut = days[120]
    first = reproduce_scores_at(prices, cut)
    second = reproduce_scores_at(prices, cut)
    assert first.display_scores == second.display_scores
    assert first.coefficients == second.coefficients


def test_t14_multi_date_reproduction_is_deterministic():
    """T-14 (2/2) — 여러 기준일에 걸쳐 재현 결과가 동일한가."""
    days = _business_days(2020, 10)
    prices = {
        "AAA": _series(days, 100.0, 0.7),
        "BBB": _series(days, 100.0, -0.3),
        "CCC": _series(days, 100.0, 0.2),
        KODEX200_TICKER: _series(days, 100.0, 0.1),
    }
    cuts = [days[100], days[140], days[180]]
    first = [reproduce_scores_at(prices, c).display_scores for c in cuts]
    second = [reproduce_scores_at(prices, c).display_scores for c in cuts]
    assert first == second
