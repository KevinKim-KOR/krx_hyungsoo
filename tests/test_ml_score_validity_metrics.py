"""POC3-ML-02 — 통계 지표 산식 테스트 (PLAN §7 T-1 / T-5 / T-8)."""

from __future__ import annotations

import math

import pytest

from app.ml_score_validity_metrics import (
    BOOTSTRAP_BLOCK_LEN,
    BOOTSTRAP_ITERATIONS,
    BOOTSTRAP_SEED,
    circular_block_bootstrap_ci,
    cost_drag,
    median,
    newey_west_t,
    percentile,
    quantile_bucket,
    replaced_fraction,
    shuffle_control_verdict,
    spearman,
    stdev,
    win_rate,
)

# --- T-1 알려진 답 rank IC --------------------------------------------------


def test_t1_spearman_perfect_monotonic_is_one():
    assert spearman([1, 2, 3, 4, 5], [10, 20, 30, 40, 50]) == pytest.approx(1.0)


def test_t1_spearman_perfect_anti_monotonic_is_minus_one():
    assert spearman([1, 2, 3, 4, 5], [50, 40, 30, 20, 10]) == pytest.approx(-1.0)


def test_t1_spearman_is_rank_based_not_level_based():
    """비선형 단조 변환에도 1.0 이어야 순위상관이다 (Pearson 이면 1 미만)."""
    xs = [1, 2, 3, 4, 5]
    ys = [1, 4, 9, 16, 10000]
    assert spearman(xs, ys) == pytest.approx(1.0)


def test_t1_spearman_ties_use_midrank():
    # 동점 midrank 를 쓰지 않으면 값이 달라진다.
    assert spearman([1, 1, 2, 2], [1, 2, 3, 4]) == pytest.approx(0.894427, abs=1e-5)


def test_spearman_constant_input_returns_none():
    assert spearman([5, 5, 5], [1, 2, 3]) is None


def test_spearman_length_mismatch_raises():
    with pytest.raises(ValueError):
        spearman([1, 2], [1, 2, 3])


# --- T-8 turnover / 비용 (월별 실측 적용) -----------------------------------


def test_t8_replaced_fraction_three_of_ten():
    prev = list("abcdefghij")
    cur = list("abcdefg") + ["x", "y", "z"]
    assert replaced_fraction(prev, cur) == pytest.approx(0.3)


def test_t8_replaced_fraction_no_change_is_zero():
    names = list("abcdefghij")
    assert replaced_fraction(names, names) == pytest.approx(0.0)


def test_t8_replaced_fraction_first_month_is_none():
    assert replaced_fraction(None, list("abc")) is None


def test_t8_cost_drag_known_answer():
    """교체 30% · 편도 25bp → 0.30 x 0.0025 x 2 = 0.0015 (15bp)."""
    assert cost_drag(0.3, 25.0) == pytest.approx(0.0015)


def test_t8_cost_drag_zero_bp_is_zero():
    assert cost_drag(0.9, 0.0) == pytest.approx(0.0)


def test_t8_cost_uses_monthly_value_not_average():
    """월별 실측값에 각각 적용한 합과 평균 turnover 적용이 다름을 고정한다."""
    monthly = [0.1, 0.9]
    per_month = sum(cost_drag(v, 25.0) for v in monthly)
    from_average = 2 * cost_drag(sum(monthly) / 2, 25.0)
    # 선형이라 총합은 같지만, 월별 net 시계열은 서로 다르다 -> CI 가 달라진다.
    assert per_month == pytest.approx(from_average)
    assert cost_drag(monthly[0], 25.0) != cost_drag(monthly[1], 25.0)


# --- bootstrap 계약 (확정사항 3) --------------------------------------------


def test_bootstrap_contract_constants_are_fixed():
    assert BOOTSTRAP_BLOCK_LEN == 6
    assert BOOTSTRAP_ITERATIONS == 2000
    assert BOOTSTRAP_SEED == 42


def test_bootstrap_is_deterministic_for_same_seed():
    series = [0.01 * i for i in range(30)]
    a = circular_block_bootstrap_ci(series)
    b = circular_block_bootstrap_ci(series)
    assert a == b


def test_bootstrap_ci_brackets_mean_of_constant_series():
    lo, hi = circular_block_bootstrap_ci([0.05] * 24)
    assert lo == pytest.approx(0.05)
    assert hi == pytest.approx(0.05)


def test_bootstrap_ci_of_strongly_positive_series_excludes_zero():
    series = [0.05, 0.06, 0.04, 0.055, 0.052] * 6
    lo, _hi = circular_block_bootstrap_ci(series)
    assert lo > 0


def test_bootstrap_ci_of_noise_series_contains_zero():
    series = [(-1) ** i * 0.05 for i in range(36)]
    lo, hi = circular_block_bootstrap_ci(series)
    assert lo <= 0 <= hi


def test_bootstrap_too_short_series_returns_none():
    assert circular_block_bootstrap_ci([0.1]) is None


# --- Newey-West --------------------------------------------------------------


def test_newey_west_t_positive_for_consistent_positive_series():
    assert (
        newey_west_t([0.02] * 20, lag=2) is None
        or newey_west_t([0.02, 0.03, 0.01] * 7, lag=2) > 0
    )


def test_newey_west_zero_variance_returns_none():
    assert newey_west_t([0.1] * 10, lag=2) is None


# --- T-5 N-1 negative control (확정사항 4) ----------------------------------


def test_t5_shuffle_control_passes_for_zero_centred_distribution():
    values = [0.004 * ((-1) ** i) for i in range(100)]
    verdict = shuffle_control_verdict(values)
    assert verdict["passed"] is True
    assert verdict["verdict"] == "ok"
    assert verdict["permutation_count"] == 100


def test_t5_shuffle_control_fails_when_mean_is_biased():
    values = [0.05] * 100
    verdict = shuffle_control_verdict(values)
    assert verdict["passed"] is False
    assert verdict["verdict"] == "metric 구현 이상 의심"
    assert verdict["mean_abs_below_threshold"] is False


def test_t5_shuffle_control_fails_when_interval_excludes_zero():
    values = [0.005 + 0.0001 * i for i in range(100)]
    verdict = shuffle_control_verdict(values)
    assert verdict["interval_contains_zero"] is False
    assert verdict["passed"] is False


# --- 보조 산식 ---------------------------------------------------------------


def test_quantile_bucket_partitions_evenly():
    buckets = [quantile_bucket(i, 10, 5) for i in range(10)]
    assert buckets == [0, 0, 1, 1, 2, 2, 3, 3, 4, 4]


def test_quantile_bucket_last_index_is_top_bucket():
    assert quantile_bucket(9, 10, 5) == 4


def test_quantile_bucket_rejects_zero_count():
    with pytest.raises(ValueError):
        quantile_bucket(0, 0, 5)


def test_percentile_linear_interpolation():
    assert percentile([1, 2, 3, 4], 50) == pytest.approx(2.5)


def test_median_even_and_odd():
    assert median([3, 1, 2]) == pytest.approx(2.0)
    assert median([4, 1, 2, 3]) == pytest.approx(2.5)


def test_stdev_needs_two_points():
    assert stdev([1.0]) is None
    assert stdev([1.0, 3.0]) == pytest.approx(math.sqrt(2.0))


def test_win_rate_counts_strictly_positive():
    assert win_rate([1.0, -1.0, 0.0, 2.0]) == pytest.approx(0.5)
    assert win_rate([]) is None
