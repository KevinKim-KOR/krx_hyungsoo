"""tests for app.ml_relative_upside_features.

검증 대상 (지시문 §17):
  - 20일 고점 대비 하락폭 계산 (정의: close / peak - 1, 음수).
  - feature 와 future target 시간 분리.
  - 미래 데이터 누수 방지 — include_future_target=False 일 때 future_excess_return_20d=None.
"""

from __future__ import annotations

from app.ml_relative_upside_features import (
    DRAWDOWN_LOOKBACK_20D,
    KODEX200_TICKER,
    build_feature_rows_for_ticker,
    build_kodex200_series,
)


def _flat_history(start_date: str, n_days: int, base_close: float = 100.0):
    """일정 close 의 시계열 생성 (날짜 ASC)."""
    from datetime import datetime, timedelta

    dt = datetime.strptime(start_date, "%Y-%m-%d")
    return [
        ((dt + timedelta(days=i)).strftime("%Y-%m-%d"), base_close)
        for i in range(n_days)
    ]


def _kodex_map_for(history):
    return {date: close for date, close in history}


def test_drawdown_zero_at_new_peak():
    """모든 종가가 동일하면 drawdown_20d = 0.0 (peak == close)."""
    history = _flat_history("2026-01-01", 50, 100.0)
    kodex_map = _kodex_map_for(history)
    rows = build_feature_rows_for_ticker(
        "TEST", history, kodex_map, include_future_target=False
    )
    assert len(rows) > 0
    for row in rows:
        assert row.drawdown_20d == 0.0


def test_drawdown_negative_when_below_peak():
    """close=90, 20일 high=100 이면 drawdown_20d = -0.10 (지시문 사용자 결정)."""
    # 20일간 100 유지 후 마지막 close = 90.
    history = _flat_history("2026-01-01", DRAWDOWN_LOOKBACK_20D + 1, 100.0)
    history[-1] = (history[-1][0], 90.0)
    kodex_map = _kodex_map_for(history)
    rows = build_feature_rows_for_ticker(
        "TEST", history, kodex_map, include_future_target=False
    )
    # 마지막 row 의 drawdown_20d 확인 (peak=100, close=90).
    last = rows[-1]
    assert last.close == 90.0
    assert last.drawdown_20d is not None
    assert abs(last.drawdown_20d - (-0.10)) < 1e-9


def test_future_target_none_when_inference_mode():
    """include_future_target=False 일 때 future_excess_return_20d 가 모두 None."""
    history = _flat_history("2026-01-01", 100, 100.0)
    kodex_map = _kodex_map_for(history)
    rows = build_feature_rows_for_ticker(
        "TEST", history, kodex_map, include_future_target=False
    )
    for row in rows:
        assert row.future_excess_return_20d is None


def test_future_target_set_only_when_horizon_available():
    """include_future_target=True 라도 i + 20 < n 일 때만 target 채워짐.

    지시문 AC-3 — 마지막 20일 row 는 미래 데이터 없으므로 target=None.
    """
    history = _flat_history("2026-01-01", 50, 100.0)
    kodex_map = _kodex_map_for(history)
    rows = build_feature_rows_for_ticker(
        "TEST", history, kodex_map, include_future_target=True
    )
    # 마지막 20개 row 의 future_excess_return_20d = None (미래 horizon 부재).
    for row in rows[-20:]:
        assert row.future_excess_return_20d is None
    # 가운데 row 는 future 값 (flat 시계열이라 future return = 0).
    middle_rows = [r for r in rows[:-20] if r.future_excess_return_20d is not None]
    assert len(middle_rows) > 0
    for row in middle_rows:
        assert abs(row.future_excess_return_20d) < 1e-9


def test_kodex200_series_builder():
    """build_kodex200_series 가 KODEX200 시계열만 dict 로 변환."""
    history = _flat_history("2026-01-01", 30, 100.0)
    prices = {KODEX200_TICKER: history, "OTHER": history}
    result = build_kodex200_series(prices)
    assert isinstance(result, dict)
    assert len(result) == 30
    for date, close in history:
        assert result[date] == close


def test_kodex200_series_empty_when_missing():
    """KODEX200 시계열 없으면 빈 dict (호출자가 excess_return None 처리)."""
    history = _flat_history("2026-01-01", 30, 100.0)
    prices = {"OTHER": history}
    result = build_kodex200_series(prices)
    assert result == {}


def test_feature_rows_minimum_lookback_skipped():
    """history 길이가 RETURN_LOOKBACK_20D 미만이면 row 0건."""
    short_history = _flat_history("2026-01-01", 10, 100.0)
    kodex_map = _kodex_map_for(short_history)
    rows = build_feature_rows_for_ticker(
        "TEST", short_history, kodex_map, include_future_target=False
    )
    assert rows == []
