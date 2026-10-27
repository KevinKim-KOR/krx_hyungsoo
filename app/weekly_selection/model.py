"""POC6-11 CPU LightGBM 학습 · 저장 · 복원 · 예측 · 해석된 전체 매개변수 · 환경 — 설계 §5.

```text
API      lightgbm.train · objective=regression_l2 · 300회 · 학습률 0.05 · early stopping 없음
규제     min_data_in_leaf=200 · lambda_l1=0 · lambda_l2=10 · max_bin=63
         bagging 1/0 · feature_fraction 1
결측     use_missing=true · zero_as_missing=false(입력의 None → NaN 만 결측 · 0 은 값)
실행     cpu · 4스레드 · deterministic · force_col_wise · seed 20261026
구조     ML_A = num_leaves 7 · max_depth 3 / ML_B = num_leaves 15 · max_depth 4
저장     model_to_string 원문(복원 = Booster(model_str)) · 같은 환경에서 저장 전후 예측 대조(허용 1e-12)
```

lightgbm 은 함수 안에서만 import 한다(설치 전에도 자료 · 장부 모듈과 시험이 돈다 · 판정 §2).
LightGBM 은 MIT License 다(https://github.com/lightgbm-org/LightGBM/blob/main/LICENSE).
"""

from __future__ import annotations

import ctypes
import importlib.metadata
import sys
from typing import Any, Optional, Sequence

import numpy as np

from app.weekly_selection.features import COLUMNS

LGB_VERSION = "4.7.0"
SEED = 20261026
NUM_ROUNDS = 300
THREADS = 4
RESTORE_TOL = 1e-12
COMMON = {
    "objective": "regression_l2",
    "learning_rate": 0.05,
    "min_data_in_leaf": 200,
    "lambda_l1": 0.0,
    "lambda_l2": 10.0,
    "max_bin": 63,
    "bagging_fraction": 1.0,
    "bagging_freq": 0,
    "feature_fraction": 1.0,
    "use_missing": True,
    "zero_as_missing": False,
    "device_type": "cpu",
    "num_threads": THREADS,
    "deterministic": True,
    "force_col_wise": True,
    "seed": SEED,
    "verbosity": -1,
}
STRUCTS = {
    "ML_A": {"num_leaves": 7, "max_depth": 3},
    "ML_B": {"num_leaves": 15, "max_depth": 4},
}
ENV_LIBS = ("lightgbm", "numpy", "scipy", "narwhals")


def lgb():
    import lightgbm

    return lightgbm


def params(struct: str) -> dict[str, Any]:
    return {**COMMON, **STRUCTS[struct]}


def matrix(X: Sequence[Sequence[Optional[float]]]) -> np.ndarray:
    """None → NaN(결측) · 나머지는 그대로 float64. 비유한 값이 이미 있으면 거절."""
    arr = np.array(
        [[np.nan if v is None else v for v in row] for row in X], dtype=np.float64
    )
    if arr.ndim != 2 or arr.shape[1] != len(COLUMNS):
        raise ValueError(f"입력 모양 {arr.shape} ≠ (n, {len(COLUMNS)})")
    if np.isinf(arr).any():
        raise ValueError("입력에 무한대")
    return arr


def train(struct: str, X: np.ndarray, y: Sequence[float], w: Sequence[float]):
    L = lgb()
    ds = L.Dataset(
        X,
        label=np.asarray(y, dtype=np.float64),
        weight=np.asarray(w, dtype=np.float64),
        feature_name=list(COLUMNS),
        free_raw_data=False,
    )
    return L.train(params(struct), ds, num_boost_round=NUM_ROUNDS)


def to_text(booster) -> str:
    return booster.model_to_string(num_iteration=-1)


def restore(text: str):
    return lgb().Booster(model_str=text)


def predict(booster, X: np.ndarray) -> np.ndarray:
    out = np.asarray(booster.predict(X, num_threads=THREADS), dtype=np.float64)
    if out.shape != (X.shape[0],) or not np.isfinite(out).all():
        raise ValueError("예측 모양 · 비유한 값 이상")
    return out


def resolved_params(text: str) -> dict[str, str]:
    """모델 원문의 `parameters:` 블록(실제 해석된 전체 매개변수 · 난수 관련 seed 파생값 포함)."""
    lines = text.splitlines()
    try:
        a = lines.index("parameters:")
        b = lines.index("end of parameters")
    except ValueError as e:
        raise ValueError("모델 원문에 parameters 블록이 없음") from e
    out = {}
    for ln in lines[a + 1 : b]:  # noqa: E203
        if ln.startswith("[") and ln.endswith("]") and ": " in ln:
            k, v = ln[1:-1].split(": ", 1)
            out[k] = v
    return out


def libomp_in_load_order() -> list[str]:
    """현재 프로세스에 실제로 올라온 libomp 경로 — dyld 목록 순서(= 올라온 순서)."""
    if sys.platform != "darwin":
        return []
    libc = ctypes.CDLL(None)
    libc._dyld_image_count.restype = ctypes.c_uint32
    libc._dyld_get_image_name.restype = ctypes.c_char_p
    libc._dyld_get_image_name.argtypes = [ctypes.c_uint32]
    names = [
        libc._dyld_get_image_name(i).decode() for i in range(libc._dyld_image_count())
    ]
    return [n for n in names if "libomp" in n]


def loaded_libomp() -> list[str]:
    return sorted(libomp_in_load_order())


def openmp_problem(order: Optional[list[str]] = None) -> Optional[str]:
    """LightGBM 이 쓸 Homebrew libomp 가 torch 의 libomp 보다 먼저 올라왔는지(아니면 학습 중 세그폴트 위험)."""
    libs = libomp_in_load_order() if order is None else order
    hb = [k for k, x in enumerate(libs) if x.startswith("/opt/homebrew/")]
    if not hb:
        return "Homebrew libomp 가 로드되지 않음"
    torch = [k for k, x in enumerate(libs) if "/torch/" in x]
    if torch and torch[0] < hb[0]:
        return "torch 의 libomp 가 Homebrew libomp 보다 먼저 로드됨(LightGBM 세그폴트 위험)"
    return None


def env() -> dict[str, Any]:
    out: dict[str, Any] = {"python": sys.version.split()[0], "platform": sys.platform}
    for lib in ENV_LIBS:
        try:
            out[lib] = importlib.metadata.version(lib)
        except importlib.metadata.PackageNotFoundError:
            out[lib] = None
    return out
