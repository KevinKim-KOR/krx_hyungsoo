"""POC4-01 작업 6 — 모델·설정 선택 분할 purge·embargo 계약 (설계자 판정 2026-09-24 §3-1).

계약은 행 개수가 아니라 **날짜**로 검사한다. 경계를 한 줄이라도 겹치게 만들면 실패해야 한다.
"""

from __future__ import annotations

import dataclasses
from datetime import date, timedelta

import pytest

from app.ml_research_split import (
    EMBARGO_DAYS,
    LABEL_HORIZON_DAYS,
    SplitContractError,
    assert_fold_contract,
    label_end_date,
    make_selection_folds,
    require_same_split,
    split_fingerprint,
)


def _calendar(n: int = 260) -> list[str]:
    out, d = [], date(2020, 1, 1)
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


CAL = _calendar()


def test_constants_are_twenty_trading_days():
    assert LABEL_HORIZON_DAYS == 20 and EMBARGO_DAYS == 20


def test_walk_forward_train_labels_end_before_validation_starts():
    folds = make_selection_folds(CAL, CAL, n_folds=3, validation_days=20)
    index = {d: i for i, d in enumerate(CAL)}
    for fold in folds:
        v0 = index[fold.validation_start]
        for d in fold.train_dates:
            assert label_end_date(CAL, d) < fold.validation_start
        # 필요한 만큼만 뺀다 — 마지막 학습일의 label 은 validation 바로 전날 끝난다
        last = index[fold.train_dates[-1]]
        assert last + LABEL_HORIZON_DAYS == v0 - 1
        assert len(fold.purged_dates) == LABEL_HORIZON_DAYS
        assert fold.embargoed_dates == ()
        assert all(d < fold.validation_start for d in fold.train_dates)


def test_blocked_fold_embargoes_twenty_days_after_validation():
    folds = make_selection_folds(
        CAL, CAL, n_folds=3, validation_days=20, train_after_validation=True
    )
    index = {d: i for i, d in enumerate(CAL)}
    first = folds[0]
    after = [d for d in first.train_dates if d > first.validation_end]
    assert after, "validation 뒤 학습 표본이 있어야 embargo 를 검사할 수 있다"
    assert index[after[0]] == index[first.validation_end] + EMBARGO_DAYS + 1
    assert len(first.embargoed_dates) == EMBARGO_DAYS


@pytest.mark.parametrize("which", ["purged", "embargoed", "validation"])
def test_one_overlapping_row_breaks_the_contract(which):
    fold = make_selection_folds(
        CAL, CAL, n_folds=3, validation_days=20, train_after_validation=True
    )[0]
    extra = {
        "purged": fold.purged_dates[-1],
        "embargoed": fold.embargoed_dates[0],
        "validation": fold.validation_dates[0],
    }[which]
    broken = dataclasses.replace(
        fold, train_dates=tuple(sorted(fold.train_dates + (extra,)))
    )
    with pytest.raises(SplitContractError):
        assert_fold_contract(broken, CAL)


def test_weaker_purge_fails_the_twenty_day_contract():
    weak = make_selection_folds(
        CAL, CAL, n_folds=2, validation_days=20, horizon=19, embargo=19
    )
    with pytest.raises(SplitContractError, match="purge"):
        assert_fold_contract(weak[0], CAL)


def test_weaker_embargo_fails_the_twenty_day_contract():
    weak = make_selection_folds(
        CAL, CAL, n_folds=2, validation_days=20, embargo=19, train_after_validation=True
    )
    with pytest.raises(SplitContractError, match="embargo"):
        assert_fold_contract(weak[0], CAL)


def test_samples_without_complete_label_are_excluded():
    folds = make_selection_folds(CAL, CAL, n_folds=1, validation_days=20)
    tail = set(CAL[-LABEL_HORIZON_DAYS:])
    used = set(folds[0].train_dates) | set(folds[0].validation_dates)
    assert not (used & tail)


def test_all_configs_share_one_split_fingerprint():
    a = split_fingerprint(make_selection_folds(CAL, CAL, n_folds=3, validation_days=20))
    b = split_fingerprint(make_selection_folds(CAL, CAL, n_folds=3, validation_days=20))
    c = split_fingerprint(make_selection_folds(CAL, CAL, n_folds=3, validation_days=21))
    assert require_same_split([a, b, b]) == a
    with pytest.raises(SplitContractError):
        require_same_split([a, c])
    with pytest.raises(SplitContractError, match="최대 3"):
        require_same_split([a, a, a, a])


def test_too_few_samples_is_refused():
    with pytest.raises(SplitContractError):
        make_selection_folds(CAL[:50], CAL[:50], n_folds=3, validation_days=20)
