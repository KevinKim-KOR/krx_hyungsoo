"""target_tickers 입력 검증 (라운드 5 검증자 지적).

`tests/test_low_frequency_push_operation.py` (1548줄) 가 KS-10 테스트 임계를
넘어 책임별로 분해한 것이다. **test 본문·docstring·assertion 을 고치지 않았다.**
helper 는 `tests/low_frequency_push/_fixtures.py` 에 있다.
"""

from __future__ import annotations

import pytest

from tests.low_frequency_push._fixtures import (
    _MISSING,
    _artifact_with_candidates,
    _cand,
    _mock_universe_artifact,
)


def test_target_tickers_raises_when_candidates_not_list(monkeypatch):
    """공용 validator: candidates 가 list 아니면 unavailable → raise."""
    from app.three_push_runtime.target_tickers import collect_target_tickers

    _mock_universe_artifact(
        monkeypatch, _artifact_with_candidates("not-a-list")  # type: ignore[arg-type]
    )
    with pytest.raises(RuntimeError, match="universe artifact invalid"):
        collect_target_tickers("spike_or_falling_alert")


def test_target_tickers_raises_when_score_result_not_dict(monkeypatch):
    from app.three_push_runtime.target_tickers import collect_target_tickers

    _mock_universe_artifact(
        monkeypatch,
        _artifact_with_candidates([{"ticker": "000660", "score_result": "not-dict"}]),
    )
    with pytest.raises(RuntimeError, match="universe artifact invalid"):
        collect_target_tickers("spike_or_falling_alert")


def test_target_tickers_raises_when_is_scored_missing(monkeypatch):
    """is_scored 필드 자체 누락은 공용 validator 가 unavailable."""
    from app.three_push_runtime.target_tickers import collect_target_tickers

    _mock_universe_artifact(
        monkeypatch,
        _artifact_with_candidates([_cand(is_scored=_MISSING)]),
    )
    with pytest.raises(RuntimeError, match="universe artifact invalid"):
        collect_target_tickers("spike_or_falling_alert")


def test_target_tickers_raises_when_is_scored_is_string(monkeypatch):
    """is_scored=\"yes\" 는 semantic-invalid (truthiness 판정 금지)."""
    from app.three_push_runtime.target_tickers import collect_target_tickers

    _mock_universe_artifact(
        monkeypatch,
        _artifact_with_candidates([_cand(is_scored="yes")]),
    )
    with pytest.raises(RuntimeError, match="universe artifact invalid"):
        collect_target_tickers("spike_or_falling_alert")


def test_target_tickers_raises_when_is_scored_is_int(monkeypatch):
    from app.three_push_runtime.target_tickers import collect_target_tickers

    _mock_universe_artifact(
        monkeypatch,
        _artifact_with_candidates([_cand(is_scored=1)]),
    )
    with pytest.raises(RuntimeError, match="universe artifact invalid"):
        collect_target_tickers("spike_or_falling_alert")


def test_target_tickers_raises_when_ticker_missing_but_scored(monkeypatch):
    from app.three_push_runtime.target_tickers import collect_target_tickers

    _mock_universe_artifact(
        monkeypatch,
        _artifact_with_candidates([_cand(ticker=_MISSING)]),
    )
    with pytest.raises(RuntimeError, match="universe artifact invalid"):
        collect_target_tickers("spike_or_falling_alert")


def test_target_tickers_raises_when_ticker_blank(monkeypatch):
    """라운드 6: 공백 ticker 도 공용 validator 가 unavailable."""
    from app.three_push_runtime.target_tickers import collect_target_tickers

    _mock_universe_artifact(
        monkeypatch,
        _artifact_with_candidates([_cand(ticker="   ")]),
    )
    with pytest.raises(RuntimeError, match="universe artifact invalid"):
        collect_target_tickers("spike_or_falling_alert")


def test_target_tickers_raises_when_scored_score_value_missing(monkeypatch):
    """라운드 6: scored 후보의 score_value 누락도 공용 validator 가 unavailable."""
    from app.three_push_runtime.target_tickers import collect_target_tickers

    _mock_universe_artifact(
        monkeypatch,
        _artifact_with_candidates([_cand(score_value=_MISSING)]),
    )
    with pytest.raises(RuntimeError, match="universe artifact invalid"):
        collect_target_tickers("spike_or_falling_alert")


def test_target_tickers_raises_when_scored_score_value_nan(monkeypatch):
    """라운드 6: scored 후보의 score_value=NaN 도 unavailable."""
    from app.three_push_runtime.target_tickers import collect_target_tickers

    _mock_universe_artifact(
        monkeypatch,
        _artifact_with_candidates([_cand(score_value=float("nan"))]),
    )
    with pytest.raises(RuntimeError, match="universe artifact invalid"):
        collect_target_tickers("spike_or_falling_alert")


def test_target_tickers_accepts_valid_scored_false(monkeypatch):
    """is_scored=False (정상 미채점) 는 skip. 단 validator 상 scored=0 은 partial
    status 여도 artifact_status_scored_inconsistency 로 차단되므로, scored 후보 1건
    과 미채점 후보 1건을 함께 두어 partial 정합을 만든다.
    """
    from app.three_push_runtime.target_tickers import collect_target_tickers

    _mock_universe_artifact(
        monkeypatch,
        _artifact_with_candidates(
            [
                _cand(ticker="000660", is_scored=True, score_value=-5.0),
                _cand(ticker="069500", is_scored=False, score_value=_MISSING),
            ],
            refresh_status="partial",
        ),
    )
    # 미채점 후보는 skip, scored 후보만 반환.
    assert collect_target_tickers("spike_or_falling_alert") == ["000660"]


def test_target_tickers_accepts_valid_scored_true(monkeypatch):
    from app.three_push_runtime.target_tickers import collect_target_tickers

    _mock_universe_artifact(
        monkeypatch,
        _artifact_with_candidates(
            [_cand(ticker="000660", is_scored=True, score_value=-5.0)]
        ),
    )
    assert collect_target_tickers("spike_or_falling_alert") == ["000660"]
