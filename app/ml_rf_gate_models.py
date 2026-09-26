"""POC4-03 — RF 동결 설정 · 입력 규칙 · 순서 고정 예측 · 검증 IC 설정 선택 · 모멘텀 점수 (PLAN §1-5 · §1-6).

설계자 PLAN 판정(2026-09-25) 확정분:

- 설정 3개(A 얕음 · B 중간 · C 깊음)는 동결 — 설정 sha 가 PLAN 값과 다르면 실행하지 않는다.
- 입력 규칙 — S′ 행 (asof_date, ticker) 오름차순 · 열 `FEATURE_COLUMNS` · X float32 · 전부 유한.
- 예측 — 트리를 `estimators_` 순서로 더해 평균(스레드 완료 순서에 따른 합산 차이 제거).
- 선택 — V 모든 거래일 Spearman(예측, 학습 target) 평균 · finite 원값 비교(반올림 없음) · 정확 동률 A→B→C ·
  None 설정 제외 · 전부 None 이면 A 를 고르지 않고 오류(`INVALID_STOP`). 평가 label 은 받지 않는다.
- 모멘텀 — t 행 `return_20d` 그대로(클수록 높은 점수 · 학습 없음).

DB·파일에 접근하지 않는다.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from typing import Optional, Sequence

import numpy as np
from sklearn.ensemble import RandomForestRegressor

from app.ml_relative_upside_features import FEATURE_COLUMNS, CandidateFeatureRow
from app.ml_score_validity_metrics import spearman

CONFIG_ORDER = ("RF_A", "RF_B", "RF_C")
RF_COMMON = {
    "n_estimators": 200,
    "criterion": "squared_error",
    "bootstrap": True,
    "max_samples": 0.25,
    "random_state": 42,
}
RF_CONFIGS = {
    "RF_A": {"max_depth": 4, "min_samples_leaf": 0.005, "max_features": 1.0},
    "RF_B": {"max_depth": 8, "min_samples_leaf": 0.001, "max_features": 0.5},
    "RF_C": {"max_depth": 16, "min_samples_leaf": 0.0002, "max_features": 0.5},
}
# PLAN §1-5 — 위 설정의 canonical JSON sha256 (n_jobs 제외). 코드와 PLAN 이 어긋나면 실행 거부.
FROZEN_CONFIG_SHA256 = (
    "edca7023bb80aebbadceb5812b73aeaf3a3fbf86bbb0209c508830a378dbbe35"
)
N_JOBS = 8  # 결과에 영향 없음 — 트리별 seed 는 병렬 실행 전에 순서대로 정해진다

REASON_MAX = "MAX"
REASON_EXACT_TIE = "EXACT_TIE"
REASON_PARTIAL_NONE = "PARTIAL_NONE"


class RfContractError(RuntimeError):
    """RF 계약 위반 — 설정 sha · 비유한 입력 · 학습 행 부족 · 검증 근거 없음 (INVALID_STOP)."""


def config_json() -> str:
    """설정 sha 의 대상 문자열 (PLAN §1-5 원문과 같은 직렬화)."""
    obj = {name: {**RF_COMMON, **RF_CONFIGS[name]} for name in CONFIG_ORDER}
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def config_sha256() -> str:
    return hashlib.sha256(config_json().encode("utf-8")).hexdigest()


def assert_frozen_config() -> None:
    got = config_sha256()
    if got != FROZEN_CONFIG_SHA256:
        raise RfContractError(f"RF 설정이 동결값과 다르다: {got}")


def recipe_block() -> dict:
    """설정 밖에서 결과에 영향을 주는 규칙 — 결과·manifest·재개 지문(recipe sha)에 같은 값이 들어간다."""
    return {
        "row_order": "S′ (asof_date, ticker) 오름차순",
        "feature_columns": list(FEATURE_COLUMNS),
        "dtype": "X float32 (float64 → float32 한 번 변환) · y float64 · 전부 유한",
        "predict": "estimators_ 순서로 predict(X32, check_input=False) 합 / 트리 수",
        "train_rows": "S′ = S − {label 끝 날짜 ≥ V 시작} (RF 만 · 선형은 S 그대로)",
        "selection": "V 모든 거래일 Spearman(예측, future_excess_return_20d) 평균 · 모집단 = 그 날짜 "
        "이름 있음 ∧ 이름 필터 통과 ∧ 7 feature 완전 ∧ target 있음 · finite 원값 최대 · 정확 동률 A→B→C · "
        "None 제외 · 전부 None → INVALID_STOP",
        "momentum": "t 행 return_20d · 클수록 높은 점수 · 학습 없음",
        "n_jobs": N_JOBS,
    }


# --- 입력 ------------------------------------------------------------------------


def row_order_key(row: CandidateFeatureRow) -> tuple[str, str]:
    """S′ 행 순서 — (asof_date, ticker) 오름차순 (선형 trainer 와 같다)."""
    return (row.asof_date, row.ticker)


def feature_matrix(rows: Sequence[CandidateFeatureRow]) -> np.ndarray:
    """(n, 7) float32 · 열 = `FEATURE_COLUMNS` · 비유한 값이 하나라도 있으면 오류."""
    x64 = np.array(
        [[getattr(r, c) for c in FEATURE_COLUMNS] for r in rows], dtype=np.float64
    ).reshape(len(rows), len(FEATURE_COLUMNS))
    # float32 범위를 넘는 값은 inf 가 되고, 아래 유한성 검사가 잡는다.
    with np.errstate(over="ignore"):
        x32 = np.ascontiguousarray(x64, dtype=np.float32)
    if not (np.isfinite(x64).all() and np.isfinite(x32).all()):
        raise RfContractError("RF 입력 feature 에 비유한 값이 있다")
    return x32


def target_vector(rows: Sequence[CandidateFeatureRow]) -> np.ndarray:
    y = np.array([r.future_excess_return_20d for r in rows], dtype=np.float64)
    if not np.isfinite(y).all():
        raise RfContractError("RF 학습 target 에 비유한 값이 있다")
    return y


def input_fingerprint(x32: np.ndarray, y: np.ndarray) -> str:
    h = hashlib.sha256()
    h.update(np.ascontiguousarray(x32).tobytes())
    h.update(np.ascontiguousarray(y).tobytes())
    return h.hexdigest()


# --- fit · 예측 ------------------------------------------------------------------


def fit_forest(name: str, x32: np.ndarray, y: np.ndarray) -> RandomForestRegressor:
    if len(y) < 2:
        raise RfContractError(f"{name} 학습 행이 2개 미만이다")
    model = RandomForestRegressor(**RF_COMMON, **RF_CONFIGS[name], n_jobs=N_JOBS)
    model.fit(x32, y)
    return model


def ordered_predict(model: RandomForestRegressor, x32: np.ndarray) -> np.ndarray:
    """트리 순서대로 더한다 — n_jobs 와 무관하게 bit 단위로 같다."""
    acc = np.zeros(x32.shape[0], dtype=np.float64)
    if x32.shape[0] == 0:
        return acc
    for est in model.estimators_:
        acc += est.predict(x32, check_input=False)
    return acc / len(model.estimators_)


def forest_fingerprint(model: RandomForestRegressor) -> str:
    """트리마다 분기 feature · threshold · 자식 · value 바이트의 sha256 — 재실행 때 숲이 같은지 증명."""
    h = hashlib.sha256()
    for est in model.estimators_:
        tree = est.tree_
        for arr in (
            tree.feature,
            tree.threshold,
            tree.children_left,
            tree.children_right,
            tree.value,
        ):
            h.update(np.ascontiguousarray(arr).tobytes())
    return h.hexdigest()


# --- 설정 선택 ---------------------------------------------------------------------


def validation_ic(
    predictions: Sequence[float], targets: Sequence[float], dates: Sequence[str]
) -> Optional[float]:
    """V 거래일마다 Spearman(예측, 학습 target) → 평균. 정의 불가한 날은 빼고, 남은 날이 없으면 None."""
    if not (len(predictions) == len(targets) == len(dates)):
        raise ValueError("predictions / targets / dates 길이가 다르다")
    by_date: dict[str, tuple[list[float], list[float]]] = {}
    for p, y, d in zip(predictions, targets, dates):
        xs, ys = by_date.setdefault(d, ([], []))
        xs.append(float(p))
        ys.append(float(y))
    ics = []
    for d in sorted(by_date):
        value = spearman(*by_date[d])
        if value is not None and math.isfinite(value):
            ics.append(value)
    if not ics:
        return None
    out = sum(ics) / len(ics)
    return out if math.isfinite(out) else None


@dataclass(frozen=True)
class Selection:
    chosen: str
    reason: str
    val_ic: dict = field(default_factory=dict)
    candidates: tuple = ()


def select_config(val_ic: dict[str, Optional[float]]) -> Selection:
    """finite 원값 최대 · 정확 동률 A→B→C · None 제외 · 전부 None 이면 오류(A 를 고르지 않는다)."""
    finite = {
        n: v
        for n in CONFIG_ORDER
        if (v := val_ic.get(n)) is not None and math.isfinite(v)
    }
    if not finite:
        raise RfContractError("세 설정 모두 검증 IC 가 없다 — 설정을 고르지 않는다")
    best = max(finite.values())
    winners = [n for n in CONFIG_ORDER if n in finite and finite[n] == best]
    if len(winners) > 1:
        reason = REASON_EXACT_TIE
    elif len(finite) < len(CONFIG_ORDER):
        reason = REASON_PARTIAL_NONE
    else:
        reason = REASON_MAX
    return Selection(winners[0], reason, dict(val_ic), tuple(finite))


# --- 모멘텀 ------------------------------------------------------------------------


def momentum_raw_scores(rows: Sequence[CandidateFeatureRow]) -> dict[str, float]:
    """t 행 `return_20d` 그대로 — 값이 없는 행은 점수가 없다."""
    return {r.ticker: float(r.return_20d) for r in rows if r.return_20d is not None}
