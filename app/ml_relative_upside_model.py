"""ML 축1 (후보 ETF 상대상승 참고점수 v0) — 모델 학습 + 추론 + 정규화.

지시문 §6:
- 단일 모델만 사용 (단일 회귀 baseline).
- 자동 튜닝 / 앙상블 / 복수 모델 비교 금지.
- 기존 ml_baseline_v0 경로 (state/ml/ml_baseline_v0_report_latest.json) 미변경.
- 신규 산출물 별도 이름: `relative_upside_score_v0`.

지시문 §6.3 (시간 순서 원칙):
- walk-forward 1회 split (사용자 결정 — 2026-06-20):
    train = (전체 row 중 시간 기준 앞 N%)
    test  = (그 이후)
- 랜덤 셔플 금지.

지시문 §7 (점수 생성):
- raw prediction 은 그대로 운영 artifact 에 보관.
- 사용자 화면용 display score 는 **현재 기준일 후보군 내 상대 순위 기반 0~100 정규화**.

모델: 단일 선형회귀 (1-layer MLP equiv, bias 포함, MSE loss). torch GPU 사용.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Optional

import torch
import torch.nn as nn

from app.ml_relative_upside_features import (
    FEATURE_COLUMNS,
    CandidateFeatureRow,
    is_complete_for_inference,
    is_complete_for_training,
)

logger = logging.getLogger(__name__)

# 학습 hyperparameter — 본 STEP 의 baseline 고정. 자동 튜닝 금지 (지시문 §6.1).
DEFAULT_TRAIN_SPLIT_RATIO = 0.8
DEFAULT_EPOCHS = 200
DEFAULT_LEARNING_RATE = 1e-3

DEFAULT_RANDOM_SEED = 42


@dataclass
class TrainResult:
    """학습 결과 메타데이터 (운영 artifact 보관용)."""

    train_row_count: int
    test_row_count: int
    train_date_range: tuple[str, str]  # (min_date, max_date)
    test_date_range: tuple[str, str]
    train_loss_final: float
    test_loss_final: float
    epochs: int
    learning_rate: float
    device_name: str
    cuda_available: bool
    gpu_execution_used: bool
    train_seconds: float
    feature_columns: tuple[str, ...]


class RelativeUpsideRegressor(nn.Module):
    """단일 선형회귀 — 단일 nn.Linear (자동 튜닝/앙상블 없음)."""

    def __init__(self, in_features: int):
        super().__init__()
        self.linear = nn.Linear(in_features, 1, bias=True)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.linear(x).squeeze(-1)


def _row_to_feature_tensor(row: CandidateFeatureRow) -> list[float]:
    """row → feature vector (FEATURE_COLUMNS 순서 고정)."""
    return [
        row.return_5d,
        row.return_10d,
        row.return_20d,
        row.excess_return_5d,
        row.excess_return_10d,
        row.excess_return_20d,
        row.drawdown_20d,
    ]  # type: ignore[list-item]


def _resolve_device() -> tuple[torch.device, str, bool]:
    """가용 device 선택. CUDA 우선, 없으면 CPU.

    환경변수 `ML_RELATIVE_UPSIDE_FORCE_CPU=true` 면 CPU 강제 (테스트용).
    """
    if os.environ.get("ML_RELATIVE_UPSIDE_FORCE_CPU", "").lower() == "true":
        return torch.device("cpu"), "cpu (forced)", False
    if torch.cuda.is_available():
        device = torch.device("cuda")
        name = torch.cuda.get_device_name(0)
        return device, name, True
    return torch.device("cpu"), "cpu", False


def train_walk_forward(
    training_rows: list[CandidateFeatureRow],
    *,
    train_split_ratio: float = DEFAULT_TRAIN_SPLIT_RATIO,
    epochs: int = DEFAULT_EPOCHS,
    learning_rate: float = DEFAULT_LEARNING_RATE,
    seed: int = DEFAULT_RANDOM_SEED,
) -> tuple[Optional[RelativeUpsideRegressor], TrainResult]:
    """walk-forward 1회 split 학습 (사용자 결정 — 2026-06-20).

    training_rows 는 **모든 ticker** 의 feature row 를 모은 리스트.
    학습 데이터는 row 의 asof_date 기준으로 시간 순서 정렬 후 앞 N% / 뒤 (1-N)%
    분할.

    학습 데이터 부족 (train/test 한쪽 행 수 0) 이면 (None, TrainResult) 반환.

    랜덤 셔플 금지 — date ASC 순서 유지 (지시문 §6.3).
    """
    import time

    torch.manual_seed(seed)

    # 완전한 training row 만 필터.
    complete = [r for r in training_rows if is_complete_for_training(r)]

    # 시간 순서 정렬 (date ASC). 같은 date 안에서는 ticker 알파벳 순으로 안정 정렬.
    complete.sort(key=lambda r: (r.asof_date, r.ticker))

    device, device_name, gpu_used = _resolve_device()

    if len(complete) < 2:
        # train/test 분할 불가.
        return None, TrainResult(
            train_row_count=0,
            test_row_count=0,
            train_date_range=("", ""),
            test_date_range=("", ""),
            train_loss_final=float("nan"),
            test_loss_final=float("nan"),
            epochs=epochs,
            learning_rate=learning_rate,
            device_name=device_name,
            cuda_available=torch.cuda.is_available(),
            gpu_execution_used=gpu_used,
            train_seconds=0.0,
            feature_columns=FEATURE_COLUMNS,
        )

    split_idx = max(1, int(len(complete) * train_split_ratio))
    if split_idx >= len(complete):
        split_idx = len(complete) - 1

    train_rows = complete[:split_idx]
    test_rows = complete[split_idx:]

    X_train = torch.tensor(
        [_row_to_feature_tensor(r) for r in train_rows],
        dtype=torch.float32,
        device=device,
    )
    y_train = torch.tensor(
        [r.future_excess_return_20d for r in train_rows],
        dtype=torch.float32,
        device=device,
    )
    X_test = torch.tensor(
        [_row_to_feature_tensor(r) for r in test_rows],
        dtype=torch.float32,
        device=device,
    )
    y_test = torch.tensor(
        [r.future_excess_return_20d for r in test_rows],
        dtype=torch.float32,
        device=device,
    )

    model = RelativeUpsideRegressor(in_features=len(FEATURE_COLUMNS)).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
    loss_fn = nn.MSELoss()

    start = time.perf_counter()
    model.train()
    for _ in range(epochs):
        optimizer.zero_grad()
        pred = model(X_train)
        loss = loss_fn(pred, y_train)
        loss.backward()
        optimizer.step()
    train_seconds = time.perf_counter() - start

    model.eval()
    with torch.no_grad():
        train_loss_final = float(loss_fn(model(X_train), y_train).item())
        if len(test_rows) > 0:
            test_loss_final = float(loss_fn(model(X_test), y_test).item())
        else:
            test_loss_final = float("nan")

    result = TrainResult(
        train_row_count=len(train_rows),
        test_row_count=len(test_rows),
        train_date_range=(train_rows[0].asof_date, train_rows[-1].asof_date),
        test_date_range=(
            (test_rows[0].asof_date, test_rows[-1].asof_date) if test_rows else ("", "")
        ),
        train_loss_final=train_loss_final,
        test_loss_final=test_loss_final,
        epochs=epochs,
        learning_rate=learning_rate,
        device_name=device_name,
        cuda_available=torch.cuda.is_available(),
        gpu_execution_used=gpu_used,
        train_seconds=train_seconds,
        feature_columns=FEATURE_COLUMNS,
    )
    return model, result


def predict_raw_scores(
    model: RelativeUpsideRegressor,
    inference_rows: list[CandidateFeatureRow],
) -> dict[str, float]:
    """현재 기준일 후보 ETF 의 raw prediction (학습 target 단위 그대로).

    inference_rows 는 동일 asof_date 의 ticker 별 feature row. None 값을
    가진 row 는 제외 (호출자가 점수 null 처리).

    반환: ticker → raw prediction (float).
    """
    if model is None:
        return {}
    valid = [r for r in inference_rows if is_complete_for_inference(r)]
    if not valid:
        return {}

    device = next(model.parameters()).device
    X = torch.tensor(
        [_row_to_feature_tensor(r) for r in valid],
        dtype=torch.float32,
        device=device,
    )
    model.eval()
    with torch.no_grad():
        preds = model(X).cpu().tolist()
    return {r.ticker: float(p) for r, p in zip(valid, preds)}


def normalize_to_display_scores(raw_scores: dict[str, float]) -> dict[str, float]:
    """raw prediction → 후보군 내 상대 순위 기반 0~100 점수 (지시문 §7).

    빈 dict 면 빈 dict.
    raw_scores 1건이면 50.0 (단일 후보 — 비교 의미 약하지만 안전 default).
    """
    if not raw_scores:
        return {}
    if len(raw_scores) == 1:
        ticker = next(iter(raw_scores.keys()))
        return {ticker: 50.0}

    items = sorted(raw_scores.items(), key=lambda kv: kv[1])
    n = len(items)
    # 상대 순위 (낮을수록 점수 낮음). 같은 값은 동일 점수.
    display: dict[str, float] = {}
    last_value: Optional[float] = None
    last_score: float = 0.0
    for rank, (ticker, value) in enumerate(items):
        if last_value is not None and abs(value - last_value) < 1e-12:
            display[ticker] = last_score
        else:
            # rank 0 → 0, rank n-1 → 100. linear.
            display[ticker] = round(rank / (n - 1) * 100.0, 2)
            last_value = value
            last_score = display[ticker]
    return display
