"""POC4-01 작업 6 — 모델·설정 선택용 train/validation 분할 (설계자 판정 2026-09-24 §3-1).

```text
TRAIN_VALIDATION_PURGE = 20 trading days
E2_EVALUATION_CHANGE   = 0      (E2 평가 label 은 기준일 뒤라 누수가 없다)
FROZEN_BASELINE_CHANGE = 0      (app/ml_relative_upside_model.py 는 건드리지 않는다)
```

계약은 **행 개수가 아니라 날짜**로 검사한다.

- purge — 학습 표본의 label 종료일(asof 뒤 20번째 거래일)이 validation 시작일보다 **앞서야** 한다.
- embargo — validation **뒤** 데이터를 학습에 쓰는 fold 면, validation 종료 뒤 20거래일은 학습에서 뺀다.
- RF 설정(최대 3개)은 모두 **같은 분할**을 써야 한다 → `split_fingerprint` 로 확인한다.

이 모듈은 분할만 만든다. 모델 학습·설정 선택은 POC4-03 에서 이 분할을 받아 쓴다.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Optional, Sequence

LABEL_HORIZON_DAYS = 20
EMBARGO_DAYS = 20
MAX_SELECTION_CONFIGS = 3  # RF 사전 고정 설정 최대 3개 (설계자 POC4-00 · RF_COMPARISON)


class SplitContractError(ValueError):
    """학습 표본이 validation 경계를 침범한다 (purge·embargo 위반)."""


@dataclass(frozen=True)
class SelectionFold:
    fold: int
    validation_start: str
    validation_end: str
    train_dates: tuple[str, ...]
    validation_dates: tuple[str, ...]
    purged_dates: tuple[str, ...]  # validation 앞 — label 이 validation 과 겹쳐 뺀 날
    embargoed_dates: tuple[str, ...]  # validation 뒤 — embargo 로 뺀 날


def label_end_date(
    calendar: Sequence[str], asof: str, horizon: int = LABEL_HORIZON_DAYS
) -> Optional[str]:
    """asof 뒤 `horizon` 번째 거래일. 달력 밖이면 None (label 미완성 표본)."""
    index = {d: i for i, d in enumerate(calendar)}
    i = index.get(asof)
    if i is None or i + horizon >= len(calendar):
        return None
    return calendar[i + horizon]


def make_selection_folds(
    calendar: Sequence[str],
    sample_dates: Sequence[str],
    *,
    n_folds: int,
    validation_days: int,
    horizon: int = LABEL_HORIZON_DAYS,
    embargo: int = EMBARGO_DAYS,
    train_after_validation: bool = False,
) -> tuple[SelectionFold, ...]:
    """표본 기간 끝의 연속 `n_folds` 개 validation 구간으로 fold 를 만든다.

    `train_after_validation=False` — walk-forward: 학습은 validation 앞만(purge 적용).
    `True` — blocked: validation 뒤 표본도 학습에 쓰되 embargo 만큼 뺀다.
    label 이 달력 안에서 끝나지 않는 표본은 학습·validation 모두에서 뺀다.
    """
    cal = list(calendar)
    index = {d: i for i, d in enumerate(cal)}
    samples = sorted({d for d in sample_dates if d in index})
    complete = [d for d in samples if index[d] + horizon < len(cal)]
    if n_folds < 1 or validation_days < 1 or len(complete) < n_folds * validation_days:
        raise SplitContractError("표본이 fold 를 만들기에 부족하다")
    folds = []
    for k in range(n_folds):
        end = len(complete) - (n_folds - 1 - k) * validation_days
        validation = complete[end - validation_days : end]  # noqa: E203
        v_start, v_end = validation[0], validation[-1]
        train, purged, embargoed = [], [], []
        for d in complete:
            if v_start <= d <= v_end:
                continue
            if d < v_start:
                end_date = cal[index[d] + horizon]
                (train if end_date < v_start else purged).append(d)
            elif train_after_validation:
                gap = index[d] - index[v_end]
                (train if gap > embargo else embargoed).append(d)
        fold = SelectionFold(
            fold=k,
            validation_start=v_start,
            validation_end=v_end,
            train_dates=tuple(train),
            validation_dates=tuple(validation),
            purged_dates=tuple(purged),
            embargoed_dates=tuple(embargoed),
        )
        assert_fold_contract(fold, cal, horizon=horizon, embargo=embargo)
        folds.append(fold)
    return tuple(folds)


def assert_fold_contract(
    fold: SelectionFold,
    calendar: Sequence[str],
    *,
    horizon: int = LABEL_HORIZON_DAYS,
    embargo: int = EMBARGO_DAYS,
) -> None:
    """날짜로 검사한다. 학습 표본 **하나라도** 경계를 넘으면 `SplitContractError`."""
    index = {d: i for i, d in enumerate(calendar)}
    v0, v1 = index[fold.validation_start], index[fold.validation_end]
    for d in fold.train_dates:
        i = index[d]
        if i < v0:
            if i + horizon >= v0:
                raise SplitContractError(
                    f"purge 위반: {d} 의 label 종료일 {calendar[i + horizon]} ≥ "
                    f"validation 시작 {fold.validation_start}"
                )
        elif i <= v1:
            raise SplitContractError(f"학습 표본 {d} 가 validation 구간 안에 있다")
        elif i - v1 <= embargo:
            raise SplitContractError(
                f"embargo 위반: {d} 는 validation 종료 {fold.validation_end} 뒤 "
                f"{i - v1}거래일 (≤ {embargo})"
            )


def split_fingerprint(folds: Sequence[SelectionFold]) -> str:
    """분할 전체의 sha256 — 설정마다 같은 분할을 썼는지 비교한다."""
    blob = json.dumps([asdict(f) for f in folds], sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def require_same_split(fingerprints: Sequence[str]) -> str:
    """RF 설정(최대 3개)이 모두 같은 분할을 썼는지. 다르거나 3개를 넘으면 `SplitContractError`."""
    if len(fingerprints) > MAX_SELECTION_CONFIGS:
        raise SplitContractError(
            f"설정은 최대 {MAX_SELECTION_CONFIGS}개다: {len(fingerprints)}"
        )
    unique = set(fingerprints)
    if len(unique) != 1:
        raise SplitContractError(f"설정마다 분할이 다르다: {sorted(unique)}")
    return unique.pop()
