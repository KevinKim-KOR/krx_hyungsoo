"""POC6-02 — 고정 MLP 후보(설계 개정 2 §5 · §5-1 · PLAN 판정 §3-1).

```text
모델    5 → 64 → 32 → 1 · Linear · ReLU · Linear · ReLU · Linear · float32
학습    Adam(lr=0.001, weight_decay=0.001) · 200 epoch · seed 42
        dropout · BatchNorm · early stopping · AMP 없음
손실    날짜 균형 가중 L1 = Σ w|f(x) − y| / Σ w (w = 1/n_d) · raw 출력 그대로(예측 범위 제한은 평가 때)
갱신    epoch 마다 한 번 — microbatch 로 나눠도 같은 분모로 gradient 를 누적한 뒤 한 번만 step
표준화  학습 표본의 날짜 균형 가중 평균 · 모집단 표준편차(상수 열 = 0) — 맥북이 학습 구간에서 확정해 넘긴다
재현    Python · torch seed · torch.use_deterministic_algorithms(True) · TF32 끔
        · CUBLAS_WORKSPACE_CONFIG
```

torch · 표준 라이브러리만 쓴다(저장소의 다른 모듈 · numpy 를 import 하지 않음) — RTX PC 실행 묶음에 이 파일이
그대로 복사되고, 맥북 시험(CPU torch)과 PC 실행(CUDA)이 같은 학습 본문을 쓴다. torch 는 함수 안에서만
불러온다(표준화 계산 · SPEC 은 torch 없이도 쓸 수 있다).
"""

from __future__ import annotations

import contextlib
import math
import os
import random
from typing import Any, Iterator, Optional, Sequence

LAYERS = (5, 64, 32, 1)
LR = 0.001
WEIGHT_DECAY = 0.001
EPOCHS = 200
SEED = 42
REPRO_TOL = 1e-6  # 같은 장비 · 같은 입력의 두 학습 예측 차이 허용값(PLAN §4 · 판정 §4)

SPEC: dict[str, Any] = {
    "layers": list(LAYERS),
    "activation": "ReLU",
    "dtype": "float32",
    "optimizer": {"name": "Adam", "lr": LR, "weight_decay": WEIGHT_DECAY},
    "epochs": EPOCHS,
    "seed": SEED,
    "loss": "date-balanced weighted L1 = sum(w*|f(x)-y|)/sum(w), w = 1/n_d, raw output",
    "update": "one optimizer step per epoch; microbatches accumulate gradients",
    "standardize": (
        "date-balanced weighted mean and population std of the training block (std 0 -> 0)"
    ),
    "not_used": ["dropout", "BatchNorm", "early stopping", "AMP", "numpy"],
    "determinism": {
        "torch.use_deterministic_algorithms": True,
        "tf32": False,
        "CUBLAS_WORKSPACE_CONFIG": ":4096:8",
    },
    "repro_tolerance": REPRO_TOL,
}


def standardize_params(
    X: Sequence[Sequence[float]], w: Sequence[float]
) -> tuple[list[float], list[float]]:
    """날짜 균형 가중 평균 · 모집단 표준편차(가중) — 순수 파이썬(torch 불필요)."""
    total = float(sum(w))
    cols = len(X[0])
    mean = [sum(wi * x[j] for x, wi in zip(X, w)) / total for j in range(cols)]
    var = [
        sum(wi * (x[j] - mean[j]) ** 2 for x, wi in zip(X, w)) / total
        for j in range(cols)
    ]
    return mean, [math.sqrt(v) for v in var]


def apply_standardize(
    X: Sequence[Sequence[float]], mean: Sequence[float], std: Sequence[float]
) -> list[list[float]]:
    return [
        [(x[j] - mean[j]) / std[j] if std[j] > 0 else 0.0 for j in range(len(mean))]
        for x in X
    ]


@contextlib.contextmanager
def deterministic(torch: Any, seed: int = SEED) -> Iterator[None]:
    """seed · 결정적 알고리즘 · TF32 끔 — 끝나면 이전 설정으로 되돌린다(같은 프로세스의 다른 torch 사용에 남지 않게).

    CUBLAS 설정은 CUDA 초기화 전에 있어야 한다 — PC 실행기는 torch 를 불러오기 전에 환경 변수를 먼저 둔다.
    """
    cudnn, matmul = torch.backends.cudnn, torch.backends.cuda.matmul
    prev = (
        torch.are_deterministic_algorithms_enabled(),
        cudnn.benchmark,
        cudnn.deterministic,
        matmul.allow_tf32,
        cudnn.allow_tf32,
    )
    env_added = "CUBLAS_WORKSPACE_CONFIG" not in os.environ
    if env_added:
        os.environ["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"
    try:
        random.seed(seed)
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
        torch.use_deterministic_algorithms(True)
        cudnn.benchmark, cudnn.deterministic = False, True
        matmul.allow_tf32, cudnn.allow_tf32 = False, False
        yield
    finally:
        torch.use_deterministic_algorithms(prev[0])
        cudnn.benchmark, cudnn.deterministic = prev[1], prev[2]
        matmul.allow_tf32, cudnn.allow_tf32 = prev[3], prev[4]
        if env_added:
            os.environ.pop("CUBLAS_WORKSPACE_CONFIG", None)


def build_net(torch: Any) -> Any:
    a, b, c, d = LAYERS
    return torch.nn.Sequential(
        torch.nn.Linear(a, b),
        torch.nn.ReLU(),
        torch.nn.Linear(b, c),
        torch.nn.ReLU(),
        torch.nn.Linear(c, d),
    )


def to_tensors(torch: Any, Xs, y, w, device: str):
    X_t = torch.tensor(Xs, dtype=torch.float32, device=device)
    y_t = torch.tensor(y, dtype=torch.float32, device=device)
    w_t = torch.tensor(w, dtype=torch.float32, device=device)
    return X_t, y_t, w_t / w_t.sum()


def run_epochs(torch: Any, net: Any, opt: Any, X_t, y_t, w_t, epochs: int, mb: int):
    """epoch 마다 전체 표본의 가중 손실 gradient 를 microbatch 로 누적한 뒤 한 번 갱신."""
    n = X_t.shape[0]
    for _ in range(epochs):
        opt.zero_grad(set_to_none=True)
        for start in range(0, n, mb):
            sl = slice(start, start + mb)
            loss = (w_t[sl] * (net(X_t[sl]).squeeze(1) - y_t[sl]).abs()).sum()
            loss.backward()
        opt.step()


def new_model(torch: Any, device: str):
    """초기값은 호출 직전 seed 로 정해진다(`deterministic` 안에서 부른다)."""
    net = build_net(torch).to(device)
    opt = torch.optim.Adam(net.parameters(), lr=LR, weight_decay=WEIGHT_DECAY)
    return net, opt


def train_predict(
    train_X: Sequence[Sequence[float]],
    train_y: Sequence[float],
    train_w: Sequence[float],
    test_X: Sequence[Sequence[float]],
    mean: Sequence[float],
    std: Sequence[float],
    *,
    device: str = "cpu",
    microbatch: Optional[int] = None,
    epochs: Optional[int] = None,
    seed: int = SEED,
) -> list[float]:
    """한 구간 학습 · 예측(raw · 범위 제한 없음). 표준화 값은 학습 구간에서 확정된 것을 받는다."""
    import torch

    Xs = apply_standardize(train_X, mean, std)
    Ts = apply_standardize(test_X, mean, std)
    with deterministic(torch, seed):
        net, opt = new_model(torch, device)
        X_t, y_t, w_t = to_tensors(torch, Xs, train_y, train_w, device)
        mb = microbatch or len(Xs)
        run_epochs(torch, net, opt, X_t, y_t, w_t, epochs or EPOCHS, mb)
        with torch.no_grad():
            out = net(torch.tensor(Ts, dtype=torch.float32, device=device)).squeeze(1)
        return [float(v) for v in out.detach().cpu().tolist()]
