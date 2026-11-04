"""POC6-20 학습 · 입력 행렬 — H1 `model` 의 설정 · 저장 · 복원 · 예측을 그대로 쓰고 열 폭만 인자로 받는다(PLAN §1 충돌 1).

```text
설정     H1 `model.params("ML_B")` · 300회 · seed · 4스레드 · deterministic(H1 model.py 수정 0)
입력     P = H1 30열 · M = 30열 + 시장 4열(30열 뒤 · 고정 순서) — 같은 함수 · 같은 행 · 같은 정답 · 가중치
행렬     None → NaN(결측) · 무한대 거절 · 폭 = 열 목록 길이
```
"""

from __future__ import annotations

from typing import Optional, Sequence

import numpy as np

from app.market_context_value import market_inputs as MI
from app.weekly_selection import features as F
from app.weekly_selection import model as M

STRUCT = "ML_B"
COLUMNS = {"P": tuple(F.COLUMNS), "M": tuple(F.COLUMNS) + MI.COLUMNS}
INPUTS = ("P", "M")


def matrix(X: Sequence[Sequence[Optional[float]]], width: int) -> np.ndarray:
    arr = np.array(
        [[np.nan if v is None else v for v in row] for row in X], dtype=np.float64
    )
    if arr.ndim != 2 or arr.shape[1] != width:
        raise ValueError(f"입력 모양 {arr.shape} ≠ (n, {width})")
    if np.isinf(arr).any():
        raise ValueError("입력에 무한대")
    return arr


def train(inp: str, X: np.ndarray, y: Sequence[float], w: Sequence[float]):
    L = M.lgb()
    ds = L.Dataset(
        X,
        label=np.asarray(y, dtype=np.float64),
        weight=np.asarray(w, dtype=np.float64),
        feature_name=list(COLUMNS[inp]),
        free_raw_data=False,
    )
    return L.train(M.params(STRUCT), ds, num_boost_round=M.NUM_ROUNDS)


def _same_param(got: Optional[str], want) -> bool:
    """모델 원문의 해석값(문자열) ↔ 고정 설정 — 별칭 · 참거짓 · 수 표기 차이만 맞춘다(H1 verify 와 같은 규칙)."""
    if got is None:
        return False
    if isinstance(want, bool):
        return got in (("1", "true") if want else ("0", "false"))
    if isinstance(want, (int, float)):
        try:
            return float(got) == float(want)
        except ValueError:
            return False
    return got == {"regression_l2": "regression"}.get(want, want)


def param_problems(text: str) -> list[str]:
    """해석된 매개변수 중 고정 ML_B 설정(300회 포함)과 다른 키(verbosity 제외)."""
    rp = M.resolved_params(text)
    want = {**M.params(STRUCT), "num_iterations": M.NUM_ROUNDS}
    return sorted(
        k for k, w in want.items() if k != "verbosity" and not _same_param(rp.get(k), w)
    )


def feature_names(text: str) -> list[str]:
    """모델 원문의 `feature_names=` 줄(학습에 쓴 열 이름 · 순서)."""
    for ln in text.splitlines():
        if ln.startswith("feature_names="):
            return ln.split("=", 1)[1].split(" ")
    raise ValueError("모델 원문에 feature_names 줄이 없음")
