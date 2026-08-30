"""POC3-ML-02 — 검증자 REJECTED 보완 계약 테스트 (설계자 보완 §7).

여기 있는 테스트는 "계약 누락이 실제로 닫혔는가" 를 확인한다. 실패가 실행을
막는지(fail-closed)까지 검증한다.

- S-1 위반 → 집계·최종 판정 미발행
- E2 평가일 coverage < 70% → `BLOCKED_COVERAGE`
- 3M 비중첩 결과가 최종 JSON 에 존재
- score top-10 결과가 최종 JSON 에 존재
- 20거래일 미충족 ticker 가 coverage 분모에서 제외
- L-4 전체 결과 객체 결정성
- A-6 `NOT_EVALUABLE / passed=null`
"""

from __future__ import annotations

import pytest

from app.ml_score_validity_eval import (
    BLOCKING_MIN_COVERAGE,
    E2_EXPECTED_POINT_COUNT,
    E2_FIRST_SIGNAL_DATE,
    MIN_OBSERVATIONS,
    PHASE_EVALUATION,
    PHASE_WARMUP,
    PRE_EVALUATION_WARMUP_DATES,
    SCORE_TOP_N,
    assert_evaluation_window,
    classify_phase,
    is_filter_universe,
    is_pit_eligible,
)
from app.ml_score_validity_report import (
    NON_DETERMINISTIC_FIELDS,
    aggregate,
    canonical_sha256,
    preflight_gate,
)

# --- fixture -----------------------------------------------------------------


def _month_dates(count: int) -> list[tuple[str, str, str, str]]:
    """(signal, entry, next_signal, exit) 을 월별로 생성."""
    out = []
    year, month = 2015, 1
    for _ in range(count):
        nm_year, nm_month = (year, month + 1) if month < 12 else (year + 1, 1)
        out.append(
            (
                f"{year:04d}-{month:02d}-28",
                f"{year:04d}-{month:02d}-29",
                f"{nm_year:04d}-{nm_month:02d}-28",
                f"{nm_year:04d}-{nm_month:02d}-29",
            )
        )
        year, month = nm_year, nm_month
    return out


def _record(signal, entry, nxt, exit_, *, ic=0.05, coverage=0.99, regime="bull"):
    tickers = [f"T{i:03d}" for i in range(SCORE_TOP_N)]
    values = [0.01 * (i + 1) for i in range(SCORE_TOP_N)]
    return {
        "phase": classify_phase(signal),
        "signal_date": signal,
        "entry_date": entry,
        "exit_date": exit_,
        "next_signal_date": nxt,
        "regime": regime,
        "train_row_count": 1000,
        "test_row_count": 250,
        "scored_count": 50,
        "asof_equals_signal_ratio": 1.0,
        "coverage_denominator": 100,
        "coverage_numerator": int(round(coverage * 100)),
        "coverage": coverage,
        "missing_reasons": {"lookback_부족": 1},
        "max_input_date": signal,
        "max_target_end_date": signal,
        "ic_filter": ic,
        "ic_all": ic,
        "ic_simple_momentum": ic,
        "ic_3m": ic,
        "n_filter": 50,
        "n_all": 60,
        "n_3m": 50,
        "quantile_means": {"0": -0.01, "1": 0.0, "2": 0.01, "3": 0.02, "4": 0.03},
        "_scores": [float(i) for i in range(20)],
        "_labels": [0.001 * i for i in range(20)],
        "top_decile_tickers": tickers[:5],
        "top_decile_values": values[:5],
        "top_decile_mean": sum(values[:5]) / 5,
        "top_decile_median": values[2],
        "top_decile_win_rate": 1.0,
        "score_top10_tickers": tickers,
        "score_top10_values": values,
        "score_top10_mean": sum(values) / len(values),
        "score_top10_median": values[4],
        "score_top10_size": SCORE_TOP_N,
        "score_top10_missing_reason": None,
        "is_quarter_end": signal[5:7] in ("03", "06", "09", "12"),
        "exclusion_3m": None,
        "quantile_means_3m": {"0": -0.02, "1": 0.0, "2": 0.01, "3": 0.02, "4": 0.04},
        "top_decile_3m_tickers": tickers[:5],
        "top_decile_3m_values": values[:5],
        "top_decile_3m_mean": sum(values[:5]) / 5,
        "screen_slate_size": 10,
        "screen_top_half_mean": 0.01,
        "screen_bottom_half_mean": 0.0,
        "screen_diff": 0.01,
        "screen_tickers": tickers,
    }


def _records(count=24, **kw):
    return [_record(*d, **kw) for d in _month_dates(count)]


def _e1_unavailable():
    return {"status": "E1_UNAVAILABLE", "reason": "테스트"}


def _days():
    return [f"2015-{m:02d}-{d:02d}" for m in range(1, 13) for d in (1, 15, 28)]


def _aggregate(records, e1=None):
    return aggregate(
        records,
        e1 or _e1_unavailable(),
        _days(),
        {"score_version": "test"},
        {},
        warmup_records=[],
    )


def _n1_pass():
    return {"passed": True, "verdict": "ok"}


def _n1_fail():
    return {"passed": False, "verdict": "metric 구현 이상 의심"}


# --- 1. warmup 분류과 평가 구간 계약 ----------------------------------------


def test_warmup_dates_are_pre_declared_not_derived():
    assert PRE_EVALUATION_WARMUP_DATES == ("2014-04-30", "2014-05-30")
    for d in PRE_EVALUATION_WARMUP_DATES:
        assert classify_phase(d) == PHASE_WARMUP
    assert classify_phase("2014-06-30") == PHASE_EVALUATION


def test_train_rows_zero_outside_warmup_is_not_reclassified():
    """warmup 은 사전 고정 집합이다 — 결과를 보고 재분류하지 않는다."""
    assert classify_phase("2019-03-29") == PHASE_EVALUATION


def test_evaluation_window_contract_is_enforced():
    dates = [E2_FIRST_SIGNAL_DATE] + [
        f"2015-{m:02d}-28" for m in range(1, E2_EXPECTED_POINT_COUNT)
    ]
    assert_evaluation_window(dates)


def test_evaluation_window_rejects_wrong_start_date():
    dates = ["2014-05-30"] + [
        f"2015-{m:02d}-28" for m in range(1, E2_EXPECTED_POINT_COUNT)
    ]
    with pytest.raises(RuntimeError, match="시작일"):
        assert_evaluation_window(dates)


def test_evaluation_window_rejects_wrong_count():
    with pytest.raises(RuntimeError, match="평가일 수"):
        assert_evaluation_window([E2_FIRST_SIGNAL_DATE, "2014-07-31"])


# --- 2. fail-closed: coverage / 누수 / N-1 ----------------------------------


def test_coverage_below_threshold_blocks_with_blocked_coverage():
    recs = _records(6)
    recs[3]["coverage"] = 0.55
    gate = preflight_gate(recs, _n1_pass())
    assert gate["status"] == "BLOCKED_COVERAGE"
    assert "BLOCKED_COVERAGE" in gate["blocked"]
    dates = [x["signal_date"] for x in gate["details"]["BLOCKED_COVERAGE"]["dates"]]
    assert recs[3]["signal_date"] in dates


def test_coverage_exactly_at_threshold_is_not_blocked():
    recs = _records(6)
    recs[2]["coverage"] = BLOCKING_MIN_COVERAGE
    assert preflight_gate(recs, _n1_pass())["status"] == "OK"


def test_missing_coverage_is_blocked():
    recs = _records(6)
    recs[1]["coverage"] = None
    assert preflight_gate(recs, _n1_pass())["status"] == "BLOCKED_COVERAGE"


def test_s1_leakage_violation_blocks_aggregation():
    recs = _records(6)
    recs[4]["max_input_date"] = "2099-01-01"  # 기준일 이후 입력
    gate = preflight_gate(recs, _n1_pass())
    assert gate["status"] == "BLOCKED_LEAKAGE"
    assert gate["details"]["BLOCKED_LEAKAGE"]["L1"] == [recs[4]["signal_date"]]


def test_s1_entry_not_after_signal_blocks():
    recs = _records(6)
    recs[2]["entry_date"] = recs[2]["signal_date"]
    gate = preflight_gate(recs, _n1_pass())
    assert gate["status"] == "BLOCKED_LEAKAGE"
    assert recs[2]["signal_date"] in gate["details"]["BLOCKED_LEAKAGE"]["L2"]


def test_s1_target_end_after_signal_blocks():
    recs = _records(6)
    recs[0]["max_target_end_date"] = "2099-01-01"
    gate = preflight_gate(recs, _n1_pass())
    assert gate["status"] == "BLOCKED_LEAKAGE"


def test_n1_failure_blocks_with_metric_control():
    gate = preflight_gate(_records(6), _n1_fail())
    assert "BLOCKED_METRIC_CONTROL" in gate["blocked"]
    assert gate["status"] != "OK"


def test_clean_records_pass_the_gate():
    gate = preflight_gate(_records(6), _n1_pass())
    assert gate["status"] == "OK"
    assert gate["blocked"] == []
    assert gate["leakage"] == {"L1": 0, "L2": 0, "L3": 0}


# --- 3. 3M 비중첩 결과가 최종 결과에 연결됐는가 ------------------------------


def test_three_month_non_overlapping_is_present_in_final_payload():
    payload = _aggregate(_records(24))
    block = payload["e2"]["three_month_non_overlapping"]
    assert block["quarter_end_dates"] > 0
    assert block["dates_used"] > 0
    assert block["ic"]["n"] == block["dates_used"]
    for key in (
        "ic",
        "quantile_spread_q5_minus_q1",
        "top_decile_gross",
        "top_decile_net_by_cost_bp",
        "turnover",
        "win_rate_by_date",
        "exclusion_reasons",
    ):
        assert key in block


def test_three_month_non_overlapping_uses_only_quarter_end_dates():
    recs = _records(24)
    quarter = [r for r in recs if r["is_quarter_end"]]
    payload = _aggregate(recs)
    assert payload["e2"]["three_month_non_overlapping"]["quarter_end_dates"] == len(
        quarter
    )
    assert len(quarter) < len(recs)


def test_three_month_non_overlapping_records_exclusion_reasons():
    recs = _records(24)
    for r in recs:
        if r["is_quarter_end"]:
            r["ic_3m"] = None
            r["exclusion_3m"] = "3M 청산일 부재 (달력 끝)"
    block = _aggregate(recs)["e2"]["three_month_non_overlapping"]
    assert block["dates_used"] == 0
    assert block["exclusion_reasons"]["3M 청산일 부재 (달력 끝)"] > 0


def test_three_month_non_overlapping_is_separate_from_overlapping():
    payload = _aggregate(_records(24))
    assert "ic_3m_overlapping" in payload["e2"]
    assert (
        payload["e2"]["three_month_non_overlapping"]["ic"]["n"]
        < payload["e2"]["ic_3m_overlapping"]["n"]
    )


# --- 4. score top-10 바스켓이 최종 결과에 연결됐는가 ------------------------


def test_score_top10_basket_is_present_in_final_payload():
    payload = _aggregate(_records(24))
    block = payload["e2"]["score_top10_basket"]
    assert block["dates_used"] == 24
    for key in (
        "gross",
        "pooled_median",
        "net_by_cost_bp",
        "turnover",
        "win_rate_by_date",
        "missing_reasons",
    ):
        assert key in block
    assert set(block["net_by_cost_bp"]) == {"0", "10", "25", "50"}


def test_score_top10_basket_is_distinct_from_screen_slate():
    payload = _aggregate(_records(24))
    assert "score_top10_basket" in payload["e2"]
    assert "screen_slate_u2" in payload["e2"]
    assert (
        payload["e2"]["score_top10_basket"]["definition"]
        != payload["e2"]["screen_slate_u2"]["definition"]
    )


def test_score_top10_basket_records_missing_reason():
    recs = _records(24)
    recs[0]["score_top10_missing_reason"] = "필터 universe 표본 부족"
    block = _aggregate(recs)["e2"]["score_top10_basket"]
    assert block["missing_reasons"]["필터 universe 표본 부족"] == 1


def test_score_top10_basket_does_not_alter_r3_criterion():
    """R-3 은 상위 10% net 로 판정한다 — score top-10 이 끼어들면 안 된다."""
    payload = _aggregate(_records(24))
    a2 = payload["verdict"]["numeric_criteria"]["A2_top_decile_net"]
    top_decile_net = payload["e2"]["top_decile_net_by_cost_bp"]["25"]["mean"]
    assert a2["mean_net"] == pytest.approx(top_decile_net)
    assert a2["mean_net"] != pytest.approx(
        payload["e2"]["score_top10_basket"]["net_by_cost_bp"]["25"]["mean"]
    )


# --- 5. coverage 분모의 20거래일 조건 ---------------------------------------


def _hist(dates):
    return [(d, 100.0 + i) for i, d in enumerate(dates)]


def test_pit_eligibility_excludes_single_close_ticker():
    days = [f"2020-01-{d:02d}" for d in range(1, 29)]
    index = {d: i for i, d in enumerate(days)}
    assert is_pit_eligible(_hist(days[:1]), days[-1], index) is False


def test_pit_eligibility_excludes_ticker_below_min_observations():
    days = [f"2020-01-{d:02d}" for d in range(1, 29)]
    index = {d: i for i, d in enumerate(days)}
    short = _hist(days[: MIN_OBSERVATIONS - 1])
    assert is_pit_eligible(short, days[-1], index) is False


def test_pit_eligibility_excludes_recent_listing_within_20_trading_days():
    """관측치는 충분해도 상장 후 20거래일이 안 지났으면 제외."""
    days = [f"2020-{m:02d}-{d:02d}" for m in (1, 2, 3) for d in range(1, 29)]
    index = {d: i for i, d in enumerate(days)}
    listed_at = 30
    hist = _hist(days[listed_at:])
    # 상장 후 정확히 20거래일 경과 + 관측치 21개 → 편입
    ok_signal = days[listed_at + 20]
    assert is_pit_eligible(hist, ok_signal, index) is True
    # 상장 후 19거래일 → 아직 편입 불가
    early_signal = days[listed_at + 19]
    assert is_pit_eligible(hist, early_signal, index) is False


def test_pit_eligibility_20_trading_day_branch_is_reachable_and_binding():
    """관측치 조건을 넘겨도 **benchmark 거래일 20일** 조건이 따로 막는가.

    ticker 가 benchmark 보다 조밀한 날짜를 가지면(휴장일 혼입 등) 관측치는 21개를
    넘으면서도 benchmark 거래일 경과는 20일 미만일 수 있다. 이 분기를 직접 친다.
    """
    # benchmark 는 주 1회, ticker 는 매일 — ticker 관측치가 훨씬 많다.
    weekly = [f"2020-02-{d:02d}" for d in (3, 10, 17, 24)] + [
        f"2020-03-{d:02d}" for d in (2, 9)
    ]
    index = {d: i for i, d in enumerate(weekly)}
    daily = [f"2020-02-{d:02d}" for d in range(3, 29)]  # 26 관측
    hist = _hist(daily)
    signal = "2020-03-09"

    assert len(hist) > MIN_OBSERVATIONS, "관측치 조건은 통과해야 분기가 의미 있다"
    # 첫 종가(2020-02-03)부터 benchmark 기준 5거래일밖에 안 지났다 → 제외.
    assert is_pit_eligible(hist, signal, index) is False


def test_pit_eligibility_accepts_seasoned_ticker():
    days = [f"2020-{m:02d}-{d:02d}" for m in (1, 2, 3) for d in range(1, 29)]
    index = {d: i for i, d in enumerate(days)}
    assert is_pit_eligible(_hist(days), days[-1], index) is True


def test_t13_coverage_denominator_needs_both_tag_and_trading_day_condition():
    """T-13 보강 — 태그 조건과 20거래일 조건 양쪽 fixture 를 검증한다."""
    days = [f"2020-{m:02d}-{d:02d}" for m in (1, 2, 3) for d in range(1, 29)]
    index = {d: i for i, d in enumerate(days)}
    seasoned = _hist(days)
    fresh = _hist(days[-5:])

    # 태그 통과 + 기간 통과 → 분모 포함
    assert is_filter_universe([]) and is_pit_eligible(seasoned, days[-1], index)
    # 태그 통과 + 기간 미달 → 분모 제외
    assert is_filter_universe([]) and not is_pit_eligible(fresh, days[-1], index)
    # 태그 실패 + 기간 통과 → 분모 제외
    assert not is_filter_universe(["leveraged"])


# --- 6. L-4 전체 결과 객체 결정성 -------------------------------------------


def test_l4_full_payload_is_deterministic_across_two_builds():
    first = _aggregate(_records(24))
    second = _aggregate(_records(24))
    assert canonical_sha256(first) == canonical_sha256(second)


def test_l4_canonical_hash_excludes_only_approved_metadata():
    assert NON_DETERMINISTIC_FIELDS == ("generated_at", "e1.elapsed_seconds")


def test_l4_canonical_hash_detects_any_substantive_change():
    """일부 지표만 같다고 통과시키지 않는다 — 어떤 실질 변화든 해시가 달라진다."""
    base = _aggregate(_records(24))
    changed = _aggregate(_records(24))
    changed["per_date"][0]["n_filter"] = 999
    assert canonical_sha256(base) != canonical_sha256(changed)


def test_l4_canonical_hash_ignores_generated_at():
    base = _aggregate(_records(24))
    other = _aggregate(_records(24))
    other["generated_at"] = "1999-01-01T00:00:00+00:00"
    assert canonical_sha256(base) == canonical_sha256(other)


# --- 7. A-6 tri-state --------------------------------------------------------


def test_a6_is_not_evaluable_when_e1_unavailable():
    payload = _aggregate(_records(24), e1={"status": "E1_UNAVAILABLE"})
    a6 = payload["verdict"]["numeric_criteria"]["A6_e1_contradiction"]
    assert a6["status"] == "NOT_EVALUABLE"
    assert a6["passed"] is None
    assert a6["reason"] == "E1_UNAVAILABLE"


def test_a6_not_evaluable_is_never_converted_to_true():
    payload = _aggregate(_records(24), e1={"status": "E1_UNAVAILABLE"})
    a6 = payload["verdict"]["numeric_criteria"]["A6_e1_contradiction"]
    assert a6["passed"] is not True


def test_all_numeric_passed_is_not_true_when_a6_not_evaluable():
    recs = _records(24, ic=0.5, coverage=1.0)
    payload = _aggregate(recs, e1={"status": "E1_UNAVAILABLE"})
    assert payload["verdict"]["all_numeric_passed"] is not True


def test_a6_records_contradiction_when_e1_reconstructed_and_negative():
    recs = _records(6)
    for r in recs:
        r["e1_ic"] = -0.2
        r["e1_screen_diff"] = -0.01
    payload = _aggregate(recs, e1={"status": "E1_RECONSTRUCTED"})
    a6 = payload["verdict"]["numeric_criteria"]["A6_e1_contradiction"]
    assert a6["status"] == "CONTRADICTED"
    assert a6["passed"] is False


def test_a6_not_contradicted_when_only_one_axis_negative():
    recs = _records(6)
    for r in recs:
        r["e1_ic"] = -0.2
        r["e1_screen_diff"] = 0.01
    payload = _aggregate(recs, e1={"status": "E1_RECONSTRUCTED"})
    a6 = payload["verdict"]["numeric_criteria"]["A6_e1_contradiction"]
    assert a6["status"] == "NOT_CONTRADICTED"
    assert a6["passed"] is True


# --- warmup 진단이 결과에 남는가 --------------------------------------------


def test_warmup_records_are_reported_separately():
    warmup = [{"signal_date": "2014-04-30", "train_row_count": 0, "scored_count": 0}]
    payload = aggregate(
        _records(24), _e1_unavailable(), _days(), {}, {}, warmup_records=warmup
    )
    block = payload["pre_evaluation_warmup"]
    assert block["dates"][0]["signal_date"] == "2014-04-30"
    assert block["dates"][0]["train_row_count"] == 0
    assert "coverage" in block["excluded_from"]
    assert "ic" in block["excluded_from"]


def test_l4_stored_hash_is_reproducible_from_stored_payload():
    """기록된 해시를 **저장된 결과 파일에서 그대로 재계산**할 수 있어야 한다.

    해시는 자기 자신을 담는 필드를 포함할 수 없다. 기록 시점에는 그 필드가 None
    이므로, 계산 시 None 으로 정규화하면 저장본에서도 같은 값이 나온다.
    검증자가 재현하지 못하는 해시는 무의미하다.
    """
    payload = _aggregate(_records(12))
    payload["determinism"] = {
        "excluded_fields": list(NON_DETERMINISTIC_FIELDS),
        "canonical_sha256": None,
    }
    written = canonical_sha256(payload)  # 기록 시점 계산
    payload["determinism"]["canonical_sha256"] = written  # 파일에 저장된 상태
    assert canonical_sha256(payload) == written


def test_l4_hash_still_detects_change_when_determinism_block_present():
    base = _aggregate(_records(12))
    base["determinism"] = {"excluded_fields": [], "canonical_sha256": None}
    h = canonical_sha256(base)
    base["determinism"]["canonical_sha256"] = h
    changed = _aggregate(_records(12))
    changed["determinism"] = {"excluded_fields": [], "canonical_sha256": h}
    changed["e2"]["ic_filter_universe"]["mean"] = 999.0
    assert canonical_sha256(changed) != h
