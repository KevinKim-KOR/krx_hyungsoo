"""tests for app.ml_relative_upside_model.

검증 대상 (지시문 §17):
  - score 범위 0~100 (display).
  - 점수 미생성 처리 (raw_scores 빈 dict / model None).
  - 시간 순서 split — train 시간 ≤ test 시간 (랜덤 셔플 없음).
"""

from __future__ import annotations

from app.ml_relative_upside_features import CandidateFeatureRow
from app.ml_relative_upside_model import (
    normalize_to_display_scores,
    train_walk_forward,
)


def _make_row(ticker: str, asof_date: str, future_target: float) -> CandidateFeatureRow:
    """모든 feature 가 채워진 row 생성. future_target 만 가변."""
    return CandidateFeatureRow(
        ticker=ticker,
        asof_index=0,
        asof_date=asof_date,
        close=100.0,
        return_5d=0.01,
        return_10d=0.02,
        return_20d=0.03,
        excess_return_5d=0.005,
        excess_return_10d=0.01,
        excess_return_20d=0.015,
        drawdown_20d=-0.01,
        future_excess_return_20d=future_target,
    )


def test_normalize_empty_returns_empty():
    """raw_scores 빈 dict → 빈 dict."""
    assert normalize_to_display_scores({}) == {}


def test_normalize_single_returns_50():
    """단일 후보는 비교 의미 약하지만 안전 default 50.0."""
    result = normalize_to_display_scores({"A": 0.5})
    assert result == {"A": 50.0}


def test_normalize_range_0_to_100():
    """여러 후보 → 점수 0~100 범위. 최저값=0, 최고값=100."""
    raw = {"A": -0.5, "B": 0.0, "C": 0.3, "D": 1.0}
    display = normalize_to_display_scores(raw)
    assert min(display.values()) == 0.0
    assert max(display.values()) == 100.0
    # 모든 값이 0~100 사이.
    for v in display.values():
        assert 0.0 <= v <= 100.0


def test_normalize_ties_get_same_score():
    """동일 raw 값은 동일 display score."""
    raw = {"A": 1.0, "B": 1.0, "C": 2.0}
    display = normalize_to_display_scores(raw)
    assert display["A"] == display["B"]
    assert display["C"] > display["A"]


def test_train_walk_forward_time_order_preserved():
    """train 시간 ≤ test 시간 (랜덤 셔플 없음). 지시문 AC-2 / AC-3."""
    # 10일치 rows. 80% split.
    rows = [_make_row(f"T{i}", f"2026-01-{i+1:02d}", 0.01 * i) for i in range(10)]
    model, result = train_walk_forward(rows, epochs=10)
    # 8 train + 2 test (split_ratio=0.8 default).
    assert result.train_row_count == 8
    assert result.test_row_count == 2
    # train 의 max date ≤ test 의 min date.
    assert result.train_date_range[1] <= result.test_date_range[0]


def test_train_walk_forward_insufficient_data_returns_none_model():
    """학습 데이터 0~1건이면 model=None 반환 + train_row_count=0."""
    model, result = train_walk_forward([], epochs=10)
    assert model is None
    assert result.train_row_count == 0


def test_train_walk_forward_no_random_shuffle():
    """동일 seed 로 재실행 시 train/test 분할이 동일 — 시간 순서 정렬만 사용."""
    rows = [_make_row(f"T{i}", f"2026-01-{i+1:02d}", 0.01 * i) for i in range(10)]
    _, r1 = train_walk_forward(rows, epochs=10)
    _, r2 = train_walk_forward(rows, epochs=10)
    assert r1.train_date_range == r2.train_date_range
    assert r1.test_date_range == r2.test_date_range
